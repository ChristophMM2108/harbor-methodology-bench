---
name: dispatched-session-output-floor
description: Pre-Completed gate for dispatched work-unit sessions. Asserts the dispatched
  session produced substantive output before the launcher emits SessionCompleted.
  Forces a minimum bar (≥1 file modified OR ≥1 commit on the branch OR a clear "no-op"
  rationale event). Triggers when a dispatched session is about to emit SessionCompleted,
  when wave-close discovers a session with outcome=success but zero substantive change,
  or during cycle-2 critic review of dispatch outputs.
criticality: important
sdlc_category: Testing / Verification
loop_layer: L4-action
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill INSIDE a dispatched session before it exits, AND in cycle-2
  critic protocols when reviewing a PR that came from a dispatched session. The skill
  prevents "outcome=success with zero work" failure mode (W23-3 hung dispatch, W24-3
  empty session).

  '
verified_at: 2026-05-06
forged_by: dfg-harness W23-3 hung dispatch + W24-3 empty session post-mortem
---
# Dispatched Session Output Floor — pre-Completed gate

## Why this skill exists

W23-3 cycle-1: dispatched session ran 33 minutes, hung, killed. 1 commit produced.
W24-3 cycle-1: dispatched session ran 6 minutes, exited cleanly with `outcome=success` and `events=SessionDispatched,Heartbeat,Turn,Completed` — but produced **ZERO files**.

Both passed the launcher's exit check. Both wasted enterprise-plan tokens. Both required central session to manually probe the worktree to discover the failure.

Pattern: **A dispatched session can `exit_code=0` while having done nothing.** The substrate doesn't catch this; only manual probe does.

## Trigger conditions (substrate-evidence only — per §amendment-5)

Per ADR-019 §amendment-5 ("Trigger discipline: substrate-evidence over natural-language"), this gate activates on **deterministic substrate signals** (event-emit attempt, manifest path, git state, PR author metadata), never on agent or operator prose.

Auto-trigger on ANY of:
1. **`_emit_session_completed()`** is about to be called by the launcher (`src/dfg_harness/orchestrator/launcher.py`) for a session whose `manifest.json` has `role: dispatched-step` — this skill's check runs as a pre-emit hook and converts a failing floor-check into a `SessionDegraded` event with `reason: output-floor-violated`
2. **PR author metadata + session manifest cross-ref** during cycle-2 critic protocol: when a PR's author commit-trailer matches a dispatched-session sid AND that session's `manifest.json` shows `outcome: success` but the PR's `git diff main..HEAD` is empty, the critic flags as BLOCKER
3. **Wave-close gate** (`dfg wave close <W>`) cross-references each unit's `SessionCompleted` event against `git log <wave-base>..HEAD --diff-filter=AM --name-only -- <unit-scope>`; empty diff with no `no-op-rationale.md` blocks the gate
4. **`dfg session probe <sid> --mode=summary`** (W23-4 protocol) calls into this skill's check function directly to report output-floor status

The trigger is the *attempt to emit `SessionCompleted`* — not a heuristic about how the session "feels." Diff-shape and manifest-path are the gate.

## Required outputs (the floor)

A dispatched session must produce AT LEAST ONE of:

### Floor-A: Substantive code change

```bash
# Inside the dispatched session, BEFORE emitting SessionCompleted:
NEW_FILES=$(git status --porcelain | grep -c "^??")
MOD_FILES=$(git status --porcelain | grep -c "^[ MARC]")
COMMITS=$(git log main..HEAD --oneline | wc -l)

# Pass condition: at least one of:
[ $NEW_FILES -gt 0 ] || [ $MOD_FILES -gt 0 ] || [ $COMMITS -gt 0 ]
```

If FAIL → do NOT emit SessionCompleted; emit `SessionDegraded` instead (W23-1) with `reason: output-floor-violated`.

### Floor-B: Explicit no-op rationale (operator-acceptable)

If the dispatched session decides the unit is genuinely a no-op (e.g., the work was already done in a prior dispatch), it MUST author a one-paragraph rationale committed to:

```
.dfg/sessions/<sid>/no-op-rationale.md
```

Format:
```
---
unit_id: <unit>
session_id: <sid>
decision_at: <ISO-timestamp>
decision: no-op
reason: |
  <Why the work was unnecessary. Cite specific evidence:
   prior PR number, prior commit sha, ADR section,
   or substrate state that made the work moot.>
---
```

This converts "empty session" from a silent failure into an auditable decision.

## Composition with other primitives

- This skill MUST run before `_emit_session_completed()` in `kit/hooks/launcher` invocation chain
- Compose with W23-1 `SessionDegraded` event: when floor fails, emit SessionDegraded with `reason: output-floor-violated`
- Compose with W23-4 probe protocol: `dfg session probe <sid> --mode=summary` should report output-floor status

## Cycle-2 critic protocol integration

When a critic reviews a PR authored by a dispatched session:

```
1. Look up the SessionCompleted event for the unit on events.jsonl
2. Read the manifest at .dfg/sessions/<sid>/
3. Cross-reference: did the session pass output-floor?
   - If FAIL but PR was opened anyway → critic flags as BLOCKER
   - If PASS → continue with critic protocol
4. If a no-op-rationale.md exists → critic must explicitly review and accept
```

## Test-of-skill (evaluation cases)

| Scenario | Expected behavior |
|---|---|
| Session modifies 5 files, commits 3 times | PASS Floor-A, emit SessionCompleted normally |
| Session reads files but writes none | FAIL Floor-A; require Floor-B rationale OR emit SessionDegraded |
| Session pivots mid-flight to "actually this is a no-op" | Author no-op-rationale.md, emit SessionCompleted with marker |
| Session crashes mid-tool-use | NO SessionCompleted emitted (already covered by launcher); skill not in path |
| W24-3-shape: 6 min, 0 files, no rationale | FAIL — emit SessionDegraded(output-floor-violated); cycle-2 critic flags |

## Layer composition

- L4 (Action): this skill, runs once per dispatched session before completion
- L3 (Unit): contract template adds expected_output_class field (code / docs / no-op)
- L2 (Wave): wave-close gate verifies all units passed output floor or have rationale
- L1 (Sprint): retro counts no-op rationales as a forward-debt signal
- L0 (Release): release-readiness audit no-op-count vs total dispatches

## References

- W23-3 retro (hung dispatch) — `dfg-harness/.dfg/retrospectives/W23/`
- W24-3 cycle-1 empty session — observed 2026-05-06
- W23-1 SessionDegraded annotation — sister skill that surfaces failures on the bus
- W23-4 session probe protocol — diagnostic surface for output-floor status
- ADR-026 §SessionCompleted — what this skill gates
