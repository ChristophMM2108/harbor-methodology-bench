from __future__ import annotations

import shutil
from pathlib import Path

import typer

from .catalogue import build_catalogue, render_json, render_markdown, suite_names
from .config import ExperimentConfig, load_config
from .environment import build_environment
from .inject import copy_task
from .manifest import tree_manifest, write_manifest
from .preflight import DEFAULT_MAX_PROBE_FILES, PreflightError, preflight_task
from .source import TaskSelection, discover_tasks, read_task_ids, select_tasks
from .validate import source_dockerfile_digest, validate_task

app = typer.Typer(no_args_is_help=True, help="Generate and validate controlled Harbor methodology variants.")

CONFIG_OPTION = typer.Option(Path("config/experiments.yaml"), help="Experiment configuration file.")
TASK_OPTION = typer.Option(None, "--task", help="Task id; repeat to select several.")
SUITE_OPTION = typer.Option(None, "--suite", help=f"Named task set: {', '.join(suite_names())}.")
TASKS_FILE_OPTION = typer.Option(None, "--tasks-file", help="File of task ids, one per line.")
CATEGORY_OPTION = typer.Option(None, "--category", help="Keep only this benchmark category.")
DIFFICULTY_OPTION = typer.Option(None, "--difficulty", help="Keep only this difficulty.")
LIMIT_OPTION = typer.Option(None, "--limit", min=1, help="Truncate the selection, applied last.")


def _config(path: Path) -> ExperimentConfig:
    try:
        return load_config(path)
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--config") from error


def _selection(
    task: list[str] | None,
    suite: list[str] | None,
    tasks_file: Path | None,
    category: list[str] | None,
    difficulty: list[str] | None,
    limit: int | None,
) -> TaskSelection:
    ids = tuple(task or ())
    if tasks_file:
        try:
            ids += read_task_ids(tasks_file)
        except OSError as error:
            raise typer.BadParameter(str(error), param_hint="--tasks-file") from error
    return TaskSelection(
        ids=ids,
        suites=tuple(suite or ()),
        categories=tuple(category or ()),
        difficulties=tuple(difficulty or ()),
        limit=limit,
    )


def _selected_tasks(settings: ExperimentConfig, selection: TaskSelection) -> list[Path]:
    try:
        return select_tasks(settings.source_root, selection)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error


@app.command("freeze-verify")
def freeze_verify(config: Path = typer.Option(Path("config/experiments.yaml"))) -> None:
    """Verify committed snapshots and their immutable metadata files."""
    settings = _config(config)
    for toolkit in settings.toolkits.values():
        root = toolkit.snapshot.parent
        missing = [name for name in ("SOURCE", "GIT_SHA", "BRANCH", "VERSION", "snapshot") if not (root / name).exists()]
        if missing:
            raise typer.BadParameter(f"{toolkit.id} missing: {', '.join(missing)}")
        sha = (root / "GIT_SHA").read_text().strip()
        if len(sha) != 40 or any(char not in "0123456789abcdef" for char in sha.lower()):
            raise typer.BadParameter(f"{toolkit.id} has invalid GIT_SHA")
        typer.echo(f"ok  {toolkit.id}  {sha}")


@app.command()
def generate(
    config: Path = CONFIG_OPTION,
    task: list[str] = TASK_OPTION,
    suite: list[str] = SUITE_OPTION,
    tasks_file: Path | None = TASKS_FILE_OPTION,
    category: list[str] = CATEGORY_OPTION,
    difficulty: list[str] = DIFFICULTY_OPTION,
    limit: int | None = LIMIT_OPTION,
    force: bool = typer.Option(False, help="Replace only generated variant directories."),
) -> None:
    """Generate baseline and toolkit variants that carry the toolkit into the container.

    Each variant keeps the standard Harbor task layout. The frozen toolkit
    snapshot is staged inside `environment/` and deployed into the agent's
    working directory by a generated Dockerfile layer, so the agent CLI
    discovers the toolkit's `CLAUDE.md` / `AGENTS.md` and skills natively.
    """
    settings = _config(config)
    tasks = _selected_tasks(
        settings, _selection(task, suite, tasks_file, category, difficulty, limit)
    )
    for task_dir in tasks:
        for variant, spec in settings.specs().items():
            destination = settings.generated_root / variant / task_dir.name
            if destination.exists() and force:
                shutil.rmtree(destination)
            copy_task(task_dir, destination)
            plan = build_environment(task_dir, destination, variant, spec)
            write_manifest(destination / ".methodology-bench-manifest.json", {
                "task_id": task_dir.name,
                "variant": variant,
                "source_files": tree_manifest(task_dir),
                "source_dockerfile_sha256": source_dockerfile_digest(task_dir),
                "toolkit_files": tree_manifest(spec.snapshot) if spec.snapshot else {},
                "environment": plan.as_manifest(),
            })
            markers = ",".join(plan.config_markers) or "-"
            typer.echo(
                f"generated {variant}/{task_dir.name}  markers={markers} "
                f"skills={len(plan.skills_registered)}"
            )


@app.command()
def validate(
    config: Path = CONFIG_OPTION,
    task: list[str] = TASK_OPTION,
    suite: list[str] = SUITE_OPTION,
    tasks_file: Path | None = TASKS_FILE_OPTION,
    category: list[str] = CATEGORY_OPTION,
    difficulty: list[str] = DIFFICULTY_OPTION,
    limit: int | None = LIMIT_OPTION,
) -> None:
    """Fail closed when generated variants are missing, modified, or contaminated."""
    settings = _config(config)
    tasks = _selected_tasks(
        settings, _selection(task, suite, tasks_file, category, difficulty, limit)
    )
    failures: list[str] = []
    variants = settings.specs()
    for task_dir in tasks:
        for variant, spec in variants.items():
            errors = validate_task(
                task_dir,
                settings.generated_root / variant / task_dir.name,
                variant,
                spec,
            )
            failures.extend(f"{variant}/{task_dir.name}: {error}" for error in errors)
    if failures:
        raise typer.Exit(typer.echo("\n".join(failures), err=True) or 1)
    typer.echo(f"validated {len(tasks)} tasks across {len(variants)} variants")


@app.command()
def preflight(
    config: Path = CONFIG_OPTION,
    task: list[str] = TASK_OPTION,
    suite: list[str] = SUITE_OPTION,
    tasks_file: Path | None = TASKS_FILE_OPTION,
    category: list[str] = CATEGORY_OPTION,
    difficulty: list[str] = DIFFICULTY_OPTION,
    limit: int | None = LIMIT_OPTION,
    max_probe_files: int = typer.Option(DEFAULT_MAX_PROBE_FILES, min=100),
    build_timeout_sec: int = typer.Option(1800, min=60),
    run_timeout_sec: int = typer.Option(300, min=10),
) -> None:
    """Build every variant image and assert the toolkit reached the container.

    This is the check that the host-side validator cannot make: it builds the
    generated environment, probes the resulting container from the inside, and
    fails when a toolkit variant lacks project instructions or skills, or when
    any variant altered the benchmark's own files.
    """
    settings = _config(config)
    tasks = _selected_tasks(
        settings, _selection(task, suite, tasks_file, category, difficulty, limit)
    )
    toolkits = {toolkit.id: toolkit.spec for toolkit in settings.toolkits.values()}
    failures: list[str] = []
    for task_dir in tasks:
        typer.echo(f"preflight {task_dir.name} ...")
        try:
            checks = preflight_task(
                task_dir,
                settings.generated_root,
                toolkits,
                max_probe_files,
                build_timeout_sec,
                run_timeout_sec,
            )
        except PreflightError as error:
            failures.append(f"{task_dir.name}: {error}")
            continue
        for check in checks:
            for warning in check.warnings:
                typer.echo(f"  warn  {check.variant}: {warning}")
            if check.errors:
                failures.extend(
                    f"{check.variant}/{task_dir.name}: {error}" for error in check.errors
                )
                continue
            expectations = settings.specs().get(check.variant)
            declared = (
                ""
                if expectations is None
                else f" expects(instructions={expectations.expect_instructions},"
                f"skills={expectations.expect_skills})"
            )
            typer.echo(
                f"  ok    {check.variant}: workdir={check.workdir} "
                f"markers={','.join(check.config_markers_present) or '-'} "
                f"skills={len(check.skills_present)} "
                f"payload_files={check.payload_file_count}{declared}"
            )
    if failures:
        raise typer.Exit(typer.echo("\n".join(failures), err=True) or 1)
    typer.echo(f"preflight passed for {len(tasks)} tasks")


@app.command()
def catalogue(
    config: Path = CONFIG_OPTION,
    task: list[str] = TASK_OPTION,
    suite: list[str] = SUITE_OPTION,
    tasks_file: Path | None = TASKS_FILE_OPTION,
    category: list[str] = CATEGORY_OPTION,
    difficulty: list[str] = DIFFICULTY_OPTION,
    limit: int | None = LIMIT_OPTION,
    md_out: Path | None = typer.Option(None, help="Write the full catalogue as markdown."),
    json_out: Path | None = typer.Option(None, help="Write the catalogue as JSON."),
    ids_only: bool = typer.Option(False, help="Print only the selected task ids, one per line."),
) -> None:
    """Classify the benchmark tasks so a task set can be chosen deliberately.

    Reads every task's manifest and prompt, derives the work-type axes, and
    reports them. With the same selection flags as `generate`, this doubles as a
    dry run of a selection: `catalogue --suite diagnose-first --ids-only` prints
    exactly the tasks that suite would generate.
    """
    settings = _config(config)
    tasks = _selected_tasks(
        settings, _selection(task, suite, tasks_file, category, difficulty, limit)
    )
    facts = build_catalogue(tasks)

    if ids_only:
        for entry in sorted(facts, key=lambda item: item.task_id):
            typer.echo(entry.task_id)
        return

    if md_out:
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(render_markdown(facts, settings.source_root))
        typer.echo(f"wrote {md_out}")
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(render_json(facts, settings.source_root))
        typer.echo(f"wrote {json_out}")
    if md_out or json_out:
        return

    typer.echo(f"{len(facts)} tasks in {settings.source_root}")
    counts: dict[str, int] = {}
    for entry in facts:
        for axis in entry.axes:
            counts[axis] = counts.get(axis, 0) + 1
    for axis, count in sorted(counts.items()):
        typer.echo(f"  {axis:26s} {count:>3}")
    typer.echo("\nPass --md-out / --json-out to write the full catalogue.")


@app.command("matrix-plan")
def matrix_plan(config: Path = CONFIG_OPTION) -> None:
    """Print the configured matrix cells as `id<TAB>variant<TAB>agent<TAB>model`.

    The experiment runners read their cells from here instead of hard-coding
    them, so a matrix change in `config/experiments.yaml` takes effect without
    editing any shell script.
    """
    settings = _config(config)
    valid_variants = {"baseline", *settings.toolkits}
    for cell in settings.matrix:
        variant = cell["toolkit"]
        if variant not in valid_variants:
            raise typer.BadParameter(f"unknown toolkit variant: {variant}")
        model = settings.models.get(cell["agent"])
        if not model:
            raise typer.BadParameter(f"no model configured for agent: {cell['agent']}")
        typer.echo(f"{cell['id']}\t{variant}\t{cell['agent']}\t{model}")


@app.command("smoke-plan")
def smoke_plan(config: Path = CONFIG_OPTION, task_id: str = typer.Option(...)) -> None:
    """Print the configured Harbor invocations; it never executes them."""
    settings = _config(config)
    valid_variants = {"baseline", *settings.toolkits}
    for cell in settings.matrix:
        variant = cell["toolkit"]
        if variant not in valid_variants:
            raise typer.BadParameter(f"unknown toolkit variant: {variant}")
        task_path = settings.generated_root / variant / task_id
        if not task_path.is_dir():
            raise typer.BadParameter(f"generate this task first: {task_path}")
        model = settings.models.get(cell["agent"])
        if not model:
            raise typer.BadParameter(f"no model configured for agent: {cell['agent']}")
        typer.echo(f"{cell['id']}: harbor run -p {task_path} -a {cell['agent']} -m {model}")
