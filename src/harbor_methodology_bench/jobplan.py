from __future__ import annotations

"""Harbor job configurations derived from an experiment configuration.

One job per agent, spanning every condition and every selected task. Harbor
names each trial directory with a random suffix and records the variant under
`config.task.path`, so a single job can hold all conditions without collision
and `hmb report` still splits them apart (see `report.parse_trial_result`).

The dataset list is emitted **task-major**: every condition of one task is
queued before the next task's conditions. Harbor extends its task list dataset
by dataset with no deduplication and then iterates attempt -> task -> agent, so
this ordering is what makes conditions run paired rather than one whole
condition after another. Paired execution keeps host contention symmetric
across conditions, which `duration_sec` would otherwise absorb.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import ExperimentConfig

# Concurrency defaults for a 16-core host. `n_concurrent_trials` covers the
# whole trial lifecycle (build, agent, verify); `n_concurrent_agents` caps only
# the agent phase, leaving slots free so builds and verifiers overlap agent runs
# and a rate-limit stall cannot idle the machine.
DEFAULT_N_CONCURRENT_TRIALS = 9
DEFAULT_N_CONCURRENT_AGENTS = 6

# Exceptions worth retrying: transient API conditions that clear on their own.
# Deliberately excluded, because retrying them would hide a real finding:
#   ApiUsageLimitError     — needs a human to recharge the account.
#   OutputTokenExceededError — a verbose configuration blowing the output cap is
#                              itself a methodology effect.
#   Timeouts               — could be genuine methodology slowness.
RETRY_EXCEPTIONS: tuple[str, ...] = (
    "ApiConnectionClosedError",
    "ApiInternalServerError",
    "ApiOverloadedError",
    "ApiRateLimitError",
    "ApiResponseStalledError",
)

DEFAULT_MAX_RETRIES = 2


class JobPlanError(ValueError):
    """The experiment configuration cannot be turned into a job plan."""


@dataclass(frozen=True)
class JobPlan:
    """One Harbor job: a single agent across every condition and task."""

    agent: str
    model: str
    job_name: str
    variants: tuple[str, ...]
    tasks: tuple[str, ...]
    config: dict[str, Any] = field(compare=False, repr=False)

    @property
    def n_cells(self) -> int:
        return len(self.variants) * len(self.tasks)

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.config, sort_keys=False, default_flow_style=False)


def _cells_by_agent(settings: ExperimentConfig) -> dict[str, list[str]]:
    """Agent -> its conditions, both in configuration order, deduplicated."""
    valid = {"baseline", *settings.toolkits}
    grouped: dict[str, list[str]] = {}
    for cell in settings.matrix:
        variant = cell["toolkit"]
        agent = cell["agent"]
        if variant not in valid:
            raise JobPlanError(f"unknown toolkit variant: {variant}")
        if agent not in settings.models:
            raise JobPlanError(f"no model configured for agent: {agent}")
        variants = grouped.setdefault(agent, [])
        if variant not in variants:
            variants.append(variant)
    return grouped


def _dataset_path(settings: ExperimentConfig, variant: str) -> str:
    """`generated/<variant>`, relative to the repository root when it can be.

    Harbor stores the plan verbatim, and `report` derives the condition from
    this path, so a relative path keeps a job config portable between checkouts.
    """
    path = settings.generated_root / variant
    try:
        return str(path.relative_to(settings.root))
    except ValueError:
        return str(path)


def plan_jobs(
    settings: ExperimentConfig,
    task_ids: list[str],
    *,
    job_prefix: str = "pilot",
    attempts: int = 1,
    jobs_dir: Path | str = "jobs",
    n_concurrent_trials: int = DEFAULT_N_CONCURRENT_TRIALS,
    n_concurrent_agents: int = DEFAULT_N_CONCURRENT_AGENTS,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> list[JobPlan]:
    """One `JobPlan` per agent in the matrix, in configuration order.

    The output is a pure function of the experiment configuration and the task
    list, so the same experiment file always yields the same job configs.
    """
    if not task_ids:
        raise JobPlanError("no tasks selected")
    if attempts < 1:
        raise JobPlanError("attempts must be at least 1")
    if n_concurrent_trials < 1:
        raise JobPlanError("n_concurrent_trials must be at least 1")
    if n_concurrent_agents < 1:
        raise JobPlanError("n_concurrent_agents must be at least 1")
    if n_concurrent_agents > n_concurrent_trials:
        raise JobPlanError(
            f"n_concurrent_agents ({n_concurrent_agents}) must not exceed "
            f"n_concurrent_trials ({n_concurrent_trials})"
        )
    if max_retries < 0:
        raise JobPlanError("max_retries must not be negative")

    plans: list[JobPlan] = []
    for agent, variants in _cells_by_agent(settings).items():
        missing = [
            f"{variant}/{task_id}"
            for task_id in task_ids
            for variant in variants
            if not (settings.generated_root / variant / task_id).is_dir()
        ]
        if missing:
            raise JobPlanError(
                "generate these variants first: " + ", ".join(sorted(missing))
            )

        datasets = [
            {"path": _dataset_path(settings, variant), "task_names": [task_id]}
            for task_id in task_ids
            for variant in variants
        ]
        job_name = f"{job_prefix}-{agent}"
        config: dict[str, Any] = {
            "job_name": job_name,
            "jobs_dir": str(jobs_dir),
            "n_attempts": attempts,
            "n_concurrent_trials": n_concurrent_trials,
            "retry": {
                "max_retries": max_retries,
                "include_exceptions": list(RETRY_EXCEPTIONS),
            },
            "agents": [
                {
                    "name": agent,
                    "model_name": settings.models[agent],
                    "n_concurrent": n_concurrent_agents,
                }
            ],
            "datasets": datasets,
        }
        plans.append(
            JobPlan(
                agent=agent,
                model=settings.models[agent],
                job_name=job_name,
                variants=tuple(variants),
                tasks=tuple(task_ids),
                config=config,
            )
        )
    return plans


def write_job_configs(plans: list[JobPlan], out_dir: Path) -> list[Path]:
    """Write `<out_dir>/<job_name>.yaml` for each plan and return the paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for plan in plans:
        path = out_dir / f"{plan.job_name}.yaml"
        path.write_text(plan.to_yaml(), encoding="utf-8")
        written.append(path)
    return written
