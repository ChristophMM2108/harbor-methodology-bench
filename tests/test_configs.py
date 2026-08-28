"""Guards on the shipped configuration files.

These are the files a newcomer copies, so a broken one wastes somebody's first
hour. Every check here is about internal consistency, not about a particular
experiment: the configurations must load, must agree with the pinned sources, and
must not declare a cell nothing can run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harbor_methodology_bench.config import load_config
from harbor_methodology_bench.sources import load_sources

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
SHIPPED_CONFIGS = sorted(CONFIG_DIR.glob("experiments*.yaml"))


def test_at_least_one_configuration_ships() -> None:
    assert SHIPPED_CONFIGS, "config/experiments.yaml is the entry point; it must exist"


@pytest.mark.parametrize("path", SHIPPED_CONFIGS, ids=lambda p: p.name)
def test_configuration_loads(path: Path) -> None:
    load_config(path)


@pytest.mark.parametrize("path", SHIPPED_CONFIGS, ids=lambda p: p.name)
def test_matrix_references_declared_conditions_and_agents(path: Path) -> None:
    """A cell naming an undeclared condition or agent fails only at run time.

    By then the runner has already built images, so catching it here is the
    difference between a typo and a wasted hour.
    """
    settings = load_config(path)
    declared = set(settings.toolkits) | {"baseline"}
    for cell in settings.matrix:
        assert cell["toolkit"] in declared, f"{path.name}: cell {cell['id']} names unknown condition"
        assert cell["agent"] in settings.models, f"{path.name}: cell {cell['id']} names unknown agent"

    ids = [cell["id"] for cell in settings.matrix]
    assert len(ids) == len(set(ids)), f"{path.name}: duplicate cell id — one run would overwrite the other"


@pytest.mark.parametrize("path", SHIPPED_CONFIGS, ids=lambda p: p.name)
def test_conditions_resolve_to_a_declared_source(path: Path) -> None:
    """Every snapshot a condition points at must be a source `hmb setup` provides.

    A path that no source produces cannot be materialised by anyone but its
    author, which is exactly the failure mode this repository exists to avoid.
    """
    settings = load_config(path)
    sources = load_sources(CONFIG_DIR / "sources.yaml")
    source_dirs = {source.dest.resolve() for source in sources}
    for toolkit in settings.toolkits.values():
        assert toolkit.snapshot.parent.resolve() in source_dirs, (
            f"{path.name}: condition {toolkit.id} points at {toolkit.snapshot}, "
            "which config/sources.yaml does not declare"
        )


def test_default_configuration_runs_without_external_access() -> None:
    """`config/experiments.yaml` must work straight after cloning.

    Its conditions may only use vendored toolkits: a default that needs access to
    a private repository is a default nobody else can run.
    """
    settings = load_config(CONFIG_DIR / "experiments.yaml")
    vendored = {source.dest.resolve() for source in load_sources(CONFIG_DIR / "sources.yaml") if source.vendored}
    for toolkit in settings.toolkits.values():
        assert toolkit.snapshot.parent.resolve() in vendored, (
            f"the default configuration uses {toolkit.id}, which is not vendored"
        )


def test_baseline_is_never_declared() -> None:
    """`baseline` is generated for every task; declaring it would shadow the control."""
    for path in SHIPPED_CONFIGS:
        settings = load_config(path)
        assert "baseline" not in settings.toolkits
