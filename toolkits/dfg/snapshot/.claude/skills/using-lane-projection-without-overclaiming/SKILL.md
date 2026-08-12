---
name: using-lane-projection-without-overclaiming
description: Layer-shaped skill teaching the W66 Parallel Wave Lanes read-only projection
  stack. Covers `dfg lane status --json`, `dfg lane conflicts --json`, `dfg sprint
  integration-preview <sprint-id> --json`, the optional plan-metadata fields (`lane_id`,
  `squad_id`, `integration_scope` — and that `integration_scope` is a SPRINT id, not
  free-form prose), ADR-019 §Amendment-20 read-only boundary, and what NOT to do (no
  lane events, no lane-aware enforcement, no DFG branches, no mini-Git). Used whenever
  an agent works with lane metadata, conflict detection, or sprint integration preview.
criticality: important
trigger: substrate-evidence
trigger_evidence: "Activate when:\n- Operator types \"show lane status\", \"check\
  \ lane conflicts\", or invokes\n  `dfg lane status` / `dfg lane conflicts` / `dfg\
  \ sprint integration-preview`.\n- Diff stages a wave with `lane_id` / `squad_id`\
  \ / `integration_scope`\n  metadata in `.dfg/plan.yaml`.\n- An agent is about to\
  \ author a \"lane-aware\" enforcement primitive\n  (which would violate ADR-019\
  \ §Amendment-20).\n- Multiple waves are active simultaneously and the agent needs\
  \ the\n  cross-lane composition picture.\n"
sdlc_category: Plan
loop_layer: L1-sprint
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill BEFORE working with lane metadata or invoking lane

  commands. The skill prevents agents from overclaiming W66''s scope —

  W66 shipped read-only projection ONLY. There are no lane events, no

  lane-aware gate enforcement, no merge queues, no DFG branches. Future

  enforcement requires a separate ADR amendment, not a casual upgrade.

  This skill is the antidote to "I see `dfg lane`, therefore lanes are

  authoritative" — a real risk per W66-5''s assumption_to_challenge.

  '
verified_at: 2026-05-17
forged_by: dfg-harness W67-2 layer-shaped-skills
---
# Using lane projection without overclaiming

## Why this skill exists

W66 shipped the Parallel Wave Lanes stack as **read-only** projection.
ADR-019 §Amendment-20 (cumulative paired-diff invariant 20) ratifies
exactly that boundary: lanes are visible and assessable, NOT authoritative.
Git remains code-history authority.

The risk W66-5's retrospective named explicitly:

> Future agents may see `lane` commands and assume enforcement exists.
> W67 contracts should explicitly cite §Amendment-20's non-ratification
> paragraph before any policy work.

This skill is that citation, lifted into a layer-shaped recipe so agents
have one place to learn what shipped + what didn't.

## What shipped in W66 (read-only)

Three CLI surfaces + one optional plan-metadata block. All read-only.

### Optional wave-level plan-metadata fields

```yaml
# .dfg/plan.yaml — under waves[*]
waves:
  - id: W66
    name: ...
    lane_id: parallel-wave-lanes      # OPTIONAL: lane bucket label
    squad_id: parallel-wave-lanes     # OPTIONAL: squad attribution
    integration_scope: S53            # OPTIONAL: SPRINT id (NOT prose)
    # ... rest of wave fields
```

**`integration_scope` is a SPRINT id, not free-form prose.** The W66-2
sandbox probe caught this — early authoring used `integration_scope:
"will integrate with W64 safety harness"` (prose) and the lane status
projection rejected it. Use `S<n>` matching a sprint declared in plan.yaml.

All three fields are OPTIONAL. Existing wave entries without them remain
valid. Adding them annotates the wave for lane projection but does NOT
trigger any enforcement.

### `dfg lane status`

```bash
# Render read-only lane status from plan + events
uv run dfg lane status --json

# Output shape (truncated):
#   {
#     "lanes": [
#       {"lane_id": "parallel-wave-lanes", "waves": [...], "status": ...},
#       ...
#     ],
#     "uncategorized_waves": [...],
#     "current_sprint": "S54"
#   }
```

Projection only. Reads `.dfg/plan.yaml` + `.dfg/events.jsonl`. Emits
nothing.

### `dfg lane conflicts`

```bash
# Advisory cross-lane integration conflicts (NOT enforcement)
uv run dfg lane conflicts --json

# Include closed/gated waves in conflict detection
uv run dfg lane conflicts --json --include-closed
```

Returns **advisory warnings only**. A returned conflict does NOT block
any operation. The signal is for operator triage. Future enforcement
would require a separate ADR amendment — not a behavioral upgrade of
this command.

### `dfg sprint integration-preview`

```bash
# Preview lane integration readiness for a sprint
uv run dfg sprint integration-preview S54 --json

# Omit sprint to infer from active_wave
uv run dfg sprint integration-preview --json
```

Read-only. Composes lane status + sprint scope into a readiness preview.

## The non-ratification list (do NOT do these)

ADR-019 §Amendment-20 explicitly does NOT ratify any of:

| Forbidden | Why |
|---|---|
| Lane events (`LaneOpened`, `LaneIntegrated`, etc.) | No new event types — assert via `tests/test_amendment_20_lane_keystone.py`. The bus has no lane-aware schema. |
| Lane-aware gate enforcement | Wave gates don't consult `lane_id`. Adding lane-awareness changes the gate authority — needs a new amendment. |
| Mini-Git / event-sharding / CRDT theater | Substrate stays simple. Git is code-history authority; events.jsonl is fact authority. |
| Merge queues per lane | Single PR queue. Parallel waves use file-disjoint parallel_groups, not lane queues. |
| `.dfg/lanes/` directories | No per-lane state. Lane state is DERIVED from plan + events, never stored. |
| Per-lane logs | Same — derived, not stored. |
| Release-capability integration | `release.publish` does not consult `lane_id`. |
| DFG branches | No `lane/` branch convention. Standard `feat/w<n>-<m>-<slug>` applies regardless of lane membership. |

The test `tests/test_amendment_20_lane_keystone.py` asserts the negative
claims explicitly — adding any of the forbidden surfaces fails the
keystone gate.

## Discipline checks

1. **Treat lane output as projection, not authority.** When `dfg lane
   conflicts` warns, surface to operator. Do NOT block actions.
2. **Never add `lane_id` to events.** The event schema is closed-enum;
   adding a lane field requires a schema bump + ADR amendment. The
   projection works without per-event lane data — it composes from
   wave-level metadata.
3. **Sprint id, not prose.** `integration_scope: S54` is valid;
   `integration_scope: "next sprint"` is rejected at validation time.
4. **Do not assume multi-wave activity implies lane enforcement.** Two
   waves active simultaneously is fine; the substrate has no opinion
   about how they integrate. Operator + agent judgement integrates them
   via standard PRs.
5. **Cite §Amendment-20 in any contract that touches lane metadata.**
   Per W66-5's `what_youd_change` recommendation, contracts should
   reference the non-ratification paragraph before any lane-related work.

## What future enforcement would require

If a future wave (W67+, W68+) wants lane-aware enforcement, the path is:

1. **Sandbox probe first.** Construct a sandbox with two open lanes and
   prove old single-lane repos remain boring. The W66-2 sandbox probe is
   the template.
2. **Author a new ADR amendment.** Cannot be inferred from §Amendment-20
   — that amendment ratifies the read-only boundary explicitly.
3. **Add cumulative invariant count.** Layer-1 paired-diff invariants
   grow by 1 per amendment; current count is 20.
4. **Keystone test pinning the new authority.** Following the W66-5
   pattern (`tests/test_amendment_20_lane_keystone.py`).
5. **No casual upgrade of `dfg lane conflicts` from advisory to
   blocking.** That's a behavioral change requiring its own amendment.

## Composing with sibling skills

- `designing-wave-parallelism` — file-disjoint parallel_groups within
  a single wave (different concept from lanes; lanes group WAVES, not units).
- `dfg-harness-plan` — sprint planning that may use lane projection
  for cross-wave visibility.
- `running-ceremony-workflows` — `dfg sprint integration-preview` runs
  inside the plan-sprint ceremony.

## Authority

- ADR-019 §Amendment-20 (W66-5 keystone, cumulative invariant count 20)
  ratifies the read-only boundary.
- `docs/spikes/PARALLEL-WAVE-LANES-SPIKE.md` is the design doc with
  shipped / deferred sections.
- `tests/test_amendment_20_lane_keystone.py` pins what didn't ship.
- `dfg lane --help` / `dfg sprint integration-preview --help` are
  canonical CLI shape.
- W66-2 sandbox probe receipt: `integration_scope` must be a sprint id.
