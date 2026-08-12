---
name: rca-harness-architecture
description: Tier-2 RCA skill — knows dfg-harness architecture (ADRs 001-022, 11 Layer-1
  invariants, 6-layer model L0-L5, substrate primitives, §amendment-trigger pattern,
  Guardian skills). Triggers when rca-general's failure pattern matches a known harness
  signature OR recurrence count ≥ 2. Composes upward to rca-dfg-codebase (T3) and
  downward to substrate-probe sub-skills.
criticality: important
sdlc_category: Operations / Debugging
loop_layer: L4-action
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill when rca-general''s reproduce + bisect produces a failure

  signature matching a known harness pattern. T2 maps the symptom to an

  ADR / invariant / canonical pattern and proposes the structural-vs-

  symptomatic fix split.

  '
verified_at: 2026-05-06
forged_by: dfg-harness 2026-05-06
---
# RCA harness-architecture — pattern matching against known signatures

## Why this skill exists

dfg-harness has accumulated 11 Layer-1 invariants + 5 ADR-019 §amendments + 16 subsystems + 4 Guardian skills + a §amendment-trigger pattern. Failures often match KNOWN signatures; mapping the symptom to the pattern accelerates RCA from hours to minutes. Without this skill, T1's general method must rediscover the pattern each time.

## Trigger conditions (substrate-evidence only — per §amendment-5)

Auto-trigger on:
1. `rca-general` (T1) requests T2 escalation (substrate signal: T1 emits an `RCAEscalationRequested` event with target=T2)
2. Failure recurrence count ≥ 2 in events.jsonl tail (configurable via cooperation-tiers.yaml)
3. Cycle-2 critic verdict references "pattern" / "recurring" / "again"

## Knowledge body

### Known harness pattern signatures

| Pattern | Symptom | ADR | Cure |
|---|---|---|---|
| **Empty-output dispatched session** | SessionCompleted outcome=success + zero work files | #559 (output-floor wiring) + #561 (ClaudeAgentOptions root cause) | Wire allowed_tools/permission_mode/max_turns/cwd into ClaudeAgentOptions; verify dispatched-session-output-floor skill is enforced in launcher |
| **Schema drift** | events.schema.json modified without schema_version bump | ADR-019 §amendment-1 (W16-1 keystone) | Layer-1 invariant: schema-version-bump pairing |
| **Empty contract → impl** | Impl commit on a feat/wN-M branch without preceding contract commit | ADR-018, ADR-019 (contract-first) | Layer-1 invariant: contract-first paired-diff |
| **Detector-without-backfill** | New _detect_*() function added without paired _backfill_*() | ADR-019 §amendment-2 (W17-2) | Layer-1 invariant: backfill-paired |
| **Plan.yaml mutation without RePlanAccepted** | .dfg/plan.yaml diff without same-PR RePlanAccepted event | ADR-019 §amendment-1 (W16-5) | Layer-1 invariant: re-plan-first |
| **External-lib hallucination** | Mocked tests pass against fabricated SDK API | ADR-019 §amendment-4 (W22-8) | Layer-1 invariant: external-library-API-verification |
| **Natural-language trigger** | New gate/skill triggers on prose hints | ADR-019 §amendment-5 | Substrate-evidence trigger discipline |
| **P7-vs-P11 cascade ordering** | P7 PR-mergeable preempts P11 wave-shippable | #516 / W22-6 | Reorder cascade so P11 fires when state.units fully COMPLETED |
| **State.json drift** | dfg index --verify fails; active_wave stale | ADR-005 + W23-2 projector | dfg index --rebuild OR projector fix |
| **Empty session reasoning** | Dispatched session decides no-op without rationale | dispatched-session-output-floor skill (PR #553) | Author no-op-rationale.md OR re-dispatch with sharper brief |
| **Branch-shape allow-list miss** | PR branch doesn't match canonical 8-shape regex | kit/hooks/branch-shape-check | Rename branch or add to allow-list |

### The §amendment-trigger pattern

Per ADR-019 §amendment-trigger discipline:
> operator-known pain × N agents = §amendment-trigger threshold

The 6 receipts (as of 2026-05-06):
1. W16-1 §amendment-1 — Structural impossibility over prose detection
2. W17-2 §amendment-2 — Temporal completeness (backfill-paired)
3. W19-2 §amendment-3 — Projector-purity tiers
4. W22-8 §amendment-4 — External-library API verification
5. W25 §amendment-5 — Trigger discipline (substrate-evidence over prose)
6. PR #560+#562 — Empty-output failure mode (ratcheted at L1 enforcement, not as 6th canonical amendment; #559 catches symptom + #561 cures cause)

When a failure matches the pattern (≥ 4 recurrences across ≥ N agents, where N depends on substrate gap severity), T2 escalates to ratchet-candidate analysis.

### The 6-layer model (ADR-019)

| Layer | Discipline | Examples |
|---|---|---|
| L0 | Structural impossibility | Layer-1 paired-diff invariants |
| L1 | CI / pre-commit gates | external-lib-verification-check.py, skill-assessment-gate-check.py |
| L2 | Tunable prompts | restart-context, post-compaction-resume |
| L3 | Norm-with-receipts | Documented in ADR/methodology |
| L4 | Vigilance | CLAUDE.md anti-goals + dispatcher.md cautions |
| L5 | Hope | Operator-internalized discipline |

T2 uses this lattice to recommend WHERE to ratchet a fix (L0 = structurally impossible, L5 = "remember not to do that").

### The 16 subsystems

Per `.dfg/governance/subsystems.yaml`:
- 8 escalation:always (vision-load-bearing): methodology-core, discipline-gates, events-schema, plan-state, modifications-ledger, orchestrator-launcher, skill-registry, agent-registry
- 5 cross-subsystem-only: cli-commands, projectors, docs-release, bootstrap-playbook, cli-config
- 3 delegable: cockpit, tests, retrospectives

T2 uses subsystem mapping to identify which discipline applies + who has authority.

## Required workflow

When invoked, T2:

1. **Reads** the T1 evidence chain (output of `rca-general` Steps 1-3)
2. **Matches** the failure signature against the pattern table above
3. **Identifies** the relevant ADR / invariant / Guardian skill
4. **Splits** the proposed fix into:
   - **Symptom fix** (immediate; closes the specific failure)
   - **Structural fix** (ratchet-candidate; makes the pain class impossible)
5. **Determines** layer placement (L0-L5)
6. **If T3 needed**, escalates with: target subsystem + suspected code path + hypothesis to test

## Composition with other primitives

- **Upward (escalates to T3 `rca-dfg-codebase`):** when the hypothesis names a specific code path or module
- **Downward (invokes sub-skills):**
  - `analyzing-event-stream` — pattern-match across events.jsonl
  - `auditing-archetype-history` — modifications.md ledger analysis
  - `verifying-substrate-coherence` — dfg substrate check + dfg validate
- **Lateral (informs operator decision):**
  - When pattern recurrence reaches §amendment-trigger threshold, recommends ratchet-as-amendment vs ratchet-as-skill-wiring (per #559+#561 receipt)

## Test-of-skill (evaluation cases)

| Scenario | Expected T2 verdict |
|---|---|
| W26-2..W26-6 empty-output | Pattern: dispatched-session-output-floor (ADR-019 §amendment-trigger pattern; 4+ recurrences) → ratchet candidate; existing skill catches symptom, need root-cause investigation in launcher.py invoker → escalate to T3 |
| events.schema.json change without version bump | Pattern: schema-drift (Layer-1 invariant) → fix is paired-diff; no escalation needed |
| New gate using grep on commit message | Pattern: natural-language trigger (§amendment-5) → reject + propose substrate-evidence twin |

## References

- ADR-019 amendments 1-5 + the 6 §amendment-trigger receipts
- `.dfg/governance/subsystems.yaml` — 16-subsystem registry
- `.dfg/governance/non-negotiables.yaml` — Layer-1 invariants + design principles
- `kit/agents/dispatcher.md` — archetype-skill mapping
- `docs/decisions/ADR-*` — 22+ ratified ADRs
