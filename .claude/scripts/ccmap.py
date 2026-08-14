#!/usr/bin/env python3
"""
ccmap.py — on-demand Python dependency map, via Emmimal/context-compiler.

Prints the cheap, useful part of the compiler's output (which files matter and
how far away they are) rather than the expensive part (the full skeleton dump,
which runs to hundreds of thousands of tokens on a real repo). The dump is
written to a file only when asked for, so it can be read selectively.

Deliberately invoked — there is no hook. A PreToolUse hook cannot substitute
content into a Read result, and firing this on every read would add context
rather than save it.

Usage:
    python3 ccmap.py <target_file> [--max-hops N] [--repo-root PATH] [--dump PATH]

Requires a clone of https://github.com/Emmimal/context-compiler at
~/context-compiler, or CONTEXT_COMPILER_ROOT pointing elsewhere.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import warnings
from pathlib import Path

# Third-party sources routinely trip these while being parsed; they say nothing
# about the file we were asked about.
warnings.filterwarnings("ignore", category=SyntaxWarning)

CC_ROOT = Path(os.environ.get("CONTEXT_COMPILER_ROOT", Path.home() / "context-compiler"))

# Directory names to keep out of results. The upstream resolver's own exclusion
# set lists "venv" but not ".venv", so vendored code otherwise leaks in.
JUNK = {
    ".git", ".venv", "venv", ".env", ".tox", ".nox", "__pycache__", "node_modules",
    "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache", "site-packages",
    ".eggs", ".hatch",
}

SCAN_NOISY = 200  # above this, suggest narrowing the root


def git_root(start: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(start.parent), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def rel(path: Path, root: Path) -> Path:
    return path.relative_to(root) if path.is_relative_to(root) else path


def main() -> int:
    ap = argparse.ArgumentParser(description="Map a Python file's intra-repo dependencies.")
    ap.add_argument("target_file", type=Path, help="the .py file you're about to work on")
    ap.add_argument("--max-hops", type=int, default=2, help="call-hop depth (default: 2)")
    ap.add_argument("--repo-root", type=Path, default=None, help="scan root (default: git root)")
    ap.add_argument("--dump", type=Path, default=None, help="write the full compiled prompt here")
    args = ap.parse_args()

    if not CC_ROOT.is_dir():
        print(f"error: context-compiler not found at {CC_ROOT}", file=sys.stderr)
        print("clone it, or set CONTEXT_COMPILER_ROOT", file=sys.stderr)
        return 2

    target = args.target_file.resolve()
    if not target.is_file():
        print(f"error: {target} is not a file", file=sys.stderr)
        return 1
    if target.suffix != ".py":
        print(f"error: context-compiler is Python-only; {target.name} is not a .py file", file=sys.stderr)
        return 1

    root = (args.repo_root or git_root(target) or target.parent).resolve()
    if not target.is_relative_to(root):
        print(f"warning: {target} is outside scan root {root}", file=sys.stderr)

    # compiler.py and skeletonizer.py import each other by top-level name, so the
    # clone has to be importable rather than merely present on disk.
    sys.path.insert(0, str(CC_ROOT))
    try:
        from compiler import ContextCompiler, estimate_tokens
    except ImportError as exc:
        print(f"error: cannot import context-compiler from {CC_ROOT}: {exc}", file=sys.stderr)
        return 2

    try:
        compiled = ContextCompiler(root, max_hops=args.max_hops).compile(target)
    except (OSError, SyntaxError, ValueError) as exc:
        print(f"error: compile failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    clean = [e for e in compiled.entries if not any(p in JUNK for p in e.path.parts)]
    dropped = len(compiled.entries) - len(clean)

    print(f"repo root   : {root}")
    print(f"target      : {rel(target, root)}")
    print(f"max hops    : {args.max_hops}")
    print(f"scanned     : {compiled.total_repo_files} .py files")
    print(f"build time  : {compiled.build_seconds * 1000:.0f} ms")
    if dropped:
        print(f"filtered    : {dropped} vendored file(s) the upstream scan let through")
    if compiled.total_repo_files > SCAN_NOISY:
        print(f"note        : large scan — pass --repo-root <subdir> to skip vendored trees")
    print()

    tier2 = sorted((e for e in clean if e.tier == 2), key=lambda e: (e.hop_distance or 0, -e.tokens))
    kept_tokens = sum(e.tokens for e in clean)

    print(f"RELEVANT FILES ({len(tier2)} dependencies within {args.max_hops} hops)")
    if not tier2:
        print("  (none resolved — the target may have no intra-repo call deps,")
        print("   or the resolver missed them; check the warnings below)")
    for e in tier2:
        print(f"  hop {e.hop_distance}  {e.tokens:>6} tok  {rel(e.path, root)}")

    print()
    print(f"reading all of these would cost ~{kept_tokens} tokens across {len(clean)} files")

    diag = compiled.diagnostics
    if diag:
        warns = []
        if diag.dynamic_dispatch_files:
            warns.append(f"{len(diag.dynamic_dispatch_files)} file(s) use getattr() dynamic dispatch — deps may be MISSING")
        if diag.decorator_hint_files:
            warns.append(f"{len(diag.decorator_hint_files)} file(s) use event decorators — handlers may be MISSING")
        if diag.name_collisions:
            warns.append(f"{len(diag.name_collisions)} call name(s) ambiguous — list may include FALSE POSITIVES")
        if warns:
            print("\nRELIABILITY WARNINGS (this map is a hint, not ground truth):")
            for w in warns:
                print(f"  ! {w}")

    if args.dump:
        text = "\n\n".join(
            f"# ---- [{'FULL SOURCE' if e.tier == 1 else 'SKELETON'}] {e.path} ----\n{e.content}"
            for e in clean
        )
        args.dump.write_text(text, encoding="utf-8")
        print(f"\nfull compiled prompt -> {args.dump} ({estimate_tokens(text)} tokens)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
