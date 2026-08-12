---
name: running-ceremony-workflows
description: Layer-shaped skill teaching the dfg ceremony workflow recipe. Covers
  `dfg run` (start a workflow), `dfg run-resume` (continue after a HITL pause), workflow
  discovery via `kit/ceremonies/*.yaml` and `dfg run --help`, parameterized inputs
  (`--input KEY=VAL`), pause/resume semantics, state files at `.dfg/ceremony-runs/<attempt_id>.json`,
  and event-emission gotchas. Used whenever an agent needs to drive a `dfg run <ceremony>`
  workflow (pre-flight, ship-release, wave-close, plan-sprint, release-prep) instead
  of reinventing the steps inline.
criticality: important
trigger: substrate-evidence
trigger_evidence: "Activate when:\n- Operator types `dfg run <name>` or `dfg run-resume\
  \ <attempt_id>`.\n- Diff stages a new file under `kit/ceremonies/*.yaml`.\n- Agent\
  \ is about to author a ceremony from inline bash steps when a\n  blessed workflow\
  \ already covers the recipe.\n- A previous `dfg run` invocation exited 3 (PAUSED)\
  \ and the agent\n  needs to resume.\n"
sdlc_category: Operations
loop_layer: L2-wave
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill BEFORE driving any `dfg run` ceremony — pre-flight before

  starting a wave, ship-release for v0.5.x publication, wave-close before

  the gate PR, plan-sprint for the next sprint. The skill prevents agents

  from reinventing the workflow inline (which loses the event-bus emission)

  and from missing the pause/resume semantics that bite at HITL boundaries.

  '
verified_at: 2026-05-17
forged_by: dfg-harness W67-2 layer-shaped-skills
---
# Running ceremony workflows

## Why this skill exists

The harness grew a ceremony layer in W57 (ADR-035) and parameterized
workflows in W61. Five blessed workflows ship under `kit/ceremonies/`:

| Workflow | Purpose | Inputs | Pauses |
|---|---|---|---|
| `pre-flight` | Establish substrate truth before any wave action | none | 0 |
| `release-prep` | Manual version-bump + doc-edit prep (1st of 2 release PRs) | none | 0 (prints prompts) |
| `wave-close` | Pre-close + operator HITL + post-close + preflight-ready | `CURRENT_WAVE` | 1 |
| `ship-release` | End-to-end blessed release with 3 HITL pauses | `VERSION`, `CURRENT_WAVE` | 3 |
| `plan-sprint` | Sprint planning ceremony | depends on substrate | varies |

Agents that reinvent these steps inline lose:

- `Ceremony*` event emission to `.dfg/events.jsonl` (PAUSE state cannot
  be resumed if the start event is missing).
- The pause/resume contract — operator-handoff turns become invisible.
- The `--input KEY=VAL` parameterization that lets one workflow YAML
  cover every wave/version.

This skill teaches the recipe so agents drive workflows through `dfg run`
rather than rebuilding them from bash.

## Workflow discovery

```bash
# Authority: dfg run --help
uv run dfg run --help

# Inspect available workflows
ls kit/ceremonies/

# Read a workflow's shape (steps + inputs + pauses)
cat kit/ceremonies/ship-release.yaml
```

The YAML shape is fixed by `kit/SCHEMAS/ceremony.schema.json` (closed-enum
step kinds: `run`, `pause`, `workflow`). Inputs are declared in the
`inputs:` block; `derive_from: cli` means `--input KEY=VAL`, `derive_from:
substrate` means dfg infers from state.json / events.jsonl.

## Starting a workflow

```bash
# Bare workflow (no parameters)
uv run dfg run pre-flight

# Parameterized workflow — repeat --input for multiple keys
uv run dfg run ship-release --input VERSION=0.5.34

# Dry-run (print step plan; do not execute or emit events)
uv run dfg run ship-release --input VERSION=0.5.34 --dry-run

# Machine-readable output (verdict on stdout)
uv run dfg run pre-flight --json
```

Exit codes (closed-enum per `dfg run --help`):

- `0` — completed (verdict PASS) or dry-run
- `1` — failed (one step failed or invalid workflow)
- `2` — workflow not found
- `3` — paused (HITL boundary; `dfg run-resume` to continue)

## Resuming after a pause

When a workflow hits a `pause:` step it exits with code 3 and persists
state to `.dfg/ceremony-runs/<attempt_id>.json`. The operator (or a
follow-up agent) completes the HITL action (e.g., opens and merges a PR),
then resumes:

```bash
# The attempt_id is printed at pause time; also recoverable from state file
ls .dfg/ceremony-runs/

# Resume — skips already-completed steps, continues from the step AFTER the pause
uv run dfg run-resume <attempt_id>

# Resume with JSON output
uv run dfg run-resume <attempt_id> --json
```

Chained pauses are supported: if the resumed workflow hits another `pause:`
it halts again with code 3 and the operator runs `dfg run-resume` again.
`ship-release` has 3 pauses (release-prep PR, gate PR, publish confirmation)
so a full v0.5.x publication involves `dfg run` once and `dfg run-resume`
three times.

## Reading the state file

```bash
# Inspect the persisted state for a paused workflow
cat .dfg/ceremony-runs/<attempt_id>.json | jq '.status, .current_step, .completed_steps'
```

State fields you care about:

- `status`: RUNNING | PAUSED | COMPLETED | FAILED
- `current_step` / `completed_steps`: which step the workflow stopped at
- `inputs`: what `--input KEY=VAL` (or substrate-derived) values are bound
- `attempt_id`: the 64-char hex id you pass to `dfg run-resume`

## Gotchas

1. **Workflows emit events on every run.** `Ceremony*` events land in
   `.dfg/events.jsonl`. Cap retries — repeated runs of a failing workflow
   bloat the bus and make subsequent `dfg index --verify` slow.
2. **Use `--no-emit` for inspection.** When testing a workflow shape or
   running it from a sandbox, pass `--no-emit` so the substrate is not
   mutated.
3. **`--dry-run` is the safest first call.** Lets you confirm the step
   plan and resolved inputs before any emission or execution.
4. **The schema validates inputs.** Misspelled `--input KEY=VAL` keys
   fail at validation time, not at the step that references them.
5. **CLI inputs win over substrate-derived inputs.** Useful for testing
   with a non-canonical `CURRENT_WAVE`, but be intentional — substrate
   is the default authority.
6. **`pause:` is operator-visible.** The pause `prompt:` text is shown
   on stderr at pause time; design clear prompts when authoring new
   workflows.

## Composing with sibling skills

- `forging-unit-contract` — runs at unit start; `dfg run pre-flight`
  always precedes contract authoring.
- `closing-wave-and-releasing` — full release recipe wraps `dfg run
  ship-release` end-to-end with the 3 HITL pauses.
- `shipping-wave-close-gate` — `dfg run wave-close` is the operator-handoff
  wrapper around `dfg wave close <wave-id>`.

## Authority

- `dfg run --help` is canonical — if recipe drifts from CLI shape, CLI wins.
- `kit/SCHEMAS/ceremony.schema.json` is the workflow schema authority.
- ADR-035 ratifies the ceremony layer (W57 keystone).
- W57/W59/W61 receipts: ceremony.discoverability, run-resume semantics,
  parameterized inputs.

## Capability routing during ceremonies

Before starting or resuming a ceremony, run the calm path rather than relying on memory:

```bash
uv run dfg flow next
uv run dfg status --json
```

Use the status/next output as the routing layer for recently shipped capabilities:

- If `capability_nudges` mentions retro planning, expect `wave-close` to run `dfg retro replan-suggest --mode lightweight` by default. Operators can opt out with `DFG_SKIP_RETRO_REPLAN_SUGGEST=1`.
- If the ceremony is release-adjacent, verify identity and policy posture before high-blast actions with `dfg actor whoami`, `dfg actor verify --id <actor>`, and `dfg permit <action> --actor <actor>`.
- If lifecycle scars are visible, inspect `dfg history` before asserting calmness; use history pardons only through the blessed history-pardon path.
- If the ceremony adds a new command or blessed workflow, run `uv run python kit/scripts/capability-packaging-check.py --base origin/main` before pre-pr so the capability has an explicit route.

The ceremony layer is the actuator. Status, actor verification, history pardon, permit, and packaging checks are the situational routing layer around it.
