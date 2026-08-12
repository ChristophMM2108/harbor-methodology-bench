---
name: drafting-adr
description: Generative skill walking the ADR ratification template. Forces evidence-first
  decisions, alternatives-considered honesty, and receipt-citation discipline. Used
  when proposing a new ADR or an amendment to an existing one.
criticality: important
trigger: substrate-evidence
trigger_evidence: "Activate when:\n- Diff stages a NEW docs/decisions/ADR-*.md file.\n\
  - Diff modifies an ADR-NNN file's `## Status` block to \"amended\" or\n  \"supersedes\"\
  .\n- Operator types \"draft ADR for ...\", \"ratify §amendment-N for\n  ADR-NNN\"\
  , or \"this is becoming a pattern\" (the §amendment-trigger\n  signal)."
---
# Drafting ADRs

## Why this skill exists

ADRs are load-bearing — they pin Layer-1 invariants and bind future
work. Free-form ADR drafting frequently produces:

- "Decision" without evidence — speculative invariants that don't
  match observed substrate.
- Missing "alternatives considered" — looks decisive but hides the
  judgment trade-offs.
- "Consequences" without receipts — claims of impact that nothing
  measures.

This skill structures the draft so each ADR meets the receipt bar.

## Template (canonical sections)

```markdown
# ADR-<NNN> — <Title in noun phrase, present tense>

**Status.** Proposed | Accepted | Superseded by ADR-<NNN> | Amended on <date>

**Date.** YYYY-MM-DD (initial ratification)

## Context

What forced this decision? Cite at least 2 substrate receipts (event-
ids, PR numbers, retros, or operator-intervention archetypes). State
the operator pain, the substrate signal, and prior workarounds tried.

## Decision

One sentence stating the invariant. Optionally a paragraph of
clarification. The decision MUST be substrate-checkable — a reviewer
can write a script that flags violations.

## Consequences

- **What this enables.** New substrate behavior unlocked.
- **What this constrains.** Behavior the substrate will now reject.
- **Costs.** Honest accounting of friction added.

## Alternatives considered

Each alternative gets a paragraph: what it would have looked like, why
it was rejected, who would have benefited from picking it.

## Ratification trigger

What event count / receipt set forced this from "discussion" to
"Layer-1 invariant"? (For amendments, what NEW receipts force the
amendment beyond the base ADR.)

## Verification

How does substrate-check / a hook / a test enforce this? Cite the
specific gate. If no gate exists, list it as a follow-up lien.
```

## §Amendment-trigger discipline

When this skill is firing for an AMENDMENT (not a new ADR):

1. The amendment MUST cite ≥ 3 receipts of the underlying pain
   pattern. Two receipts is "coincidence"; three is "pattern".
2. The amendment MUST propose a substrate-checkable invariant, not
   a documentation-only norm.
3. The amendment is added to the parent ADR's `## Amendments` block
   with a date and PR reference, not as a new ADR file (unless it
   reverses the original decision, in which case it supersedes).

## Anti-patterns this skill rejects

- "Decision: we should be more careful about X." Not substrate-
  checkable. Reword.
- "Alternatives considered: none." Always at least one alternative.
- "Verification: TBD." File a follow-up lien with an issue number.
- ADRs that say what but not why. Each section answers a different
  question.

## Cross-references

- ADR-007 — planning/re-planning protocol
- ADR-016 — modifications ledger archetypes
- ADR-019 — pain-to-hook ratchet (the §amendment pattern)
- 11 canonical Layer-1 paired-diff invariants
