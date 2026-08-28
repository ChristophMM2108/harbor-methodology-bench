"""Environment checks: is this machine able to run an experiment?

Every check answers one question, reports what it found, and names the command
that fixes it. Nothing here mutates the machine — `hmb setup` does that — so
`hmb doctor` is safe to run at any time, including in CI.

Severities: `ok` (usable), `warn` (usable, with a caveat that will bite later),
`fail` (an experiment cannot run).
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .sources import Source, load_sources

MIN_PYTHON = (3, 12)
MIN_FREE_GB = 20.0


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # "ok" | "warn" | "fail"
    detail: str
    fix: str = ""


def _run(args: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        return 127, str(error)
    return result.returncode, (result.stdout or result.stderr).strip()


def _first_line(text: str) -> str:
    return text.splitlines()[0].strip() if text.strip() else ""


def _tool(
    name: str,
    args: list[str],
    fix: str,
    severity: str = "fail",
    label: str | None = None,
) -> Check:
    """A command-line tool: present on PATH, and answering when asked its version."""
    title = label or name
    if shutil.which(name) is None:
        return Check(title, severity, f"`{name}` is not on PATH", fix)
    code, output = _run(args)
    if code != 0:
        return Check(title, severity, f"`{' '.join(args)}` exited {code}: {_first_line(output)}", fix)
    return Check(title, "ok", _first_line(output) or "present")


def check_python() -> Check:
    version = sys.version_info
    found = f"{version.major}.{version.minor}.{version.micro}"
    if (version.major, version.minor) < MIN_PYTHON:
        return Check(
            "python",
            "fail",
            f"{found}, below the required {MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
            "install a newer Python, or let uv manage it: `uv python install 3.12`",
        )
    return Check("python", "ok", found)


def check_docker() -> Check:
    """Docker must exist *and* its daemon must answer; a dead daemon is the common case."""
    if shutil.which("docker") is None:
        return Check("docker", "fail", "`docker` is not on PATH", "install Docker and start its daemon")
    code, output = _run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=30)
    if code != 0:
        return Check(
            "docker daemon",
            "fail",
            f"daemon not reachable: {_first_line(output)}",
            "start Docker; on Linux a broken bridge needs `sudo modprobe veth && sudo systemctl restart docker`",
        )
    return Check("docker daemon", "ok", f"server {_first_line(output)}")


def check_disk(root: Path) -> Check:
    """Task images are large; running out of disk mid-run wastes the whole run."""
    usage = shutil.disk_usage(root)
    free_gb = usage.free / 1024**3
    detail = f"{free_gb:.0f} GB free at {root}"
    if free_gb < MIN_FREE_GB:
        return Check(
            "disk space",
            "warn",
            f"{detail}, below the {MIN_FREE_GB:.0f} GB a multi-task image build usually needs",
            "free space, or `docker image prune` to drop old preflight images",
        )
    return Check("disk space", "ok", detail)


def check_credentials(root: Path) -> Check:
    """Agents authenticate inside the container from this file."""
    env_file = root / "config" / "local.env"
    if not env_file.is_file():
        return Check(
            "agent credentials",
            "warn",
            "config/local.env is absent, so no credentials are forwarded into containers",
            "`hmb setup` writes a template; fill it with `claude setup-token`",
        )
    text = env_file.read_text(encoding="utf-8", errors="replace")
    filled = [
        line.split("=", 1)[0]
        for line in text.splitlines()
        if "=" in line
        and not line.lstrip().startswith("#")
        and line.split("=", 1)[1].strip().strip('"').strip("'")
        and "<" not in line.split("=", 1)[1]
    ]
    mode = stat.S_IMODE(env_file.stat().st_mode)
    if not filled:
        return Check(
            "agent credentials",
            "warn",
            "config/local.env exists but every value is still a placeholder",
            "run `claude setup-token` and paste the token into config/local.env",
        )
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        return Check(
            "agent credentials",
            "warn",
            f"config/local.env is group/world readable (mode {mode:o}) and holds {len(filled)} value(s)",
            "`chmod 600 config/local.env`",
        )
    return Check("agent credentials", "ok", f"{len(filled)} value(s) set, mode {mode:o}")


def check_source(source: Source) -> Check:
    state = source.state()
    label = f"{source.kind} {source.id}"
    if state == "ready":
        return Check(label, "ok", f"at {(source.ref or '')[:12] or 'committed content'}")
    if state == "vendored":
        return Check(label, "ok", "vendored in this repository")
    if state == "stale":
        return Check(label, "warn", "present, but not at the pinned commit", "`hmb setup --force`")
    severity = "warn" if source.optional else "fail"
    detail = "not fetched" + (" (optional)" if source.optional else "")
    return Check(label, severity, detail, "`hmb setup`")


def run_checks(root: Path, sources_file: Path | None = None) -> list[Check]:
    """Every check, in the order a newcomer hits them."""
    checks = [
        check_python(),
        _tool("git", ["git", "--version"], "install git"),
        _tool("uv", ["uv", "--version"], "curl -LsSf https://astral.sh/uv/install.sh | sh"),
        check_docker(),
        _tool(
            "harbor",
            ["harbor", "--version"],
            "`uv tool install harbor`, or re-run `./bootstrap.sh`",
            label="harbor CLI",
        ),
        _tool(
            "claude",
            ["claude", "--version"],
            "install Claude Code — https://claude.com/claude-code",
            severity="warn",
            label="claude CLI",
        ),
        _tool(
            "codex",
            ["codex", "--version"],
            "install the Codex CLI, or run Claude-only experiments",
            severity="warn",
            label="codex CLI",
        ),
        check_disk(root),
        check_credentials(root),
    ]
    path = sources_file or (root / "config" / "sources.yaml")
    if path.is_file():
        checks += [check_source(source) for source in load_sources(path)]
    else:
        checks.append(Check("pinned sources", "fail", f"{path} is missing", "restore config/sources.yaml"))
    return checks


def worst(checks: list[Check]) -> str:
    for severity in ("fail", "warn"):
        if any(check.status == severity for check in checks):
            return severity
    return "ok"


def in_container() -> bool:
    """Cheap hint: benchmark agents sometimes run this from inside a container."""
    return Path("/.dockerenv").exists() or os.environ.get("container") is not None
