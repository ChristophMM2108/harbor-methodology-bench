#!/usr/bin/env python3
"""dfg-harness-plan — pre-flight check script (W37-3).

Run before invoking the planning skill to verify the substrate is
ready for a new wave/sprint. Returns exit 0 if planning may proceed,
non-zero with a clear diagnostic otherwise.

Checks (per kit/METHODOLOGY/08-planning-ceremony.md §Pre-flight):

1. `dfg validate` is clean
2. state.json.active_wave is consistent with last passed gate
3. No uncommitted plan.yaml changes
4. Latest gate file readable with verdict ∈ {PASS, DEFERRED, REJECTED}

Usage
-----

    python .claude/skills/dfg-harness-plan/check.py

    # Or from the skill at conversation time:
    uv run python .claude/skills/dfg-harness-plan/check.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(out.stdout.strip())


def _check_dfg_validate(repo: Path) -> tuple[bool, str]:
    """Run `dfg validate` (without --no-emit since that's not always available)."""
    result = subprocess.run(
        ["uv", "run", "dfg", "validate"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, f"dfg validate exited {result.returncode}: {result.stderr.strip()}"
    if "OK:" not in result.stdout and "OK:" not in result.stderr:
        return False, "dfg validate did not emit OK marker"
    return True, "dfg validate: OK"


def _check_dfg_index_verify(repo: Path) -> tuple[bool, str]:
    """Run `dfg index --verify` — BLOCKING per ADR-032 §D1.

    state.json must match the canonical projector. Pre-W39-2 this could
    drift silently; post-W39-2 it is single-authority and any drift is
    a real consistency violation.
    """
    result = subprocess.run(
        ["uv", "run", "dfg", "index", "--verify"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, "dfg index --verify: state.json matches projection"
    snippet = (result.stdout.strip() + " " + result.stderr.strip())[:400]
    return False, f"dfg index --verify exited {result.returncode}: {snippet}"


def _check_substrate_check(repo: Path) -> tuple[bool, str]:
    """Run `dfg substrate check --no-emit` — BLOCKING per ADR-032 §D2.

    Every closed-wave gate.md must have a matching WaveGatePass event.
    Audit substrate's whole job is being hostile to ledger-drift.
    """
    result = subprocess.run(
        ["uv", "run", "dfg", "substrate", "check", "--no-emit"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, "dfg substrate check: cross-coherence consistent"
    snippet = (result.stdout.strip() + " " + result.stderr.strip())[:400]
    return False, f"dfg substrate check exited {result.returncode}: {snippet}"


def _check_state_consistency(repo: Path) -> tuple[bool, str]:
    """active_wave shape + presence check (post-W39-4 informational only).

    Per ADR-032 §D1, the lower-bound monotonicity check (``active_wave
    >= max(passed gate)``) was DROPPED. The canonical state-vs-events
    check is `dfg index --verify` (above). This validator only confirms
    state.json has a parseable active_wave field.
    """
    state_path = repo / ".dfg" / "state.json"
    if not state_path.exists():
        return False, f"missing {state_path}"
    state = json.loads(state_path.read_text())
    active_wave = state.get("active_wave")
    if not active_wave:
        return False, "state.json missing active_wave"

    m = re.match(r"^W(\d+)$", active_wave)
    if not m:
        return False, f"active_wave='{active_wave}' does not match W<n>"
    aw = int(m.group(1))

    checkpoints_dir = repo / ".dfg" / "checkpoints"
    if not checkpoints_dir.is_dir():
        return True, f"active_wave=W{aw} (no checkpoints dir yet)"

    passed: list[int] = []
    for gate_file in checkpoints_dir.glob("W*-gate.md"):
        gm = re.match(r"^W(\d+)-gate\.md$", gate_file.name)
        if not gm:
            continue
        text = gate_file.read_text()
        if re.search(r"verdict:\s*(PASS|DEFERRED|REJECTED)\b", text):
            passed.append(int(gm.group(1)))
    if not passed:
        return True, f"active_wave=W{aw} (no passed gates yet)"

    max_passed = max(passed)
    return True, f"active_wave=W{aw}, max passed=W{max_passed} (informational)"


def _check_plan_uncommitted(repo: Path) -> tuple[bool, str]:
    """No uncommitted plan.yaml changes."""
    result = subprocess.run(
        ["git", "diff", "--name-only", ".dfg/plan.yaml"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        return False, "uncommitted changes in .dfg/plan.yaml — commit or stash first"
    return True, "plan.yaml: clean"


def _check_latest_gate(repo: Path) -> tuple[bool, str]:
    """Latest checkpoint file should have a recognized verdict."""
    checkpoints_dir = repo / ".dfg" / "checkpoints"
    if not checkpoints_dir.is_dir():
        return True, "no checkpoints dir yet (first sprint?)"
    gate_files = list(checkpoints_dir.glob("W*-gate.md"))
    if not gate_files:
        return True, "no gate files yet (first sprint?)"

    def _wave_num(p: Path) -> int:
        m = re.match(r"^W(\d+)-gate\.md$", p.name)
        return int(m.group(1)) if m else -1

    latest = max(gate_files, key=_wave_num)
    text = latest.read_text()
    if not re.search(r"verdict:\s*(PASS|DEFERRED|REJECTED)\b", text):
        return (
            False,
            f"latest gate {latest.name} has no recognized verdict "
            "(expected PASS / DEFERRED / REJECTED)",
        )
    return True, f"latest gate {latest.name}: verdict OK"


def main() -> int:
    repo = _repo_root()
    checks = (
        ("dfg validate", _check_dfg_validate),
        ("dfg index --verify", _check_dfg_index_verify),
        ("dfg substrate check", _check_substrate_check),
        ("state consistency", _check_state_consistency),
        ("plan.yaml clean", _check_plan_uncommitted),
        ("latest gate verdict", _check_latest_gate),
    )
    failures: list[str] = []
    for label, fn in checks:
        ok, msg = fn(repo)
        marker = "✓" if ok else "✗"
        print(f"{marker} {label}: {msg}")
        if not ok:
            failures.append(label)
    if failures:
        print()
        print(f"PRE-FLIGHT FAILED: {', '.join(failures)}")
        print("Halt planning ceremony and remediate before drafting units.")
        return 1
    print()
    print("PRE-FLIGHT OK: planning may proceed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
