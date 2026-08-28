"""Pinned external sources: benchmark task suites and methodology toolkits.

Nothing external is vendored into this repository. `config/sources.yaml` records
a repository URL and an immutable commit for each input, and this module
materialises them on demand. A pin plus a URL is enough for anyone to re-derive
byte-identical content, which is what makes a result reproducible; a vendored
copy is provenance only its author can vouch for.

Every path is resolved from the repository root, never from the caller's working
directory, so a command means the same thing wherever it is run.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

SHA_LENGTH = 40
PROVENANCE_FILES = ("SOURCE", "GIT_SHA", "BRANCH", "VERSION")
# Names never copied out of a fetched tree: build detritus and the checkout's own
# git directory. A snapshot is content, not a working copy.
FETCH_EXCLUDES = (
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


class SourceError(RuntimeError):
    """A pinned source could not be resolved."""


@dataclass(frozen=True)
class Source:
    """One pinned external input."""

    id: str
    kind: str  # "task-suite" | "toolkit"
    dest: Path
    repo: str | None = None
    ref: str | None = None
    branch: str = "main"
    description: str = ""
    optional: bool = False
    vendored: bool = False
    layout: str = "tree"  # "tree" | "task-dirs-at-root"

    @property
    def snapshot_dir(self) -> Path:
        """Where content lands: toolkits keep it under `snapshot/`."""
        return self.dest / "snapshot" if self.kind == "toolkit" else self.dest

    def state(self) -> str:
        """`vendored`, `missing`, `stale` or `ready` — cheap, no network."""
        if self.vendored:
            return "vendored" if self.snapshot_dir.is_dir() else "missing"
        if not self.snapshot_dir.is_dir() or not any(self.snapshot_dir.iterdir()):
            return "missing"
        recorded = self.dest / "GIT_SHA"
        if self.ref and recorded.is_file():
            return "ready" if recorded.read_text().strip() == self.ref else "stale"
        return "ready"


def _validate_sha(value: str, source_id: str) -> str:
    sha = value.strip()
    if len(sha) != SHA_LENGTH or any(char not in "0123456789abcdef" for char in sha.lower()):
        raise SourceError(f"{source_id}: `ref` must be a full 40-character commit SHA, got {value!r}")
    return sha


def _source(item: dict, kind: str, root: Path) -> Source:
    if "id" not in item:
        raise SourceError(f"a {kind} entry has no `id`")
    source_id = str(item["id"])
    vendored = bool(item.get("vendored", False))
    default_dest = ("toolkits" if kind == "toolkit" else "source-tasks") + f"/{source_id}"
    dest = (root / str(item.get("dest", default_dest))).resolve()
    ref = None if vendored else _validate_sha(str(item.get("ref", "")), source_id)
    if not vendored and not item.get("repo"):
        raise SourceError(f"{source_id}: a non-vendored source needs a `repo` URL")
    return Source(
        id=source_id,
        kind=kind,
        dest=dest,
        repo=item.get("repo"),
        ref=ref,
        branch=str(item.get("branch", "main")),
        description=" ".join(str(item.get("description", "")).split()),
        optional=bool(item.get("optional", False)),
        vendored=vendored,
        layout=str(item.get("layout", "tree")),
    )


def load_sources(path: Path) -> list[Source]:
    """Parse `config/sources.yaml`. Task suites first, then toolkits."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as error:
        raise SourceError(f"cannot read {path}: {error}") from error
    root = path.parent.parent.resolve()
    sources = [_source(item, "task-suite", root) for item in data.get("task_suites") or []]
    sources += [_source(item, "toolkit", root) for item in data.get("toolkits") or []]
    if not sources:
        raise SourceError(f"{path} declares no task_suites and no toolkits")
    ids = [source.id for source in sources]
    duplicates = {name for name in ids if ids.count(name) > 1}
    if duplicates:
        raise SourceError(f"duplicate source ids: {', '.join(sorted(duplicates))}")
    return sources


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
def _git(args: list[str], cwd: Path, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _checkout_pin(repo: str, ref: str, branch: str, work: Path) -> None:
    """Shallow-fetch one commit into an empty scratch checkout.

    Fetching a bare SHA works on hosts that allow reachable-SHA1-in-want (GitHub
    does). Where it is refused, fall back to fetching the branch and checking the
    commit out of it — same result, more bytes.
    """
    for step in (["init", "-q", "."], ["remote", "add", "origin", repo]):
        result = _git(step, work)
        if result.returncode != 0:
            raise SourceError(f"git {' '.join(step)} failed: {result.stderr.strip()}")

    fetched = _git(["fetch", "-q", "--depth", "1", "origin", ref], work)
    if fetched.returncode != 0:
        fallback = _git(["fetch", "-q", "--depth", "50", "origin", branch], work)
        if fallback.returncode != 0:
            raise SourceError(
                f"cannot fetch {ref[:12]} or branch {branch} from {repo}: "
                f"{fetched.stderr.strip() or fallback.stderr.strip()}"
            )

    checked_out = _git(["checkout", "-q", ref], work)
    if checked_out.returncode != 0:
        checked_out = _git(["checkout", "-q", "FETCH_HEAD"], work)
    if checked_out.returncode != 0:
        raise SourceError(f"cannot check out {ref[:12]} from {repo}: {checked_out.stderr.strip()}")

    head = _git(["rev-parse", "HEAD"], work)
    if head.returncode != 0 or head.stdout.strip() != ref:
        raise SourceError(
            f"{repo} resolved to {head.stdout.strip()[:12] or 'nothing'}, not the pinned {ref[:12]}"
        )


def _copy_tree(src: Path, dest: Path) -> int:
    """Copy a fetched tree, dropping build detritus. Returns files written."""
    ignore = shutil.ignore_patterns(*FETCH_EXCLUDES)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, ignore=ignore, symlinks=True)
    return sum(1 for path in dest.rglob("*") if path.is_file())


def _copy_task_dirs(src: Path, dest: Path) -> int:
    """Copy every directory that holds a `task.toml`. Returns tasks written."""
    manifests = sorted(src.glob("*/task.toml"))
    if not manifests:
        raise SourceError(f"no */task.toml found in the fetched tree at {src}")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns(*FETCH_EXCLUDES)
    for manifest in manifests:
        shutil.copytree(manifest.parent, dest / manifest.parent.name, ignore=ignore, symlinks=True)
    return len(manifests)


def _write_provenance(source: Source, sha: str) -> None:
    """Record what was fetched, next to it, in the format `freeze-verify` reads."""
    source.dest.mkdir(parents=True, exist_ok=True)
    (source.dest / "SOURCE").write_text(f"{source.repo}\n", encoding="utf-8")
    (source.dest / "GIT_SHA").write_text(f"{sha}\n", encoding="utf-8")
    (source.dest / "BRANCH").write_text(f"{source.branch}\n", encoding="utf-8")
    (source.dest / "VERSION").write_text(f"{sha[:7]}\n", encoding="utf-8")


@dataclass(frozen=True)
class FetchResult:
    source: Source
    status: str  # "fetched" | "up-to-date" | "vendored" | "skipped"
    detail: str


def fetch_source(source: Source, force: bool = False) -> FetchResult:
    """Materialise one pinned source. Idempotent unless `force`."""
    if source.vendored:
        if source.snapshot_dir.is_dir():
            return FetchResult(source, "vendored", f"committed at {_relative(source.snapshot_dir)}")
        return FetchResult(source, "skipped", "declared vendored but no snapshot is committed")

    state = source.state()
    if state == "ready" and not force:
        return FetchResult(source, "up-to-date", f"{source.ref[:12]} already at {_relative(source.dest)}")

    assert source.repo is not None and source.ref is not None
    try:
        with tempfile.TemporaryDirectory(prefix="hmb-fetch-") as scratch:
            work = Path(scratch)
            _checkout_pin(source.repo, source.ref, source.branch, work)
            if source.layout == "task-dirs-at-root":
                count = _copy_task_dirs(work, source.snapshot_dir)
                unit = "tasks"
            else:
                count = _copy_tree(work, source.snapshot_dir)
                unit = "files"
        _write_provenance(source, source.ref)
    except SourceError as error:
        if source.optional:
            return FetchResult(source, "skipped", str(error))
        raise
    except (OSError, subprocess.SubprocessError) as error:
        if source.optional:
            return FetchResult(source, "skipped", str(error))
        raise SourceError(f"{source.id}: {error}") from error

    return FetchResult(source, "fetched", f"{count} {unit} at {source.ref[:12]}")


def _relative(path: Path) -> str:
    """Path relative to the repository root when possible; never absolute noise."""
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)
