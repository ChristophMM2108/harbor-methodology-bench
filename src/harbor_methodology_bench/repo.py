"""Locate the repository root, so no command depends on the caller's directory.

Every path in a configuration file and every generated artefact is resolved
against this root. A checkout can therefore live anywhere, and `hmb` can be
installed globally (`uv tool install`) and still be run from a subdirectory.
"""

from __future__ import annotations

import os
from pathlib import Path

# A directory is this repository's root when it carries all of these.
ROOT_MARKERS = ("pyproject.toml", "config", "src/harbor_methodology_bench")
ENV_VAR = "HMB_ROOT"


class RootNotFound(RuntimeError):
    """The command was run outside a checkout of this repository."""


def _is_root(path: Path) -> bool:
    return all((path / marker).exists() for marker in ROOT_MARKERS)


def find_root(start: Path | None = None) -> Path:
    """The nearest enclosing repository root.

    `HMB_ROOT` wins when set, which is what lets a scheduled job or a CI step run
    `hmb` from anywhere without a `cd`.
    """
    override = os.environ.get(ENV_VAR)
    if override:
        candidate = Path(override).expanduser().resolve()
        if not _is_root(candidate):
            raise RootNotFound(f"{ENV_VAR}={candidate} is not a harbor-methodology-bench checkout")
        return candidate

    here = (start or Path.cwd()).resolve()
    for path in (here, *here.parents):
        if _is_root(path):
            return path
    raise RootNotFound(
        "not inside a harbor-methodology-bench checkout: run the command from the repository, "
        f"or set {ENV_VAR} to its path"
    )


def resolve(path: Path, root: Path | None = None) -> Path:
    """Resolve a possibly-relative path against the repository root."""
    if path.is_absolute():
        return path
    return ((root or find_root()) / path).resolve()
