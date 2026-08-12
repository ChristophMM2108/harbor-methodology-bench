---
name: verifying-worktree-env
description: Pre-dispatch substrate check verifying the dispatched-session worktree's
  Python environment has all declared dependencies installed AND smoke-imports succeed.
  Catches the "uv extra not inherited" failure mode where the launcher reports outcome=success
  but the dispatched session can't even import its required SDK. Triggers before `dfg
  session dispatch` invocation, on worktree creation, after `uv sync`, and during
  cycle-2 critic protocols.
criticality: important
sdlc_category: Operations / Observability
loop_layer: L4-action
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill BEFORE invoking `dfg session dispatch <unit-id>` from
  a fresh worktree, AND inside cycle-2 critic protocols when reviewing dispatch outputs
  that may have suffered from venv isolation. The skill prevents the "no SDK installed"
  cascade observed in W23 cycle-1 (4 simultaneous dispatch failures, all silent).

  '
verified_at: 2026-05-06
forged_by: dfg-harness W23 cycle-1 4-way dispatch failure post-mortem
---
# Verifying Worktree Env — pre-dispatch substrate check

## Why this skill exists

W23 cycle-1 dispatch (4 units in parallel via `dfg session dispatch`):

```
W23-1 dispatched (pid 54764)  →  ❌ "no SDK installed"
W23-2 dispatched (pid 54767)  →  ❌ "no SDK installed"
W23-3 dispatched (pid 54775)  →  ❌ "no SDK installed"
W23-4 dispatched (pid ...)    →  ❌ "no SDK installed"
```

Root cause: `claude-agent-sdk` was installed in the **main repo's `.venv`** (`/Users/.../dfg-harness/.venv`). Each worktree at `/private/tmp/wXX-worktree/` has its OWN `.venv` (created by `uv` during `uv run`). The optional extra `[claude-agent]` was NOT inherited.

The launcher detected the missing SDK and exited cleanly with stderr "no SDK installed: neither 'anthropic' (with ANTHROPIC_API_KEY) nor 'claude_agent_sdk' is importable. Install one or invoke with --dry-run." But this stderr went to `/tmp/<unit>-dispatch.log` via `nohup`, invisible to the central session. **The substrate didn't surface the failure.**

Pattern: **uv worktree venvs do NOT inherit optional extras from the main venv.**

## Trigger conditions (substrate-evidence only — per §amendment-5)

Per ADR-019 §amendment-5 ("Trigger discipline: substrate-evidence over natural-language"), this skill activates on **deterministic substrate signals** (CLI invocation entry, filesystem state, manifest absence), never on prose.

Auto-trigger on ANY of:
1. **`dfg session dispatch <unit-id>`** invocation: the launcher's pre-flight checks call this skill's verifier; absence of `.dfg/sessions/.pre-dispatch/<unit>.json` (or stale receipt > 1h) AND `cwd` resolves to a path under `git worktree list` triggers the verification
2. **`git worktree add`** completion (detectable via post-add hook composition with W24-2 substrate cleanup): worktree path with no `.venv/` triggers the "first-uv-run-pending" precondition
3. **`uv run`** in a worktree creates `.venv/` — the launcher's pre-dispatch check then verifies `uv pip show <pkg>` against the unit contract's `read_contract.external_libs[]` package list
4. **Cycle-2 critic protocol** cross-references the dispatched session's manifest path (`/private/tmp/<unit>-worktree/`) against the pre-dispatch receipt; absence of receipt for a session whose manifest exists triggers a retro-active verification call

The trigger is the *invocation of dispatch from a worktree path* combined with *receipt absence/staleness* — not "the agent thinks dispatch is about to happen."

## Required steps

### Step 1 — Read the unit's required deps from contract

```yaml
# .dfg/agents/<unit>-<slug>.md frontmatter
read_contract:
  external_libs:
    - package: claude-agent-sdk
      ...
```

Extract the package name list.

### Step 2 — Verify each is installed in THIS worktree's venv

```bash
# In the worktree:
for pkg in <required-list>; do
  uv pip show $pkg > /dev/null 2>&1 || echo "MISSING: $pkg"
done
```

If any MISSING → STOP. Do not dispatch.

### Step 3 — Sync optional extras explicitly

If `pyproject.toml` declares the package as an optional extra:

```bash
# Find which extra contains the package:
EXTRA=$(grep -B1 "$pkg" pyproject.toml | head -1)

# Sync that extra in the worktree:
uv sync --extra <extra-name>
```

Repeat verification after sync.

### Step 4 — Smoke-import in the worktree's venv

```bash
# Use the worktree's venv explicitly:
source .venv/bin/activate
python -c "import <pkg>; print(f'{pkg.__name__} v{pkg.__version__ if hasattr(pkg, \"__version__\") else \"unknown\"}')"
```

Verify the import succeeds AND the version matches what `uv pip show` reported.

### Step 5 — For SDK-style packages, verify auth/CLI prereqs

The `verifying-external-package` skill (sister) classifies packages as `python_native` vs `subprocess-cli-bridge`. For subprocess-bridges:

```bash
# E.g., claude-agent-sdk depends on the `claude` CLI being on PATH:
which claude || echo "MISSING: claude CLI on PATH"

# AND on auth being configured:
[ -d ~/.claude ] && echo "OK ~/.claude exists" || echo "MISSING: ~/.claude not configured"

# AND on env vars when applicable:
[ -n "$ANTHROPIC_API_KEY" ] && echo "OK ANTHROPIC_API_KEY set" || echo "WARN: ANTHROPIC_API_KEY not set (only required for anthropic package fallback)"
```

### Step 6 — Emit pre-dispatch receipt

Before `dfg session dispatch` fires, write to `.dfg/sessions/.pre-dispatch/<unit>.json`:

```json
{
  "unit_id": "W23-1",
  "worktree": "/private/tmp/w23-1-worktree",
  "venv_check_at": "2026-05-06T...",
  "deps_verified": ["claude-agent-sdk@0.1.74"],
  "auth_verified": {"~/.claude": "exists", "ANTHROPIC_API_KEY": "absent-but-not-required"},
  "ready_to_dispatch": true
}
```

This receipt is the evidence the dispatched session inherits a working environment.

## Failure mode prevented

- Worktree dispatch succeeds with `outcome=success` but the dispatched session never actually invoked its real SDK
- Empty work + wasted tokens + invisible failure
- Operator surprise when probing post-hoc

## Composition with other primitives

- Pre-runs `verifying-external-package` skill (sister) for the pre-import discipline
- Composes with W24-2 substrate cleanup discipline: `dfg worktree clean` should prefer cleaning worktrees that NEVER passed pre-dispatch check
- Pairs with `dispatched-session-output-floor` (sister): prevents empty-session issue from a different direction (this skill catches BEFORE dispatch; that one catches AT completion)

## Test-of-skill (evaluation cases)

| Scenario | Expected behavior |
|---|---|
| Fresh worktree, all deps installed via `uv sync --extra claude-agent` | PASS, emit pre-dispatch receipt, allow dispatch |
| Fresh worktree, deps NOT synced (just `uv sync` without extras) | FAIL — refuse dispatch with clear error message |
| Worktree where `~/.claude/` doesn't exist but ANTHROPIC_API_KEY is set | PASS with warning (anthropic-only path) |
| Worktree where neither `~/.claude` nor `ANTHROPIC_API_KEY` exists | FAIL — neither SDK auth path is configured |
| Re-dispatch into a worktree that already has the receipt | Re-verify (don't trust stale receipt > 1h old) |

## Layer composition

- L4 (Action): this skill, fires once per dispatch
- L3 (Unit): contract template's `external_libs` field declares what to verify
- L2 (Wave): wave-launch ceremony runs this skill across all parallel dispatches at once
- L1 (Sprint): sprint-replan ceremony verifies main venv has the new sprint's deps
- L0 (Release): release smoke-test runs this against a clean checkout

## References

- W23 cycle-1 4-way dispatch failure — observed 2026-05-06 (4 silent failures via nohup)
- W22-8 ADR-019 §amendment-4 — the parent discipline (external lib citation)
- ADR-026 §dispatched-session-env — recursion-bound env vars (this skill verifies BEFORE recursion-bound applies)
- W24-2 ADR-031 — substrate cleanup; this skill is the inverse (pre-creation verification)
- https://docs.astral.sh/uv/concepts/projects/workspaces/ — uv worktree venv semantics (verified 2026-05-06)
