"""Tests for the setup path: pinned sources, environment checks, scaffolding.

The fetch tests use a real local git repository over `file://`, so the code path
under test is the one that runs against GitHub — clone, pin verification, copy —
without needing the network.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from harbor_methodology_bench import repo
from harbor_methodology_bench.doctor import check_credentials, run_checks, worst
from harbor_methodology_bench.scaffold import (
    ScaffoldError,
    check_name,
    credentials_template,
    new_analysis,
    new_experiment,
    render,
)
from harbor_methodology_bench.sources import (
    SourceError,
    fetch_source,
    load_sources,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"},
    )
    return result.stdout.strip()


def make_upstream(tmp_path: Path, files: dict[str, str]) -> tuple[Path, str]:
    """A local git repository with one commit. Returns (path, sha)."""
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(["init", "-q", "-b", "main", "."], upstream)
    for name, content in files.items():
        path = upstream / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(["add", "-A"], upstream)
    git(["commit", "-q", "-m", "seed"], upstream)
    # Fetching a bare SHA is what `hmb setup` does; a local repository refuses it
    # unless told otherwise, exactly as a server would.
    git(["config", "uploadpack.allowReachableSHA1InWant", "true"], upstream)
    return upstream, git(["rev-parse", "HEAD"], upstream)


def sources_file(tmp_path: Path, body: str) -> Path:
    """A sources file inside a directory that looks like a checkout root."""
    config = tmp_path / "config"
    config.mkdir(parents=True, exist_ok=True)
    path = config / "sources.yaml"
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Pinned sources
# ---------------------------------------------------------------------------
def test_shipped_sources_file_parses() -> None:
    sources = load_sources(REPO_ROOT / "config" / "sources.yaml")
    ids = {source.id for source in sources}
    assert "terminal-bench" in ids, "the benchmark task suite must be pinned"
    assert any(source.vendored for source in sources), (
        "at least one toolkit must be vendored so the default configuration runs after cloning"
    )


def test_a_short_ref_is_rejected(tmp_path: Path) -> None:
    """An abbreviated SHA is ambiguous, and a pin that can drift is not a pin."""
    path = sources_file(tmp_path, "toolkits:\n  - id: k\n    repo: https://example.com/k.git\n    ref: abc1234\n")
    with pytest.raises(SourceError, match="40-character"):
        load_sources(path)


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    # A digits-only ref would be read as a YAML integer; use hex, as a real SHA is.
    sha = "a" * 40
    path = sources_file(
        tmp_path,
        f"toolkits:\n  - id: k\n    repo: https://e/k.git\n    ref: {sha}\n"
        f"  - id: k\n    repo: https://e/other.git\n    ref: {sha}\n",
    )
    with pytest.raises(SourceError, match="duplicate"):
        load_sources(path)


def test_fetch_toolkit_materialises_the_pin(tmp_path: Path) -> None:
    upstream, sha = make_upstream(tmp_path, {"CLAUDE.md": "method\n", ".claude/skills/s/SKILL.md": "x\n"})
    path = sources_file(
        tmp_path,
        f"toolkits:\n  - id: kit\n    repo: file://{upstream}\n    ref: {sha}\n    dest: toolkits/kit\n",
    )
    source = load_sources(path)[0]
    assert source.state() == "missing"

    result = fetch_source(source)
    assert result.status == "fetched"
    assert (source.dest / "snapshot" / "CLAUDE.md").read_text() == "method\n"
    assert (source.dest / "GIT_SHA").read_text().strip() == sha
    assert not (source.dest / "snapshot" / ".git").exists(), "a snapshot is content, not a working copy"
    assert source.state() == "ready"

    # Idempotent: a second call does no work.
    assert fetch_source(source).status == "up-to-date"


def test_fetch_task_suite_copies_only_task_directories(tmp_path: Path) -> None:
    upstream, sha = make_upstream(
        tmp_path,
        {
            "task-a/task.toml": "[task]\nname='a'\n",
            "task-a/instruction.md": "do a\n",
            "task-b/task.toml": "[task]\nname='b'\n",
            "docs/notes.md": "not a task\n",
            "README.md": "not a task\n",
        },
    )
    path = sources_file(
        tmp_path,
        f"task_suites:\n  - id: suite\n    repo: file://{upstream}\n    ref: {sha}\n"
        f"    dest: source-tasks/suite\n    layout: task-dirs-at-root\n",
    )
    source = load_sources(path)[0]
    result = fetch_source(source)

    assert result.status == "fetched"
    assert sorted(p.name for p in source.dest.iterdir() if p.is_dir()) == ["task-a", "task-b"]
    assert (source.dest / "task-a" / "instruction.md").is_file()
    assert not (source.dest / "docs").exists()


def test_a_wrong_pin_fails_rather_than_fetching_something_else(tmp_path: Path) -> None:
    upstream, _ = make_upstream(tmp_path, {"a": "1\n"})
    wrong = "b" * 40
    path = sources_file(
        tmp_path,
        f"toolkits:\n  - id: kit\n    repo: file://{upstream}\n    ref: {wrong}\n    dest: toolkits/kit\n",
    )
    with pytest.raises(SourceError):
        fetch_source(load_sources(path)[0])


def test_an_optional_source_is_skipped_not_fatal(tmp_path: Path) -> None:
    """A colleague without access to a private toolkit must still be able to set up."""
    path = sources_file(
        tmp_path,
        f"toolkits:\n  - id: private\n    repo: file://{tmp_path / 'nope'}\n"
        f"    ref: {'c' * 40}\n    dest: toolkits/private\n    optional: true\n",
    )
    result = fetch_source(load_sources(path)[0])
    assert result.status == "skipped"
    assert result.detail


def test_stale_content_is_reported(tmp_path: Path) -> None:
    upstream, sha = make_upstream(tmp_path, {"CLAUDE.md": "v1\n"})
    path = sources_file(
        tmp_path,
        f"toolkits:\n  - id: kit\n    repo: file://{upstream}\n    ref: {sha}\n    dest: toolkits/kit\n",
    )
    source = load_sources(path)[0]
    fetch_source(source)
    (source.dest / "GIT_SHA").write_text("d" * 40 + "\n", encoding="utf-8")
    assert source.state() == "stale"


# ---------------------------------------------------------------------------
# Repository root resolution
# ---------------------------------------------------------------------------
def test_root_is_found_from_a_subdirectory() -> None:
    assert repo.find_root(REPO_ROOT / "src" / "harbor_methodology_bench") == REPO_ROOT


def test_root_override_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(repo.ENV_VAR, str(REPO_ROOT))
    assert repo.find_root(tmp_path) == REPO_ROOT


def test_outside_a_checkout_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(repo.ENV_VAR, raising=False)
    with pytest.raises(repo.RootNotFound):
        repo.find_root(tmp_path)


# ---------------------------------------------------------------------------
# Environment checks
# ---------------------------------------------------------------------------
def test_doctor_reports_every_pinned_source() -> None:
    checks = run_checks(REPO_ROOT)
    names = {check.name for check in checks}
    assert "python" in names and "docker daemon" in names
    assert any(name.startswith("task-suite ") for name in names)
    assert worst(checks) in ("ok", "warn", "fail")


def test_every_failing_check_names_a_fix() -> None:
    """A check that reports a problem without a remedy is a dead end for the reader."""
    for check in run_checks(REPO_ROOT):
        if check.status != "ok":
            assert check.fix, f"{check.name} reports {check.status} with no fix"


def test_credentials_check_sees_placeholders(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    env = tmp_path / "config" / "local.env"
    env.write_text('CLAUDE_CODE_OAUTH_TOKEN="<paste-your-token>"\n', encoding="utf-8")
    env.chmod(0o600)
    assert check_credentials(tmp_path).status == "warn"

    env.write_text('CLAUDE_CODE_OAUTH_TOKEN="real-token"\n', encoding="utf-8")
    assert check_credentials(tmp_path).status == "ok"

    env.chmod(0o644)
    check = check_credentials(tmp_path)
    assert check.status == "warn" and "readable" in check.detail


# ---------------------------------------------------------------------------
# Scaffolding
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["Prog16", "with space", "../escape", "", "a" * 42])
def test_unsafe_experiment_names_are_rejected(name: str) -> None:
    """A name becomes a file name, a job prefix and a Docker tag."""
    with pytest.raises(ScaffoldError):
        check_name(name)


def test_new_experiment_writes_a_runnable_pair(tmp_path: Path) -> None:
    scaffold = new_experiment(tmp_path, "my-run", ["demo-kit"], ["claude-code"], ["task-a", "task-b"])
    config = scaffold.config.read_text()
    tasks = scaffold.tasks_file.read_text()

    assert "id: demo-kit" in config
    assert "{id: claude-code-baseline, agent: claude-code, toolkit: baseline}" in config
    assert "{id: claude-code-demo-kit, agent: claude-code, toolkit: demo-kit}" in config
    assert "task-a" in tasks and "task-b" in tasks
    assert "{{" not in config and "{{" not in tasks, "a placeholder survived rendering"


def test_new_experiment_refuses_to_overwrite(tmp_path: Path) -> None:
    """A scenario file is the record of what a run measured."""
    new_experiment(tmp_path, "my-run", ["demo-kit"], ["claude-code"])
    with pytest.raises(ScaffoldError, match="already exists"):
        new_experiment(tmp_path, "my-run", ["demo-kit"], ["claude-code"])
    new_experiment(tmp_path, "my-run", ["demo-kit"], ["claude-code"], force=True)


def test_new_experiment_needs_a_condition(tmp_path: Path) -> None:
    with pytest.raises(ScaffoldError, match="at least one toolkit"):
        new_experiment(tmp_path, "my-run", [], ["claude-code"])


def test_new_analysis_writes_a_valid_notebook(tmp_path: Path) -> None:
    scaffold = new_analysis(tmp_path, "my-run", "my-run-*")
    payload = json.loads(scaffold.notebook.read_text())
    assert payload["nbformat"] == 4
    source = "".join("".join(cell["source"]) for cell in payload["cells"])
    assert 'PATTERN = "my-run-*"' in source
    assert "{{" not in source
    assert (scaffold.directory / "data").is_dir() and (scaffold.directory / "figures").is_dir()


def test_unfilled_placeholder_is_an_error() -> None:
    with pytest.raises(ScaffoldError, match="unfilled"):
        render("experiment.yaml", {"NAME": "x"})


def test_credentials_template_is_written_once_and_kept_private(tmp_path: Path) -> None:
    path, written = credentials_template(tmp_path)
    assert written and path.is_file()
    assert path.stat().st_mode & 0o777 == 0o600

    path.write_text("CLAUDE_CODE_OAUTH_TOKEN=real\n", encoding="utf-8")
    path, written = credentials_template(tmp_path)
    assert not written, "an existing credentials file must never be overwritten"
    assert path.read_text() == "CLAUDE_CODE_OAUTH_TOKEN=real\n"
