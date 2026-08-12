---
name: dfg-harness-plan
description: 'Plan a new wave or sprint in dfg-harness following the canonical planning
  ceremony (kit/METHODOLOGY/08). Walks the operator through scope framing, unit decomposition,
  plan-time context curation, critic-mode inference, replan-propose ceremony, and
  issue-435 same-diff staging. Use this skill when the operator asks to plan a NEW
  sprint or wave, add scope to an in-flight wave, or invokes `/plan`. Triggers on
  phrases like "plan a sprint", "plan wave Wn", "what should the next sprint be",
  "/plan". Does NOT trigger on refactor planning, exploratory "what should we do"
  without harness context, or replan ceremonies for existing scope (those are conversational
  dispatches without ceremony).

  '
criticality: important
trigger: explicit-or-substrate
trigger_evidence: "Activate when:\n- Operator types `/plan` (slash command — auto-invoke)\n\
  - Operator's message matches planning-intent: \"plan a sprint\",\n  \"plan wave\
  \ Wn\", \"let's plan\", \"what should the next sprint be\",\n  \"add unit to W<n>\"\
  , \"design the next wave\"\n- The last passed wave gate is older than the current\
  \ active_wave\n  pointer (substrate signals planning is overdue)\nDo NOT activate\
  \ for:\n- \"Plan how I'll refactor this function\" (code planning, not sprint)\n\
  - \"What do you think we should do?\" without harness context\n- Replan to alter\
  \ unit scope of an in-flight wave (different ceremony)"
---
# dfg-harness-plan — the planning ceremony skill

This skill is the **conversational wrapper** around the canon at
`kit/METHODOLOGY/08-planning-ceremony.md`. The canon describes the
recipe in every detail; this skill walks the operator through it
turn by turn.

The deterministic parts of the recipe (schema validation,
parallel-groups derivation, dry-run preview) are implemented in
`dfg plan {validate, parallel-groups, dry-run}` (W37-2). This skill
calls those CLIs at the appropriate steps and surfaces results to
the operator.

## Pre-flight (always)

Before drafting any unit, run:

```bash
uv run dfg validate
uv run dfg status        # surface active_wave + last passed gate
```

Halt on any error. Surface the specific failure to the operator —
planning on a broken ledger compounds error.

Specifically check:

1. `dfg validate` clean
2. `state.json.active_wave ≥ max(passed gates)` and `≤ max(plan.yaml waves) + 1`
3. No uncommitted `plan.yaml` changes
4. Latest gate file readable with `verdict:` ∈ `{PASS, DEFERRED, REJECTED}`

## The 11-step walk

Follow the canon §The 11-step recipe. For each step:

1. **Scope framing** — Ask the operator (in chat) for theme + trigger
   reason + target version. Trigger reason is controlled vocabulary:
   `retro-driven | critic-finding | ci-failure | operator-intervention
   | stakeholder-decision`. Map informal language to canon vocabulary
   yourself; surface mappings for confirmation.

2. **Unit decomposition** — Propose a unit table in chat:

   | ID | Slug | Files (excerpt) | Depends_on | Size |
   |---|---|---|---|---|

   Each unit's `files` list MUST include implicit retro + contract
   paths. The skill writes them automatically; never let the
   operator forget them.

3. **Implicit file enumeration** — automated; skill appends
   `.dfg/agents/<unit-id>-<slug>.md` and
   `.dfg/retrospectives/W<wave>/<unit-id>.md` to every unit's files.

4. **Smell-tests** — for each draft unit, surface ANY of:
   - >3 non-trivial files (flag for split)
   - cycle in `depends_on` (HALT)
   - size mismatch (e.g. "L" with 1 file, "S" with 8 files)
   - purpose >200 chars
   - slug not kebab-case or >40 chars
   - file paths that would collide with existing modules/packages
     (lesson from W37-2: `src/dfg_harness/cli/plan.py` would have
     conflicted with the existing `cli.py`)

5. **Parallelism derivation** — NEVER author by hand. Run:

   ```bash
   uv run dfg plan parallel-groups <wave-id> --plan-path <draft>
   ```

   Surface the derived `parallel_groups` to the operator for
   inspection. If it differs from operator expectation, the
   `depends_on` graph or `files` lists are wrong — fix THOSE,
   never the parallel_groups.

6. **Plan-time context curation (W37 contribution)** — for EACH unit,
   forge:
   - `read_contract.curated_context` — 1-paragraph (≤1500 chars)
     "what matters about this unit." Sources: stakeholder pressure,
     prior-PR receipts, ADR linkage, hidden constraints visible
     at plan time.
   - `read_contract.priority_pointers` — list of explicit
     ADR/retro/transcript/PR references the dispatched session
     must consult.

   Surface the forged context to the operator: "for W<n>, I forged:
   <paragraph>. Pointers: [...]. Confirm or edit?" Then for critics
   (if `critic_mode != none`):
   - `critic_context.curated_context` — what critics should weigh
     beyond the diff
   - `critic_context.priority_pointers` — critic reading list

7. **Critic-mode inference** — propose per-unit `critic_mode` per
   the canon §7 heuristic:

   | Signal | → mode |
   |---|---|
   | Touches kit/SCHEMAS, ADRs, state.json, plan.yaml | dual |
   | Adds new public CLI / API / event type | dual |
   | Cross-cutting refactor (>3 files, >300 LOC) | dual |
   | Single-file additive, well-typed | lightweight |
   | Pure docs / retro | lightweight or none |
   | Test-only additions | lightweight |

   `critic_mode: none` is rare and explicit — requires
   `critic_context.curated_context` to contain the operator's
   one-line justification. The skill defaults UP (lightweight not
   none) unless operator explicitly chooses none.

   When ambiguous, propose `dual` and ask. Default to MORE review.

8. **Gate criteria** — for each criterion, validate it's
   verifiable: file existence, PR merge state, exit code of a
   `dfg` subcommand, schema validation. REJECT aspirational
   language ("works correctly", "is robust", "operator-friendly").
   Examples in canon §8.

9. **Operator-review menu** — surface in chat ALL ambiguities:
   - sprint version naming (if cadence rule could go either way)
   - unit splits (if any smell-test borderline)
   - critic_mode overrides
   - scope deferrals
   - forged curated_context revisions

   Use the dispatcher-HITL format: numbered options with
   recommendation. Reply menu: `go` / `tweak` / `wait`.

   DO NOT proceed past this step without explicit affirmative.
   Silent acceleration past operator review is the exact failure
   mode #597 was filed against.

10. **Replan propose** — once approved, run:

    ```bash
    uv run dfg replan propose \
      --scope-level sprint \
      --scope-target v<X.Y.Z> \
      --action add \
      --rationale "<theme + every piece of scope>" \
      --trigger <controlled vocab>
    ```

    The rationale MUST name everything the sprint will ship. If
    asking the operator surfaces additional scope mid-conversation,
    update the rationale before proposing.

11. **Same-diff staging (#435)** — after operator runs:

    ```bash
    DFG_OPERATOR=1 uv run dfg replan accept <proposal-id> \
      --operator-note "..."
    ```

    Edit `.dfg/plan.yaml` to insert the wave block. Stage:
    - `.dfg/plan.yaml` (the wave addition)
    - `.dfg/events.jsonl` (the RePlanProposed/Accepted entries)
    - `.dfg/replan-proposals/<id>.yaml` (the proposal file itself)

    All in one commit per #435 invariant. Branch + PR + merge.

## Anti-patterns the skill prevents

- ❌ Hand-authoring `parallel_groups` (canon §5; ADR-022 §amendment)
- ❌ Verify items that aren't deterministically checkable (canon §8)
- ❌ Skipping step 9 operator-review (canon §9)
- ❌ Proposal rationale that omits scope (canon §10; W37 itself receipt)
- ❌ `plan.yaml` without same-diff `RePlanAccepted` (#435)
- ❌ `critic_mode: none` without justification (canon §7)
- ❌ Implicit retro/contract files missing from `files` list (canon §3)

## Edge cases

### Operator ambiguity
If the operator's request is unclear ("plan something for W38"),
ask before proceeding. The skill is conversational; it doesn't
guess at intent.

### Mid-conversation scope expansion
If new scope surfaces during step 9 review, return to step 1.
Do NOT silently expand and propose. The W37 itself receipt:
operator surfaced context-routing in conversation; original
proposal was declined → re-proposed with full scope.

### Branch-prefix selection
Default `branch_name` prefix per canon §branch-prefix-convention:

| Unit primary delivery | Prefix |
|---|---|
| Code (CLI, schema, src/) | feat |
| Bug fix | fix |
| Documentation | docs |
| Tests, lint, CI | chore |
| Pure restructure | refactor |

## Composition with other skills

- `designing-wave-parallelism` — sister skill for parallel-group
  risk analysis (color graph + risk gradient). The two compose:
  this skill calls `dfg plan parallel-groups` for mechanical
  derivation; that skill adds risk-aware ordering on top.
- `forging-unit-contract` — sister skill for filling out the
  `.dfg/agents/<unit-id>-<slug>.md` contract files. This skill
  writes the *plan.yaml* entry; that skill writes the per-unit
  contract.
- `enforcing-non-negotiables` — invoked at substrate-mutation
  time; ensures plan.yaml diff has same-diff `RePlanAccepted`.

## Receipts

This skill was authored as W37-3 of v0.5.5 (Planning ceremony as
substrate). The canon at `kit/METHODOLOGY/08-planning-ceremony.md`
is the authoritative spec; this SKILL.md is the operational
wrapper. If they disagree, the canon wins.
