from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .catalogue import build_catalogue, suite_members


def discover_tasks(source_root: Path) -> list[Path]:
    """Return Harbor tasks, requiring the task manifest in every directory."""
    if not source_root.is_dir():
        raise ValueError(f"source root does not exist: {source_root}")
    tasks = sorted(path for path in source_root.iterdir() if (path / "task.toml").is_file())
    if not tasks:
        raise ValueError(f"no Harbor tasks found under {source_root}")
    return tasks


@dataclass(frozen=True)
class TaskSelection:
    """A reproducible task subset.

    Filters compose: explicit ids and suites union first, then category and
    difficulty narrow the result, then `limit` truncates. Truncation is applied
    last and to a sorted list, so a selection is always reproducible from its
    arguments alone.
    """

    ids: tuple[str, ...] = ()
    suites: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    difficulties: tuple[str, ...] = ()
    limit: int | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.ids or self.suites or self.categories or self.difficulties or self.limit)


def read_task_ids(path: Path) -> tuple[str, ...]:
    """Read one task id per line, ignoring blanks and `#` comments."""
    lines = (line.split("#", 1)[0].strip() for line in path.read_text().splitlines())
    return tuple(line for line in lines if line)


def select_tasks(source_root: Path, selection: TaskSelection) -> list[Path]:
    """Resolve a selection against the task source, failing on unknown names."""
    tasks = discover_tasks(source_root)
    if selection.is_empty:
        return tasks

    by_id = {task.name: task for task in tasks}
    needs_metadata = bool(selection.suites or selection.categories or selection.difficulties)
    catalogue = build_catalogue(tasks) if needs_metadata else []
    facts_by_id = {facts.task_id: facts for facts in catalogue}

    chosen: set[str] = set()
    unknown = sorted(name for name in selection.ids if name not in by_id)
    if unknown:
        raise ValueError(f"unknown task id(s): {', '.join(unknown)}")
    chosen.update(selection.ids)
    for suite in selection.suites:
        chosen.update(suite_members(catalogue, suite))

    if not chosen:
        chosen = set(by_id)

    if selection.categories:
        allowed = set(selection.categories)
        chosen = {name for name in chosen if facts_by_id[name].category in allowed}
    if selection.difficulties:
        allowed = set(selection.difficulties)
        chosen = {name for name in chosen if facts_by_id[name].difficulty in allowed}

    selected = [by_id[name] for name in sorted(chosen)]
    if not selected:
        raise ValueError("task selection matched no tasks")
    if selection.limit:
        selected = selected[: selection.limit]
    return selected
