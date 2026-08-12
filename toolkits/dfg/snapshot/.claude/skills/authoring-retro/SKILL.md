---
name: authoring-retro
description: Generative skill for unit retrospectives following the §amendment-trigger
  discipline. Structures cycle outcomes, surfaces unstated assumptions, and proposes
  substrate ratchets when a pain pattern recurs.
criticality: important
trigger: substrate-evidence
trigger_evidence: "Activate when:\n- Diff stages a NEW .dfg/retrospectives/W*/W*-*.md\
  \ file.\n- Wave-close ceremony just ran (WaveGatePass event); per-unit\n  retros\
  \ must follow.\n- Operator types \"author retro for W*-*\" or \"what should the\
  \ W*-*\n  retro say?\"."
---
# Authoring retrospectives

## Why this skill exists

Retros are the §amendment-trigger feedstock. A pattern that surfaces in
3+ retros becomes a ratified ADR amendment (W22-8 receipt: 8
§amendment-trigger ratifications across W16-1, W17-2, W19-2, W22-8,
W25, #561 cluster, dispatch-discipline tripod, sprint-manifest-
coherence). Free-form retros lose the signal:

- "Worked fine" — surfaces no pattern.
- Cycle outcomes hidden in prose — pattern recognizers can't grep.
- Unstated assumptions ratified silently — drift compounds.

## Template

```markdown
# W<wave>-<n> retrospective — <unit name>

**Wave:** W<wave> (<sprint version> — <sprint theme>)
**Status:** COMPLETED | DEFERRED | SCRUBBED
**Cycles:** 1 | 2 | 3+ (with reason if >1)

## Outcome

One paragraph stating what shipped (or what didn't and why). Cite
the PR number, file paths, and tests added.

## What worked

2-4 bullets. Specific. "The W30 projector pattern transferred cleanly"
beats "things went well".

## Lessons

2-4 bullets. Each lesson follows the format:
- **Pattern observed.** What surprised us.
- **Why it matters.** What this constrains in future work.
- **Whether it's already a §amendment.** If yes, cite the
  ratification. If no but feels like one, file the proposal.

## Forward signals (optional)

When this retro raises a flag for v0.5+ (or beyond): what to watch
for, what would constitute the 3rd receipt forcing a §amendment.

## §Amendment proposal (optional)

Only when this retro IS the receipt that pushes a 3rd-instance pain
pattern over the ratification threshold. State the proposed invariant,
the 2 prior receipts, and the substrate gate that would enforce it.
```

## Discipline checks

1. **Cycles field is honest.** If cycle-2 happened, name what cycle-1
   missed. If cycle-3, note the §amendment-trigger ratification.
2. **At least one lesson.** A retro with no lessons is suspicious —
   either the unit was trivial (then `Cycles: 1` and a one-line outcome
   suffices) or the author skipped reflection.
3. **Forward signals are concrete.** "Watch for X happening Y times"
   beats "be careful about that".

## §Amendment-trigger discipline

When the retro author sees a pattern they've also seen in 2 prior
retros, the §amendment proposal section is MANDATORY. The pattern's
file/event evidence must cite the prior receipts (PR or retro paths).

## Anti-patterns this skill rejects

- "What worked: everything." Too vague.
- "Lessons: be careful." Not actionable.
- Retro that fails to mention cycle-2 hardening when the PR clearly
  had two cycles' worth of dual-critic verdicts.
- Retro authored AFTER the wave-gate, retroactively. Discipline says
  retros precede or accompany the gate, not chase it.

## Cross-references

- ADR-019 §amendment-trigger pattern
- 11 canonical Layer-1 paired-diff invariants
- Receipts ratified to date: W16-1, W17-2, W19-2, W22-8, W25, #561
  cluster, dispatch-discipline tripod, sprint-manifest-coherence W29-2
