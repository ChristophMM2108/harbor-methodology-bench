from __future__ import annotations

import shlex
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# Host-side layout inside a generated task's `environment/` build context.
STAGE_DIRNAME = ".methodology-bench"
PAYLOAD_SUBDIR = "payload"
SKILLS_SUBDIR = "skills"
DEPLOY_SCRIPT_NAME = "deploy-payload.sh"

# Container-side layout. Everything the harness owns lives outside the task
# workdir so that a baseline container is byte-identical to its base image.
CONTAINER_STAGE = "/methodology-bench"
CONTAINER_PAYLOAD_DIR = f"{CONTAINER_STAGE}/{PAYLOAD_SUBDIR}"
CONTAINER_SKILLS_DIR = f"{CONTAINER_STAGE}/{SKILLS_SUBDIR}"
CONTAINER_REPORT = f"{CONTAINER_STAGE}/deployment-report.tsv"
CONTAINER_COLLISIONS = f"{CONTAINER_STAGE}/toolkit-collisions"

# Build artifacts of a host-side checkout that must never enter a container.
DEFAULT_SNAPSHOT_EXCLUDES = (
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".DS_Store",
)

# Directories inside a toolkit that hold installable agent skills, in
# precedence order. The first source that provides a given skill name wins.
SKILL_SOURCE_DIRS = (".claude/skills", ".agents/skills", "skills")

# Project-level instruction files an agent CLI discovers from its cwd.
CONFIG_MARKERS = ("CLAUDE.md", "AGENTS.md")

DOCKERFILE_NAME = "Dockerfile"
COMPOSE_FILE_NAME = "docker-compose.yaml"

PREBUILT_BASE = "prebuilt-image-base"
APPENDED_DOCKERFILE = "appended-source-dockerfile"


@dataclass(frozen=True)
class PayloadSpec:
    """One experimental condition's payload, declared rather than inferred.

    `excludes` drops matching names at any depth; `includes`, when non-empty,
    keeps only those top-level snapshot entries. The two `expect_*` flags state
    what the condition is *supposed* to put in front of the agent, and both the
    validator and the in-container preflight assert them in both directions —
    a condition declaring no project instructions fails if a `CLAUDE.md`
    reaches the agent's working directory, exactly as a full-toolkit condition
    fails if one does not.
    """

    snapshot: Path | None = None
    excludes: tuple[str, ...] = DEFAULT_SNAPSHOT_EXCLUDES
    includes: tuple[str, ...] = ()
    expect_instructions: bool = True
    expect_skills: bool = True
    skill_sources: tuple[str, ...] = SKILL_SOURCE_DIRS


BASELINE_SPEC = PayloadSpec(expect_instructions=False, expect_skills=False)


@dataclass(frozen=True)
class TaskEnvironment:
    """The parts of a source `task.toml` that drive environment generation."""

    docker_image: str | None
    workdir: str | None
    skills_dir: str | None
    verifier_is_separate: bool
    verifier_has_environment: bool


@dataclass
class EnvironmentPlan:
    """Deterministic description of a generated `environment/` directory."""

    variant: str
    strategy: str
    base_image: str | None
    workdir_arg: str
    skills_dir: str
    expect_instructions: bool = True
    expect_skills: bool = True
    payload_files: dict[str, str] = field(default_factory=dict)
    skills_registered: list[str] = field(default_factory=list)
    skill_name_conflicts: dict[str, list[str]] = field(default_factory=dict)
    dropped_names: list[str] = field(default_factory=list)
    include_filter: list[str] = field(default_factory=list)
    task_toml_patches: list[str] = field(default_factory=list)
    config_markers: list[str] = field(default_factory=list)

    def as_manifest(self) -> dict:
        return {
            "variant": self.variant,
            "strategy": self.strategy,
            "base_image": self.base_image,
            "workdir_arg": self.workdir_arg,
            "container_skills_dir": self.skills_dir,
            "container_stage": CONTAINER_STAGE,
            "expect_instructions": self.expect_instructions,
            "expect_skills": self.expect_skills,
            "payload_files": self.payload_files,
            "skills_registered": self.skills_registered,
            "skill_name_conflicts": self.skill_name_conflicts,
            "dropped_names": self.dropped_names,
            "include_filter": self.include_filter,
            "task_toml_patches": self.task_toml_patches,
            "config_markers": self.config_markers,
        }


def read_task_environment(task_toml: Path) -> TaskEnvironment:
    """Read the environment- and verifier-relevant fields of a task manifest."""
    data = tomllib.loads(task_toml.read_text())
    environment = data.get("environment") or {}
    verifier = data.get("verifier") or {}
    steps = data.get("steps") or []
    modes = [verifier.get("environment_mode")]
    modes.extend((step.get("verifier") or {}).get("environment_mode") for step in steps)
    has_environment = verifier.get("environment") is not None or any(
        (step.get("verifier") or {}).get("environment") is not None for step in steps
    )
    return TaskEnvironment(
        docker_image=environment.get("docker_image"),
        workdir=environment.get("workdir"),
        skills_dir=environment.get("skills_dir"),
        verifier_is_separate=any(mode == "separate" for mode in modes),
        verifier_has_environment=has_environment,
    )


def _ignore_names(spec: PayloadSpec, root: Path, seen: set[str]):
    root_key = str(root)

    def ignore(directory: str, names: list[str]) -> set[str]:
        skipped = {name for name in names if name in spec.excludes}
        if spec.includes and str(directory) == root_key:
            skipped.update(name for name in names if name not in spec.includes)
        seen.update(skipped)
        return skipped

    return ignore


def stage_dir(environment_dir: Path) -> Path:
    return environment_dir / STAGE_DIRNAME


def stage_payload(spec: PayloadSpec, environment_dir: Path) -> list[str]:
    """Copy the snapshot into the build stage; return the names left behind."""
    stage = stage_dir(environment_dir)
    stage.mkdir(parents=True, exist_ok=True)
    if spec.snapshot is None:
        return []
    dropped: set[str] = set()
    shutil.copytree(
        spec.snapshot,
        stage / PAYLOAD_SUBDIR,
        symlinks=True,
        ignore=_ignore_names(spec, spec.snapshot, dropped),
    )
    return sorted(dropped)


def stage_skills(
    environment_dir: Path,
    sources: tuple[str, ...] = SKILL_SOURCE_DIRS,
) -> tuple[list[str], dict[str, list[str]]]:
    """Assemble one installable skill registry from the staged payload."""
    stage = stage_dir(environment_dir)
    skills = stage / SKILLS_SUBDIR
    skills.mkdir(parents=True, exist_ok=True)
    (skills / ".keep").write_text("")
    payload = stage / PAYLOAD_SUBDIR
    registered: dict[str, str] = {}
    conflicts: dict[str, list[str]] = {}
    if not payload.is_dir():
        return [], {}
    for source in sources:
        root = payload / source
        if not root.is_dir():
            continue
        for candidate in sorted(root.iterdir()):
            if not candidate.is_dir() or not (candidate / "SKILL.md").is_file():
                continue
            origin = f"{source}/{candidate.name}"
            if candidate.name in registered:
                conflicts.setdefault(candidate.name, [registered[candidate.name]]).append(origin)
                continue
            registered[candidate.name] = origin
            shutil.copytree(candidate, skills / candidate.name, symlinks=True)
    return sorted(registered), conflicts


def staged_config_markers(environment_dir: Path) -> list[str]:
    """Project instruction files the payload deploys into the agent workdir."""
    payload = stage_dir(environment_dir) / PAYLOAD_SUBDIR
    return [marker for marker in CONFIG_MARKERS if (payload / marker).is_file()]


def render_deploy_script() -> str:
    """Render the POSIX script that deploys the payload inside the image.

    Collision handling happens against the real container filesystem rather
    than against the source task directory: a payload entry whose name already
    exists in the workdir is preserved under the collision archive instead of
    overwriting benchmark-owned content.
    """
    return f"""#!/bin/sh
# Generated by harbor-methodology-bench. Deploys a frozen methodology toolkit
# into the agent workdir without overwriting any pre-existing path.
set -eu

VARIANT="$1"
TARGET="$2"
SKILLS_TARGET="$3"

STAGE="{CONTAINER_STAGE}"
PAYLOAD="{CONTAINER_PAYLOAD_DIR}"
REPORT="{CONTAINER_REPORT}"
COLLISIONS="{CONTAINER_COLLISIONS}"

mkdir -p "$TARGET"
cd "$TARGET"
WORKDIR="$(pwd)"

mkdir -p "$STAGE"
: > "$REPORT"
printf 'variant\\t%s\\n' "$VARIANT" >> "$REPORT"
printf 'workdir\\t%s\\n' "$WORKDIR" >> "$REPORT"
printf 'skills_dir\\t%s\\n' "$SKILLS_TARGET" >> "$REPORT"

mkdir -p "$SKILLS_TARGET"
if [ -d "$STAGE/{SKILLS_SUBDIR}" ] && [ "$SKILLS_TARGET" != "$STAGE/{SKILLS_SUBDIR}" ]; then
    cp -a "$STAGE/{SKILLS_SUBDIR}/." "$SKILLS_TARGET/"
fi

if [ ! -d "$PAYLOAD" ]; then
    printf 'payload\\tabsent\\n' >> "$REPORT"
    exit 0
fi
printf 'payload\\tpresent\\n' >> "$REPORT"
mkdir -p "$COLLISIONS"

for entry in "$PAYLOAD"/* "$PAYLOAD"/.[!.]* "$PAYLOAD"/..?*; do
    [ -e "$entry" ] || continue
    name="${{entry##*/}}"
    if [ -e "$WORKDIR/$name" ] || [ -L "$WORKDIR/$name" ]; then
        printf 'collision\\t%s\\n' "$name" >> "$REPORT"
        cp -a "$entry" "$COLLISIONS/$name"
    else
        printf 'deployed\\t%s\\n' "$name" >> "$REPORT"
        cp -a "$entry" "$WORKDIR/$name"
    fi
done
"""


def render_dockerfile(plan: EnvironmentPlan, source_dockerfile: str | None) -> str:
    """Render the generated `environment/Dockerfile` for one variant.

    The rendered text is identical across variants of the same task; only the
    staged payload differs. That keeps the image build path free of any
    baseline-versus-toolkit confound.
    """
    header = [
        "# Generated by harbor-methodology-bench. Do not edit.",
        f"# strategy: {plan.strategy}",
        "# The methodology payload is deployed by a single layer on top of the",
        "# unmodified task base image; a variant without a toolkit stages none.",
        "",
    ]
    if plan.strategy == PREBUILT_BASE:
        body = [f"FROM {plan.base_image}", ""]
    else:
        if source_dockerfile is None:
            raise ValueError("appended strategy requires a source Dockerfile")
        body = [source_dockerfile.rstrip("\n"), ""]
    arguments = " ".join(
        shlex.quote(argument)
        for argument in (plan.variant, plan.workdir_arg, plan.skills_dir)
    )
    layer = [
        f"COPY {STAGE_DIRNAME}/ {CONTAINER_STAGE}/",
        f"RUN sh {CONTAINER_STAGE}/{DEPLOY_SCRIPT_NAME} {arguments}",
        "",
    ]
    return "\n".join([*header, *body, *layer])


def _section_bounds(lines: list[str], section: str) -> tuple[int, int] | None:
    start: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if start is None:
            if stripped == f"[{section}]":
                start = index
            continue
        if stripped.startswith("["):
            return start, index
    if start is None:
        return None
    return start, len(lines)


def patch_task_toml(text: str, plan: EnvironmentPlan, environment: TaskEnvironment) -> tuple[str, list[str]]:
    """Rewrite a task manifest so the generated Dockerfile is authoritative.

    Two edits, both recorded in the variant manifest:

    1. `[environment].docker_image` is removed, because Harbor prefers a
       prebuilt image over `environment/Dockerfile` and would otherwise ignore
       the generated payload layer entirely.
    2. `[environment].skills_dir` is set so the agent adapter installs the
       toolkit's skills into its own skills configuration directory.

    When a task runs its verifier in a separate environment and does not pin
    one explicitly, the original image is pinned for the verifier so that
    verification keeps running against clean, toolkit-free benchmark code.
    """
    patches: list[str] = []
    lines = text.splitlines()
    bounds = _section_bounds(lines, "environment")
    if bounds is None:
        lines.extend(["", "[environment]", f'skills_dir = "{plan.skills_dir}"'])
        patches.append("added [environment] with skills_dir")
        bounds = _section_bounds(lines, "environment")
        assert bounds is not None
    else:
        start, end = bounds
        for index in range(start + 1, end):
            if lines[index].strip().startswith("docker_image"):
                lines[index] = (
                    "# docker_image removed by harbor-methodology-bench "
                    f"(kept as Dockerfile base): {environment.docker_image}"
                )
                patches.append("removed [environment].docker_image")
                break
        if environment.skills_dir is None:
            lines.insert(start + 1, f'skills_dir = "{plan.skills_dir}"')
            patches.append("set [environment].skills_dir")

    if (
        environment.verifier_is_separate
        and not environment.verifier_has_environment
        and environment.docker_image
    ):
        lines.extend(
            [
                "",
                "# Pinned by harbor-methodology-bench so a separate verifier keeps",
                "# using the unmodified benchmark image.",
                "[verifier.environment]",
                f'docker_image = "{environment.docker_image}"',
            ]
        )
        patches.append("pinned [verifier.environment].docker_image")

    return "\n".join(lines) + "\n", patches


def build_environment(
    source_task: Path,
    generated_task: Path,
    variant: str,
    spec: PayloadSpec = BASELINE_SPEC,
) -> EnvironmentPlan:
    """Turn a copied task into a variant whose container carries the payload."""
    environment_dir = generated_task / "environment"
    environment_dir.mkdir(parents=True, exist_ok=True)
    task_environment = read_task_environment(source_task / "task.toml")

    source_dockerfile_path = source_task / "environment" / DOCKERFILE_NAME
    source_dockerfile = (
        source_dockerfile_path.read_text() if source_dockerfile_path.is_file() else None
    )
    if task_environment.docker_image:
        strategy = PREBUILT_BASE
        base_image: str | None = task_environment.docker_image
    elif source_dockerfile is not None:
        strategy = APPENDED_DOCKERFILE
        base_image = None
    else:
        raise ValueError(
            f"{source_task.name}: task declares neither [environment].docker_image "
            f"nor environment/{DOCKERFILE_NAME}; cannot generate a payload layer"
        )
    if (source_task / "environment" / COMPOSE_FILE_NAME).is_file():
        raise ValueError(
            f"{source_task.name}: compose-defined environments are not supported yet; "
            "the payload layer only patches Dockerfile-defined tasks"
        )

    plan = EnvironmentPlan(
        variant=variant,
        strategy=strategy,
        base_image=base_image,
        workdir_arg=task_environment.workdir or ".",
        skills_dir=task_environment.skills_dir or CONTAINER_SKILLS_DIR,
        expect_instructions=spec.expect_instructions,
        expect_skills=spec.expect_skills,
        include_filter=list(spec.includes),
    )
    plan.dropped_names = stage_payload(spec, environment_dir)
    plan.skills_registered, plan.skill_name_conflicts = stage_skills(
        environment_dir, spec.skill_sources
    )
    plan.config_markers = staged_config_markers(environment_dir)

    stage = stage_dir(environment_dir)
    (stage / DEPLOY_SCRIPT_NAME).write_text(render_deploy_script())
    (environment_dir / DOCKERFILE_NAME).write_text(
        render_dockerfile(plan, source_dockerfile)
    )

    task_toml = generated_task / "task.toml"
    patched, patches = patch_task_toml(
        (source_task / "task.toml").read_text(), plan, task_environment
    )
    task_toml.write_text(patched)
    plan.task_toml_patches = patches
    return plan
