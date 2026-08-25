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


def test_codezen_agent_halves_partition_the_full_matrix() -> None:
    """The Claude and Codex halves together must be exactly the full matrix.

    Not a subset and not a superset: a cell present in the full matrix but in
    neither half would never be run, and a cell in a half but not in the full
    matrix would make the two paths disagree about the experiment's size.
    """
    full = load(REFERENCE)
    claude = load("experiments.codezen-claude.yaml")
    codex = load("experiments.codezen-codex.yaml")

    def ids(config) -> set[str]:
        return {cell["id"] for cell in config.matrix}

    halves = ids(claude) | ids(codex)
    assert halves == ids(full)
    assert not (ids(claude) & ids(codex)), "a cell appears in both agent halves"


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
