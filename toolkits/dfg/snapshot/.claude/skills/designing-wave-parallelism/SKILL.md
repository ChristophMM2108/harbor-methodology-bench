---
name: designing-wave-parallelism
description: Generative skill computing parallel_groups from a unit set by file-disjointness
  analysis. Recommends serial / parallel layering with risk-gradient ordering. Used
  during wave authoring before contracts are committed to plan.yaml.
criticality: important
trigger: substrate-evidence
trigger_evidence: "Activate when:\n- Diff stages new wave entries under plan.yaml.waves[*]\
  \ AND no\n  parallel_groups field is present.\n- `dfg replan accept` just ratified\
  \ a wave addition.\n- Operator types \"design W* parallelism\" or \"what should\n\
  \  parallel_groups look like for ...\"."
---
# Designing wave parallelism

## Why this skill exists

File-disjointness is necessary-but-insufficient for safe parallelism
(W19-3 receipt: collapsed parallel_groups ignored operator-encoded risk
gradient; later restored). Operator pain shows two recurring mistakes:

1. **Naive optimism** — "all units touch different files, so all
   parallel" ignores upstream risk dependencies.
2. **Conservative pessimism** — "everything serial" forgoes ~3-4×
   throughput on truly independent units.

This skill formalizes the analysis.

## Inputs

- The unit set (id, files, depends_on).
- Optional risk hints: which units are speculative vs proven? Which
  call external APIs? Which mutate substrate the others read?

## Algorithm

1. **Collect file-touch-sets** — for each unit, the union of
   `read_contract.must_read` and `output_contract.files`.
2. **Build collision graph** — units U and V have an edge iff their
   file sets intersect on a file that ANY of them WRITES (file pairs
   read-only by both don't conflict).
3. **Color the graph greedily** by ascending risk gradient: kernel/
   substrate first, then code, then docs, then tests. Each color
   class becomes one parallel_group; classes serialize in color
   order.
4. **Honor `depends_on`** — append serializing layer if any unit's
   dependency is in a later color class.
5. **Insert risk barriers** — after VT0 / VT1 (substrate / kernel)
   units, force a layer break even if file-disjoint, so failures
   surface before downstream units start.

## Output

```yaml
parallel_groups:
  - [W*-1, W*-3]      # color class 1, file-disjoint, low-risk
  - [W*-2]            # serial after due to file collision
  - [W*-4, W*-5]      # color class 2 — all in parallel
```

## Risk-gradient rules

| Tier | Touches | Rule |
|---|---|---|
| VT0 | ADRs, kit/, hooks | Serial — never parallel |
| VT1 | src/dfg_harness/ | Parallel only when file-disjoint |
| VT1 | tests/ | Always parallel |
| VT2 | docs/ | Always parallel |

## Discipline checks

1. Every unit appears in exactly one parallel_group.
2. parallel_groups respect `depends_on` (no unit dispatches before
   its dependency completes).
3. No two units in the same parallel_group write to the same file.
4. Run `kit/scripts/parallel-groups-coherence-check.py` before
   committing the wave.

## §Amendment-trigger guard

If the operator says "we shouldn't have parallelized X with Y" for the
2nd+ time on the same kind of pair (e.g., "always two units writing
launcher.py"), surface the §amendment trigger: this is now a Layer-1
substrate-encoded constraint, not a per-wave judgment call.

## Parallel-lane routing bundle

For multi-agent or multi-lane work, compute parallelism from the substrate before dispatching agents:

```bash
uv run dfg lane status --json
uv run dfg lane conflicts --json
uv run dfg sprint integration-preview <SPRINT_ID> --json
uv run dfg coordination status --json
```

Use the outputs as routing constraints:

- `dfg lane conflicts --json` must be empty before claiming lanes are independent.
- `dfg sprint integration-preview <SPRINT_ID> --json` is the sprint-level readiness check; open wave gates mean integration is not ready yet.
- `dfg coordination status --json` is the waiting/nudge/fallback surface when one lane is blocked on another actor or captain.
- If a lane introduces a new command or ceremony, require capability packaging evidence in that lane before allowing it to become a shared dependency.
- If actor ownership matters, pair lane assignment with `dfg actor verify --id <actor>` and `dfg permit <action> --actor <actor>` instead of accepting self-asserted labels.

Max parallelism means independent useful concurrency, not maximum busy agents. The lane bundle is the guardrail against turning throughput into correlated rework.
