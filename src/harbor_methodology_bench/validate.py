from __future__ import annotations

from pathlib import Path

from .inject import deployment_paths
from .manifest import file_digest, tree_manifest

TOOLKIT_MARKERS = ("AGENTS.md", "CLAUDE.md", ".agents", ".claude")
HARNESS_FILES = frozenset({".methodology-bench-manifest.json"})


def validate_task(source: Path, generated: Path, toolkit_snapshot: Path | None) -> list[str]:
    """Validate task identity and toolkit isolation; return all violations."""
    errors: list[str] = []
    if not (generated / "task.toml").is_file():
        errors.append("missing task.toml")
        return errors
    source_files = tree_manifest(source)
    generated_files = {
        relative: digest
        for relative, digest in tree_manifest(generated).items()
        if relative not in HARNESS_FILES
    }
    if toolkit_snapshot is None:
        if generated_files != source_files:
            errors.append("baseline file manifest differs from source")
        if any((generated / marker).exists() and not (source / marker).exists() for marker in TOOLKIT_MARKERS):
            errors.append("baseline contains unexpected toolkit marker")
        return errors

    snapshot_files = tree_manifest(toolkit_snapshot)
    for relative, digest in source_files.items():
        if generated_files.get(relative) != digest:
            errors.append(f"source file changed or missing: {relative}")
    for relative, deployed_relative in deployment_paths(toolkit_snapshot, source).items():
        if generated_files.get(deployed_relative) != snapshot_files[relative]:
            errors.append(f"toolkit file changed or missing: {relative}")
    if not any((generated / marker).exists() for marker in TOOLKIT_MARKERS):
        errors.append("toolkit markers are absent")
    return errors
