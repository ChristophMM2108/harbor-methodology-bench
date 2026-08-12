---
name: enforcing-non-negotiables
description: Guardian skill that scans PR diffs against .dfg/governance/non-negotiables.yaml
  and BLOCKS merge on violation. Enforces Carlos's vision invariants — the principles
  no PR may violate regardless of author authority. Activated structurally by kit/scripts/enforcing-non-negotiables-check.py
  — never by natural-language nudges (per ADR-019 §amendment-5).
criticality: important
sdlc_category: Review
loop_layer: L2-wave
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill BEFORE merging any PR to verify it doesn''t violate the
  governance invariants defined in non-negotiables.yaml. The skill is the structural
  enforcement of owner-authority governance per ADR-022 (v0.4.5 W26).

  '
verified_at: 2026-05-06
forged_by: dfg-harness W26-3 2026-05-06 Guardian skill per Build-Skills-Not-Agents
  pattern
---
# Enforcing Non-Negotiables — governance invariant enforcement

## Why this skill exists

The dfg-harness governance model has three authority tiers (owner-only / operator / contributor-tier-0-4). Some principles are **non-negotiable** — they must hold regardless of author authority. Examples:

- **Contract-first invariant** — every feat branch starts with a contract commit
- **Schema-version-bump invariant** — schema changes require version increment
- **Retro-present invariant** — every unit ships with a retrospective
- **External-library API verification** — every outside-core import requires docs verification

These invariants are codified in `.dfg/governance/non-negotiables.yaml`. This skill is the enforcement surface that scans every PR diff for violation signals and BLOCKS merge until resolved.

## Trigger conditions (substrate-evidence only — per §amendment-5)

Per ADR-019 §amendment-5 ("Trigger discipline: substrate-evidence over natural-language"), this gate activates on **deterministic diff/path signals**, never on operator or agent prose. The detector is `.claude/skills/enforcing-non-negotiables/check.py`, run in the pre-pr battery and CI.

Auto-trigger on ANY of:
1. **PR opened / updated** — `git diff <base>...HEAD` produces a non-empty diff AND the skill is invoked explicitly via `/enforcing-non-negotiables` OR automatically via pre-pr battery
2. **Pre-pr battery** — `dfg pre-pr` includes this check in its standard battery
3. **CI workflow** — `.github/workflows/non-negotiables-gate.yml` (if forged) runs the check on every PR

Explicitly NOT triggers (deleted per §amendment-5):
- ❌ "Operator says 'check non-negotiables'" — natural-language; the request becomes a `/enforcing-non-negotiables` invocation which IS the substrate signal (#1)
- ❌ "Agent decides to check governance" — irrelevant until the check is actually invoked via one of the substrate triggers above

## How it works

### Step 1 — Load non-negotiables.yaml

```python
import yaml
with open('.dfg/governance/non-negotiables.yaml') as f:
    spec = yaml.safe_load(f)
```

The spec has three sections:
- `layer1_invariants` — 11 canonical paired-diff invariants (per ADR-019 §amendment-1)
- `design_principles` — 5 higher-level composition principles
- `forbidden_patterns` — 5 substrate-detectable bypasses

### Step 2 — Scan PR diff for violation signals

For each invariant/principle/pattern, the `violation_signal` field describes a substrate-evidence pattern:

```yaml
- id: contract-first
  violation_signal: "impl commit on a feat/wN-M branch without preceding contract commit"
```

The check.py script:
1. Runs `git log --oneline <base>..HEAD` to get the commit list
2. For `feat/w<N>-<M>-*` branches, asserts commit-1 adds only `.dfg/agents/W<N>-<M>-*.md`
3. If violation detected → emit `NonNegotiableViolation` event

### Step 3 — Emit violation events

```python
from dfg_harness.emit import emit_event

emit_event({
    "event_type": "NonNegotiableViolation",
    "invariant_id": "contract-first",
    "violation_signal": "impl commit on feat/w26-3 without contract",
    "remediation": "Author the contract as commit-1",
    "detected_at": datetime.now(timezone.utc).isoformat(),
    "pr_ref": "<base>..HEAD"
})
```

### Step 4 — Return non-zero exit code to block merge

The check.py script exits with code 1 if ANY violations detected. CI gates (if configured) block merge on non-zero.

## Violation signals catalog (examples from non-negotiables.yaml)

| Invariant | Violation signal (substrate-evidence) |
|---|---|
| contract-first | impl commit on `feat/wN-M` without preceding contract commit |
| schema-version-bump | `events.schema.json` modified without `schema_version` increment |
| retro-present | PR closing unit lacks `.dfg/retrospectives/W<N>/W<N>-<M>.md` |
| discipline-change-paired | PR modifies gate script without DISCIPLINE-CHANGELOG.md entry |
| modifications-ledger | admin-merge / --no-verify / force-push without `.dfg/modifications.md` entry |
| external-library-API-verification | outside-core import without `read_contract.external_libs[]` citation |
| substrate-evidence-triggers | new SKILL.md trigger section uses natural-language hints instead of diff/AST signals |

## When this skill REFUSES to check

- The PR is a revert commit (revert commits bypass some invariants)
- The PR is operator-staged with explicit `--bypass-non-negotiables` flag (archetype-07 admin-merge exception)
- The non-negotiables.yaml file itself is being modified (owner-authority edit; separate review required)

## Test-of-skill (evaluation cases)

| Scenario | Expected verdict |
|---|---|
| `feat/w26-3` branch starts with contract commit | PASS |
| `feat/w26-3` branch starts with impl commit | FAIL — contract-first violated |
| PR modifies `events.schema.json` AND bumps `schema_version` | PASS |
| PR modifies `events.schema.json` WITHOUT version bump | FAIL — schema-version-bump violated |
| PR closes unit W26-3 with retro at `.dfg/retrospectives/W26/W26-3.md` | PASS |
| PR closes unit W26-3 without retro | FAIL — retro-present violated |
| PR adds `from anthropic import Anthropic` with contract citation | PASS |
| PR adds `from anthropic import Anthropic` without citation | FAIL — external-library-API-verification violated |

## Layer composition

- L2 (Wave): this skill, fires per PR in a wave
- L1 (Sprint): `harness-pre-pr-checklist` invokes this skill as part of the battery
- L0 (Release): release-cadence skill verifies all non-negotiables held across the release

## Composition with other primitives

- **skill-assessment-gate** — This skill is harness-forged (`forged_by: dfg-harness ...`) so it auto-passes external assessment
- **ADR-019 §amendment-1** — Defines the Layer-1 invariants this skill enforces
- **ADR-019 §amendment-5** — Defines the trigger discipline (substrate-evidence only)
- **ADR-022** (forthcoming) — Will ratify non-negotiables.yaml as governance authority
- **non-negotiables.yaml** — The canonical spec this skill enforces

## References

- `.dfg/governance/non-negotiables.yaml` — The governance authority
- ADR-019 §amendment-1 — Structural impossibility over prose detection
- ADR-019 §amendment-5 — Trigger discipline: substrate-evidence over natural-language
- Operator directive 2026-05-06 — "Non-negotiables must be enforced structurally"
- governance-component-view artifact — `docs/_drafts/governance-component-view-2026-05-06.html` (origin)
