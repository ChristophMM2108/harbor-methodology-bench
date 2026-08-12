---
name: rca-dfg-codebase
description: Tier-3 RCA skill — knows the dfg-harness codebase (src/dfg_harness/ structure,
  dispatcher.md archetype mapping, subsystem→file mapping per .dfg/governance/subsystems.yaml).
  Triggers when rca-harness-architecture (T2) names a specific subsystem or code path.
  Composes downward to debug primitives (probing-substrate-state, testing-hypothesis,
  inspecting-external-library-call-shape, etc.).
criticality: important
sdlc_category: Operations / Debugging
loop_layer: L4-action
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill when T2 (rca-harness-architecture) identifies the

  failure subsystem and a code path is suspected. T3 navigates the

  codebase, runs targeted probes, and proposes a code-level fix.

  '
verified_at: 2026-05-06
forged_by: dfg-harness 2026-05-06
---
# RCA dfg-codebase — code-level inspection + targeted probes

## Why this skill exists

T1 (general method) + T2 (architecture pattern matching) narrow the
failure space; T3 finishes the job by reading the actual code, running
targeted tests, and proposing the precise diff. Without T3, RCA stops
at hypothesis generation; the code-reading step is left to the
operator manually.

## Trigger conditions (substrate-evidence only — per §amendment-5)

Auto-trigger on:
1. T2 (`rca-harness-architecture`) emits `RCAEscalationRequested` event
   with target=T3 + named subsystem
2. Hypothesis from T2 names a specific file path / module / function
3. Operator-prompt explicitly requests code-level analysis ("read the
   launcher.py and tell me why X")

## Knowledge body

### Subsystem → file path mapping

Per `.dfg/governance/subsystems.yaml`:

| Subsystem | Path patterns | Owner |
|---|---|---|
| methodology-core | `docs/decisions/ADR-*.md`, `kit/METHODOLOGY/*.md` | Carlos (escalation:always) |
| discipline-gates | `kit/scripts/*-check.py`, `.github/workflows/*-discipline.yml` | Carlos |
| events-schema | `kit/SCHEMAS/events.schema.json`, `kit/SCHEMAS/agent-spec.schema.json` | Carlos |
| plan-state | `.dfg/plan.yaml`, `.dfg/state.json` | Carlos |
| orchestrator-launcher | `src/dfg_harness/orchestrator/**/*.py` | Carlos |
| skill-registry | `.claude/skills/**/SKILL.md` | Carlos |
| cli-commands | `src/dfg_harness/commands/*.py`, `src/dfg_harness/cli.py` | Carlos (delegable) |
| projectors | `src/dfg_harness/projectors/**/*.py` | Carlos (delegable) |
| cockpit | `src/dfg_harness/commands/trace.py`, `src/dfg_harness/cockpit/**/*` | Carlos (delegable) |
| tests | `tests/**/*.py` | per-author |
| retrospectives | `.dfg/retrospectives/W*/*.md` | per-unit-author |

### Key code paths for common failures

| Failure | First place to look |
|---|---|
| Empty-output dispatched session | `src/dfg_harness/orchestrator/launcher.py` `_claude_agent_sdk_invoker` `ClaudeAgentOptions` (ROOT CAUSE of #561) |
| Schema validation drift | `kit/SCHEMAS/events.schema.json` + `kit/SCHEMAS/agent-spec.schema.json` |
| Wave-gate failure | `.dfg/checkpoints/W<N>-gate.md` `verify:` array |
| Plan.yaml mutation rejection | `kit/scripts/replan-discipline-check.sh` |
| Pre-pr battery failure | `src/dfg_harness/commands/pre_pr.py` `_check_*` functions |
| dfg index drift | `src/dfg_harness/commands/index.py` `_resolve_active_wave` (W23-2 + W23-3 + #554 history) |
| Dispatch idempotency | `src/dfg_harness/orchestrator/launcher.py` `_release_idempotency_marker` |
| External-lib gate fail | `kit/scripts/external-lib-verification-check.py` (W22-8 keystone) |
| Skill-assessment-gate | `kit/scripts/skill-assessment-gate-check.py` (W25 keystone) |
| Cooperation-classifier | `kit/scripts/cooperation-classifier.py` (W26-2) |

### Standard probes (all available via dfg verbs)

| Probe | Command |
|---|---|
| Substrate state | `uv run dfg status` |
| Index coherence | `uv run dfg index --verify` |
| Substrate health | `uv run dfg substrate check --no-emit` |
| Validate plan + contracts | `uv run dfg validate` |
| Pre-PR battery | `uv run dfg pre-pr --json` |
| Cockpit (live) | `uv run dfg trace export --watch` |
| Wave-close dry run | `uv run dfg wave close W<N> --no-hygiene` |
| Recent operator interventions | `tail -100 .dfg/modifications.md` |
| Recent events tail | `tail -50 .dfg/events.jsonl` |
| Failure-pattern search | `grep -E 'SessionDegraded\|outcome=aborted\|FAIL' .dfg/events.jsonl` |

### Targeted test selectors

| What | Selector |
|---|---|
| Launcher tests | `uv run pytest tests/test_orchestrator_launcher.py -q` |
| Schema tests | `uv run pytest tests/test_governance_schemas.py tests/test_validate.py tests/test_events_schema.py -q` |
| Pre-pr tests | `uv run pytest tests/test_pre_pr*.py -q` |
| State projector | `uv run pytest tests/test_state_projector.py tests/test_index.py -q` |
| Impacted-only | `uv run dfg test impacted` (when testmon hashed) |

## Required workflow

When invoked, T3:

1. **Maps** the T2 hypothesis to the subsystem(s) → file paths
2. **Reads** the named files (typically <500 LOC each)
3. **Probes** substrate state via `dfg status` + `dfg index --verify` + targeted grep
4. **Tests** the hypothesis with a targeted pytest selector OR a manual reproduction
5. **Authors** the precise fix diff (or escalates to operator if VT3+)
6. **Verifies** by re-running the failing case post-fix
7. **Documents** the fix in retro / DISCIPLINE-CHANGELOG / no-op-rationale as appropriate

## Composition with other primitives

- **Sub-skills (debug primitives)** invoked as needed:
  - `probing-substrate-state` — read events.jsonl tail, dfg status
  - `testing-hypothesis` — pytest with operator-defined selector
  - `inspecting-external-library-call-shape` — diff actual SDK call vs documented surface (would have caught #561)
  - `analyzing-event-stream` — pattern frequency on events.jsonl
  - `auditing-archetype-history` — modifications.md correlation
  - `inspecting-dispatched-session` — read .dfg/sessions/<sid>/* artifacts
- **Upward (escalation):** if the hypothesis crosses subsystems or requires
  ratification, escalate back to T2 + lien-filing
- **Lateral:** if the fix is operator-territory (state hand-edit, force-push,
  schema break), surface for archetype-07 ledger entry

## Test-of-skill (evaluation cases)

| Scenario | Expected T3 outcome |
|---|---|
| #561 W26 empty-output | T2 names launcher.py SDK invoker as suspect → T3 reads `_claude_agent_sdk_invoker` → invokes `inspecting-external-library-call-shape` sub-skill → identifies missing 4 ClaudeAgentOptions fields → fix diff proposed |
| #516 P7-vs-P11 cascade | T2 names dispatch.py priority cascade → T3 reads `_dispatch_decisions` → finds wrong-order check → reorder → test |
| `dfg validate` schema fail | T2 names events.schema.json → T3 reads schema + the modifying contract → finds missing version bump → propose pairing |

## References

- `.dfg/governance/subsystems.yaml` — canonical subsystem→path mapping
- `kit/agents/dispatcher.md` — archetype to skill triggers
- `src/dfg_harness/` — actual source of truth for code paths
- ADR-005 (events as truth) — substrate-evidence priority
- #561 receipt — the failure mode T3 exists to catch faster
