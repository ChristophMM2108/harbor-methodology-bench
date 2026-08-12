---
description: Dispatch a wave. Reads DFG.md; spawns work-unit branches/PRs.
---

# /harness-run-wave

You are dispatching a wave from `DFG.md`. Each work unit gets a worktree, a
branch, and a dispatch prompt.

## Arguments

`/harness-run-wave <wave-id>` — e.g. `W2`, `W2-4a`. If omitted, dispatch the
next wave whose prerequisites are met.

## Process

1. **Read `DFG.md`.** Locate the wave section. Confirm prerequisites: every
   unit in the previous wave is `MERGED` in `PROVENANCE_INDEX.md`.

2. **Confirm dual-critic gate** (M / L sized work). Run
   `/harness-critic-problem` and `/harness-critic-assumption` against the
   wave plan. Both must score ≥ 3.5 / 5 with BS-score < 2.0. If not, halt
   and report.

3. **For each work unit in the wave (in parallel):**

   a. Run the `create-and-branch` recipe from `kit/WORKTREE-COOKBOOK/`.
      Worktree path: `<repo-parent>/<repo-name>-<wave>-<unit>`. Branch:
      `feat/w<wave>-<unit>-<slug>`.

   b. Append a row to `PROVENANCE_INDEX.md`:
      `| <unit-id> | <branch> | <worktree-path> | OPEN |`.

   c. Spawn a Task agent with:
      - **Working dir** = worktree path
      - **Prompt** = the unit's spec (from the issue body) plus the
        relevant `kit/SPEC-TEMPLATES/*` and the wave's gate criteria
      - **Pre-PR discipline** = run `make ci` and `/harness-pre-pr-checklist`
        before pushing
      - **PR discipline** = open with `kit/PR-TEMPLATES/feature-pr.md`
        body, link to issue, request critic review for M / L sized work

4. **Track progress.** Watch for PR opens, CI status, critic reviews. Do
   not auto-merge — wave gate close is its own step (see
   `/harness-close-wave`).

5. **On critic findings:** route fixes back to the responsible agent, not
   a wholesale re-dispatch. Allow up to 3 hardening cycles per unit before
   surfacing to operator.

## Output

Per unit log: id, worktree path, branch, PR number, status (OPEN /
IN_REVIEW / MERGED / BLOCKED). End with a wave-progress summary: total
units, in-flight, merged, blockers, next gate-check time.

## Discipline

- **Do not exceed declared parallelism.** If `DFG.md` says parallelism 4,
  dispatch 4 — not 5.
- **Do not skip the dual-critic gate** for M / L work, even under time
  pressure (see `kit/METHODOLOGY/04-dual-critic.md` anti-pattern).
- **Do not merge** as part of dispatch. Merging is a gate-close action.

## When to invoke

Operator runs `/harness-run-wave` once `DFG.md` is approved and the prior
wave is closed.
