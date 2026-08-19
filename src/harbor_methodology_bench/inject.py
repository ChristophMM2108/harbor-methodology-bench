from __future__ import annotations

import shutil
from pathlib import Path


def copy_task(source: Path, destination: Path) -> None:
    if destination.exists():
        raise ValueError(f"refusing to overwrite generated task: {destination}")
    shutil.copytree(source, destination, symlinks=True)
