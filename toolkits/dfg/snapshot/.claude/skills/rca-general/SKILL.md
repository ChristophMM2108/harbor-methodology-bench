---
name: rca-general
description: Universal root-cause analysis discipline. 5-step workflow (reproduce
  → bisect → hypothesize → test → verify → document). Composes with rca-harness-architecture
  (T2) and rca-dfg-codebase (T3). Triggers on Cycle2Trigger event, on operator question
  "why is X failing?", or when failure recurs ≥ 2 times.
criticality: important
sdlc_category: Operations / Debugging
loop_layer: L4-action
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill as the FIRST RCA tier whenever a failure surfaces. The

  skill enforces a disciplined evidence-chain so the eventual fix

  proposal has falsifiable hypotheses + verification steps. It composes

  upward to T2 (architecture-aware) and T3 (codebase-aware) when the

  general method needs domain knowledge.

  '
verified_at: 2026-05-06
forged_by: dfg-harness 2026-05-06
---
# RCA general — universal debugging discipline

## Why this skill exists

Recurring failures (4+ recurrences before #561 root cause was found)
indicate the substrate lacks a disciplined RCA primitive. Without a
canonical workflow, RCA happens ad-hoc; specialists are not invoked
when needed; root causes are missed in favor of symptom-patches.

Per Anthropic's *Build Skills Not Agents* paradigm: this skill is the
T1 universal layer; it composes upward to T2 (`rca-harness-architecture`)
and T3 (`rca-dfg-codebase`) for domain depth, and downward to sub-skills
(`probing-substrate-state`, `bisecting-failure`, `testing-hypothesis`,
`inspecting-external-library-call-shape`, etc.).

## Trigger conditions (substrate-evidence only — per §amendment-5)

Auto-trigger on ANY of:
1. New `Cycle2Trigger` event on `events.jsonl` (forge candidate v0.5.0)
2. Operator-prompt contains an explicit RCA-keyword pattern: "why is X failing", "what's the root cause", "RCA on Y", "investigate Z"
3. Same failure signature appears ≥ 2 times in events.jsonl tail (recurrence threshold)
4. Cycle-2 critic verdict "REVISE" or "BLOCK"

Explicitly NOT triggers (per §amendment-5):
- ❌ "Operator looks frustrated" — natural-language emotional inference
- ❌ "Things seem broken" — vague intent

## Required workflow

### Step 1 — REPRODUCE
Establish the failure is consistent (not transient). Run the failing
operation 3× and capture all 3 transcripts. If the failure is
intermittent, capture the rate; document the conditions when it does
fire vs doesn't.

### Step 2 — BISECT
Narrow the failure scope along orthogonal axes:
- **Code axis**: git bisect against a known-good baseline if reproducible deterministically
- **Input axis**: vary inputs to find the boundary
- **Environment axis**: vary env vars / SDK versions / cwd
- **Time axis**: when did it start? cross-reference git log + events.jsonl

The output is a narrowed hypothesis space.

### Step 3 — HYPOTHESIZE
For each viable hypothesis, write down:
- The mechanism (why this would cause the observed failure)
- The substrate evidence that would CONFIRM or REFUTE it
- The cost of testing it

Reject hypotheses that lack substrate-evidence falsifiability per
§amendment-5.

### Step 4 — TEST
Run the cheapest disconfirming experiment first (Goldratt theory of
constraints applied to RCA).

For each tested hypothesis, document:
- The test command / probe / assertion
- The actual result
- Whether the hypothesis was supported or refuted

### Step 5 — VERIFY + DOCUMENT
After identifying the root cause:
- Author a fix proposal that addresses the cause (not the symptom)
- Verify by reproducing the original failure scenario after fix
- Document the full evidence chain in a retro / no-op-rationale / lien

## Composition with other primitives

- **T2 escalation:** when the failure pattern matches a known harness
  signature (e.g., empty-output, schema-drift, cascade-ordering),
  escalate to `rca-harness-architecture`.
- **T3 escalation:** when T2 names a specific subsystem, escalate to
  `rca-dfg-codebase` for code-level inspection.
- **Sub-skills:** invoke `probing-substrate-state`, `bisecting-failure`,
  `testing-hypothesis`, `analyzing-event-stream`,
  `inspecting-external-library-call-shape` as needed.

## Test-of-skill (evaluation cases)

| Scenario | Expected outcome |
|---|---|
| W26-2..W26-6 empty-output | T1 reproduces → T2 matches "dispatched-session-output-floor pattern" → T3 inspects launcher.py → `inspecting-external-library-call-shape` finds 4 missing ClaudeAgentOptions fields → ROOT CAUSE in 1 cycle (vs 4+ recurrences without the skill) |
| Single-occurrence test failure | T1 reproduces → bisect points to commit → fix proposed |
| Schema-drift error | T1 reproduces → T2 matches "events.schema.json version-bump invariant" → ratchet to Layer-1 invariant if recurring |

## References

- ADR-019 §amendment-1 (W16-1 keystone) — structural-impossibility-over-prose
- ADR-019 §amendment-5 — substrate-evidence triggers
- Anthropic *Build Skills Not Agents* — Barry Zhang & Mahesh Murag
- Goldratt — *Theory of Constraints* (cheapest-disconfirming-test-first)
- #561 receipt — empty-output failure mode 4+ recurrences without an RCA skill to invoke
