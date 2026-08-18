from pathlib import Path

import pytest

from harbor_methodology_bench.catalogue import (
    build_catalogue,
    describe_task,
    render_json,
    render_markdown,
    suite_members,
    suite_names,
)
from harbor_methodology_bench.source import TaskSelection, read_task_ids, select_tasks

TASK_TOML = """schema_version = "1.1"

[task]
name = "example"
description = "{description}"

[metadata]
category = "{category}"
difficulty = "{difficulty}"
expert_time_estimate_min = {expert}

[agent]
timeout_sec = {timeout}

[environment]
docker_image = "example/base:1"
"""


def write_task(
    root: Path,
    task_id: str,
    *,
    category: str = "software-engineering",
    difficulty: str = "medium",
    expert: float = 60.0,
    timeout: float = 900.0,
    instruction: str = "Do the thing.",
    description: str = "A task.",
    test_code: str = "echo ok\n",
    test_data_bytes: int = 0,
) -> Path:
    task = root / task_id
    (task / "tests").mkdir(parents=True)
    (task / "task.toml").write_text(
        TASK_TOML.format(
            category=category,
            difficulty=difficulty,
            expert=expert,
            timeout=timeout,
            description=description,
        )
    )
    (task / "instruction.md").write_text(instruction)
    (task / "tests" / "test.sh").write_text(test_code)
    if test_data_bytes:
        (task / "tests" / "fixture.bin").write_bytes(b"\0" * test_data_bytes)
    return task


def test_spec_dense_follows_the_requirement_count(tmp_path: Path) -> None:
    instruction = "Build it.\n" + "\n".join(f"- requirement {n}" for n in range(9))
    facts = describe_task(write_task(tmp_path, "many-requirements", instruction=instruction))
    assert facts.requirements == 9
    assert "spec-dense" in facts.axes
    assert "underspecified" not in facts.axes


def test_underspecified_needs_a_short_prompt_and_no_requirements(tmp_path: Path) -> None:
    facts = describe_task(write_task(tmp_path, "terse", instruction="Crack the hash."))
    assert "underspecified" in facts.axes
    assert "spec-dense" not in facts.axes


def test_long_horizon_uses_the_expert_estimate_not_the_timeout(tmp_path: Path) -> None:
    """A generous agent budget on a short task is not a long horizon."""
    generous = describe_task(write_task(tmp_path, "quick-but-generous", expert=5.0, timeout=3600.0))
    assert "long-horizon" not in generous.axes

    lengthy = describe_task(write_task(tmp_path, "genuinely-long", expert=480.0, timeout=900.0))
    assert "long-horizon" in lengthy.axes


def test_quick_axis_marks_cheap_tasks(tmp_path: Path) -> None:
    facts = describe_task(write_task(tmp_path, "cheap", expert=20.0, timeout=900.0))
    assert "quick" in facts.axes


def test_debugging_category_implies_diagnose_first(tmp_path: Path) -> None:
    facts = describe_task(write_task(tmp_path, "some-task", category="debugging"))
    assert "diagnose-first" in facts.axes
    assert "greenfield-algorithmic" not in facts.axes


def test_failure_vocabulary_implies_diagnose_first(tmp_path: Path) -> None:
    facts = describe_task(
        write_task(
            tmp_path,
            "silent-name",
            instruction="The build is broken and the test suite fails. Repair it.",
        )
    )
    assert "diagnose-first" in facts.axes


def test_verification_heavy_when_the_prompt_demands_tests(tmp_path: Path) -> None:
    facts = describe_task(
        write_task(tmp_path, "own-tests", instruction="Formal testing is required for the module.")
    )
    assert facts.requires_own_tests
    assert "verification-heavy" in facts.axes


def test_fixture_data_does_not_count_as_verification_surface(tmp_path: Path) -> None:
    facts = describe_task(write_task(tmp_path, "big-fixture", test_data_bytes=200_000))
    assert facts.test_data_bytes >= 200_000
    assert facts.test_code_bytes < 10_000
    assert "verification-heavy" not in facts.axes


def test_environment_engineering_from_category_or_id(tmp_path: Path) -> None:
    by_category = describe_task(
        write_task(tmp_path, "plain-name", category="system-administration")
    )
    by_id = describe_task(write_task(tmp_path, "compile-something"))
    assert "environment-engineering" in by_category.axes
    assert "environment-engineering" in by_id.axes


def test_greenfield_excludes_modify_diagnose_and_environment(tmp_path: Path) -> None:
    facts = describe_task(write_task(tmp_path, "write-a-sampler", instruction="Implement a sampler."))
    assert "greenfield-algorithmic" in facts.axes


def test_suites_resolve_to_sorted_ids_and_reject_unknown_names(tmp_path: Path) -> None:
    write_task(tmp_path, "b-task", category="debugging")
    write_task(tmp_path, "a-task", category="debugging")
    write_task(tmp_path, "c-task", category="security", expert=5.0)
    catalogue = build_catalogue(sorted(tmp_path.iterdir()))

    assert suite_members(catalogue, "diagnose-first") == ["a-task", "b-task"]
    assert suite_members(catalogue, "all") == ["a-task", "b-task", "c-task"]
    with pytest.raises(ValueError, match="unknown suite"):
        suite_members(catalogue, "nonsense")
    assert "balanced" in suite_names()


def test_balanced_suite_takes_the_cheapest_task_per_category(tmp_path: Path) -> None:
    write_task(tmp_path, "cheap-se", category="software-engineering", expert=10.0)
    write_task(tmp_path, "dear-se", category="software-engineering", expert=900.0)
    write_task(tmp_path, "only-sec", category="security", expert=120.0)
    catalogue = build_catalogue(sorted(tmp_path.iterdir()))
    assert suite_members(catalogue, "balanced") == ["cheap-se", "only-sec"]


def test_selection_composes_suite_then_filters_then_limit(tmp_path: Path) -> None:
    write_task(tmp_path, "dbg-easy", category="debugging", difficulty="easy")
    write_task(tmp_path, "dbg-hard", category="debugging", difficulty="hard")
    write_task(tmp_path, "sec-easy", category="security", difficulty="easy")

    everything = select_tasks(tmp_path, TaskSelection())
    assert [t.name for t in everything] == ["dbg-easy", "dbg-hard", "sec-easy"]

    suite = select_tasks(tmp_path, TaskSelection(suites=("diagnose-first",)))
    assert [t.name for t in suite] == ["dbg-easy", "dbg-hard"]

    narrowed = select_tasks(
        tmp_path, TaskSelection(suites=("diagnose-first",), difficulties=("easy",))
    )
    assert [t.name for t in narrowed] == ["dbg-easy"]

    truncated = select_tasks(tmp_path, TaskSelection(limit=2))
    assert [t.name for t in truncated] == ["dbg-easy", "dbg-hard"]


def test_selection_rejects_unknown_ids_and_empty_results(tmp_path: Path) -> None:
    write_task(tmp_path, "only-task")
    with pytest.raises(ValueError, match="unknown task id"):
        select_tasks(tmp_path, TaskSelection(ids=("ghost",)))
    with pytest.raises(ValueError, match="matched no tasks"):
        select_tasks(tmp_path, TaskSelection(categories=("nothing-here",)))


def test_tasks_file_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    listing = tmp_path / "set.txt"
    listing.write_text("# a comment\n\nalpha\nbeta  # trailing\n")
    assert read_task_ids(listing) == ("alpha", "beta")


def test_renderers_cover_every_task_and_suite(tmp_path: Path) -> None:
    write_task(tmp_path, "alpha", category="debugging")
    write_task(tmp_path, "beta", category="security", expert=480.0)
    catalogue = build_catalogue(sorted(tmp_path.iterdir()))

    markdown = render_markdown(catalogue, tmp_path)
    assert "`alpha`" in markdown and "`beta`" in markdown
    assert "## Suites" in markdown and "`diagnose-first`" in markdown

    payload = render_json(catalogue, tmp_path)
    assert '"n_tasks": 2' in payload
    assert '"long-horizon"' in payload
