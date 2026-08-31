"""Tests for the two metrics prog16's discussion asked for, and for censoring.

Both are order- and outcome-sensitive readings of a trajectory, so the guards
here are about what the metric must *not* say: a test command that exited
nonzero is not a passing test, and a skill invoked after the code was already
written is not the method being followed.
"""

from __future__ import annotations

import json
from pathlib import Path

from harbor_methodology_bench.analysis import extract_all
from harbor_methodology_bench.report import write_report

TRAJECTORY = "agent/trajectory.json"


def call(call_id: str, name: str, **arguments) -> dict:
    return {"tool_call_id": call_id, "function_name": name, "arguments": arguments}


def observation(*results: tuple[str, str, bool]) -> dict:
    return {
        "results": [
            {
                "source_call_id": call_id,
                "content": content,
                "extra": {"tool_result_metadata": {"tool_result_is_error": is_error}},
            }
            for call_id, content, is_error in results
        ]
    }


def step(minute: int, calls: list[dict], results: dict | None = None) -> dict:
    return {
        "step_id": minute,
        "timestamp": f"2026-08-27T10:{minute:02d}:00.000Z",
        "source": "agent",
        "message": "",
        "llm_call_count": 1,
        "metrics": {"prompt_tokens": 10, "completion_tokens": 5, "cached_tokens": 0, "extra": {}},
        "tool_calls": calls,
        "observation": results,
        "extra": {"is_sidechain": False},
    }


def make_trial(root: Path, steps: list[dict], *, exception: str | None = None) -> Path:
    trial_dir = root / "jobs" / "run-claude-code" / "task-a__abc"
    (trial_dir / "agent").mkdir(parents=True, exist_ok=True)
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "task_name": "suite/task-a",
                "trial_name": "task-a__abc",
                "task_id": {"path": "generated/kit/task-a"},
                "agent_info": {"name": "claude-code", "model_info": {"name": "claude-sonnet-5"}},
                "agent_result": {"n_input_tokens": 1, "n_output_tokens": 1, "cost_usd": 0.1},
                "verifier_result": {"rewards": {"reward": 0.0}},
                "exception_info": (
                    {"exception_type": exception, "exception_message": "x"} if exception else None
                ),
                "started_at": "2026-08-27T10:00:00Z",
                "finished_at": "2026-08-27T10:30:00Z",
            }
        ),
        encoding="utf-8",
    )
    (trial_dir / TRAJECTORY).write_text(
        json.dumps({"schema_version": "ATIF-v1.7", "steps": steps}), encoding="utf-8"
    )
    (root / "generated" / "kit" / "task-a").mkdir(parents=True, exist_ok=True)
    return trial_dir


def only_row(tmp_path: Path) -> dict:
    return extract_all(tmp_path / "jobs", "run-*", None, tmp_path)["trials"][0]


def test_a_failing_test_run_is_not_a_passing_one(tmp_path: Path) -> None:
    """Exit status is the signal; a test runner exits nonzero when a test fails."""
    make_trial(
        tmp_path,
        [
            step(1, [call("c1", "Write", file_path="/app/solve.py")]),
            step(
                2,
                [call("c2", "Bash", command="pytest -q")],
                observation(("c2", "Exit code 1\n1 failed", False)),
            ),
            step(
                5,
                [call("c3", "Bash", command="pytest -q")],
                observation(("c3", "2 passed", False)),
            ),
        ],
    )
    row = only_row(tmp_path)

    assert row["n_test_runs"] == 2
    assert row["n_passing_test_runs"] == 1
    assert row["time_to_first_test_sec"] == 60.0
    assert row["time_to_first_passing_test_sec"] == 240.0
    assert row["steps_to_first_passing_test"] == 2


def test_a_tool_error_is_not_a_passing_test(tmp_path: Path) -> None:
    make_trial(
        tmp_path,
        [
            step(1, [call("c1", "Write", file_path="/app/solve.py")]),
            step(
                2,
                [call("c2", "Bash", command="pytest -q")],
                observation(("c2", "boom", True)),
            ),
        ],
    )
    row = only_row(tmp_path)

    assert row["n_test_runs"] == 1
    assert row["n_passing_test_runs"] == 0
    assert row["time_to_first_passing_test_sec"] is None


def test_compliance_reads_what_happened_before_the_first_code_edit(tmp_path: Path) -> None:
    """The claim both toolkits make is about order, so the metric is about order."""
    make_trial(
        tmp_path,
        [
            step(1, [call("c1", "Read", file_path="/app/CLAUDE.md")]),
            step(2, [call("c2", "Skill", skill="kit-plan")]),
            step(3, [call("c3", "Write", file_path="/app/PLAN.md")]),
            step(4, [call("c4", "Write", file_path="/app/solve.py")]),
            step(
                5,
                [call("c5", "Bash", command="pytest -q")],
                observation(("c5", "1 passed", False)),
            ),
        ],
    )
    row = only_row(tmp_path)

    assert row["config_read_before_code"] is True
    assert row["skill_before_code"] is True
    assert row["doc_written_before_code"] is True
    assert row["test_run_before_code"] is False
    assert row["compliance_score"] == 0.75


def test_a_skill_called_after_the_code_was_written_does_not_count(tmp_path: Path) -> None:
    make_trial(
        tmp_path,
        [
            step(1, [call("c1", "Write", file_path="/app/solve.py")]),
            step(2, [call("c2", "Skill", skill="kit-plan")]),
            step(3, [call("c3", "Write", file_path="/app/PLAN.md")]),
        ],
    )
    row = only_row(tmp_path)

    assert row["skill_before_code"] is False
    assert row["doc_written_before_code"] is False
    assert row["compliance_score"] == 0.0


def test_compliance_is_undefined_when_no_code_was_written(tmp_path: Path) -> None:
    """Nothing can have happened "first" in a trial that never touched code."""
    make_trial(tmp_path, [step(1, [call("c1", "Bash", command="ls")])])
    assert only_row(tmp_path)["compliance_score"] is None


def test_a_timeout_is_censored_rather_than_failed(tmp_path: Path) -> None:
    """A trial stopped by the clock produced no graded outcome to average."""
    make_trial(
        tmp_path,
        [step(1, [call("c1", "Write", file_path="/app/solve.py")])],
        exception="AgentTimeoutError",
    )
    markdown, trials = write_report(tmp_path / "jobs", "run-*")

    assert trials[0]["censored"] is True
    assert "1 of 1 trial(s) censored" in markdown
    assert "CENSORED" in markdown
