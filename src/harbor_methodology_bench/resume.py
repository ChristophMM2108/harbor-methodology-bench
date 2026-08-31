from __future__ import annotations

"""Selective re-runs of a finished Harbor job.

A bare `harbor job resume` treats an errored trial as a finished one: a
rate-limited trial keeps its 0.0 reward forever and reads like a finding. The
filter that prevents this must never be left to the operator's memory, so this
module classifies a job's trials first and always passes an explicit filter.

The filter is also bounded. Only infrastructure and transient-API failures may
be re-run; a genuine task failure has no `exception_info` at all and can never
be caught by a filter, and the failures that *are* methodology effects
(`OutputTokenExceededError`, timeouts) are deliberately not re-runnable.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from .jobplan import RETRY_EXCEPTIONS

# Re-runnable without an operator doing anything first: the trial died for a
# reason unrelated to what the task or the methodology did.
INFRA_EXCEPTIONS: tuple[str, ...] = ("CancelledError", "RuntimeError")

# Re-runnable only after a human recharges the account, hence `--recharged`.
RECHARGE_EXCEPTIONS: tuple[str, ...] = ("ApiUsageLimitError",)

FILTERABLE: frozenset[str] = frozenset(
    (*INFRA_EXCEPTIONS, *RETRY_EXCEPTIONS, *RECHARGE_EXCEPTIONS)
)

# Failures that are findings, not accidents. Named so the refusal can say why.
NEVER_FILTER: dict[str, str] = {
    "OutputTokenExceededError": "a configuration blowing the output cap is a methodology effect",
    "TimeoutError": "a timeout can be genuine methodology slowness",
    "AgentTimeoutError": "a timeout can be genuine methodology slowness",
    "TrialTimeoutError": "a timeout can be genuine methodology slowness",
}

# Neither a completed trial nor an errored one: Harbor's resume skips a
# result.json it cannot parse, so the directory survives every filter while
# reconciliation re-runs the trial beside it. Left unreported it inflates the
# trial count and can contribute a phantom 0.0 reward to a report.
UNREADABLE = "<unreadable result.json>"
NO_RESULT = "<no result.json>"
OK = "<no exception>"


class ResumeError(ValueError):
    """The job directory cannot be resumed as asked."""


@dataclass(frozen=True)
class TrialState:
    name: str
    exception_type: str


def classify_trials(job_dir: Path) -> list[TrialState]:
    """Every trial directory in the job, labelled by exception type."""
    states: list[TrialState] = []
    for trial_dir in sorted(path for path in job_dir.iterdir() if path.is_dir()):
        result_path = trial_dir / "result.json"
        if not result_path.is_file():
            states.append(TrialState(trial_dir.name, NO_RESULT))
            continue
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            states.append(TrialState(trial_dir.name, UNREADABLE))
            continue
        info = data.get("exception_info") or {}
        states.append(TrialState(trial_dir.name, info.get("exception_type") or OK))
    return states


def breakdown(states: list[TrialState]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for state in states:
        counts[state.exception_type] = counts.get(state.exception_type, 0) + 1
    return dict(sorted(counts.items()))


def check_job_dir(job_dir: Path) -> dict:
    """Load the job's stored config, refusing a directory resume would not touch.

    Harbor resumes the `jobs_dir` / `job_name` recorded inside `config.json`,
    not the path given on the command line. A copied job directory therefore
    resumes the original in place, silently. Fail instead.
    """
    if not job_dir.is_dir():
        raise ResumeError(f"job directory does not exist: {job_dir}")
    config_path = job_dir / "config.json"
    if not config_path.is_file():
        raise ResumeError(f"not a Harbor job directory (no config.json): {job_dir}")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ResumeError(f"cannot read {config_path}: {error}") from error

    recorded = (Path(config.get("jobs_dir", "jobs")) / config.get("job_name", "")).resolve()
    if recorded != job_dir.resolve():
        raise ResumeError(
            f"this job's config.json points at {recorded}, not {job_dir.resolve()}.\n"
            "Harbor resumes the recorded path, so resuming here would operate on the "
            "other directory. Resume the original in place, or start a new job."
        )
    return config


def resume_filters(
    states: list[TrialState],
    *,
    extra: tuple[str, ...] = (),
    recharged: bool = False,
) -> list[str]:
    """The exception types to re-run, validated against the allowlist.

    Only types actually present in the job are returned, so the printed filter
    is what will really happen rather than a wish list.
    """
    for name in extra:
        if name in NEVER_FILTER:
            raise ResumeError(f"refusing to re-run {name}: {NEVER_FILTER[name]}")
        if name not in FILTERABLE:
            raise ResumeError(
                f"refusing to re-run {name}: not an infrastructure or transient API "
                "failure. A task failure must stay in the results."
            )

    allowed = set(INFRA_EXCEPTIONS) | set(RETRY_EXCEPTIONS) | set(extra)
    if recharged:
        allowed |= set(RECHARGE_EXCEPTIONS)
    present = {state.exception_type for state in states}
    return sorted(allowed & present)


def read_env_file(path: Path) -> dict[str, str]:
    """The `KEY=VALUE` pairs in a dotenv-style file.

    `harbor job resume` has no `--env-file`, and an agent config stores its
    sensitive values as templates resolved from the process environment, so the
    credentials have to be exported by the caller or every re-run trial fails
    to authenticate.
    """
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            values[key] = value
    return values
