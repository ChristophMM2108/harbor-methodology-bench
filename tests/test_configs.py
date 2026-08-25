"""Guards on the shipped experiment configurations.

The CodeZen experiment is split across four configuration files so that the
Claude and Codex halves can be run separately and a cheap probe can gate an
expensive measurement. Splitting them duplicates the `toolkits:` block, and a
divergent edit to one copy would silently produce two experiments whose results
are not comparable — the failure would surface only as an unexplained difference
in a report, long after the tokens were spent.

These tests make that divergence a test failure instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harbor_methodology_bench.config import load_config

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"

# Every configuration that describes the CodeZen experiment. The probe and the
# two agent halves must agree with the full matrix on what a condition *is*.
CODEZEN_CONFIGS = (
    "experiments.codezen.yaml",
    "experiments.codezen-probe.yaml",
    "experiments.codezen-claude.yaml",
    "experiments.codezen-codex.yaml",
)

REFERENCE = "experiments.codezen.yaml"


def load(name: str):
    path = CONFIG_DIR / name
    if not path.is_file():
        pytest.skip(f"{name} is not present in this checkout")
    return load_config(path)


@pytest.mark.parametrize("name", [n for n in CODEZEN_CONFIGS if n != REFERENCE])
def test_codezen_configs_declare_identical_conditions(name: str) -> None:
    """A condition must mean the same thing in every CodeZen configuration.

    Only the matrix and the repetition count are allowed to differ. If this
    fails, one file was edited and the others were not, and any comparison
    across the two runs is invalid.
    """
    reference = load(REFERENCE)
    other = load(name)

    assert other.source_root == reference.source_root
    assert other.generated_root == reference.generated_root
    assert other.specs() == reference.specs(), (
        f"{name} declares different conditions than {REFERENCE}; "
        "the payload specs must match exactly for the runs to be comparable"
    )


def test_codezen_agent_halves_are_disjoint_cells_of_the_full_matrix() -> None:
    """Each half must draw its cells from the full matrix, and never overlap.

    The halves are allowed to run *fewer* cells than the full matrix declares —
    the measurement currently skips `codezen-full` to hold the trial count down,
    while the probe still exercises it. What is not allowed is a half inventing
    a cell the full matrix does not declare, or the two halves sharing a cell:
    the first makes the two paths disagree about what the experiment is, and the
    second means one run would overwrite the other's job directories.
    """
    full = load(REFERENCE)
    claude = load("experiments.codezen-claude.yaml")
    codex = load("experiments.codezen-codex.yaml")

    def ids(config) -> set[str]:
        return {cell["id"] for cell in config.matrix}

    assert ids(claude) <= ids(full)
    assert ids(codex) <= ids(full)
    assert not (ids(claude) & ids(codex)), "a cell appears in both agent halves"


def test_codezen_agent_halves_exercise_the_same_conditions() -> None:
    """B1 and B2 must cover identical conditions, or comparing them is invalid.

    The point of running the Codex half is to ask whether a methodology effect
    belongs to the method or to one CLI. That question needs both halves to have
    measured the same set of conditions; a condition present in one half only
    would silently drop out of the cross-CLI comparison.
    """
    claude = load("experiments.codezen-claude.yaml")
    codex = load("experiments.codezen-codex.yaml")

    def toolkits(config) -> set[str]:
        return {cell["toolkit"] for cell in config.matrix}

    assert toolkits(claude) == toolkits(codex)
    assert claude.repetitions == codex.repetitions, (
        "the two halves must use the same attempt count to be comparable"
    )


def test_codezen_probe_is_a_subset_of_the_full_matrix() -> None:
    """The probe may run fewer cells, but never a cell the experiment lacks."""
    full = load(REFERENCE)
    probe = load("experiments.codezen-probe.yaml")

    full_ids = {cell["id"] for cell in full.matrix}
    probe_ids = {cell["id"] for cell in probe.matrix}
    assert probe_ids <= full_ids
    assert probe.repetitions == 1, "a probe runs one attempt; it is not a measurement"


def test_programming_probe_tasks_are_a_subset_of_the_programming_set() -> None:
    """The probe's findings must be about tasks the measurement also runs.

    Otherwise a probe result says nothing about the experiment it gates.
    """

    def read(name: str) -> list[str]:
        lines = (CONFIG_DIR / name).read_text().splitlines()
        return [line.strip() for line in lines if line.strip() and not line.startswith("#")]

    probe = read("tasks-programming-probe.txt")
    full = read("tasks-programming.txt")

    assert probe, "the probe task file is empty"
    assert set(probe) <= set(full)
    assert len(set(full)) == len(full), "the programming task set lists a task twice"
