"""Guards on the Harbor job plan and on the bounded resume filter.

Both modules exist to keep a run's results honest: a job config that ordered its
datasets by condition would let host contention fall unevenly across conditions,
and a resume without a filter would turn an infrastructure failure into a
permanent 0.0 reward that reads like a finding.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from harbor_methodology_bench.config import load_config
from harbor_methodology_bench.jobplan import (
    DEFAULT_N_CONCURRENT_AGENTS,
    DEFAULT_N_CONCURRENT_TRIALS,
    RETRY_EXCEPTIONS,
    JobPlanError,
    plan_jobs,
    write_job_configs,
)
from harbor_methodology_bench.resume import (
    NEVER_FILTER,
    NO_RESULT,
    OK,
    UNREADABLE,
    ResumeError,
    breakdown,
    check_job_dir,
    classify_trials,
    read_env_file,
    resume_filters,
)

CONFIG_TEMPLATE = """
source_root: source-tasks/terminal-bench
generated_root: generated
models:
  claude-code: claude-sonnet-5
toolkits:
  - id: kit-a
    snapshot: toolkits/kit-a/snapshot
  - id: kit-b
    snapshot: toolkits/kit-b/snapshot
matrix:
  - {id: c-baseline, agent: claude-code, toolkit: baseline}
  - {id: c-kit-a, agent: claude-code, toolkit: kit-a}
  - {id: c-kit-b, agent: claude-code, toolkit: kit-b}
"""

TASKS = ["task-one", "task-two"]
VARIANTS = ["baseline", "kit-a", "kit-b"]


@pytest.fixture()
def settings(tmp_path: Path):
    (tmp_path / "config").mkdir()
    config_path = tmp_path / "config" / "experiments.yaml"
    config_path.write_text(CONFIG_TEMPLATE)
    for variant in VARIANTS:
        for task in TASKS:
            (tmp_path / "generated" / variant / task).mkdir(parents=True)
    for kit in ("kit-a", "kit-b"):
        (tmp_path / "toolkits" / kit / "snapshot").mkdir(parents=True)
    return load_config(config_path)


def test_datasets_are_task_major(settings) -> None:
    """Conditions of one task queue together, so they run side by side.

    Harbor extends its task list dataset by dataset with no deduplication, so
    the dataset order is the execution order. Condition-major order would run
    every baseline trial before any toolkit trial, which delays comparable
    results and lets contention fall unevenly across conditions.
    """
    (plan,) = plan_jobs(settings, TASKS)
    paths = [(entry["path"], entry["task_names"]) for entry in plan.config["datasets"]]
    assert paths == [
        ("generated/baseline", ["task-one"]),
        ("generated/kit-a", ["task-one"]),
        ("generated/kit-b", ["task-one"]),
        ("generated/baseline", ["task-two"]),
        ("generated/kit-a", ["task-two"]),
        ("generated/kit-b", ["task-two"]),
    ]


def test_one_job_per_agent_holds_every_condition(settings) -> None:
    plans = plan_jobs(settings, TASKS, job_prefix="run")
    assert [plan.job_name for plan in plans] == ["run-claude-code"]
    assert plans[0].variants == ("baseline", "kit-a", "kit-b")
    assert len(plans[0].config["agents"]) == 1


def test_dataset_paths_are_relative_to_the_repository_root(settings) -> None:
    """`report` derives the condition from this path, and a job config travels."""
    (plan,) = plan_jobs(settings, TASKS)
    for entry in plan.config["datasets"]:
        assert not Path(entry["path"]).is_absolute()


def test_plan_is_deterministic(settings) -> None:
    first = plan_jobs(settings, TASKS)[0].to_yaml()
    second = plan_jobs(settings, TASKS)[0].to_yaml()
    assert first == second


def test_retry_allowlist_holds_only_transient_failures(settings) -> None:
    """A methodology effect must never be retried away."""
    (plan,) = plan_jobs(settings, TASKS)
    retry = plan.config["retry"]["include_exceptions"]
    assert retry == list(RETRY_EXCEPTIONS)
    assert "ApiUsageLimitError" not in retry
    assert "OutputTokenExceededError" not in retry


def test_concurrency_defaults_and_the_sub_cap_bound(settings) -> None:
    (plan,) = plan_jobs(settings, TASKS)
    assert plan.config["n_concurrent_trials"] == DEFAULT_N_CONCURRENT_TRIALS
    assert plan.config["agents"][0]["n_concurrent"] == DEFAULT_N_CONCURRENT_AGENTS
    with pytest.raises(JobPlanError):
        plan_jobs(settings, TASKS, n_concurrent_trials=4, n_concurrent_agents=6)


def test_ungenerated_variant_is_refused(settings) -> None:
    with pytest.raises(JobPlanError, match="generate these variants first"):
        plan_jobs(settings, ["task-three"])


def test_written_configs_are_loadable_yaml(settings, tmp_path: Path) -> None:
    plans = plan_jobs(settings, TASKS, attempts=3)
    (path,) = write_job_configs(plans, tmp_path / "plan")
    written = yaml.safe_load(path.read_text())
    assert written["n_attempts"] == 3
    assert written["job_name"] == path.stem


def _job_dir(tmp_path: Path, trials: dict[str, object]) -> Path:
    job_dir = tmp_path / "jobs" / "run-claude-code"
    job_dir.mkdir(parents=True)
    (job_dir / "config.json").write_text(
        json.dumps({"jobs_dir": str(tmp_path / "jobs"), "job_name": "run-claude-code"})
    )
    for name, exception in trials.items():
        trial = job_dir / name
        trial.mkdir()
        if exception is UNREADABLE:
            (trial / "result.json").write_text("{not json")
        elif exception is NO_RESULT:
            continue
        else:
            payload: dict[str, object] = {"trial_name": name}
            if exception is not None:
                payload["exception_info"] = {"exception_type": exception}
            (trial / "result.json").write_text(json.dumps(payload))
    return job_dir


def test_classification_names_every_trial_state(tmp_path: Path) -> None:
    job_dir = _job_dir(
        tmp_path,
        {
            "a": None,
            "b": "ApiRateLimitError",
            "c": "ApiUsageLimitError",
            "d": UNREADABLE,
            "e": NO_RESULT,
        },
    )
    counts = breakdown(classify_trials(job_dir))
    assert counts == {
        OK: 1,
        "ApiRateLimitError": 1,
        "ApiUsageLimitError": 1,
        UNREADABLE: 1,
        NO_RESULT: 1,
    }


def test_usage_limit_needs_the_recharged_flag(tmp_path: Path) -> None:
    """Re-running an exhausted quota before recharging just burns the trials again."""
    states = classify_trials(_job_dir(tmp_path, {"a": "ApiUsageLimitError", "b": None}))
    assert resume_filters(states) == []
    assert resume_filters(states, recharged=True) == ["ApiUsageLimitError"]


def test_filter_only_names_types_present_in_the_job(tmp_path: Path) -> None:
    states = classify_trials(_job_dir(tmp_path, {"a": "CancelledError", "b": None}))
    assert resume_filters(states) == ["CancelledError"]


@pytest.mark.parametrize("name", sorted(NEVER_FILTER))
def test_methodology_failures_can_never_be_filtered(tmp_path: Path, name: str) -> None:
    states = classify_trials(_job_dir(tmp_path, {"a": name}))
    with pytest.raises(ResumeError, match="refusing to re-run"):
        resume_filters(states, extra=(name,))


def test_unknown_exception_type_is_refused(tmp_path: Path) -> None:
    states = classify_trials(_job_dir(tmp_path, {"a": None}))
    with pytest.raises(ResumeError, match="refusing to re-run"):
        resume_filters(states, extra=("AssertionError",))


def test_a_copied_job_directory_is_refused(tmp_path: Path) -> None:
    """Harbor resumes the recorded path, so a copy would silently touch the original."""
    job_dir = _job_dir(tmp_path, {"a": None})
    copy = job_dir.parent / "copy-of-run"
    copy.mkdir()
    (copy / "config.json").write_text((job_dir / "config.json").read_text())
    check_job_dir(job_dir)
    with pytest.raises(ResumeError, match="points at"):
        check_job_dir(copy)


def test_env_file_parsing(tmp_path: Path) -> None:
    path = tmp_path / "local.env"
    path.write_text(
        "# a comment\n"
        "CLAUDE_CODE_OAUTH_TOKEN=abc123\n"
        "export CODEX_FORCE_AUTH_JSON=1\n"
        'QUOTED="with spaces"\n'
        "\n"
    )
    assert read_env_file(path) == {
        "CLAUDE_CODE_OAUTH_TOKEN": "abc123",
        "CODEX_FORCE_AUTH_JSON": "1",
        "QUOTED": "with spaces",
    }
