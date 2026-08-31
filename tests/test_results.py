"""Tests for the result-reading path: adherence, aggregation, trial-level tables.

The adherence tests are regression guards. An earlier version of the reporter
counted the substring `"name": "Skill"`, which the ATIF trajectory never emits —
it names the field `function_name` — so every run reported zero skill
invocations. A metric that silently reads zero is worse than a missing metric,
because it looks like a finding.
"""

from __future__ import annotations

import json
from pathlib import Path

from harbor_methodology_bench.analysis import classify_bash, extract_all
from harbor_methodology_bench.report import find_all_trials, parse_adherence, write_report

SKILLS = ["kit-plan", "kit-verify"]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_variant(root: Path, condition: str, task: str) -> Path:
    """A generated variant carrying a manifest, as `hmb generate` writes it."""
    task_dir = root / "generated" / condition / task
    write_json(
        task_dir / ".methodology-bench-manifest.json",
        {"environment": {"skills_registered": SKILLS}},
    )
    return task_dir


def make_trial(
    root: Path,
    job: str,
    task: str,
    condition: str,
    *,
    steps: list[dict],
    reward: float | None = 1.0,
    tests: tuple[int, int] | None = (4, 3),
    exception: str | None = None,
) -> Path:
    trial_dir = root / "jobs" / job / f"{task}__abc"
    write_json(
        trial_dir / "result.json",
        {
            "task_name": f"suite/{task}",
            "trial_name": f"{task}__abc",
            "task_id": {"path": f"generated/{condition}/{task}"},
            "agent_info": {"name": "claude-code", "model_info": {"name": "claude-sonnet-5"}},
            "agent_result": {
                "n_input_tokens": 1000,
                "n_cache_tokens": 900,
                "n_output_tokens": 100,
                "cost_usd": 0.25,
            },
            "verifier_result": {"rewards": {} if reward is None else {"reward": reward}},
            "exception_info": {"exception_type": exception, "exception_message": "x"} if exception else None,
            "started_at": "2026-08-27T10:00:00Z",
            "finished_at": "2026-08-27T10:20:00Z",
            "environment_setup": {"started_at": "2026-08-27T10:00:00Z", "finished_at": "2026-08-27T10:01:00Z"},
            "agent_setup": {"started_at": "2026-08-27T10:01:00Z", "finished_at": "2026-08-27T10:02:00Z"},
            "agent_execution": {"started_at": "2026-08-27T10:02:00Z", "finished_at": "2026-08-27T10:17:00Z"},
            "verifier": {"started_at": "2026-08-27T10:17:00Z", "finished_at": "2026-08-27T10:19:00Z"},
        },
    )
    write_json(
        trial_dir / "agent" / "trajectory.json",
        {"schema_version": "ATIF-v1.7", "agent": {"name": "claude-code"}, "steps": steps},
    )
    (trial_dir / "agent" / "claude-code.txt").write_text(
        '{"skills":["kit-plan","kit-verify","unrelated"]}\n', encoding="utf-8"
    )
    if tests is not None:
        total, passed = tests
        write_json(
            trial_dir / "verifier" / "ctrf.json",
            {
                "results": {
                    "summary": {"tests": total, "passed": passed, "failed": total - passed, "skipped": 0},
                    "tests": [
                        {"name": f"t{i}", "status": "passed" if i < passed else "failed", "duration": 0.1}
                        for i in range(total)
                    ],
                }
            },
        )
    return trial_dir


def step(step_id: int, message: str = "", tool_calls: list[dict] | None = None, **extra) -> dict:
    return {
        "step_id": step_id,
        "timestamp": f"2026-08-27T10:{step_id:02d}:00.000Z",
        "source": "agent",
        "model_name": "claude-sonnet-5",
        "message": message,
        "llm_call_count": 1,
        "metrics": {"prompt_tokens": 100, "completion_tokens": 20, "cached_tokens": 80,
                    "extra": {"output_tokens_details": {"thinking_tokens": 10}}},
        "tool_calls": tool_calls or [],
        "extra": {"is_sidechain": False, **extra},
    }


def tool(name: str, **arguments) -> dict:
    return {"tool_call_id": f"toolu_{name}", "function_name": name, "arguments": arguments}


# ---------------------------------------------------------------------------
# Adherence
# ---------------------------------------------------------------------------
def test_a_skill_tool_call_is_counted(tmp_path: Path) -> None:
    """The regression guard: `function_name` is the field the trajectory uses."""
    task_dir = make_variant(tmp_path, "kit", "task-a")
    trial = make_trial(
        tmp_path, "run-claude-kit-task-a", "task-a", "kit",
        steps=[step(1, "planning", [tool("Skill", skill="kit-plan", args="do it")])],
    )
    adherence = parse_adherence(trial, task_dir)

    assert adherence["skill_tool_calls"] == 1
    assert adherence["skills_invoked"] == ["kit-plan"]
    assert adherence["skills_available"] == SKILLS


def test_a_mention_is_not_an_invocation(tmp_path: Path) -> None:
    """Naming a skill in prose must not score as using it.

    An agent that lists its own skills directory names every skill it owns; the
    loose measure exists, but under its own name.
    """
    task_dir = make_variant(tmp_path, "kit", "task-b")
    trial = make_trial(
        tmp_path, "run-claude-kit-task-b", "task-b", "kit",
        steps=[step(1, "I could use kit-plan or kit-verify here, but I will not.")],
    )
    adherence = parse_adherence(trial, task_dir)

    assert adherence["skill_tool_calls"] == 0
    assert adherence["skills_invoked"] == []
    assert adherence["skills_named"] == SKILLS


def test_a_foreign_skill_call_is_not_toolkit_adherence(tmp_path: Path) -> None:
    """Built-in CLI skills are always available; only the toolkit's own count."""
    task_dir = make_variant(tmp_path, "kit", "task-c")
    trial = make_trial(
        tmp_path, "run-claude-kit-task-c", "task-c", "kit",
        steps=[step(1, "", [tool("Skill", skill="dataviz")])],
    )
    adherence = parse_adherence(trial, task_dir)

    assert adherence["skill_tool_calls"] == 0
    assert adherence["foreign_skill_calls"] == 1


def test_config_markers_come_only_from_agent_steps(tmp_path: Path) -> None:
    task_dir = make_variant(tmp_path, "kit", "task-d")
    trial = make_trial(
        tmp_path, "run-claude-kit-task-d", "task-d", "kit",
        steps=[
            {"step_id": 1, "source": "user", "message": "read AGENTS.md", "timestamp": "2026-08-27T10:00:00Z"},
            step(2, "checking the working agreement", [tool("Read", file_path="/app/CLAUDE.md")]),
        ],
    )
    adherence = parse_adherence(trial, task_dir)
    assert "CLAUDE.md" in adherence["config_markers_seen"]


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def test_report_aggregates_cells_and_writes_both_forms(tmp_path: Path) -> None:
    make_variant(tmp_path, "kit", "task-a")
    make_trial(tmp_path, "run-claude-kit-task-a", "task-a", "kit",
               steps=[step(1, "", [tool("Skill", skill="kit-plan")])], reward=1.0)
    make_variant(tmp_path, "kit", "task-b")
    make_trial(tmp_path, "run-claude-kit-task-b", "task-b", "kit", steps=[step(1)], reward=0.0,
               exception="AgentTimeoutError")

    markdown, trials = write_report(
        tmp_path / "jobs", "run-*", tmp_path / "out.md", tmp_path / "out.json"
    )

    assert len(trials) == 2
    assert "Skills Named" in markdown and "Skills Invoked" in markdown
    assert "AgentTimeoutError" in markdown
    payload = json.loads((tmp_path / "out.json").read_text())
    assert payload["total_trials"] == 2
    assert {t["used_toolkit_skill"] for t in payload["trials"]} == {True, False}


def test_report_records_the_concurrency_each_job_ran_at(tmp_path: Path) -> None:
    """A duration measured under concurrency is not comparable with a serial one.

    The reader can only know which they are looking at if the report says so.
    """
    make_variant(tmp_path, "kit", "task-a")
    make_trial(tmp_path, "run-claude-code", "task-a", "kit", steps=[step(1)])
    write_json(
        tmp_path / "jobs" / "run-claude-code" / "config.json",
        {
            "job_name": "run-claude-code",
            "n_attempts": 3,
            "n_concurrent_trials": 9,
            "agents": [{"name": "claude-code", "n_concurrent": 6}],
        },
    )

    markdown, _ = write_report(tmp_path / "jobs", "run-*", None, tmp_path / "out.json")

    assert "9 concurrent trial(s), agent phase cap 6, 3 attempt(s)" in markdown
    assert "duration_sec` carries host contention" in markdown
    payload = json.loads((tmp_path / "out.json").read_text())
    assert payload["jobs"][0]["n_concurrent_trials"] == 9


def test_pattern_selects_jobs(tmp_path: Path) -> None:
    make_variant(tmp_path, "kit", "task-a")
    make_trial(tmp_path, "keep-claude-kit-task-a", "task-a", "kit", steps=[step(1)])
    make_trial(tmp_path, "drop-claude-kit-task-a", "task-a", "kit", steps=[step(1)])

    assert len(find_all_trials(tmp_path / "jobs", "keep-*")) == 1
    assert len(find_all_trials(tmp_path / "jobs", "*")) == 2


# ---------------------------------------------------------------------------
# Trial-level tables
# ---------------------------------------------------------------------------
def test_extract_derives_partial_credit_and_behaviour(tmp_path: Path) -> None:
    make_variant(tmp_path, "kit", "task-a")
    make_trial(
        tmp_path, "run-claude-kit-task-a", "task-a", "kit",
        steps=[
            step(1, "", [tool("Bash", command="ls -la /app")]),
            step(2, "", [tool("Write", file_path="/app/PLAN.md")]),
            step(3, "", [tool("Bash", command="python -m pytest tests/ -q")]),
            step(4, "", [tool("Skill", skill="kit-verify")]),
        ],
        tests=(4, 3),
    )
    catalogue = tmp_path / "catalogue.json"
    write_json(catalogue, {"tasks": [{"task_id": "task-a", "difficulty": "hard",
                                      "category": "software-engineering", "axes": ["long-horizon"],
                                      "agent_timeout_sec": 1800.0, "expert_min": 240.0}]})

    tables = extract_all(tmp_path / "jobs", "run-*", catalogue, root=tmp_path)
    row = tables["trials"][0]

    assert row["partial_credit"] == 0.75, "partial credit comes from the verifier's own per-test results"
    assert row["tests_total"] == 4 and len(tables["tests"]) == 4
    assert row["n_toolkit_skill_calls"] == 1
    assert row["bash_test"] == 1 and row["n_bash"] == 2
    assert row["n_write"] == 1 and row["files_touched"] == 1
    assert row["difficulty"] == "hard" and row["axes"] == "long-horizon"
    # 15 minutes of agent execution against a 1800 s budget.
    assert row["agent_sec"] == 900.0
    assert row["budget_used"] == 0.5
    assert len(tables["steps"]) == 4 and len(tables["tool_calls"]) == 4


def test_extract_survives_a_missing_verifier_and_catalogue(tmp_path: Path) -> None:
    """A verifier timeout leaves no reward and no per-test detail; that is data, not a crash."""
    make_variant(tmp_path, "kit", "task-a")
    make_trial(tmp_path, "run-claude-kit-task-a", "task-a", "kit", steps=[step(1)],
               reward=None, tests=None, exception="VerifierTimeoutError")

    tables = extract_all(tmp_path / "jobs", "run-*", None, root=tmp_path)
    row = tables["trials"][0]

    assert row["reward"] is None and row["success"] is False
    assert row["partial_credit"] is None and row["ctrf_found"] is False
    assert row["verifier_timeout"] is True
    assert row["budget_used"] is None, "no catalogue means no declared budget to normalise against"


def test_no_matching_jobs_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "jobs").mkdir()
    try:
        extract_all(tmp_path / "jobs", "nothing-*", None, root=tmp_path)
    except FileNotFoundError as error:
        assert "nothing-*" in str(error)
    else:
        raise AssertionError("an empty selection must fail loudly, not return empty tables")


def test_bash_classifier_buckets_verification_over_inspection() -> None:
    assert classify_bash("python -m pytest tests/ -q") == "test"
    assert classify_bash("cargo test --all") == "test"
    assert classify_bash("./verify_output.sh") == "test"
    assert classify_bash("make -j4") == "build"
    assert classify_bash("pip install -e .") == "build"
    assert classify_bash("ls -la /app") == "inspect"
    assert classify_bash("git status") == "inspect"
    assert classify_bash("echo hello > /tmp/x") == "other"
