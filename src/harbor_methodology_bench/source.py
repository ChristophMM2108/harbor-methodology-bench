from __future__ import annotations

from pathlib import Path


def discover_tasks(source_root: Path) -> list[Path]:
    """Return Harbor tasks, requiring the task manifest in every directory."""
    if not source_root.is_dir():
        raise ValueError(f"source root does not exist: {source_root}")
    tasks = sorted(path for path in source_root.iterdir() if (path / "task.toml").is_file())
    if not tasks:
        raise ValueError(f"no Harbor tasks found under {source_root}")
    return tasks
