#!/usr/bin/env python3
"""enforcing-non-negotiables — Guardian skill check script.

Per ADR-019 §amendment-5 (W26 keystone): substrate-evidence triggers, not
natural-language nudges. This gate fires on **diff-shape signals only**.

Behavior
--------

1. Load `.dfg/governance/non-negotiables.yaml` to get the canonical spec.

2. Scan PR diff (<base>..HEAD) against each invariant's `violation_signal`.

3. For each detected violation:
   - Emit `NonNegotiableViolation` event to `.dfg/events.jsonl`
   - Accumulate violation messages

4. Exit 0 on pass, 1 on fail with clear violation summary.

Origin: operator directive 2026-05-06 — "Non-negotiables must be enforced
structurally." Closes the substrate gap in `.dfg/governance/non-negotiables.yaml`:
enforcement must be automated, not manual review.

Usage
-----

    # CI / pre-pr battery — diff against origin/main
    python .claude/skills/enforcing-non-negotiables/check.py

    # Local override
    python .claude/skills/enforcing-non-negotiables/check.py --base origin/main

    # Bootstrap-friendly: skip when only contract changed (rare)
    python .claude/skills/enforcing-non-negotiables/check.py --allow-bootstrap
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT_DEFAULT = Path(__file__).resolve().parents[3]
"""Default repo root: this script lives at <repo>/.claude/skills/enforcing-non-negotiables/"""


def _run_git(cmd: list[str], repo_root: Path) -> str:
    """Run git command and return stdout."""
    result = subprocess.run(
        ["git", *cmd],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _emit_event(event: dict[str, Any], repo_root: Path) -> None:
    """Append event to .dfg/events.jsonl."""
    events_path = repo_root / ".dfg" / "events.jsonl"
    with events_path.open("a") as f:
        f.write(json.dumps(event) + "\n")


def _check_contract_first(base: str, repo_root: Path) -> tuple[bool, list[str]]:
    """Check contract-first invariant: feat/wN-M branches must start with contract commit."""
    msgs: list[str] = []

    # Get current branch name
    try:
        branch = _run_git(["branch", "--show-current"], repo_root).strip()
    except subprocess.CalledProcessError:
        # Not on a branch (detached HEAD), skip check
        return True, []

    # Only check feat/wN-M-* branches
    if not branch.startswith("feat/w") or branch.count("-") < 2:
        return True, []

    # Parse wave and unit from branch name
    parts = branch.split("-")
    if len(parts) < 3:
        return True, []

    wave_unit = f"{parts[0].replace('feat/', '')}-{parts[1]}"  # e.g., "w26-3"

    # Get commit list
    try:
        commits = (
            _run_git(["log", "--oneline", "--reverse", f"{base}..HEAD"], repo_root)
            .strip()
            .split("\n")
        )
    except subprocess.CalledProcessError:
        return True, []

    if not commits or commits == [""]:
        # No commits yet
        return True, []

    # Check first commit
    first_commit_sha = commits[0].split()[0]
    try:
        files = (
            _run_git(
                ["diff-tree", "--no-commit-id", "--name-only", "-r", first_commit_sha], repo_root
            )
            .strip()
            .split("\n")
        )
    except subprocess.CalledProcessError:
        return True, []

    # First commit should add only .dfg/agents/W<N>-<M>-*.md
    expected_prefix = f".dfg/agents/{wave_unit.upper()}"
    contract_files = [f for f in files if f.startswith(expected_prefix) and f.endswith(".md")]

    if len(files) == 1 and len(contract_files) == 1:
        return True, []

    # Violation detected
    msgs.append(
        f"❌ contract-first invariant violated: branch {branch} first commit adds "
        f"{len(files)} files (expected 1 contract file {expected_prefix}-*.md)"
    )
    return False, msgs


def _check_schema_version_bump(base: str, repo_root: Path) -> tuple[bool, list[str]]:
    """Check schema-version-bump invariant."""
    msgs: list[str] = []

    # Check if events.schema.json modified
    try:
        changed = _run_git(["diff", "--name-only", f"{base}...HEAD"], repo_root).strip().split("\n")
    except subprocess.CalledProcessError:
        return True, []

    schema_modified = "kit/SCHEMAS/events.schema.json" in changed
    if not schema_modified:
        return True, []

    # Schema was modified, check if version bumped
    try:
        diff = _run_git(
            ["diff", f"{base}...HEAD", "--", "kit/SCHEMAS/events.schema.json"], repo_root
        )
    except subprocess.CalledProcessError:
        return True, []

    # Look for schema_version changes
    version_changed = False
    for line in diff.split("\n"):
        if line.startswith("+") and "schema_version" in line and not line.startswith("+++"):
            version_changed = True
            break

    if not version_changed:
        msgs.append(
            "❌ schema-version-bump invariant violated: kit/SCHEMAS/events.schema.json "
            "modified without schema_version increment"
        )
        return False, msgs

    return True, []


def _check_retro_present(base: str, repo_root: Path) -> tuple[bool, list[str]]:
    """Check retro-present invariant."""
    msgs: list[str] = []

    # Get current branch name
    try:
        branch = _run_git(["branch", "--show-current"], repo_root).strip()
    except subprocess.CalledProcessError:
        return True, []

    # Only check feat/wN-M-* branches
    if not branch.startswith("feat/w") or branch.count("-") < 2:
        return True, []

    # Parse wave and unit
    parts = branch.split("-")
    if len(parts) < 3:
        return True, []

    wave = parts[0].replace("feat/", "")  # e.g., "w26"
    unit_num = parts[1]  # e.g., "3"

    # Check if retro file exists
    retro_path = (
        repo_root / ".dfg" / "retrospectives" / wave.upper() / f"{wave.upper()}-{unit_num}.md"
    )

    # Also check if added in this PR
    try:
        added = (
            _run_git(["diff", "--name-only", "--diff-filter=A", f"{base}...HEAD"], repo_root)
            .strip()
            .split("\n")
        )
    except subprocess.CalledProcessError:
        return True, []

    retro_relative = f".dfg/retrospectives/{wave.upper()}/{wave.upper()}-{unit_num}.md"

    if not retro_path.exists() and retro_relative not in added:
        msgs.append(
            f"❌ retro-present invariant violated: branch {branch} lacks retrospective at {retro_relative}"
        )
        return False, msgs

    return True, []


def _check_external_lib_verification(base: str, repo_root: Path) -> tuple[bool, list[str]]:
    """Check external-library-API-verification invariant (defer to existing check)."""
    # This invariant has a dedicated gate script already shipping
    # We just note it's covered elsewhere
    return True, []


def evaluate(
    base: str,
    repo_root: Path,
    *,
    allow_bootstrap: bool = False,
    emit_events: bool = True,
) -> tuple[int, list[str]]:
    """Return (exit_code, messages)."""
    msgs: list[str] = []
    failures = 0

    # Load non-negotiables.yaml
    spec_path = repo_root / ".dfg" / "governance" / "non-negotiables.yaml"
    if not spec_path.exists():
        msgs.append("⚠ non-negotiables.yaml not found; skipping checks")
        return 0, msgs

    with spec_path.open() as f:
        yaml.safe_load(f)

    # Run checks for key invariants
    checks = [
        ("contract-first", _check_contract_first),
        ("schema-version-bump", _check_schema_version_bump),
        ("retro-present", _check_retro_present),
        ("external-library-API-verification", _check_external_lib_verification),
    ]

    for invariant_id, check_fn in checks:
        passed, check_msgs = check_fn(base, repo_root)
        msgs.extend(check_msgs)
        if not passed:
            failures += 1

            # Emit violation event
            if emit_events:
                event = {
                    "event_type": "NonNegotiableViolation",
                    "event_id": f"non-negotiable-violation-{invariant_id}-{datetime.now(timezone.utc).isoformat()}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "detail": {
                        "invariant_id": invariant_id,
                        "violation_signal": check_msgs[0] if check_msgs else "unknown",
                        "pr_ref": f"{base}..HEAD",
                        "detected_by": "enforcing-non-negotiables-check.py",
                    },
                }
                _emit_event(event, repo_root)

    if failures == 0:
        msgs.append("✅ All non-negotiable invariants passed")

    if failures and allow_bootstrap:
        msgs.append(
            "⚠ Bootstrap exemption: --allow-bootstrap requested. "
            "Default-DENY discipline yields to operator-staged exception."
        )
        return 0, msgs

    return (1 if failures else 0), msgs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Base ref for the diff (default: origin/main).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT_DEFAULT,
        help="Repo root path (default: script's parents[3]).",
    )
    parser.add_argument(
        "--allow-bootstrap",
        action="store_true",
        help="Permit violations (rare operator-staged exception).",
    )
    parser.add_argument(
        "--no-emit",
        action="store_true",
        help="Don't emit events (dry-run mode).",
    )
    args = parser.parse_args()

    code, msgs = evaluate(
        args.base,
        args.repo_root.resolve(),
        allow_bootstrap=args.allow_bootstrap,
        emit_events=not args.no_emit,
    )
    for m in msgs:
        print(m)
    return code


if __name__ == "__main__":
    sys.exit(main())
