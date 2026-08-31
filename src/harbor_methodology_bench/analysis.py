"""Trial-level analysis: raw Harbor job output to tidy tables.

`hmb report` aggregates one number per cell. This module goes back to the raw
trial artefacts under `jobs/<pattern>/` and derives what an aggregate cannot
carry — per-test partial credit, budget utilisation, censoring, per-step token
and tool-call telemetry, and a strict adherence measure.

Sources, per trial directory:

    result.json              rewards, token/cost totals, phase timestamps, exception
    verifier/ctrf.json       per-test results from the verifier's test run
    agent/trajectory.json    ATIF trajectory: steps, tool calls, per-step tokens
    agent/<agent>.txt        the agent CLI's own startup log (skill registration)

Task metadata (difficulty, axes, agent budget) is joined from a catalogue JSON
when one is present; `hmb catalogue --json-out` writes it.

Everything here is read-only with respect to the job output.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

CONFIG_MARKERS = ("CLAUDE.md", "AGENTS.md")
TABLE_NAMES = ("trials", "tests", "steps", "tool_calls")

# ---------------------------------------------------------------------------
# Bash command taxonomy
#
# These are heuristics over the command string, not a parse. They are good
# enough to compare conditions against each other on the same corpus, and they
# are deliberately conservative: a command that matches nothing lands in
# `other` rather than being forced into a bucket.
# ---------------------------------------------------------------------------
TEST_PATTERNS = (
    r"\bpytest\b",
    r"python[0-9.]*\s+-m\s+(pytest|unittest)\b",
    r"\bunittest\b",
    r"\bmake\s+(test|check|runtest)",
    r"\bcargo\s+test\b",
    r"\bgo\s+test\b",
    r"\bctest\b",
    r"\bnpm\s+(run\s+)?test\b",
    r"\bdune\s+(runtest|test)\b",
    r"\btox\b",
    r"\bnose2?\b",
    r"(^|[\s/])run_tests?\.(sh|py)",
    r"(^|[\s/])tests?\.sh\b",
    r"(^|[\s/])test_[\w-]+\.py\b",
    # Ad-hoc self-verification: running a script or binary the agent named test /
    # verify / check. Agents do this far more often than they call a test runner.
    r"(^|[\s;&|])\./?(test|verify|check)[\w-]*\b",
    r"python[0-9.]*\s+[^\s]*(test|verify|check)[\w-]*\.py\b",
)
BUILD_PATTERNS = (
    r"\bmake\b(?!\s+(test|check|runtest))",
    r"\bcmake\b",
    r"\bgcc\b|\bg\+\+\b|\bclang\b|\bcc\s+-",
    r"\bcargo\s+(build|check)\b",
    r"\bsetup\.py\s+(build|install)",
    r"\bpip[0-9.]*\s+install\b",
    r"\buv\s+(pip|sync|add)\b",
    r"\bapt-get\b|\bapt\b\s+install",
    r"\bopam\b|\bdune\s+build\b",
    r"\bnpm\s+(install|ci)\b",
)
INSPECT_PATTERNS = (
    r"^\s*(ls|cat|head|tail|find|grep|rg|wc|tree|pwd|which|sed\s+-n|awk|file|nm|objdump|stat|du)\b",
    r"\bgit\s+(status|log|diff|show)\b",
)
ERROR_MARKERS = (
    "Traceback (most recent call last)",
    "command not found",
    "No such file or directory",
    "error:",
    "ERROR:",
    "Error:",
    "fatal:",
    "FAILED",
    "AssertionError",
    "SyntaxError",
    "Segmentation fault",
    "cannot find",
    "undefined reference",
    "Permission denied",
)
EDIT_TOOLS = ("Edit", "Write", "NotebookEdit")

# A file the agent wrote as process output rather than as the solution: a plan,
# a specification, a set of notes. Both toolkits under comparison ask for one
# before code is touched, so writing one is evidence the method was followed and
# not merely available.
DOC_SUFFIXES = (".md", ".markdown", ".rst", ".txt", ".adoc")

# The shell reports a nonzero exit status on the first line of a tool result,
# and omits the line entirely when the command succeeded.
EXIT_CODE_RE = re.compile(r"^Exit code (\d+)")
TOOL_FAILURE_MARKER = "[error] tool reported failure"
TEST_FILE_RE = re.compile(r"(^|/)(test_[\w-]+|[\w-]+_test)\.(py|rs|c|ml|js|ts|go)$|(^|/)tests?/")

_TEST_RE = [re.compile(p) for p in TEST_PATTERNS]
_BUILD_RE = [re.compile(p) for p in BUILD_PATTERNS]
_INSPECT_RE = [re.compile(p) for p in INSPECT_PATTERNS]


def _call_results(step: dict[str, Any]) -> dict[str, bool]:
    """`tool_call_id -> whether the call failed`, from one step's observation.

    Failure is read from the exit status the harness records, not from the text:
    a test runner exits nonzero when a test fails, which is the only signal here
    that does not depend on guessing a framework's output format.
    """
    observation = step.get("observation")
    if not isinstance(observation, dict):
        return {}
    failed: dict[str, bool] = {}
    for entry in observation.get("results") or []:
        call_id = entry.get("source_call_id")
        if not call_id:
            continue
        content = str(entry.get("content") or "")
        metadata = (entry.get("extra") or {}).get("tool_result_metadata") or {}
        match = EXIT_CODE_RE.match(content)
        failed[call_id] = bool(
            metadata.get("tool_result_is_error")
            or TOOL_FAILURE_MARKER in content
            or (match and match.group(1) != "0")
        )
    return failed


def _is_doc(path: str) -> bool:
    return path.lower().endswith(DOC_SUFFIXES)


def _any(patterns: Iterable[re.Pattern[str]], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def classify_bash(command: str) -> str:
    """Bucket a shell command. Test wins over build, build over inspection."""
    if _any(_TEST_RE, command):
        return "test"
    if _any(_BUILD_RE, command):
        return "build"
    if _any(_INSPECT_RE, command):
        return "inspect"
    return "other"


def _ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _phase_seconds(block: dict[str, Any] | None) -> float | None:
    if not block:
        return None
    start, end = _ts(block.get("started_at")), _ts(block.get("finished_at"))
    if not start or not end:
        return None
    return (end - start).total_seconds()


# ---------------------------------------------------------------------------
# Task metadata
# ---------------------------------------------------------------------------
def load_catalogue(path: Path | None) -> dict[str, dict[str, Any]]:
    """Task metadata by task id, or an empty mapping when no catalogue exists.

    A missing catalogue is not an error: it costs the axis, difficulty and budget
    columns, and every other column is still derived.
    """
    if path is None or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {task["task_id"]: task for task in data.get("tasks", [])}


# ---------------------------------------------------------------------------
# Per-trial extraction
# ---------------------------------------------------------------------------
@dataclass
class Trial:
    row: dict[str, Any]
    tests: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]


def _condition_from_task_path(result: dict[str, Any]) -> str:
    path = ((result.get("task_id") or {}).get("path")) or ""
    parts = Path(path).parts
    return parts[1] if len(parts) >= 2 else "unknown"


def read_ctrf(trial_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The verifier's own test summary and per-test rows, when it wrote them."""
    ctrf = trial_dir / "verifier" / "ctrf.json"
    if not ctrf.is_file():
        return {}, []
    try:
        payload = json.loads(ctrf.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}, []
    results = payload.get("results") or {}
    summary = results.get("summary") or {}
    tests = results.get("tests") or []
    return summary, tests


def toolkit_skills(task_path: str | None, root: Path) -> list[str]:
    """The skill names the generator installed for this variant.

    Read from the variant's own manifest, so it is the toolkit's skill set and
    not the agent CLI's built-ins.
    """
    if not task_path:
        return []
    manifest = root / task_path / ".methodology-bench-manifest.json"
    if not manifest.is_file():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return sorted((data.get("environment") or {}).get("skills_registered") or [])


def _skills_registered(trial_dir: Path) -> list[str]:
    """Skill names the CLI printed in its own startup log.

    The startup line is a JSON array under the key "skills"; reading it is more
    honest than substring-matching the toolkit's expected names, because it
    reports what the CLI actually loaded.
    """
    logs = sorted((trial_dir / "agent").glob("*.txt")) if (trial_dir / "agent").is_dir() else []
    if not logs:
        return []
    text = "\n".join(log.read_text(encoding="utf-8", errors="replace") for log in logs)
    names: set[str] = set()
    for match in re.finditer(r'"skills"\s*:\s*\[(.*?)\]', text, re.S):
        names.update(re.findall(r'"([^"]+)"', match.group(1)))
    return sorted(names)


def extract_trial(result_path: Path, catalogue: dict[str, dict[str, Any]], root: Path) -> Trial:
    trial_dir = result_path.parent
    result = json.loads(result_path.read_text(encoding="utf-8"))

    job_name = trial_dir.parent.name
    task = str(result.get("task_name") or "").split("/")[-1]
    condition = _condition_from_task_path(result)
    agent_result = result.get("agent_result") or {}
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    reward = rewards.get("reward")
    exception_info = result.get("exception_info") or {}

    summary, tests = read_ctrf(trial_dir)
    tests_total = summary.get("tests")
    tests_passed = summary.get("passed")

    row: dict[str, Any] = {
        "job_name": job_name,
        "trial_name": trial_dir.name,
        "task": task,
        "condition": condition,
        "agent": ((result.get("agent_info") or {}).get("name")),
        "model": (((result.get("agent_info") or {}).get("model_info")) or {}).get("name"),
        "reward": float(reward) if reward is not None else None,
        "success": bool(reward is not None and float(reward) >= 1.0),
        "exception_type": exception_info.get("exception_type"),
        "agent_timeout": exception_info.get("exception_type") == "AgentTimeoutError",
        "verifier_timeout": exception_info.get("exception_type") == "VerifierTimeoutError",
        # cost and tokens
        "cost_usd": agent_result.get("cost_usd"),
        "input_tokens": agent_result.get("n_input_tokens"),
        "output_tokens": agent_result.get("n_output_tokens"),
        "cache_tokens": agent_result.get("n_cache_tokens"),
        # phase durations
        "env_setup_sec": _phase_seconds(result.get("environment_setup")),
        "agent_setup_sec": _phase_seconds(result.get("agent_setup")),
        "agent_sec": _phase_seconds(result.get("agent_execution")),
        "verifier_sec": _phase_seconds(result.get("verifier")),
        "wall_sec": _phase_seconds(
            {"started_at": result.get("started_at"), "finished_at": result.get("finished_at")}
        ),
        # verifier test detail
        "tests_total": tests_total,
        "tests_passed": tests_passed,
        "tests_failed": summary.get("failed"),
        "tests_skipped": summary.get("skipped"),
        "partial_credit": (tests_passed / tests_total) if tests_total else None,
        "ctrf_found": bool(summary),
    }

    row.update(_trajectory_features(trial_dir))

    registered = _skills_registered(trial_dir)
    expected = toolkit_skills((result.get("task_id") or {}).get("path"), root)
    called = [name for name in row["skill_call_sequence"].split(";") if name]
    row["skills_registered"] = ";".join(registered)
    row["n_skills_registered"] = len(registered)
    row["toolkit_skills"] = ";".join(expected)
    row["n_toolkit_skills"] = len(expected)
    row["n_toolkit_skills_registered"] = len(set(expected) & set(registered))
    row["n_toolkit_skill_calls"] = sum(1 for name in called if name in expected)
    row["n_foreign_skill_calls"] = sum(1 for name in called if name not in expected)
    row["used_toolkit_skill"] = row["n_toolkit_skill_calls"] > 0
    if row["input_tokens"]:
        row["cache_hit_ratio"] = (row["cache_tokens"] or 0) / row["input_tokens"]
    else:
        row["cache_hit_ratio"] = None
    if row["output_tokens"]:
        row["thinking_share"] = (row["thinking_tokens"] or 0) / row["output_tokens"]
    else:
        row["thinking_share"] = None

    meta = catalogue.get(task, {})
    row.update(
        {
            "difficulty": meta.get("difficulty"),
            "category": meta.get("category"),
            "axes": ";".join(meta.get("axes") or []),
            "expert_min": meta.get("expert_min"),
            "budget_sec": meta.get("agent_timeout_sec"),
            "instruction_words": meta.get("instruction_words"),
            "requirement_lines": meta.get("requirement_lines"),
            "test_code_bytes": meta.get("test_code_bytes"),
            "requires_own_tests": meta.get("requires_own_tests"),
        }
    )
    if row["budget_sec"] and row["agent_sec"]:
        row["budget_used"] = row["agent_sec"] / row["budget_sec"]
    else:
        row["budget_used"] = None

    test_rows = [
        {
            "job_name": job_name,
            "task": task,
            "condition": condition,
            "test_name": entry.get("name"),
            "status": entry.get("status"),
            "duration": entry.get("duration"),
        }
        for entry in tests
    ]

    steps, tool_calls = _trajectory_tables(trial_dir, job_name, task, condition)
    return Trial(row=row, tests=test_rows, steps=steps, tool_calls=tool_calls)


def _load_trajectory(trial_dir: Path) -> dict[str, Any] | None:
    path = trial_dir / "agent" / "trajectory.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def _trajectory_features(trial_dir: Path) -> dict[str, Any]:
    """Behavioural features of one trial, read from its ATIF trajectory."""
    empty = {
        "n_steps": None,
        "n_llm_calls": None,
        "n_tool_calls": None,
        "thinking_tokens": None,
        "sidechain_steps": None,
        "sidechain_share": None,
        "n_agent_spawns": 0,
        "n_skill_calls": 0,
        "skills_called": "",
        "skill_call_sequence": "",
        "n_bash": 0,
        "bash_test": 0,
        "bash_build": 0,
        "bash_inspect": 0,
        "bash_other": 0,
        "n_read": 0,
        "n_edit": 0,
        "n_write": 0,
        "n_edits_total": 0,
        "files_touched": 0,
        "edits_per_file": None,
        "wrote_test_file": False,
        "time_to_first_edit_sec": None,
        "explore_share": None,
        # Speed that survives a ceiling: when the work first demonstrably worked,
        # rather than whether it did by the end.
        "n_test_runs": 0,
        "n_passing_test_runs": 0,
        "time_to_first_test_sec": None,
        "time_to_first_passing_test_sec": None,
        "steps_to_first_passing_test": None,
        # Was the method followed, or merely available? Each flag is about order:
        # what the agent did before it first touched code.
        "config_read_before_code": False,
        "skill_before_code": False,
        "doc_written_before_code": False,
        "test_run_before_code": False,
        "compliance_score": None,
        "error_observations": 0,
        "error_rate": None,
        "config_markers": "",
        "n_config_reads": 0,
        "traj_span_sec": None,
        "trajectory_found": False,
    }
    data = _load_trajectory(trial_dir)
    if not data:
        return empty

    steps = data.get("steps") or []
    agent_steps = [s for s in steps if s.get("source") not in ("user", "system")]
    out = dict(empty)
    out["trajectory_found"] = True
    out["n_steps"] = len(agent_steps)
    out["n_llm_calls"] = sum(int(s.get("llm_call_count") or 0) for s in agent_steps)

    thinking = 0
    sidechain = 0
    tool_calls: list[tuple[datetime | None, str, dict[str, Any], bool]] = []
    errors = 0
    observations = 0
    files: set[str] = set()
    skills: list[str] = []
    config_seen: set[str] = set()

    first_ts = _ts(steps[0].get("timestamp")) if steps else None
    last_ts = _ts(steps[-1].get("timestamp")) if steps else None
    if first_ts and last_ts:
        out["traj_span_sec"] = (last_ts - first_ts).total_seconds()

    first_edit_ts: datetime | None = None
    steps_before_first_edit: int | None = None
    first_code_edit_index: int | None = None
    first_test_ts: datetime | None = None
    first_pass_ts: datetime | None = None
    steps_to_first_pass: int | None = None
    first_config_read_index: int | None = None
    first_skill_index: int | None = None
    first_doc_write_index: int | None = None
    first_test_index: int | None = None

    for index, step in enumerate(agent_steps):
        metrics = step.get("metrics") or {}
        extra = metrics.get("extra") or {}
        thinking += int(((extra.get("output_tokens_details") or {}).get("thinking_tokens")) or 0)
        is_side = bool((step.get("extra") or {}).get("is_sidechain"))
        sidechain += int(is_side)

        message = step.get("message") or ""
        for marker in CONFIG_MARKERS:
            if marker in message:
                config_seen.add(marker)

        ts = _ts(step.get("timestamp"))
        failed_calls = _call_results(step)
        for call in step.get("tool_calls") or []:
            name = call.get("function_name") or ""
            args = call.get("arguments") or {}
            tool_calls.append((ts, name, args, is_side))
            if name in EDIT_TOOLS:
                path = str(args.get("file_path") or args.get("notebook_path") or "")
                if path:
                    files.add(path)
                    if TEST_FILE_RE.search(path):
                        out["wrote_test_file"] = True
                    if _is_doc(path):
                        if first_doc_write_index is None:
                            first_doc_write_index = index
                    elif first_code_edit_index is None:
                        first_code_edit_index = index
                elif first_code_edit_index is None:
                    first_code_edit_index = index
                if first_edit_ts is None:
                    first_edit_ts = ts
                    steps_before_first_edit = index
            if name == "Skill":
                skills.append(str(args.get("skill") or ""))
                if first_skill_index is None:
                    first_skill_index = index
            if name == "Bash" and classify_bash(str(args.get("command") or "")) == "test":
                out["n_test_runs"] += 1
                if first_test_index is None:
                    first_test_index = index
                if first_test_ts is None:
                    first_test_ts = ts
                if not failed_calls.get(str(call.get("tool_call_id") or ""), False):
                    out["n_passing_test_runs"] += 1
                    if first_pass_ts is None:
                        first_pass_ts = ts
                        steps_to_first_pass = index
            arg_text = json.dumps(args)
            for marker in CONFIG_MARKERS:
                if marker in arg_text:
                    config_seen.add(marker)
                    # An instruction file named in a Read path or a shell command is
                    # the agent actually opening it, not merely mentioning it.
                    if name == "Read" or (name == "Bash" and marker in str(args.get("command") or "")):
                        out["n_config_reads"] += 1
                        if first_config_read_index is None:
                            first_config_read_index = index

        observation = step.get("observation")
        if observation:
            text = json.dumps(observation)
            observations += 1
            if any(marker in text for marker in ERROR_MARKERS):
                errors += 1

    out["thinking_tokens"] = thinking
    out["sidechain_steps"] = sidechain
    out["sidechain_share"] = (sidechain / len(agent_steps)) if agent_steps else None
    out["n_tool_calls"] = len(tool_calls)
    out["error_observations"] = errors
    out["error_rate"] = (errors / observations) if observations else None
    out["config_markers"] = ";".join(sorted(config_seen))

    for _, name, args, _side in tool_calls:
        if name == "Bash":
            out["n_bash"] += 1
            bucket = classify_bash(str(args.get("command") or ""))
            out[f"bash_{bucket}"] += 1
        elif name == "Read":
            out["n_read"] += 1
        elif name == "Edit":
            out["n_edit"] += 1
        elif name == "Write":
            out["n_write"] += 1
        elif name == "Agent":
            out["n_agent_spawns"] += 1

    out["n_edits_total"] = out["n_edit"] + out["n_write"]
    out["files_touched"] = len(files)
    out["edits_per_file"] = (out["n_edits_total"] / len(files)) if files else None
    out["n_skill_calls"] = len(skills)
    out["skill_call_sequence"] = ";".join(s for s in skills if s)
    out["skills_called"] = ";".join(sorted(set(s for s in skills if s)))

    if first_edit_ts and first_ts:
        out["time_to_first_edit_sec"] = (first_edit_ts - first_ts).total_seconds()
    if steps_before_first_edit is not None and agent_steps:
        out["explore_share"] = steps_before_first_edit / len(agent_steps)
    if first_test_ts and first_ts:
        out["time_to_first_test_sec"] = (first_test_ts - first_ts).total_seconds()
    if first_pass_ts and first_ts:
        out["time_to_first_passing_test_sec"] = (first_pass_ts - first_ts).total_seconds()
    out["steps_to_first_passing_test"] = steps_to_first_pass

    # Compliance is about order, so it is only defined once code was touched:
    # a trial that never edited anything cannot have done these things "first".
    code_at = first_code_edit_index if first_code_edit_index is not None else len(agent_steps)
    flags = {
        "config_read_before_code": first_config_read_index is not None
        and first_config_read_index < code_at,
        "skill_before_code": first_skill_index is not None and first_skill_index < code_at,
        "doc_written_before_code": first_doc_write_index is not None
        and first_doc_write_index < code_at,
        "test_run_before_code": first_test_index is not None and first_test_index < code_at,
    }
    out.update(flags)
    if first_code_edit_index is not None:
        out["compliance_score"] = sum(flags.values()) / len(flags)

    return out


def _trajectory_tables(
    trial_dir: Path, job_name: str, task: str, condition: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = _load_trajectory(trial_dir)
    if not data:
        return [], []
    steps = data.get("steps") or []
    first_ts = _ts(steps[0].get("timestamp")) if steps else None

    step_rows: list[dict[str, Any]] = []
    call_rows: list[dict[str, Any]] = []
    for step in steps:
        if step.get("source") in ("user", "system"):
            continue
        ts = _ts(step.get("timestamp"))
        offset = (ts - first_ts).total_seconds() if ts and first_ts else None
        metrics = step.get("metrics") or {}
        extra = metrics.get("extra") or {}
        step_rows.append(
            {
                "job_name": job_name,
                "task": task,
                "condition": condition,
                "step_id": step.get("step_id"),
                "t_sec": offset,
                "prompt_tokens": metrics.get("prompt_tokens"),
                "completion_tokens": metrics.get("completion_tokens"),
                "cached_tokens": metrics.get("cached_tokens"),
                "thinking_tokens": (extra.get("output_tokens_details") or {}).get(
                    "thinking_tokens"
                ),
                "is_sidechain": bool((step.get("extra") or {}).get("is_sidechain")),
                "stop_reason": (step.get("extra") or {}).get("stop_reason"),
                "n_tool_calls": len(step.get("tool_calls") or []),
            }
        )
        for call in step.get("tool_calls") or []:
            name = call.get("function_name") or ""
            args = call.get("arguments") or {}
            call_rows.append(
                {
                    "job_name": job_name,
                    "task": task,
                    "condition": condition,
                    "step_id": step.get("step_id"),
                    "t_sec": offset,
                    "tool": name,
                    "bash_class": classify_bash(str(args.get("command") or ""))
                    if name == "Bash"
                    else None,
                    "is_sidechain": bool((step.get("extra") or {}).get("is_sidechain")),
                }
            )
    return step_rows, call_rows


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------
def extract_all(
    jobs_dir: Path,
    pattern: str = "*",
    catalogue_path: Path | None = None,
    root: Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Every trial matching a job-name glob, as four tidy tables.

    `pattern` is a glob over job directory names, the same shape `hmb report
    --pattern` takes, so one analysis can span a whole experiment or a single
    cell.
    """
    root = root or jobs_dir.parent
    catalogue = load_catalogue(catalogue_path)
    trials = sorted(jobs_dir.glob(f"{pattern}/*/result.json"))
    if not trials:
        raise FileNotFoundError(f"no trials matching {pattern!r} under {jobs_dir}")
    rows: list[dict[str, Any]] = []
    tests: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    for path in trials:
        trial = extract_trial(path, catalogue, root)
        rows.append(trial.row)
        tests.extend(trial.tests)
        steps.extend(trial.steps)
        calls.extend(trial.tool_calls)
    return {"trials": rows, "tests": tests, "steps": steps, "tool_calls": calls}


def write_csvs(
    out_dir: Path, tables: dict[str, list[dict[str, Any]]], prefix: str = ""
) -> dict[str, Path]:
    """Write one CSV per table. Column order follows first appearance."""
    import csv

    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, rows in tables.items():
        if not rows:
            continue
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        path = out_dir / f"{prefix}{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        written[name] = path
    return written
