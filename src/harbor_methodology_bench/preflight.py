from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .environment import (
    APPENDED_DOCKERFILE,
    BASELINE_SPEC,
    CONFIG_MARKERS,
    CONTAINER_REPORT,
    CONTAINER_STAGE,
    PAYLOAD_SUBDIR,
    STAGE_DIRNAME,
    PayloadSpec,
    read_task_environment,
)
from .manifest import tree_manifest
from .validate import expected_environment

DEFAULT_MAX_PROBE_FILES = 20000
IMAGE_PREFIX = "harbor-methodology-bench-preflight"

# Where the probe replays the agent adapters' skill install. Both the Claude
# Code and Codex adapters register skills with the same
# `cp -r <skills_dir>/* <destination>/` idiom, so one replay covers both.
INSTALL_PROBE_DIR = "/tmp/harbor-methodology-bench-installed-skills"

_SECTION = re.compile(r"^::([A-Z]+)::$")


class PreflightError(RuntimeError):
    """Raised when the container cannot be built or probed at all."""


@dataclass
class Probe:
    """What a container actually contains, as observed from inside it."""

    workdir: str = ""
    hashes: dict[str, str] = field(default_factory=dict)
    top: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    installed_skills: list[str] = field(default_factory=list)
    report: dict[str, list[str]] = field(default_factory=dict)
    file_count: int = 0
    truncated: bool = False


def probe_script(skills_dir: str, max_files: int) -> str:
    """Shell that reports the container's workdir contents and skill registry."""
    skills = shlex.quote(skills_dir)
    report = shlex.quote(CONTAINER_REPORT)
    return f"""set -eu
printf 'WORKDIR\\t%s\\n' "$(pwd)"
printf '::REPORT::\\n'
if [ -f {report} ]; then cat {report}; fi
printf '::SKILLS::\\n'
if [ -d {skills} ]; then find {skills} -maxdepth 2 -name SKILL.md 2>/dev/null | sort; fi
printf '::TOP::\\n'
ls -1a . 2>/dev/null | sort
printf '::HASHES::\\n'
find . -type f -exec sha256sum {{}} + 2>/dev/null | sort | head -n {max_files}
printf '::COUNT::\\n'
find . -type f 2>/dev/null | wc -l
printf '::INSTALL::\\n'
mkdir -p {INSTALL_PROBE_DIR}
(cp -r {skills}/* {INSTALL_PROBE_DIR}/ 2>/dev/null || true)
find {INSTALL_PROBE_DIR} -maxdepth 2 -name SKILL.md 2>/dev/null | sort
"""


def parse_probe(stdout: str, skills_dir: str, max_files: int) -> Probe:
    probe = Probe()
    section = "HEAD"
    for line in stdout.splitlines():
        match = _SECTION.match(line.strip())
        if match:
            section = match.group(1)
            continue
        if section == "HEAD":
            if line.startswith("WORKDIR\t"):
                probe.workdir = line.split("\t", 1)[1].strip()
            continue
        if section == "REPORT":
            if "\t" in line:
                key, value = line.split("\t", 1)
                probe.report.setdefault(key, []).append(value.strip())
            continue
        if section == "SKILLS":
            candidate = line.strip()
            if candidate.endswith("/SKILL.md") and candidate.startswith(skills_dir):
                probe.skills.append(Path(candidate).parent.name)
            continue
        if section == "TOP":
            entry = line.strip()
            if entry and entry not in (".", ".."):
                probe.top.append(entry)
            continue
        if section == "HASHES":
            parts = line.rstrip("\n").split(None, 1)
            if len(parts) == 2:
                probe.hashes[parts[1].strip().removeprefix("./")] = parts[0]
            continue
        if section == "COUNT":
            stripped = line.strip()
            if stripped.isdigit():
                probe.file_count = int(stripped)
            continue
        if section == "INSTALL":
            candidate = line.strip()
            if candidate.endswith("/SKILL.md") and candidate.startswith(INSTALL_PROBE_DIR):
                probe.installed_skills.append(Path(candidate).parent.name)
    probe.truncated = probe.file_count > max_files
    probe.skills.sort()
    probe.installed_skills.sort()
    _drop_stage_paths(probe)
    return probe


def _drop_stage_paths(probe: Probe) -> None:
    """Ignore the harness stage when the workdir happens to be the filesystem root."""
    if probe.workdir.rstrip("/") != "":
        return
    prefix = CONTAINER_STAGE.lstrip("/") + "/"
    probe.hashes = {
        path: digest for path, digest in probe.hashes.items() if not path.startswith(prefix)
    }
    probe.top = [entry for entry in probe.top if entry != CONTAINER_STAGE.lstrip("/")]


def _docker(arguments: list[str], timeout_sec: int) -> str:
    try:
        completed = subprocess.run(
            ["docker", *arguments],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except FileNotFoundError as error:
        raise PreflightError("docker is not installed or not on PATH") from error
    except subprocess.TimeoutExpired as error:
        raise PreflightError(f"docker {arguments[0]} timed out after {timeout_sec}s") from error
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-12:]
        raise PreflightError(f"docker {arguments[0]} failed:\n" + "\n".join(tail))
    return completed.stdout


def build_image(context: Path, tag: str, timeout_sec: int) -> None:
    _docker(["build", "--tag", tag, str(context)], timeout_sec)


def probe_image(tag: str, workdir: str | None, skills_dir: str, max_files: int, timeout_sec: int) -> Probe:
    arguments = ["run", "--rm", "--entrypoint", "sh"]
    if workdir and workdir != ".":
        arguments.extend(["--workdir", workdir])
    arguments.extend([tag, "-c", probe_script(skills_dir, max_files)])
    return parse_probe(_docker(arguments, timeout_sec), skills_dir, max_files)


def _tag(variant: str, task_id: str) -> str:
    safe = re.sub(r"[^a-z0-9_.-]", "-", f"{variant}-{task_id}".lower())
    return f"{IMAGE_PREFIX}:{safe}"


@dataclass
class VariantCheck:
    """Per-variant preflight outcome, persisted next to the generated task."""

    variant: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    workdir: str = ""
    deployed: list[str] = field(default_factory=list)
    collisions: list[str] = field(default_factory=list)
    skills_present: list[str] = field(default_factory=list)
    skills_installable: list[str] = field(default_factory=list)
    config_markers_present: list[str] = field(default_factory=list)
    payload_file_count: int = 0

    def as_dict(self) -> dict:
        return {
            "variant": self.variant,
            "passed": not self.errors,
            "errors": self.errors,
            "warnings": self.warnings,
            "workdir": self.workdir,
            "deployed_top_level": self.deployed,
            "collisions": self.collisions,
            "skills_present": self.skills_present,
            "skills_installable": self.skills_installable,
            "config_markers_present": self.config_markers_present,
            "payload_file_count": self.payload_file_count,
        }


def _payload_expectations(generated_task: Path) -> dict[str, str]:
    payload = generated_task / "environment" / STAGE_DIRNAME / PAYLOAD_SUBDIR
    return tree_manifest(payload) if payload.is_dir() else {}


def check_baseline(
    source: Path,
    generated_task: Path,
    max_files: int,
    build_timeout_sec: int,
    run_timeout_sec: int,
) -> tuple[VariantCheck, Probe]:
    """Prove the payload layer is inert for the baseline condition.

    The baseline container is compared against the untouched task base image.
    Any difference means the generated Dockerfile changed the benchmark
    environment, which would invalidate every comparison drawn from it.
    """
    check = VariantCheck(variant="baseline")
    environment = read_task_environment(source / "task.toml")
    _, _, plan = expected_environment(source, "baseline", BASELINE_SPEC)

    if plan.strategy == APPENDED_DOCKERFILE:
        base_tag = _tag("base", source.name)
        build_image(source / "environment", base_tag, build_timeout_sec)
    else:
        assert plan.base_image is not None
        base_tag = plan.base_image

    base = probe_image(base_tag, environment.workdir, plan.skills_dir, max_files, run_timeout_sec)
    built_tag = _tag("baseline", source.name)
    build_image(generated_task / "environment", built_tag, build_timeout_sec)
    built = probe_image(built_tag, environment.workdir, plan.skills_dir, max_files, run_timeout_sec)

    check.workdir = built.workdir
    if built.truncated or base.truncated:
        check.warnings.append(
            f"workdir holds {built.file_count} files; tree comparison capped at {max_files}"
        )
    if built.workdir != base.workdir:
        check.errors.append(f"workdir moved: base {base.workdir!r} vs built {built.workdir!r}")
    changed = sorted(
        path for path, digest in base.hashes.items() if built.hashes.get(path) != digest
    )
    added = sorted(set(built.hashes) - set(base.hashes))
    if changed:
        check.errors.append(f"baseline layer modified benchmark files: {changed[:10]}")
    if added:
        check.errors.append(f"baseline layer added files to the workdir: {added[:10]}")
    if built.skills:
        check.errors.append(f"baseline registered skills: {built.skills}")
    if built.installed_skills:
        check.errors.append(
            f"baseline would install skills into the agent config: {built.installed_skills}"
        )
    markers = [marker for marker in CONFIG_MARKERS if marker in built.top]
    base_markers = [marker for marker in CONFIG_MARKERS if marker in base.top]
    if markers != base_markers:
        check.errors.append(f"baseline gained project instruction files: {markers}")
    check.config_markers_present = markers
    return check, built


def check_toolkit(
    source: Path,
    generated_task: Path,
    variant: str,
    spec: PayloadSpec,
    baseline: Probe,
    max_files: int,
    build_timeout_sec: int,
    run_timeout_sec: int,
) -> VariantCheck:
    """Prove the container matches the condition the spec declares.

    The declared intent decides the direction of each assertion: a condition
    that expects project instructions fails when none reach the agent workdir,
    and a condition that expects none fails when any do.
    """
    check = VariantCheck(variant=variant)
    environment = read_task_environment(source / "task.toml")
    _, _, plan = expected_environment(source, variant, spec)

    tag = _tag(variant, source.name)
    build_image(generated_task / "environment", tag, build_timeout_sec)
    probe = probe_image(tag, environment.workdir, plan.skills_dir, max_files, run_timeout_sec)

    check.workdir = probe.workdir
    check.deployed = sorted(probe.report.get("deployed", []))
    check.collisions = sorted(probe.report.get("collision", []))
    check.skills_present = probe.skills
    if probe.truncated:
        check.warnings.append(
            f"workdir holds {probe.file_count} files; tree comparison capped at {max_files}"
        )
    if probe.report.get("payload") != ["present"]:
        check.errors.append("deployment report does not record a staged payload")
    if probe.report.get("variant") != [variant]:
        check.errors.append(f"deployment report names variant {probe.report.get('variant')}")

    expectations = _payload_expectations(generated_task)
    check.payload_file_count = len(expectations)
    collided = set(check.collisions)
    expected_deployed = {
        relative: digest
        for relative, digest in expectations.items()
        if relative.split("/", 1)[0] not in collided
    }
    missing = sorted(
        relative
        for relative, digest in expected_deployed.items()
        if probe.hashes.get(relative) != digest
    )
    if missing:
        check.errors.append(f"toolkit files absent or altered in the container: {missing[:10]}")

    changed = sorted(
        path for path, digest in baseline.hashes.items() if probe.hashes.get(path) != digest
    )
    if changed:
        check.errors.append(f"toolkit layer overwrote benchmark files: {changed[:10]}")
    unexpected = sorted(set(probe.hashes) - set(baseline.hashes) - set(expected_deployed))
    if unexpected:
        check.errors.append(f"unexplained files in the container workdir: {unexpected[:10]}")

    markers = [marker for marker in CONFIG_MARKERS if marker in probe.top]
    baseline_markers = [marker for marker in CONFIG_MARKERS if marker in baseline.top]
    check.config_markers_present = markers
    if spec.expect_instructions:
        if not markers:
            check.errors.append(
                "no CLAUDE.md or AGENTS.md in the agent workdir; the agent would start "
                "without the toolkit's project instructions"
            )
        marker_collisions = sorted(collided.intersection(CONFIG_MARKERS))
        if marker_collisions:
            check.errors.append(
                f"benchmark image already owns {marker_collisions}; the toolkit copy was "
                "archived instead of deployed"
            )
    elif markers != baseline_markers:
        check.errors.append(
            "condition expects no project instructions but the agent workdir contains "
            f"{markers}"
        )

    skill_roots = {source_dir.split("/")[0] for source_dir in spec.skill_sources}
    skill_collisions = sorted(name for name in collided if name in skill_roots)
    if skill_collisions:
        check.warnings.append(f"skill source directories collided with the image: {skill_collisions}")
    if check.collisions:
        check.warnings.append(f"payload entries archived on collision: {check.collisions}")

    check.skills_installable = probe.installed_skills
    expected_skills = set(plan.skills_registered)
    if spec.expect_skills:
        absent_skills = sorted(expected_skills - set(probe.skills))
        if absent_skills:
            check.errors.append(
                f"registered skills missing from the skills directory: {absent_skills}"
            )
        not_installable = sorted(expected_skills - set(probe.installed_skills))
        if not_installable:
            check.errors.append(
                "skills the agent adapter would fail to install into its own config: "
                f"{not_installable}"
            )
    else:
        if probe.skills:
            check.errors.append(
                f"condition expects no skills but the container registered {probe.skills}"
            )
        if probe.installed_skills:
            check.errors.append(
                "condition expects no skills but the agent adapter would install "
                f"{probe.installed_skills}"
            )
    return check


def preflight_task(
    source: Path,
    generated_root: Path,
    toolkits: dict[str, PayloadSpec],
    max_files: int = DEFAULT_MAX_PROBE_FILES,
    build_timeout_sec: int = 1800,
    run_timeout_sec: int = 300,
) -> list[VariantCheck]:
    """Build and probe every variant of one task; write per-variant reports."""
    checks: list[VariantCheck] = []
    baseline_task = generated_root / "baseline" / source.name
    baseline_check, baseline_probe = check_baseline(
        source, baseline_task, max_files, build_timeout_sec, run_timeout_sec
    )
    checks.append(baseline_check)
    _write_report(baseline_task, baseline_check)

    for variant, spec in toolkits.items():
        generated_task = generated_root / variant / source.name
        check = check_toolkit(
            source,
            generated_task,
            variant,
            spec,
            baseline_probe,
            max_files,
            build_timeout_sec,
            run_timeout_sec,
        )
        checks.append(check)
        _write_report(generated_task, check)
    return checks


def _write_report(generated_task: Path, check: VariantCheck) -> None:
    path = generated_task / ".methodology-bench-preflight.json"
    path.write_text(json.dumps(check.as_dict(), indent=2, sort_keys=True) + "\n")
