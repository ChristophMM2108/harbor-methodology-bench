from __future__ import annotations

import datetime
import os
import shutil
import subprocess
from pathlib import Path

import typer
import yaml

from .analysis import extract_all, write_csvs
from .catalogue import build_catalogue, render_json, render_markdown, suite_names
from .config import ExperimentConfig, load_config
from .doctor import in_container, run_checks, worst
from .environment import build_environment
from .inject import copy_task
from .jobplan import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_N_CONCURRENT_AGENTS,
    DEFAULT_N_CONCURRENT_TRIALS,
    JobPlanError,
    plan_jobs,
    write_job_configs,
)
from .manifest import tree_manifest, write_manifest
from .preflight import (
    DEFAULT_MAX_PROBE_FILES,
    DEFAULT_PREFLIGHT_JOBS,
    PreflightError,
    preflight_tasks,
)
from .report import write_report
from .screen import (
    BASELINE_SUFFIX,
    INCLUDE,
    SOLVABILITY_SUFFIX,
    UNKNOWN,
    ScreenError,
    baseline_job,
    read_screen,
    render_task_file,
    solvability_job,
)
from .resume import (
    NO_RESULT,
    UNREADABLE,
    ResumeError,
    breakdown,
    check_job_dir,
    classify_trials,
    read_env_file,
    resume_filters,
)
from .repo import RootNotFound, find_root
from .scaffold import ScaffoldError, credentials_template, new_analysis, new_experiment
from .source import TaskSelection, discover_tasks, read_task_ids, select_tasks
from .sources import SourceError, fetch_source, load_sources
from .validate import source_dockerfile_digest, validate_task

app = typer.Typer(
    no_args_is_help=True,
    help=(
        "Measure what a repository's agent configuration does to a coding agent. "
        "Run `hmb doctor` first, then `hmb setup`."
    ),
)
experiment_app = typer.Typer(no_args_is_help=True, help="Create and inspect experiment scenarios.")
analysis_app = typer.Typer(no_args_is_help=True, help="Trial-level analysis of a finished run.")
app.add_typer(experiment_app, name="experiment")
app.add_typer(analysis_app, name="analysis")

CONFIG_OPTION = typer.Option(Path("config/experiments.yaml"), help="Experiment configuration file.")
SOURCES_OPTION = typer.Option(Path("config/sources.yaml"), help="Pinned external sources.")


def _root() -> Path:
    """The repository root, so every command means the same from any directory."""
    try:
        return find_root()
    except RootNotFound as error:
        raise typer.BadParameter(str(error)) from error


def _at_root(path: Path) -> Path:
    return path if path.is_absolute() else (_root() / path)
TASK_OPTION = typer.Option(None, "--task", help="Task id; repeat to select several.")
SUITE_OPTION = typer.Option(None, "--suite", help=f"Named task set: {', '.join(suite_names())}.")
TASKS_FILE_OPTION = typer.Option(None, "--tasks-file", help="File of task ids, one per line.")
CATEGORY_OPTION = typer.Option(None, "--category", help="Keep only this benchmark category.")
DIFFICULTY_OPTION = typer.Option(None, "--difficulty", help="Keep only this difficulty.")
LIMIT_OPTION = typer.Option(None, "--limit", min=1, help="Truncate the selection, applied last.")


def _config(path: Path) -> ExperimentConfig:
    path = _at_root(path)
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
def freeze_verify(
    config: Path = CONFIG_OPTION,
    sources: Path = SOURCES_OPTION,
) -> None:
    """Verify each condition's snapshot and its immutable provenance files.

    A toolkit declared `vendored: true` in the sources file is committed here and
    has no upstream commit, so it is checked for content only. Everything else
    must carry a full 40-character `GIT_SHA`: without it the snapshot is
    provenance nobody can re-derive.
    """
    settings = _config(config)
    sources_path = _at_root(sources)
    vendored: set[str] = set()
    if sources_path.is_file():
        try:
            vendored = {source.id for source in load_sources(sources_path) if source.vendored}
        except SourceError as error:
            raise typer.BadParameter(str(error), param_hint="--sources") from error

    for toolkit in settings.toolkits.values():
        root = toolkit.snapshot.parent
        if not toolkit.snapshot.is_dir() or not any(toolkit.snapshot.iterdir()):
            raise typer.BadParameter(
                f"{toolkit.id}: {_show(toolkit.snapshot)} is missing or empty — run `hmb setup`"
            )
        # A toolkit id may differ from the directory that holds it; match on both.
        is_vendored = toolkit.id in vendored or root.name in vendored
        required = ("SOURCE", "BRANCH", "VERSION") if is_vendored else ("SOURCE", "GIT_SHA", "BRANCH", "VERSION")
        missing = [name for name in required if not (root / name).exists()]
        if missing:
            raise typer.BadParameter(f"{toolkit.id} missing: {', '.join(missing)}")
        if is_vendored:
            typer.echo(f"ok  {toolkit.id}  vendored")
            continue
        sha = (root / "GIT_SHA").read_text().strip()
        if len(sha) != 40 or any(char not in "0123456789abcdef" for char in sha.lower()):
            raise typer.BadParameter(f"{toolkit.id} has invalid GIT_SHA")
        typer.echo(f"ok  {toolkit.id}  {sha}")


def _show(path: Path) -> str:
    """A path as the user would type it: relative to the repository root."""
    try:
        return str(path.relative_to(_root()))
    except (ValueError, typer.BadParameter):
        return str(path)


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
    jobs: int = typer.Option(
        DEFAULT_PREFLIGHT_JOBS, min=1, help="Image builds and probes to run at once."
    ),
) -> None:
    """Build every variant image and assert the toolkit reached the container.

    This is the check that the host-side validator cannot make: it builds the
    generated environment, probes the resulting container from the inside, and
    fails when a toolkit variant lacks project instructions or skills, or when
    any variant altered the benchmark's own files.

    Builds run `--jobs` at a time. Results are still reported task by task in
    selection order, so a parallel preflight reads exactly like a serial one.
    """
    settings = _config(config)
    tasks = _selected_tasks(
        settings, _selection(task, suite, tasks_file, category, difficulty, limit)
    )
    toolkits = {toolkit.id: toolkit.spec for toolkit in settings.toolkits.values()}
    failures: list[str] = []
    for task_dir, outcome in preflight_tasks(
        tasks,
        settings.generated_root,
        toolkits,
        max_probe_files,
        build_timeout_sec,
        run_timeout_sec,
        jobs,
    ):
        typer.echo(f"preflight {task_dir.name}")
        if isinstance(outcome, PreflightError):
            failures.append(f"{task_dir.name}: {outcome}")
            continue
        for check in outcome:
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
        md_out.write_text(render_markdown(facts, settings.source_root, settings.root))
        typer.echo(f"wrote {md_out}")
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(render_json(facts, settings.source_root, settings.root))
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


@app.command("plan-job")
def plan_job(
    config: Path = CONFIG_OPTION,
    task: list[str] = TASK_OPTION,
    suite: list[str] = SUITE_OPTION,
    tasks_file: Path | None = TASKS_FILE_OPTION,
    category: list[str] = CATEGORY_OPTION,
    difficulty: list[str] = DIFFICULTY_OPTION,
    limit: int | None = LIMIT_OPTION,
    job_prefix: str = typer.Option("pilot", help="Job name prefix; each job is '<prefix>-<agent>'."),
    attempts: int = typer.Option(1, min=1, help="Repetitions per cell (Harbor's n_attempts)."),
    jobs_dir: Path = typer.Option(Path("jobs"), help="Where Harbor should write its job output."),
    n_concurrent: int = typer.Option(
        DEFAULT_N_CONCURRENT_TRIALS, min=1, help="Concurrent trials over the whole lifecycle."
    ),
    n_concurrent_agents: int = typer.Option(
        DEFAULT_N_CONCURRENT_AGENTS, min=1, help="Concurrent agent phases; must not exceed --n-concurrent."
    ),
    max_retries: int = typer.Option(
        DEFAULT_MAX_RETRIES, min=0, help="Retries per trial, for transient API errors only."
    ),
    out_dir: Path | None = typer.Option(
        None, help="Write one job config per agent here instead of printing them."
    ),
) -> None:
    """Emit a Harbor job configuration per agent; it never executes anything.

    One job spans every condition, with one dataset entry per (condition, task)
    in task-major order, so conditions of the same task run paired instead of
    one whole condition after another. Output is a pure function of the
    experiment file and the selection, so a job config is reproducible.
    """
    settings = _config(config)
    tasks = _selected_tasks(settings, _selection(task, suite, tasks_file, category, difficulty, limit))
    try:
        plans = plan_jobs(
            settings,
            [path.name for path in tasks],
            job_prefix=job_prefix,
            attempts=attempts,
            jobs_dir=jobs_dir,
            n_concurrent_trials=n_concurrent,
            n_concurrent_agents=n_concurrent_agents,
            max_retries=max_retries,
        )
    except JobPlanError as error:
        raise typer.BadParameter(str(error)) from error

    if out_dir is None:
        for index, plan in enumerate(plans):
            if index:
                typer.echo("---")
            typer.echo(plan.to_yaml().rstrip())
        return

    for plan, path in zip(plans, write_job_configs(plans, _at_root(out_dir))):
        typer.echo(
            f"{_show(path)}  {plan.agent} ({plan.model})  "
            f"{len(plan.variants)} condition(s) x {len(plan.tasks)} task(s) "
            f"x {plan.config['n_attempts']} attempt(s) = "
            f"{plan.n_cells * plan.config['n_attempts']} trial(s)"
        )


# ---------------------------------------------------------------------------
# Environment and setup
# ---------------------------------------------------------------------------
STATUS_MARK = {"ok": "ok  ", "warn": "warn", "fail": "FAIL"}


@app.command()
def doctor(
    sources: Path = SOURCES_OPTION,
    strict: bool = typer.Option(False, help="Exit non-zero on a warning as well as a failure."),
) -> None:
    """Check whether this machine can run an experiment. Changes nothing.

    Every check names the command that fixes it, so the output is a to-do list
    rather than a verdict.
    """
    root = _root()
    checks = run_checks(root, _at_root(sources))
    for check in checks:
        line = f"{STATUS_MARK[check.status]}  {check.name:26s} {check.detail}"
        typer.echo(line)
        if check.fix and check.status != "ok":
            typer.echo(f"      fix: {check.fix}")
    if in_container():
        typer.echo("note  running inside a container; docker-in-docker is not supported")

    severity = worst(checks)
    counts = {level: sum(1 for check in checks if check.status == level) for level in ("ok", "warn", "fail")}
    typer.echo(f"\n{counts['ok']} ok, {counts['warn']} warning(s), {counts['fail']} failure(s)")
    if severity == "fail" or (strict and severity == "warn"):
        raise typer.Exit(code=1)


@app.command()
def setup(
    sources: Path = SOURCES_OPTION,
    only: list[str] = typer.Option(None, "--only", help="Source id; repeat to limit the fetch."),
    force: bool = typer.Option(False, help="Re-fetch even when a source is already at its pin."),
    skip_credentials: bool = typer.Option(False, help="Do not write the config/local.env template."),
) -> None:
    """Materialise every pinned source, then write the credentials template.

    Idempotent: a source already at its pin is left alone. An `optional` source
    that cannot be fetched is reported and skipped, so a colleague without access
    to a private toolkit can still set the framework up.
    """
    root = _root()
    sources_path = _at_root(sources)
    try:
        declared = load_sources(sources_path)
    except SourceError as error:
        raise typer.BadParameter(str(error), param_hint="--sources") from error

    wanted = set(only or ())
    unknown = wanted - {source.id for source in declared}
    if unknown:
        raise typer.BadParameter(f"unknown source id(s): {', '.join(sorted(unknown))}", param_hint="--only")
    selected = [source for source in declared if not wanted or source.id in wanted]

    failures: list[str] = []
    for source in selected:
        typer.echo(f"{source.kind:11s} {source.id} ...")
        try:
            result = fetch_source(source, force=force)
        except SourceError as error:
            failures.append(f"{source.id}: {error}")
            typer.echo(f"  FAIL  {error}")
            continue
        typer.echo(f"  {result.status:11s} {result.detail}")

    if not skip_credentials:
        path, written = credentials_template(root)
        state = "written" if written else "present"
        typer.echo(f"credentials  {state}: {_show(path)}")
        if written:
            typer.echo("  fill it with `claude setup-token`; it is git-ignored and mode 600")

    if failures:
        typer.echo("\nrequired sources failed:")
        for failure in failures:
            typer.echo(f"  {failure}")
        raise typer.Exit(code=1)
    typer.echo("\nsetup complete — run `hmb doctor` to confirm, then `hmb catalogue --suite balanced`")


@app.command("sources")
def sources_status(sources: Path = SOURCES_OPTION) -> None:
    """List every pinned source and whether it is present at its pin."""
    try:
        declared = load_sources(_at_root(sources))
    except SourceError as error:
        raise typer.BadParameter(str(error), param_hint="--sources") from error
    for source in declared:
        pin = (source.ref or "-")[:12]
        flags = ",".join(filter(None, ["optional" if source.optional else "", "vendored" if source.vendored else ""]))
        typer.echo(
            f"{source.state():9s} {source.kind:11s} {source.id:16s} {pin:13s} "
            f"{_show(source.dest)}{'  [' + flags + ']' if flags else ''}"
        )


SCREEN_STAGES = ("solvability", "baseline", "all", "report")


def _run_harbor(config_path: Path, env_file: Path | None) -> int:
    command = ["harbor", "run", "-c", str(config_path)]
    environment = dict(os.environ)
    if env_file is not None and env_file.is_file():
        command += ["--env-file", str(env_file)]
        environment.update(read_env_file(env_file))
    typer.echo("$ " + " ".join(command))
    return subprocess.run(command, env=environment).returncode


@app.command("screen")
def screen_command(
    config: Path = CONFIG_OPTION,
    task: list[str] = TASK_OPTION,
    suite: list[str] = SUITE_OPTION,
    tasks_file: Path | None = TASKS_FILE_OPTION,
    category: list[str] = CATEGORY_OPTION,
    difficulty: list[str] = DIFFICULTY_OPTION,
    limit: int | None = LIMIT_OPTION,
    stage: str = typer.Option(
        "all", help=f"Which stage to run: {', '.join(SCREEN_STAGES)}. `report` runs nothing."
    ),
    job_prefix: str = typer.Option("screen", help="Job name prefix for the screen's own jobs."),
    jobs_dir: Path = typer.Option(Path("jobs"), help="Where Harbor writes the screen's jobs."),
    attempts: int = typer.Option(1, min=1, help="Baseline trials per task."),
    n_concurrent: int = typer.Option(DEFAULT_N_CONCURRENT_TRIALS, min=1),
    n_concurrent_agents: int = typer.Option(DEFAULT_N_CONCURRENT_AGENTS, min=1),
    env_file: Path = typer.Option(Path("config/local.env"), help="Credentials for the baseline stage."),
    out: Path | None = typer.Option(None, help="Write the surviving task list here."),
    dry_run: bool = typer.Option(False, help="Write the job configs and print the commands only."),
) -> None:
    """Decide which tasks can discriminate, before spending a matrix on them.

    Two stages. `solvability` runs `oracle` and `nop` over each task's baseline
    variant and spends no tokens: the oracle must score 1.0, or the task or its
    verifier is broken, and `nop` must score 0.0, or the task passes without any
    work. `baseline` then spends one bare-agent trial per task and drops the
    tasks it already passes — a task every condition passes carries no
    information about the comparison and still costs a full trial in every cell.
    """
    if stage not in SCREEN_STAGES:
        raise typer.BadParameter(f"stage must be one of {', '.join(SCREEN_STAGES)}")
    settings = _config(config)
    tasks = [
        path.name
        for path in _selected_tasks(
            settings, _selection(task, suite, tasks_file, category, difficulty, limit)
        )
    ]
    missing = [name for name in tasks if not (settings.generated_root / "baseline" / name).is_dir()]
    if missing:
        raise typer.BadParameter(
            f"generate the baseline variants first, e.g. {missing[0]}: "
            f"hmb generate --config {_show(_at_root(config))} ..."
        )

    agents = sorted({cell["agent"] for cell in settings.matrix})
    if len(agents) != 1:
        raise typer.BadParameter(
            "the screen spends its baseline trials on one agent; this matrix declares "
            f"{', '.join(agents)}. Screen with a single-agent configuration."
        )
    agent = agents[0]
    jobs_root = _at_root(jobs_dir)
    plan_dir = jobs_root / f"{job_prefix}-plan"
    plan_dir.mkdir(parents=True, exist_ok=True)

    try:
        planned: list[tuple[str, dict]] = []
        if stage in ("solvability", "all"):
            planned.append(
                (
                    SOLVABILITY_SUFFIX,
                    solvability_job(
                        tasks,
                        job_name=f"{job_prefix}-{SOLVABILITY_SUFFIX}",
                        jobs_dir=jobs_dir,
                        n_concurrent_trials=n_concurrent,
                    ),
                )
            )
        if stage in ("baseline", "all"):
            planned.append(
                (
                    BASELINE_SUFFIX,
                    baseline_job(
                        tasks,
                        job_name=f"{job_prefix}-{BASELINE_SUFFIX}",
                        jobs_dir=jobs_dir,
                        agent=agent,
                        model=settings.models[agent],
                        n_concurrent_trials=n_concurrent,
                        n_concurrent_agents=n_concurrent_agents,
                        n_attempts=attempts,
                    ),
                )
            )
    except ScreenError as error:
        raise typer.BadParameter(str(error)) from error

    for suffix, job in planned:
        path = plan_dir / f"{job_prefix}-{suffix}.yaml"
        path.write_text(yaml.safe_dump(job, sort_keys=False), encoding="utf-8")
        typer.echo(f"{_show(path)}  {len(tasks)} task(s)")
        if dry_run:
            continue
        if (jobs_root / f"{job_prefix}-{suffix}").is_dir():
            typer.echo(f"--> {job_prefix}-{suffix} exists; leaving it in place. "
                       f"Resume it with `hmb resume {_show(jobs_root / f'{job_prefix}-{suffix}')}`.")
            continue
        # The token-free stage needs no credentials; the baseline stage does.
        code = _run_harbor(path, _at_root(env_file) if suffix == BASELINE_SUFFIX else None)
        if code != 0:
            typer.echo(f"warn  {job_prefix}-{suffix} exited {code}; the verdicts below may be partial.")

    if dry_run:
        return

    screens = read_screen(jobs_root, tasks, job_prefix=job_prefix, baseline_agent=agent)
    kept = 0
    for entry in screens:
        verdict, reason = entry.verdict()
        kept += verdict == INCLUDE
        oracle = "-" if entry.oracle is None else f"{entry.oracle:.2f}"
        nop = "-" if entry.nop is None else f"{entry.nop:.2f}"
        base = (
            "-"
            if not entry.baseline_rewards
            else f"{entry.baseline_passes}/{len(entry.baseline_rewards)}"
        )
        typer.echo(f"  {verdict:8s} {entry.task:34s} oracle={oracle} nop={nop} baseline={base}  {reason}")
    undecided = sum(1 for entry in screens if entry.verdict()[0] == UNKNOWN)
    typer.echo(f"{kept} of {len(screens)} task(s) can discriminate; {undecided} undecided.")

    if out is not None:
        destination = _at_root(out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            render_task_file(
                screens,
                config_name=_show(_at_root(config)),
                job_prefix=job_prefix,
                generated_at=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
            ),
            encoding="utf-8",
        )
        typer.echo(f"task set -> {_show(destination)}")


@app.command("resume")
def resume_command(
    job_dir: Path = typer.Argument(..., help="The Harbor job directory to resume, in place."),
    recharged: bool = typer.Option(
        False, help="Also re-run ApiUsageLimitError trials; say this after recharging the account."
    ),
    filter_type: list[str] = typer.Option(
        None, "--filter", help="Additional exception type to re-run; must be infrastructure or transient."
    ),
    env_file: Path = typer.Option(
        Path("config/local.env"), help="Credentials to export; `harbor job resume` has no --env-file."
    ),
    dry_run: bool = typer.Option(False, help="Print the classification and the harbor command only."),
) -> None:
    """Re-run only the trials that failed for reasons unrelated to the task.

    A bare `harbor job resume` accepts a failed trial as a result, so a
    rate-limited trial keeps a permanent 0.0 reward that reads like a finding.
    This classifies every trial first, then passes an explicit, bounded filter:
    a genuine task failure can never be laundered into a retry.
    """
    job_dir = _at_root(job_dir)
    try:
        check_job_dir(job_dir)
        states = classify_trials(job_dir)
        filters = resume_filters(states, extra=tuple(filter_type or ()), recharged=recharged)
    except ResumeError as error:
        raise typer.BadParameter(str(error)) from error

    counts = breakdown(states)
    typer.echo(f"{len(states)} trial(s) in {_show(job_dir)}")
    for name, count in counts.items():
        mark = "re-run" if name in filters else "keep  "
        typer.echo(f"  {mark}  {name:28s} {count:>3}")
    if counts.get(UNREADABLE) or counts.get(NO_RESULT):
        typer.echo(
            "note  Harbor skips a trial it cannot read: the directory survives every "
            "filter and is re-run beside it. Delete those directories by hand."
        )
    if not filters:
        typer.echo("nothing to re-run.")
        return

    command = ["harbor", "job", "resume", "-p", str(job_dir)]
    for name in filters:
        command += ["-f", name]
    typer.echo("$ " + " ".join(command))
    if dry_run:
        return

    environment = dict(os.environ)
    env_path = _at_root(env_file)
    if env_path.is_file():
        environment.update(read_env_file(env_path))
    else:
        typer.echo(f"warn  {_show(env_path)} not found; resuming with the ambient environment.")

    completed = subprocess.run(command, env=environment)
    raise typer.Exit(completed.returncode)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
@app.command("report")
def report_command(
    jobs_dir: Path = typer.Option(Path("jobs"), help="Where Harbor wrote its job output."),
    pattern: str = typer.Option("*", help="Glob over job names, e.g. 'prog16-*'."),
    md_out: Path | None = typer.Option(None, help="Write the markdown comparison here."),
    json_out: Path | None = typer.Option(None, help="Write the machine-readable summary here."),
) -> None:
    """Aggregate trial results into a comparison table and a JSON summary."""
    try:
        markdown, trials = write_report(
            _at_root(jobs_dir),
            pattern,
            _at_root(md_out) if md_out else None,
            _at_root(json_out) if json_out else None,
        )
    except FileNotFoundError as error:
        raise typer.BadParameter(str(error), param_hint="--jobs-dir") from error

    if md_out:
        typer.echo(f"{len(trials)} trial(s) matching {pattern!r} -> {_show(_at_root(md_out))}")
    else:
        typer.echo(markdown)
    if json_out:
        typer.echo(f"summary -> {_show(_at_root(json_out))}")


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
@experiment_app.command("new")
def experiment_new(
    name: str = typer.Argument(..., help="Experiment name; becomes the config, task file and job prefix."),
    toolkit: list[str] = typer.Option(None, "--toolkit", help="Condition id; repeat for several."),
    agent: list[str] = typer.Option(None, "--agent", help="Agent id; repeat for several."),
    suite: list[str] = SUITE_OPTION,
    task: list[str] = TASK_OPTION,
    category: list[str] = CATEGORY_OPTION,
    difficulty: list[str] = DIFFICULTY_OPTION,
    limit: int | None = LIMIT_OPTION,
    config: Path = CONFIG_OPTION,
    force: bool = typer.Option(False, help="Overwrite an existing scenario of this name."),
) -> None:
    """Scaffold `config/experiments.<name>.yaml` and `config/tasks-<name>.txt`.

    Any task-selection flag resolves now and is written out as explicit ids, so
    the experiment records the task set it measured rather than a query that can
    drift when the task-suite pin moves.
    """
    root = _root()
    toolkits = list(toolkit or ["demo-kit"])
    agents = list(agent or ["claude-code"])

    tasks: list[str] = []
    if suite or task or category or difficulty or limit:
        settings = _config(config)
        selection = _selection(task, suite, None, category, difficulty, limit)
        tasks = [path.name for path in _selected_tasks(settings, selection)]

    try:
        scaffold = new_experiment(root, name, toolkits, agents, tasks, force=force)
    except ScaffoldError as error:
        raise typer.BadParameter(str(error)) from error

    typer.echo(f"config      {_show(scaffold.config)}")
    typer.echo(f"task set    {_show(scaffold.tasks_file)}  ({len(tasks) or 'no'} task ids)")
    typer.echo("")
    typer.echo("next:")
    typer.echo(f"  hmb catalogue --config {_show(scaffold.config)} --tasks-file {_show(scaffold.tasks_file)}")
    typer.echo(f"  hmb generate  --config {_show(scaffold.config)} --tasks-file {_show(scaffold.tasks_file)} --force")
    typer.echo(f"  hmb validate  --config {_show(scaffold.config)} --tasks-file {_show(scaffold.tasks_file)}")
    typer.echo(f"  hmb preflight --config {_show(scaffold.config)} --tasks-file {_show(scaffold.tasks_file)}")
    typer.echo(f"  ./scripts/run-pilot-experiment.sh --config {_show(scaffold.config)} \\")
    typer.echo(f"      --tasks-file {_show(scaffold.tasks_file)} --job-prefix {name} --attempts 1 --dry-run")


@experiment_app.command("list")
def experiment_list() -> None:
    """List the experiment configurations in this checkout."""
    root = _root()
    configs = sorted((root / "config").glob("experiments*.yaml"))
    if not configs:
        typer.echo("no experiment configurations found under config/")
        return
    for path in configs:
        try:
            settings = load_config(path)
        except (OSError, KeyError, TypeError, ValueError) as error:
            typer.echo(f"{path.name:44s} unreadable: {error}")
            continue
        conditions = ",".join(sorted(settings.toolkits)) or "-"
        typer.echo(
            f"{path.name:44s} {len(settings.matrix)} cell(s)  "
            f"repetitions={settings.repetitions}  conditions={conditions}"
        )


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
@analysis_app.command("extract")
def analysis_extract(
    pattern: str = typer.Option(..., help="Glob over job names, e.g. 'prog16-*'."),
    jobs_dir: Path = typer.Option(Path("jobs"), help="Where Harbor wrote its job output."),
    out_dir: Path = typer.Option(Path("results/analysis/data"), help="Where the CSV tables are written."),
    catalogue_json: Path = typer.Option(
        Path("results/task_catalogue.json"),
        help="Task metadata to join; write it with `hmb catalogue --json-out`.",
    ),
) -> None:
    """Derive the tidy per-trial, per-test, per-step and per-tool-call tables."""
    root = _root()
    try:
        tables = extract_all(_at_root(jobs_dir), pattern, _at_root(catalogue_json), root=root)
    except FileNotFoundError as error:
        raise typer.BadParameter(str(error), param_hint="--pattern") from error
    written = write_csvs(_at_root(out_dir), tables)
    for name, path in written.items():
        typer.echo(f"{name:11s} {len(tables[name]):6d} rows -> {_show(path)}")


@analysis_app.command("init")
def analysis_init(
    name: str = typer.Argument(..., help="Analysis name; becomes results/analysis-<name>/."),
    pattern: str = typer.Option(..., help="Glob over job names this analysis covers."),
    extract: bool = typer.Option(True, help="Also derive the tables now."),
    force: bool = typer.Option(False, help="Overwrite an existing notebook of this name."),
) -> None:
    """Scaffold an analysis notebook for a finished run, and fill its tables."""
    root = _root()
    try:
        scaffold = new_analysis(root, name, pattern, force=force)
    except ScaffoldError as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(f"notebook  {_show(scaffold.notebook)}")

    if extract:
        try:
            tables = extract_all(
                root / "jobs", pattern, root / "results" / "task_catalogue.json", root=root
            )
        except FileNotFoundError as error:
            typer.echo(f"warn  no tables written: {error}")
        else:
            write_csvs(scaffold.directory / "data", tables)
            typer.echo(f"tables    {len(tables['trials'])} trials -> {_show(scaffold.directory / 'data')}")

    typer.echo("")
    typer.echo("next:")
    typer.echo("  uv sync --group analysis")
    typer.echo(f"  uv run --group analysis jupyter lab {_show(scaffold.notebook)}")
