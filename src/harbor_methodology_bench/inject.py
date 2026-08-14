from __future__ import annotations

import shutil
from pathlib import Path

COLLISION_ARCHIVE = Path(".methodology-bench/toolkit-collisions")

def copy_task(source: Path, destination: Path) -> None:
    if destination.exists():
        raise ValueError(f"refusing to overwrite generated task: {destination}")
    shutil.copytree(source, destination, symlinks=True)


def deployment_paths(snapshot: Path, source_task: Path) -> dict[str, str]:
    """Map snapshot files to their location in a generated task.

    Native paths are retained unless the source task already owns the
    top-level path. Colliding paths are archived rather than overwritten;
    this documented transformation is included in the generated manifest.
    """
    paths: dict[str, str] = {}
    for item in snapshot.rglob("*"):
        if not item.is_file() or item.is_symlink():
            continue
        relative = item.relative_to(snapshot)
        if (source_task / relative.parts[0]).exists():
            target = COLLISION_ARCHIVE / relative
        else:
            target = relative
        paths[relative.as_posix()] = target.as_posix()
    return paths


def inject_snapshot(snapshot: Path, task_root: Path, source_task: Path) -> dict[str, str]:
    """Copy a complete snapshot without changing any benchmark-owned path."""
    if not snapshot.is_dir():
        raise ValueError(f"toolkit snapshot does not exist: {snapshot}")
    for entry in snapshot.iterdir():
        target = task_root / entry.name
        if (source_task / entry.name).exists():
            target = task_root / COLLISION_ARCHIVE / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, symlinks=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry, target, follow_symlinks=False)
    return deployment_paths(snapshot, source_task)
