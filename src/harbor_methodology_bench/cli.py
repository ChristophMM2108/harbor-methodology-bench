from __future__ import annotations

import shutil
from pathlib import Path

import typer

from .config import ExperimentConfig, load_config
from .inject import copy_task, inject_snapshot
from .manifest import tree_manifest, write_manifest
from .source import discover_tasks
from .validate import validate_task

app = typer.Typer(no_args_is_help=True, help="Generate and validate controlled Harbor methodology variants.")


def _config(path: Path) -> ExperimentConfig:
    try:
        return load_config(path)
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--config") from error


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
    config: Path = typer.Option(Path("config/experiments.yaml")),
    limit: int | None = typer.Option(None, min=1),
    force: bool = typer.Option(False, help="Replace only generated variant directories."),
) -> None:
    """Generate baseline and one complete native snapshot variant per toolkit."""
    settings = _config(config)
    tasks = discover_tasks(settings.source_root)
    if limit:
        tasks = tasks[:limit]
    variants: dict[str, Path | None] = {"baseline": None}
    variants.update({toolkit.id: toolkit.snapshot for toolkit in settings.toolkits.values()})
    for task in tasks:
        for variant, snapshot in variants.items():
            destination = settings.generated_root / variant / task.name
            if destination.exists() and force:
                shutil.rmtree(destination)
            copy_task(task, destination)
            deployment = inject_snapshot(snapshot, destination, task) if snapshot else {}
            write_manifest(destination / ".methodology-bench-manifest.json", {
                "task_id": task.name,
                "variant": variant,
                "source_files": tree_manifest(task),
                "toolkit_files": tree_manifest(snapshot) if snapshot else {},
                "toolkit_deployment": deployment,
            })
            typer.echo(f"generated {variant}/{task.name}")


@app.command()
def validate(
    config: Path = typer.Option(Path("config/experiments.yaml")),
    limit: int | None = typer.Option(None, min=1),
) -> None:
    """Fail closed when generated variants are missing, modified, or contaminated."""
    settings = _config(config)
    tasks = discover_tasks(settings.source_root)
    if limit:
        tasks = tasks[:limit]
    failures: list[str] = []
    variants: dict[str, Path | None] = {"baseline": None}
    variants.update({toolkit.id: toolkit.snapshot for toolkit in settings.toolkits.values()})
    for task in tasks:
        for variant, snapshot in variants.items():
            errors = validate_task(task, settings.generated_root / variant / task.name, snapshot)
            failures.extend(f"{variant}/{task.name}: {error}" for error in errors)
    if failures:
        raise typer.Exit(typer.echo("\n".join(failures), err=True) or 1)
    typer.echo(f"validated {len(tasks)} tasks across {len(variants)} variants")


@app.command("smoke-plan")
def smoke_plan(config: Path = typer.Option(Path("config/experiments.yaml")), task_id: str = typer.Option(...)) -> None:
    """Print the six controlled Harbor invocations; it never executes them."""
    settings = _config(config)
    valid_variants = {"baseline", *settings.toolkits}
    cells = settings.matrix
    if len(cells) != 6:
        raise typer.BadParameter("the smoke matrix must contain exactly six cells")
    for cell in cells:
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
