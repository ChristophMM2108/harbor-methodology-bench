from __future__ import annotations

import tempfile
from pathlib import Path

from .environment import (
    BASELINE_SPEC,
    CONFIG_MARKERS,
    DOCKERFILE_NAME,
    PAYLOAD_SUBDIR,
    STAGE_DIRNAME,
    EnvironmentPlan,
    PayloadSpec,
    build_environment,
)
from .manifest import file_digest, tree_manifest

MANIFEST_FILE = ".methodology-bench-manifest.json"
PREFLIGHT_FILE = ".methodology-bench-preflight.json"
HARNESS_FILES = frozenset({MANIFEST_FILE, PREFLIGHT_FILE})

# Paths the generator owns and therefore may differ from the source task.
GENERATED_PATHS = (
    "task.toml",
    f"environment/{DOCKERFILE_NAME}",
)
GENERATED_PREFIXES = (f"environment/{STAGE_DIRNAME}/",)


def _is_generated(relative: str) -> bool:
    return (
        relative in HARNESS_FILES
        or relative in GENERATED_PATHS
        or relative.startswith(GENERATED_PREFIXES)
    )


def expected_environment(
    source: Path,
    variant: str,
    spec: PayloadSpec = BASELINE_SPEC,
) -> tuple[dict[str, str], str, EnvironmentPlan]:
    """Re-derive the generated files for one variant from the frozen inputs.

    Returns the digests of every generator-owned file, the patched `task.toml`
    text, and the plan. Re-deriving through the same code path that produced
    the variant is what makes the validator a real reproducibility check rather
    than a restatement of whatever is on disk.
    """
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory)
        plan = build_environment(source, staging, variant, spec)
        digests = {
            f"environment/{relative}": digest
            for relative, digest in tree_manifest(staging / "environment").items()
        }
        return digests, (staging / "task.toml").read_text(), plan


def validate_task(
    source: Path,
    generated: Path,
    variant: str,
    spec: PayloadSpec = BASELINE_SPEC,
) -> list[str]:
    """Validate task identity, generator reproducibility, and payload intent."""
    errors: list[str] = []
    if not (generated / "task.toml").is_file():
        return ["missing task.toml"]

    expected_files, expected_task_toml, plan = expected_environment(source, variant, spec)
    generated_files = tree_manifest(generated)
    source_files = tree_manifest(source)

    for relative, digest in source_files.items():
        if _is_generated(relative):
            continue
        if generated_files.get(relative) != digest:
            errors.append(f"benchmark file changed or missing: {relative}")

    for relative, digest in expected_files.items():
        if generated_files.get(relative) != digest:
            errors.append(f"generated environment file is not reproducible: {relative}")

    unexpected = sorted(
        relative
        for relative in generated_files
        if relative not in source_files
        and relative not in expected_files
        and not _is_generated(relative)
    )
    errors.extend(f"unexpected file in generated task: {relative}" for relative in unexpected)

    if (generated / "task.toml").read_text() != expected_task_toml:
        errors.append("task.toml patch is not reproducible")

    payload_prefix = f"environment/{STAGE_DIRNAME}/{PAYLOAD_SUBDIR}/"
    payload_present = any(relative.startswith(payload_prefix) for relative in generated_files)

    if spec.snapshot is None:
        if payload_present:
            errors.append("variant declares no snapshot but stages a payload")
        for marker in CONFIG_MARKERS:
            if (generated / marker).exists() and not (source / marker).exists():
                errors.append(f"variant carries an unexpected instruction file: {marker}")
        return errors

    if not payload_present:
        errors.append("variant declares a snapshot but stages no payload")

    if plan.expect_instructions and not plan.config_markers:
        errors.append(
            "condition expects project instructions but the payload provides neither "
            "CLAUDE.md nor AGENTS.md at its root"
        )
    if not plan.expect_instructions and plan.config_markers:
        errors.append(
            "condition expects no project instructions but the payload still carries "
            f"{', '.join(plan.config_markers)}; add them to `exclude`"
        )

    if plan.expect_skills:
        has_sources = any((spec.snapshot / name).is_dir() for name in spec.skill_sources)
        if has_sources and not plan.skills_registered:
            errors.append(
                "condition expects skills but none were registered; expected `SKILL.md` "
                f"under one of {', '.join(spec.skill_sources)}"
            )
    elif plan.skills_registered:
        errors.append(
            "condition expects no skills but the payload registered "
            f"{len(plan.skills_registered)}; exclude the skill source directories"
        )
    return errors


def source_dockerfile_digest(source: Path) -> str | None:
    """Digest of the untouched benchmark Dockerfile, for the variant manifest."""
    path = source / "environment" / DOCKERFILE_NAME
    return file_digest(path) if path.is_file() else None
