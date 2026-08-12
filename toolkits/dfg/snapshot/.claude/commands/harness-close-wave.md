---
description: Wave-gate close discipline — verify all units MERGED, check CI, run retrospective.
---

# /harness-close-wave

You are closing a wave gate. This is **not** a merge action — merges happen
per-unit. This is the gate that says "this wave is done; the next one may
dispatch."

## Arguments

`/harness-close-wave <wave-id>` — e.g. `W2`, `W2-4a`.

## Process

1. **Verify all work units are `MERGED`.**

   ```bash
   grep "^| W<wave>-" PROVENANCE_INDEX.md | grep -v MERGED
   ```

   If any row is not `MERGED`, halt with a list of outstanding units.

2. **Verify gate criteria from `DFG.md`.** Read the wave's
   `**Wave-N gate (closes when all true):**` block. Every condition must
   be verifiable. Mark each ✓ / ✗.

3. **Run main-CI inspection.**

   ```bash
   gh run list --branch main --status failure --limit 5
   ```

   Any `failure` since the wave opened is a discipline gap. If found:
   - Halt the close
   - Surface the failure(s) with run id and head SHA
   - Operator decides: hotfix-then-close, or reopen the responsible unit

4. **Run the post-wave retrospective task.** Spawn an agent (or run
   inline) with the prompt from `kit/OUTER-LOOP-TASKS/post-wave-retrospective.md`.
   The retrospective produces:
   - `docs/RETROSPECTIVES/YYYY-MM-W<N>.md`
   - Follow-up GitHub issues, one per concrete lesson

5. **Confirm the retrospective doc was filed.** Check `git log main` for
   the retrospective commit; check `gh issue list` for the follow-up
   issues. Both must exist before the gate closes.

6. **Mark the wave closed.** In `PROVENANCE_INDEX.md`, transition the wave
   row to `CLOSED`. Reference the retrospective:

   `Closes wave W<N>; retrospective: docs/RETROSPECTIVES/YYYY-MM-W<N>.md`

## Output format

```
Wave W<N>: gate close
  Units MERGED:    <n / N>
  Gate criteria:   <m / M passed>
  Main CI:         <PASS | FAIL — n failures>
  Retrospective:   <path | NOT FILED>
  Follow-up issues: <count> (#<n>, #<n>, ...)

  Verdict: CLOSED | HALTED — <reason>
```

## Discipline

- **Do not close on amber.** If any of the four verification steps is
  amber (e.g., 4 / 5 units merged, 1 in-flight), halt. Wave gate is binary.
- **Never skip the retrospective.** A wave without retrospective doesn't
  close. The retrospective is part of the gate, not optional.
- **Don't silently auto-fix CI failures.** Surface them; let the operator
  decide whether to close or re-open units.

## When to invoke

Operator runs `/harness-close-wave <N>` once they see all units merged
and want to dispatch the next wave. The verification is the gate.
