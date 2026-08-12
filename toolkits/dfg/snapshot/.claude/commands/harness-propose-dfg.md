---
description: From an issue list, propose a DFG. Reads issues; outputs DFG.md draft.
---

# /harness-propose-dfg

You are proposing a directly-follows graph (DFG) from a set of GitHub issues.
The output is a `DFG.md` draft the operator will review before dispatching.

## Inputs

- The current repo (you are in its root)
- The issue list passed via arguments, or — if no arguments — the open
  issues with label `wave-N` for the next wave

## Process

1. Read the listed issues (`gh issue view <#>` for each).

2. Read `kit/METHODOLOGY/02-dfg-construction.md` for the construction rules.
   You must follow steps 1-5 of "Building a DFG (M / L)".

3. **Inventory work units.** One row per issue. List the files each issue
   touches (read the issue body's `## Files` section). If absent, read the
   issue's referenced design doc; if still absent, mark `TBD` and surface
   to the operator.

4. **Map file dependencies.** For every pair, ask: do they touch overlapping
   files? Build the dependency edges.

5. **Group into waves.** Place each unit in the earliest wave where its
   prerequisites are satisfied. Verify file-disjointness within each wave.
   Cap wave parallelism at 6 (re-decompose if larger; see anti-pattern).

6. **Define gate criteria** per wave: testable conditions (CI green,
   acceptance criteria met, no critical/major critic findings).

7. **Mark hardening policy** per unit (default: 3 cycles before escalation).

## Output format

Write to `DFG.md` at the repo root using the template from
`kit/METHODOLOGY/02-dfg-construction.md` "What a DFG file looks like":

```markdown
# DFG — <project> build plan

## Wave overview

```
W0 (parallelism: N) → W1 (parallelism: N) → ...
```

## Wave 0 — <name> (parallelism: N)

| #    | Work unit          | Files (disjoint)     | Gate criterion                |
|------|--------------------|----------------------|-------------------------------|
| W0-1 | <description>      | <file paths>         | <testable condition>          |

**Wave-0 gate (closes when all true):**
- <condition 1>

## Hardening loop policy

Default: 3 cycles before operator escalation.
```

## Discipline

- Do not dispatch — this slash command **proposes** a DFG. The operator
  approves or revises before any wave runs.
- If you find an issue too vague to inventory (no Files, no acceptance
  criteria), do not invent a DFG row. Surface the issue with `[TBD]` and
  list it under "Issues needing operator clarification".
- If wave parallelism would exceed 6, re-decompose. Don't ship a > 6 row.

## When to invoke

Operator runs `/harness-propose-dfg` after triage of a sprint's issues, or
when a new wave's issue set is ready.
