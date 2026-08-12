---
description: Classify the most recent operator turn into one of the 8 HITL archetypes.
---

# /harness-classify-intervention

You are classifying the most recent operator turn into one of the 8 HITL
archetypes from `kit/HITL-ARCHETYPES/`. The output feeds the
`intervention-density` metric and the wave retrospective.

## Inputs

- The session transcript (read the last 5 turns at minimum)
- The 8 archetype pages: `kit/HITL-ARCHETYPES/01-direction-change.md`
  through `08-rollback.md`
- The README at `kit/HITL-ARCHETYPES/README.md`

## Process

1. **Identify the operator's turn.** It is the most recent `user` turn in
   the transcript. Quote it verbatim (clipped if long).

2. **Read the 8 archetype headlines** from
   `kit/METHODOLOGY/05-hitl-interaction.md` § "The eight archetypes". The
   pattern of each archetype is:

   - **#1 Direction change** — switches technical strategy mid-wave
   - **#2 Scope escalation** — expands probe → full run
   - **#3 Skepticism / correction** — refuses a claim, demands re-derivation
   - **#4 Priority reframe** — redirects what success means
   - **#5 Context injection** — supplies info the agent could not fetch
   - **#6 Interrupt** — stops a tool call before it commits
   - **#7 Gate delegation** — delegates the merge gate with conditions
   - **#8 Rollback** — reverses a completed action

3. **Match to one archetype.** The match is the closest pattern. If two
   plausibly fit, pick the one with stronger evidence and note the
   alternative in the output.

4. **If no archetype fits**, classify as `00-unclassified` and surface to
   operator. The kit's anti-pattern is exactly the kind of free-form
   coaching that is *not* a typed intervention. Do not force a fit.

## Output format

```
{
  "session_id": "<uuid>",
  "turn_index": <int>,
  "timestamp": "<iso8601>",
  "operator_text": "<verbatim, ≤ 200 chars>",
  "archetype": "<one of 01-08 or 00-unclassified>",
  "confidence": "high | medium | low",
  "alternatives": ["<archetype-id>"],
  "trigger": "<what was the agent doing when this fired>",
  "agent_response_required": "<typed response per archetype page>"
}
```

## Examples

- "Re-derive on the full suite" → `03-skepticism`
- "Stop. Don't push." → `06-interrupt`
- "If 0 critical / 0 major, merge." → `07-gate-delegation`
- "Try harder." → `00-unclassified` (anti-pattern; surface)

## Discipline

- **One archetype per turn.** A multi-turn conversation about one issue
  classifies as one intervention; classify the **first** typed turn.
- **Do not re-classify previously-classified turns** without an explicit
  operator request.
- **Never invent archetypes.** If the kit's 8 don't fit, that's a finding —
  file an issue rather than stretching a category.

## When to invoke

Operator (or harness, automatically) runs this after each operator turn
that looks like an intervention. The output appends to the
`intervention-density` log.
