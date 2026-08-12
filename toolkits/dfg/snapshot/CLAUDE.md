# harness-perf

This project was bootstrapped with `dfg-harness` v0.11.71.

For agents (and humans) entering cold:
1. Read `MASTER_CONTEXT_INDEX.md` — the routing table.
2. Read `DFG.md` — the wave plan.
3. Read `PROVENANCE_INDEX.md` — what's in flight.

<!-- BEGIN dfg-harness v0.11.71 -->
## dfg-harness — installed kit

This project uses the `dfg-harness` methodology and templates. The kit
contributes the marker-bracketed section below; everything outside the
markers is yours to edit. Do **not** edit between the markers — `dfg-harness
update` regenerates this block (with a backup of the prior contents).

**Routing entry point:** `MASTER_CONTEXT_INDEX.md`

**Slash commands** (under `.claude/commands/`, flat with `harness-` prefix):

- `/harness-classify-intervention`
- `/harness-close-wave`
- `/harness-critic-assumption`
- `/harness-critic-problem`
- `/harness-pre-pr-checklist`
- `/harness-propose-dfg`
- `/harness-run-wave`

**Subagents** (under `.claude/agents/`):

- `harness-critic-assumption`
- `harness-critic-problem`
- `harness-dfg-planner`
- `harness-hitl-classifier`
- `harness-wave-gate`

**Settings:** Pre-approved permissions live in `.claude/settings.local.json`
(see the SDLC settings template for the merge contract).

**Marker discipline:** Edits inside `<!-- BEGIN dfg-harness ... -->` /
`<!-- END dfg-harness -->` are owned by the kit. To customise instructions
for agents, add your sections **outside** the markers.
<!-- END dfg-harness -->

## Project-specific guidance

<!-- Add any project-specific guidance for agents here. This section is
yours to edit; the harness will not touch it on `update`. -->
