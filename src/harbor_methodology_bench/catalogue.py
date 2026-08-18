"""Classify benchmark tasks by what a methodology has to do to solve them.

The benchmark's own `[metadata].category` says what a task is *about*
(`security`, `data-science`, …). It says nothing about the kind of work the
agent must perform, which is what decides whether a given methodology skill can
help. This module derives a second, orthogonal classification — the *axes* — from
measurable task metadata, so a task set can be chosen for the capability under
test rather than by alphabetical accident.

Every rule below is a threshold over a measured signal. They are heuristics over
the tasks' own metadata, not editorial judgements, and they live here so a single
edit re-classifies the whole suite.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# Files under tests/ that carry verification logic rather than fixture data.
TEST_CODE_SUFFIXES = frozenset(
    {
        ".py", ".sh", ".bash", ".ps1", ".bat", ".js", ".ts", ".rs", ".c", ".cpp",
        ".go", ".rb", ".pl", ".lua", ".r", ".toml", ".cfg", ".ini", ".yaml", ".yml",
    }
)

REQUIREMENT_LINE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+", re.M)

# Vocabulary of a task that hands the agent a broken system to diagnose.
FAILURE_WORDS = (
    "fix", "repair", "broken", "crash", "fails", "failing", "error", "bug",
    "debug", "recover", "corrupt", "truncat", "leak", "vulnerab", "regression",
    "does not work", "no longer",
)

# Vocabulary and id patterns of a task that changes code the agent did not write.
CHANGE_WORDS = (
    "existing", "already", "currently", "modify", "refactor", "rewrite",
    "moderniz", "migrat", "port the", "convert", "translate", "replace",
    "optimize", "improve", "update the", "given implementation", "provided code",
)
CHANGE_ID_MARKERS = (
    "fix-", "-modify", "-recovery", "-reverse", "moderniz", "-to-", "break-",
    "tune-", "sanitize-", "-truncate", "optimize", "-leak-", "merge-diff",
)

ENVIRONMENT_ID_PREFIXES = ("build-", "compile-", "install-", "configure-", "qemu-")
ENVIRONMENT_CATEGORIES = ("system-administration",)

WRITE_TESTS = re.compile(
    r"(formal testing|write (?:a |the )?tests?|test (?:function|suite)|"
    r"must (?:include|provide) tests?|your tests?)",
    re.I,
)

# Thresholds. Tune here; everything downstream follows.
SPEC_DENSE_REQUIREMENTS = 8
SPEC_DENSE_WORDS = 250
UNDERSPECIFIED_WORDS = 60
LONG_HORIZON_EXPERT_MIN = 240.0
LONG_HORIZON_TIMEOUT_SEC = 1800.0
QUICK_EXPERT_MIN = 30.0
QUICK_TIMEOUT_SEC = 900.0
VERIFICATION_TEST_CODE_BYTES = 10_000
FAILURE_HITS = 2
CHANGE_HITS = 2

AXIS_DESCRIPTIONS = {
    "spec-dense": "Many explicit, individually checkable requirements in one prompt.",
    "underspecified": "Short prompt with no enumerated requirements; the agent must decide what done means.",
    "long-horizon": "Expert estimate at or above 4 hours of human work.",
    "quick": "Cheap to run: expert estimate at or below 30 minutes and a 15-minute agent budget.",
    "diagnose-first": "A broken system is supplied; the cause must be found before anything is fixed.",
    "modify-existing": "The agent changes code or state it did not write.",
    "verification-heavy": "Graded by a large test surface, or the prompt requires the agent to write tests.",
    "environment-engineering": "Build systems, toolchains, servers and virtual machines rather than application code.",
    "greenfield-algorithmic": "Implement something from scratch against a short, self-contained statement.",
}


@dataclass
class TaskFacts:
    """Measured signals and derived axes for one benchmark task."""

    task_id: str
    category: str | None = None
    difficulty: str | None = None
    expert_min: float | None = None
    agent_timeout_sec: float | None = None
    verifier_timeout_sec: float | None = None
    words: int = 0
    requirements: int = 0
    test_code_bytes: int = 0
    test_data_bytes: int = 0
    requires_own_tests: bool = False
    docker_image: str | None = None
    tags: list[str] = field(default_factory=list)
    description: str = ""
    axes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "category": self.category,
            "difficulty": self.difficulty,
            "expert_min": self.expert_min,
            "agent_timeout_sec": self.agent_timeout_sec,
            "verifier_timeout_sec": self.verifier_timeout_sec,
            "instruction_words": self.words,
            "requirement_lines": self.requirements,
            "test_code_bytes": self.test_code_bytes,
            "test_data_bytes": self.test_data_bytes,
            "requires_own_tests": self.requires_own_tests,
            "docker_image": self.docker_image,
            "tags": self.tags,
            "description": self.description,
            "axes": self.axes,
        }


def _count_hits(haystack: str, needles: tuple[str, ...]) -> int:
    return sum(1 for needle in needles if needle in haystack)


def _test_surface(task_dir: Path) -> tuple[int, int]:
    tests = task_dir / "tests"
    if not tests.is_dir():
        return 0, 0
    code = 0
    data = 0
    for path in tests.rglob("*"):
        if not path.is_file():
            continue
        size = path.stat().st_size
        if path.suffix.lower() in TEST_CODE_SUFFIXES:
            code += size
        else:
            data += size
    return code, data


def classify(facts: TaskFacts, haystack: str) -> list[str]:
    """Assign axes from the measured signals. Order is stable for reporting."""
    axes: list[str] = []
    expert = facts.expert_min or 0.0
    timeout = facts.agent_timeout_sec or 0.0

    if facts.requirements >= SPEC_DENSE_REQUIREMENTS or facts.words >= SPEC_DENSE_WORDS:
        axes.append("spec-dense")
    if facts.words <= UNDERSPECIFIED_WORDS and facts.requirements == 0:
        axes.append("underspecified")
    # The expert estimate measures the workload; the agent timeout is only a
    # budget, so a generous timeout on a five-minute task is not a long horizon.
    long_horizon = expert >= LONG_HORIZON_EXPERT_MIN or (
        facts.expert_min is None and timeout >= LONG_HORIZON_TIMEOUT_SEC
    )
    if long_horizon:
        axes.append("long-horizon")
    if 0 < expert <= QUICK_EXPERT_MIN and 0 < timeout <= QUICK_TIMEOUT_SEC:
        axes.append("quick")

    diagnose = facts.category == "debugging" or _count_hits(haystack, FAILURE_WORDS) >= FAILURE_HITS
    if diagnose:
        axes.append("diagnose-first")

    change = (
        _count_hits(haystack, CHANGE_WORDS) >= CHANGE_HITS
        or any(marker in facts.task_id for marker in CHANGE_ID_MARKERS)
    )
    if change:
        axes.append("modify-existing")

    if facts.test_code_bytes >= VERIFICATION_TEST_CODE_BYTES or facts.requires_own_tests:
        axes.append("verification-heavy")

    environment = facts.category in ENVIRONMENT_CATEGORIES or facts.task_id.startswith(
        ENVIRONMENT_ID_PREFIXES
    )
    if environment:
        axes.append("environment-engineering")

    if not (diagnose or change or environment) and facts.requirements <= 3:
        axes.append("greenfield-algorithmic")
    return axes


def describe_task(task_dir: Path) -> TaskFacts:
    """Read one task's manifest and prompt, then classify it."""
    config = tomllib.loads((task_dir / "task.toml").read_text())
    task = config.get("task") or {}
    metadata = config.get("metadata") or {}
    environment = config.get("environment") or {}

    instruction_path = task_dir / "instruction.md"
    instruction = (
        instruction_path.read_text(errors="replace") if instruction_path.is_file() else ""
    )
    code_bytes, data_bytes = _test_surface(task_dir)
    expert = metadata.get("expert_time_estimate_min")

    facts = TaskFacts(
        task_id=task_dir.name,
        category=metadata.get("category"),
        difficulty=metadata.get("difficulty"),
        expert_min=float(expert) if isinstance(expert, (int, float)) else None,
        agent_timeout_sec=(config.get("agent") or {}).get("timeout_sec"),
        verifier_timeout_sec=(config.get("verifier") or {}).get("timeout_sec"),
        words=len(instruction.split()),
        requirements=len(REQUIREMENT_LINE.findall(instruction)),
        test_code_bytes=code_bytes,
        test_data_bytes=data_bytes,
        requires_own_tests=bool(WRITE_TESTS.search(instruction)),
        docker_image=environment.get("docker_image"),
        tags=list(metadata.get("tags") or task.get("keywords") or []),
        description=(task.get("description") or "").strip(),
    )
    haystack = f"{facts.task_id} {facts.description} {instruction}".lower()
    facts.axes = classify(facts, haystack)
    return facts


def build_catalogue(tasks: list[Path]) -> list[TaskFacts]:
    return [describe_task(task) for task in tasks]


# ---------------------------------------------------------------- suites


def suite_members(catalogue: list[TaskFacts], name: str) -> list[str]:
    """Resolve a named suite to task ids, deterministically ordered.

    Axis names are themselves suite names. `balanced` is the exception: it takes
    the cheapest task from each benchmark category, which is the right default
    for a pipeline shakedown that must not be dominated by one domain.
    """
    if name == "balanced":
        return _balanced(catalogue)
    if name == "all":
        return sorted(facts.task_id for facts in catalogue)
    if name in AXIS_DESCRIPTIONS:
        return sorted(facts.task_id for facts in catalogue if name in facts.axes)
    raise ValueError(
        f"unknown suite: {name}. Available: all, balanced, {', '.join(sorted(AXIS_DESCRIPTIONS))}"
    )


def _cost_key(facts: TaskFacts) -> tuple:
    return (facts.expert_min or 1e9, facts.agent_timeout_sec or 1e9, facts.task_id)


def _balanced(catalogue: list[TaskFacts]) -> list[str]:
    by_category: dict[str, list[TaskFacts]] = {}
    for facts in catalogue:
        by_category.setdefault(facts.category or "uncategorised", []).append(facts)
    picks = [min(group, key=_cost_key).task_id for group in by_category.values()]
    return sorted(picks)


def suite_names() -> list[str]:
    return ["all", "balanced", *sorted(AXIS_DESCRIPTIONS)]


# ---------------------------------------------------------------- rendering


def _cell(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def render_markdown(catalogue: list[TaskFacts], source_root: Path) -> str:
    """Render the full catalogue: axis legend, per-axis and per-category rollups, task table."""
    lines = [
        "# Benchmark Task Catalogue",
        "",
        "Generated by `harbor-methodology-bench catalogue`. Do not edit by hand;",
        "re-run the command after changing the task suite.",
        "",
        f"- Source: `{source_root}`",
        f"- Tasks: **{len(catalogue)}**",
        "",
        "## Axes",
        "",
        "The benchmark's own `category` says what a task is *about*. An axis says what",
        "kind of work the agent has to do, which is what decides whether a methodology",
        "skill can help. Axes are not exclusive; a task usually carries several.",
        "",
        "| Axis | Tasks | Meaning |",
        "|---|---:|---|",
    ]
    for axis, description in sorted(AXIS_DESCRIPTIONS.items()):
        count = sum(1 for facts in catalogue if axis in facts.axes)
        lines.append(f"| `{axis}` | {count} | {description} |")

    lines += ["", "## Benchmark categories", "", "| Category | Tasks | easy | medium | hard |", "|---|---:|---:|---:|---:|"]
    categories: dict[str, list[TaskFacts]] = {}
    for facts in catalogue:
        categories.setdefault(facts.category or "uncategorised", []).append(facts)
    for category, group in sorted(categories.items(), key=lambda item: (-len(item[1]), item[0])):
        counts = {level: sum(1 for f in group if f.difficulty == level) for level in ("easy", "medium", "hard")}
        lines.append(
            f"| `{category}` | {len(group)} | {counts['easy']} | {counts['medium']} | {counts['hard']} |"
        )

    lines += [
        "",
        "## Tasks",
        "",
        "`req` is the number of enumerated requirement lines in `instruction.md`;",
        "`words` its length; `expert` the benchmark's own expert-time estimate in minutes;",
        "`budget` the agent timeout in seconds; `test kB` the size of the verification",
        "code under `tests/` excluding fixture data.",
        "",
        "| Task | Category | Diff | expert | budget | words | req | test kB | Axes |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for facts in sorted(catalogue, key=lambda f: (f.category or "", f.task_id)):
        axes = ", ".join(f"`{axis}`" for axis in facts.axes) or "—"
        lines.append(
            f"| `{facts.task_id}` | {_cell(facts.category)} | {_cell(facts.difficulty)} | "
            f"{_cell(facts.expert_min)} | {_cell(facts.agent_timeout_sec)} | {facts.words} | "
            f"{facts.requirements} | {facts.test_code_bytes // 1024} | {axes} |"
        )

    lines += ["", "## Suites", "", "| Suite | Tasks | Members |", "|---|---:|---|"]
    for name in suite_names():
        if name == "all":
            continue
        members = suite_members(catalogue, name)
        joined = ", ".join(f"`{member}`" for member in members) or "—"
        lines.append(f"| `{name}` | {len(members)} | {joined} |")
    return "\n".join(lines) + "\n"


def render_json(catalogue: list[TaskFacts], source_root: Path) -> str:
    payload = {
        "source_root": str(source_root),
        "n_tasks": len(catalogue),
        "axis_descriptions": AXIS_DESCRIPTIONS,
        "suites": {
            name: suite_members(catalogue, name) for name in suite_names() if name != "all"
        },
        "tasks": [facts.as_dict() for facts in catalogue],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
