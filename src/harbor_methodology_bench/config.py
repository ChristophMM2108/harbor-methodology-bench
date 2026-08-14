from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Toolkit:
    id: str
    snapshot: Path


@dataclass(frozen=True)
class ExperimentConfig:
    root: Path
    source_root: Path
    generated_root: Path
    toolkits: dict[str, Toolkit]
    models: dict[str, str]
    matrix: list[dict[str, str]]
    repetitions: int


def load_config(path: Path) -> ExperimentConfig:
    """Load the small, portable experiment configuration.

    Relative paths are resolved from the repository root (the config file's
    parent directory), not from the caller's current working directory.
    """
    data = yaml.safe_load(path.read_text()) or {}
    root = path.parent.parent.resolve()
    toolkits = {
        item["id"]: Toolkit(item["id"], (root / item["snapshot"]).resolve())
        for item in data.get("toolkits", [])
    }
    matrix = data.get("matrix", [])
    models = data.get("models", {})
    if not matrix or not toolkits or not models:
        raise ValueError("configuration requires non-empty toolkits, models, and matrix")
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
