---
name: demo-checklist
description: Use when a task has more than two steps. Writes a numbered plan to PLAN.md, then verifies each step before moving to the next, and reports the evidence for each step at the end.
---

# demo-checklist

## When to use

Any task with more than two steps, or any task where a later step can silently
invalidate an earlier one.

## Procedure

1. **Enumerate.** Write `PLAN.md` with one numbered line per step. Each line
   must name the command or observation that will prove that step.
2. **Execute one step at a time.** After each step, run its proof command.
   Record the result next to the step in `PLAN.md`.
3. **Stop on a failed proof.** Fix the step before starting the next one. Do not
   accumulate unverified work.
4. **Close out.** Print each step with its evidence. Mark anything unproven as
   unproven — an unverified step reported as done is worse than a missing step.

## Notes

Keep `PLAN.md` in the working directory; it is the artefact that shows the
method was followed.
