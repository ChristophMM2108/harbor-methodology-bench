from __future__ import annotations

"""Task screening: deciding which tasks can discriminate before spending on them.

A benchmark task earns its place in a comparison only if it can separate the
conditions. Two failure modes make a task worthless for that, and both are
cheap to detect:

* **The task or its verifier is broken.** `oracle` runs the task's own reference
  solution and must score 1.0; `nop` does nothing and must score 0.0. Neither
  spends a token.
* **The bare agent already passes it.** Then every condition passes, the task
  carries no information about the comparison, and it still costs a full trial
  in every cell. In the prog16 run 10 of 16 tasks were like that and consumed
  60 % of the budget.

The second check costs one baseline trial per task — the cheapest cell of the
matrix, run once — and turns a ceiling effect that used to be discovered after
the money was spent into an inclusion criterion applied before it.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .jobplan import DEFAULT_MAX_RETRIES, RETRY_EXCEPTIONS

SOLVABILITY_SUFFIX = "solvability"
BASELINE_SUFFIX = "baseline"

INCLUDE = "include"
EXCLUDE = "exclude"
UNKNOWN = "unknown"


class ScreenError(ValueError):
    """The screen cannot be planned or read."""


@dataclass(frozen=True)
class TaskScreen:
    """What the screen learned about one task."""

    task: str
    oracle: float | None = None
    nop: float | None = None
    baseline_rewards: tuple[float | None, ...] = ()
    exceptions: tuple[str, ...] = ()

    @property
    def baseline_passes(self) -> int:
        return sum(1 for reward in self.baseline_rewards if reward is not None and reward >= 1.0)

    def verdict(self) -> tuple[str, str]:
        """`(verdict, reason)` — the inclusion decision and why it was taken."""
        if self.oracle is None:
            return UNKNOWN, "oracle has not run"
        if self.oracle < 1.0:
            return EXCLUDE, f"oracle scored {self.oracle:.2f}: the task or its verifier is broken"
        if self.nop is None:
            return UNKNOWN, "nop has not run"
        if self.nop > 0.0:
            return EXCLUDE, f"nop scored {self.nop:.2f}: the task passes without doing any work"
        if not self.baseline_rewards:
            return UNKNOWN, "no baseline trial yet"
        if self.exceptions:
            return UNKNOWN, f"baseline trial errored: {', '.join(sorted(set(self.exceptions)))}"
        if self.baseline_passes == len(self.baseline_rewards):
            return EXCLUDE, "the bare agent already passes it, so no condition can discriminate"
        return INCLUDE, "solvable, not self-passing, and the bare agent fails it"


def _job_config(
    job_name: str,
    jobs_dir: Path | str,
    tasks: Iterable[str],
    agents: list[dict[str, Any]],
    generated_root_name: str = "generated",
    n_concurrent_trials: int = 9,
    n_attempts: int = 1,
) -> dict[str, Any]:
    """A Harbor job over the **baseline** variant of each task.

    Screening is a property of the task, not of a condition, so it runs against
    the baseline variant only: the task and nothing else.
    """
    task_list = list(tasks)
    if not task_list:
        raise ScreenError("no tasks selected")
    return {
        "job_name": job_name,
        "jobs_dir": str(jobs_dir),
        "n_attempts": n_attempts,
        "n_concurrent_trials": n_concurrent_trials,
        "retry": {
            "max_retries": DEFAULT_MAX_RETRIES,
            "include_exceptions": list(RETRY_EXCEPTIONS),
        },
        "agents": agents,
        "datasets": [
            {"path": f"{generated_root_name}/baseline", "task_names": [task]}
            for task in task_list
        ],
    }


def solvability_job(
    tasks: Iterable[str],
    *,
    job_name: str,
    jobs_dir: Path | str,
    n_concurrent_trials: int = 9,
) -> dict[str, Any]:
    """The token-free half: `oracle` must score 1.0, `nop` must score 0.0."""
    return _job_config(
        job_name,
        jobs_dir,
        tasks,
        [{"name": "oracle"}, {"name": "nop"}],
        n_concurrent_trials=n_concurrent_trials,
    )


def baseline_job(
    tasks: Iterable[str],
    *,
    job_name: str,
    jobs_dir: Path | str,
    agent: str,
    model: str,
    n_concurrent_trials: int = 9,
    n_concurrent_agents: int = 6,
    n_attempts: int = 1,
) -> dict[str, Any]:
    """The paid half: one bare-agent trial per task, to find the ceiling."""
    return _job_config(
        job_name,
        jobs_dir,
        tasks,
        [{"name": agent, "model_name": model, "n_concurrent": n_concurrent_agents}],
        n_concurrent_trials=n_concurrent_trials,
        n_attempts=n_attempts,
    )


def _trial_rows(job_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not job_dir.is_dir():
        return rows
    for result_path in sorted(job_dir.glob("*/result.json")):
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        config = data.get("config") or {}
        task_path = (config.get("task") or {}).get("path") or (data.get("task_id") or {}).get("path") or ""
        parts = Path(task_path).parts
        rewards = (data.get("verifier_result") or {}).get("rewards") or {}
        reward = rewards.get("reward")
        rows.append(
            {
                "task": parts[-1] if parts else "",
                "agent": ((data.get("agent_info") or {}).get("name"))
                or (config.get("agent") or {}).get("name")
                or "",
                "reward": float(reward) if reward is not None else None,
                "exception": (data.get("exception_info") or {}).get("exception_type"),
            }
        )
    return rows


def read_screen(
    jobs_dir: Path,
    tasks: Iterable[str],
    *,
    job_prefix: str,
    baseline_agent: str,
) -> list[TaskScreen]:
    """Collect both screen stages into one verdict per task, in selection order."""
    rows = _trial_rows(jobs_dir / f"{job_prefix}-{SOLVABILITY_SUFFIX}")
    rows += _trial_rows(jobs_dir / f"{job_prefix}-{BASELINE_SUFFIX}")

    oracle: dict[str, float | None] = {}
    nop: dict[str, float | None] = {}
    baseline: dict[str, list[float | None]] = {}
    errors: dict[str, list[str]] = {}
    for row in rows:
        task = row["task"]
        if row["agent"] == "oracle":
            oracle[task] = row["reward"]
        elif row["agent"] == "nop":
            nop[task] = row["reward"]
        elif row["agent"] == baseline_agent:
            baseline.setdefault(task, []).append(row["reward"])
            if row["exception"]:
                errors.setdefault(task, []).append(row["exception"])

    return [
        TaskScreen(
            task=task,
            oracle=oracle.get(task),
            nop=nop.get(task),
            baseline_rewards=tuple(baseline.get(task, ())),
            exceptions=tuple(errors.get(task, ())),
        )
        for task in tasks
    ]


def render_task_file(
    screens: list[TaskScreen],
    *,
    config_name: str,
    job_prefix: str,
    generated_at: str,
) -> str:
    """The task list, with every excluded task kept as a commented line.

    A task set is a claim about what was measured, so the tasks that were
    considered and dropped belong in the file next to the ones that were kept —
    otherwise the selection looks arbitrary to the next reader.
    """
    included = [screen for screen in screens if screen.verdict()[0] == INCLUDE]
    excluded = [screen for screen in screens if screen.verdict()[0] == EXCLUDE]
    unknown = [screen for screen in screens if screen.verdict()[0] == UNKNOWN]

    lines = [
        f"# Screened task set — {len(included)} of {len(screens)} candidates",
        "#",
        f"# Written by `hmb screen --config {config_name} --job-prefix {job_prefix}`",
        f"# on {generated_at}. Do not hand-edit: re-run the screen instead, so the",
        "# set stays a derivation rather than an opinion.",
        "#",
        "# A task is kept when all three hold:",
        "#   oracle scores 1.0     the task and its verifier work",
        "#   nop scores 0.0        the task does not pass without doing the work",
        "#   the bare agent fails  the task can still discriminate between conditions",
        "#",
        f"# Excluded: {len(excluded)}.  Undecided: {len(unknown)}.",
        "",
    ]
    for screen in included:
        lines.append(screen.task)
    if excluded or unknown:
        lines.append("")
        lines.append("# --- not measured -------------------------------------------------------")
    for screen in excluded + unknown:
        verdict, reason = screen.verdict()
        lines.append(f"# {screen.task}  ({verdict}: {reason})")
    return "\n".join(lines) + "\n"
