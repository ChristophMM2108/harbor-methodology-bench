"""Tests for task screening.

The screen decides where the money goes, so its refusals matter more than its
acceptances: a task whose oracle fails, or one the bare agent already passes,
must never reach the matrix.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harbor_methodology_bench.screen import (
    EXCLUDE,
    INCLUDE,
    UNKNOWN,
    ScreenError,
    TaskScreen,
    baseline_job,
    read_screen,
    render_task_file,
    solvability_job,
)


def test_screen_jobs_run_against_the_baseline_variant_only() -> None:
    """Solvability is a property of the task, not of a condition."""
    job = solvability_job(["task-a", "task-b"], job_name="screen-solvability", jobs_dir="jobs")
    assert [entry["path"] for entry in job["datasets"]] == ["generated/baseline"] * 2
    assert [agent["name"] for agent in job["agents"]] == ["oracle", "nop"]


def test_baseline_job_carries_the_agent_and_its_cap() -> None:
    job = baseline_job(
        ["task-a"],
        job_name="screen-baseline",
        jobs_dir="jobs",
        agent="claude-code",
        model="claude-sonnet-5",
        n_concurrent_agents=6,
    )
    assert job["agents"] == [
        {"name": "claude-code", "model_name": "claude-sonnet-5", "n_concurrent": 6}
    ]


def test_an_empty_selection_is_refused() -> None:
    with pytest.raises(ScreenError):
        solvability_job([], job_name="screen-solvability", jobs_dir="jobs")


def test_a_broken_oracle_excludes_the_task() -> None:
    verdict, reason = TaskScreen("t", oracle=0.0, nop=0.0, baseline_rewards=(0.0,)).verdict()
    assert verdict == EXCLUDE
    assert "verifier" in reason


def test_a_task_that_passes_without_work_is_excluded() -> None:
    verdict, reason = TaskScreen("t", oracle=1.0, nop=1.0, baseline_rewards=(0.0,)).verdict()
    assert verdict == EXCLUDE
    assert "without doing any work" in reason


def test_a_task_the_bare_agent_passes_is_excluded() -> None:
    """It cannot discriminate, and it still costs a trial in every cell."""
    verdict, reason = TaskScreen("t", oracle=1.0, nop=0.0, baseline_rewards=(1.0,)).verdict()
    assert verdict == EXCLUDE
    assert "already passes" in reason


def test_a_task_the_bare_agent_fails_is_included() -> None:
    assert TaskScreen("t", oracle=1.0, nop=0.0, baseline_rewards=(0.0,)).verdict()[0] == INCLUDE


def test_a_partially_passed_task_is_included() -> None:
    """One pass in two attempts still leaves room for a condition to differ."""
    assert TaskScreen("t", oracle=1.0, nop=0.0, baseline_rewards=(1.0, 0.0)).verdict()[0] == INCLUDE


def test_an_errored_baseline_trial_decides_nothing() -> None:
    verdict, reason = TaskScreen(
        "t", oracle=1.0, nop=0.0, baseline_rewards=(0.0,), exceptions=("ApiUsageLimitError",)
    ).verdict()
    assert verdict == UNKNOWN
    assert "ApiUsageLimitError" in reason


def test_a_missing_stage_decides_nothing() -> None:
    assert TaskScreen("t").verdict()[0] == UNKNOWN
    assert TaskScreen("t", oracle=1.0, nop=0.0).verdict()[0] == UNKNOWN


def _trial(job_dir: Path, name: str, task: str, agent: str, reward: float) -> None:
    (job_dir / name).mkdir(parents=True, exist_ok=True)
    (job_dir / name / "result.json").write_text(
        json.dumps(
            {
                "config": {"task": {"path": f"generated/baseline/{task}"}},
                "agent_info": {"name": agent},
                "verifier_result": {"rewards": {"reward": reward}},
            }
        ),
        encoding="utf-8",
    )


def test_read_screen_joins_both_stages(tmp_path: Path) -> None:
    solvability = tmp_path / "screen-solvability"
    baseline = tmp_path / "screen-baseline"
    _trial(solvability, "task-a__1", "task-a", "oracle", 1.0)
    _trial(solvability, "task-a__2", "task-a", "nop", 0.0)
    _trial(baseline, "task-a__3", "task-a", "claude-code", 0.0)
    _trial(solvability, "task-b__1", "task-b", "oracle", 1.0)
    _trial(solvability, "task-b__2", "task-b", "nop", 0.0)
    _trial(baseline, "task-b__3", "task-b", "claude-code", 1.0)

    screens = read_screen(
        tmp_path, ["task-a", "task-b"], job_prefix="screen", baseline_agent="claude-code"
    )

    assert [entry.verdict()[0] for entry in screens] == [INCLUDE, EXCLUDE]


def test_the_task_file_keeps_the_rejected_tasks_as_comments() -> None:
    """A task set is a claim about what was measured; the rejects belong with it."""
    text = render_task_file(
        [
            TaskScreen("kept", oracle=1.0, nop=0.0, baseline_rewards=(0.0,)),
            TaskScreen("dropped", oracle=1.0, nop=0.0, baseline_rewards=(1.0,)),
        ],
        config_name="config/experiments.x.yaml",
        job_prefix="screen",
        generated_at="2026-08-31",
    )
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]

    assert lines == ["kept"]
    assert "# dropped  (exclude: the bare agent already passes it" in text
