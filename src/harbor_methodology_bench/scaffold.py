"""Scaffolding: turn a name into a runnable experiment or analysis.

The templates live beside this module as package data, so they ship with the
installed tool rather than being read out of a checkout. Placeholders are
`{{TOKEN}}` — deliberately not `$TOKEN`, because the templates contain shell and
YAML that use `$` for their own purposes.

Nothing here overwrites an existing file. A scenario is a file whose name is the
experiment's identity; silently rewriting one would rewrite the record of what a
past run measured.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent / "templates"
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


class ScaffoldError(RuntimeError):
    """A scaffold could not be written."""


def check_name(name: str) -> str:
    """Names become file names, job prefixes and image tags — keep them safe."""
    if not NAME_PATTERN.match(name):
        raise ScaffoldError(
            f"{name!r} is not a usable experiment name: use lower-case letters, digits and "
            "hyphens, starting with a letter or digit, at most 41 characters"
        )
    return name


def render(template: str, values: dict[str, str]) -> str:
    text = (TEMPLATE_DIR / template).read_text(encoding="utf-8")
    for token, value in values.items():
        text = text.replace(f"{{{{{token}}}}}", value)
    remaining = re.findall(r"\{\{([A-Z_]+)\}\}", text)
    if remaining:
        raise ScaffoldError(f"{template}: unfilled placeholders {sorted(set(remaining))}")
    return text


def _write(path: Path, text: str, force: bool) -> Path:
    if path.exists() and not force:
        raise ScaffoldError(f"{path} already exists; pass --force to overwrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@dataclass(frozen=True)
class ExperimentScaffold:
    name: str
    config: Path
    tasks_file: Path


def new_experiment(
    root: Path,
    name: str,
    toolkits: list[str],
    agents: list[str],
    tasks: list[str] | None = None,
    force: bool = False,
) -> ExperimentScaffold:
    """Write `config/experiments.<name>.yaml` and `config/tasks-<name>.txt`."""
    check_name(name)
    if not toolkits:
        raise ScaffoldError("an experiment needs at least one toolkit condition besides the baseline")

    toolkit_block = "\n".join(
        f"  - id: {toolkit}\n    snapshot: toolkits/{toolkit}/snapshot" for toolkit in toolkits
    )
    cells = [f"  - {{id: {agent}-baseline, agent: {agent}, toolkit: baseline}}" for agent in agents]
    cells += [
        f"  - {{id: {agent}-{toolkit}, agent: {agent}, toolkit: {toolkit}}}"
        for agent in agents
        for toolkit in toolkits
    ]

    config = _write(
        root / "config" / f"experiments.{name}.yaml",
        render("experiment.yaml", {"NAME": name, "TOOLKITS": toolkit_block, "MATRIX": "\n".join(cells)}),
        force,
    )
    tasks_file = _write(
        root / "config" / f"tasks-{name}.txt",
        render(
            "tasks.txt",
            {
                "NAME": name,
                "TASKS": "\n".join(tasks)
                if tasks
                else "# no tasks selected yet — add ids here, one per line",
            },
        ),
        force,
    )
    return ExperimentScaffold(name, config, tasks_file)


@dataclass(frozen=True)
class AnalysisScaffold:
    name: str
    directory: Path
    notebook: Path


def new_analysis(root: Path, name: str, pattern: str, force: bool = False) -> AnalysisScaffold:
    """Write `results/analysis-<name>/<name>_analysis.ipynb` from the template."""
    check_name(name)
    directory = root / "results" / f"analysis-{name}"
    notebook = directory / f"{name}_analysis.ipynb"
    text = render(
        "analysis.ipynb",
        {
            "PATTERN": pattern,
            "NOTEBOOK": str(notebook.relative_to(root)),
        },
    )
    _write(notebook, text, force)
    (directory / "data").mkdir(parents=True, exist_ok=True)
    (directory / "figures").mkdir(parents=True, exist_ok=True)
    return AnalysisScaffold(name, directory, notebook)


def credentials_template(root: Path, force: bool = False) -> tuple[Path, bool]:
    """Write `config/local.env` if it is absent. Returns (path, written)."""
    path = root / "config" / "local.env"
    if path.exists() and not force:
        return path, False
    _write(path, render("local.env", {}), force=True)
    path.chmod(0o600)
    return path, True
