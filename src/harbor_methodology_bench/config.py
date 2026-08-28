from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .environment import (
    BASELINE_SPEC,
    DEFAULT_SNAPSHOT_EXCLUDES,
    SKILL_SOURCE_DIRS,
    PayloadSpec,
)


@dataclass(frozen=True)
class Toolkit:
    """One non-baseline experimental condition."""

    id: str
    spec: PayloadSpec

    @property
    def snapshot(self) -> Path:
        assert self.spec.snapshot is not None
        return self.spec.snapshot


@dataclass(frozen=True)
class ExperimentConfig:
    root: Path
    source_root: Path
    generated_root: Path
    toolkits: dict[str, Toolkit]
    models: dict[str, str]
    matrix: list[dict[str, str]]
    repetitions: int

    def specs(self) -> dict[str, PayloadSpec]:
        """Every variant's payload spec, baseline first."""
        specs: dict[str, PayloadSpec] = {"baseline": BASELINE_SPEC}
        specs.update({toolkit.id: toolkit.spec for toolkit in self.toolkits.values()})
        return specs


def _toolkit(item: dict, root: Path, excludes: tuple[str, ...], skill_sources: tuple[str, ...]) -> Toolkit:
    spec = PayloadSpec(
        snapshot=(root / item["snapshot"]).resolve(),
        excludes=tuple(item.get("exclude", excludes)),
        includes=tuple(item.get("include", ())),
        expect_instructions=bool(item.get("expect_instructions", True)),
        expect_skills=bool(item.get("expect_skills", True)),
        skill_sources=tuple(item.get("skill_sources", skill_sources)),
    )
    return Toolkit(item["id"], spec)


def load_config(path: Path) -> ExperimentConfig:
    """Load the small, portable experiment configuration.

    Relative paths are resolved from the repository root (the config file's
    parent directory), not from the caller's current working directory.
    """
    data = yaml.safe_load(path.read_text()) or {}
    root = path.parent.parent.resolve()
    excludes = tuple(data.get("snapshot_excludes", DEFAULT_SNAPSHOT_EXCLUDES))
    skill_sources = tuple(data.get("skill_sources", SKILL_SOURCE_DIRS))
    toolkits = {
        item["id"]: _toolkit(item, root, excludes, skill_sources)
        for item in data.get("toolkits", [])
    }
    matrix = data.get("matrix", [])
    models = data.get("models", {})
    if not matrix or not toolkits or not models:
        raise ValueError("configuration requires non-empty toolkits, models, and matrix")
    if "baseline" in toolkits:
        raise ValueError("`baseline` is reserved; it is generated for every task")
    repetitions = data.get("repetitions", 1)
    if not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    return ExperimentConfig(
        root=root,
        source_root=(root / data["source_root"]).resolve(),
        generated_root=(root / data.get("generated_root", "generated")).resolve(),
        toolkits=toolkits,
        models=models,
        matrix=matrix,
        repetitions=repetitions,
    )
