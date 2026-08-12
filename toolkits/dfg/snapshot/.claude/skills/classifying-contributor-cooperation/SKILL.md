---
name: classifying-contributor-cooperation
description: Guardian skill that wraps cooperation-classifier.py to score PR contributions
  across 12 substrate-evidence signals and classify into cooperation tiers (0-3).
  Emits CooperationTierClassified events that drive notification fabric and critic
  cadence per .dfg/governance/cooperation-tiers.yaml. Activated structurally by PR
  open/sync events — never by natural-language nudges (per ADR-019 §amendment-5).
criticality: important
sdlc_category: Review
loop_layer: L3-unit
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill to classify contributor cooperation tier based on substrate
  evidence.

  The classification drives:

  - Critic auto-fire cadence (Tier 2/3: force-on, cannot be disabled)

  - Notification fabric (weekly digest → daily digest → immediate ping)

  - Gate composition (Tier 2: +coaching, Tier 3: +vision-guardian + auto-draft)

  - Velocity levers (Tier 0/1: available, Tier 2/3: disabled)

  '
verified_at: 2026-05-06
forged_by: dfg-harness W26-4 2026-05-06 contract-first authoring
---
# Classifying Contributor Cooperation — Guardian Skill

## Why this skill exists

The operator directive 2026-05-06:

> **"If contributor bypasses all guidance, notify Carlos / offer to escalate.  
> If contributor agrees and adopts -- even if not entirely, we turn on  
> critics (do not let them be turned off) and watch + notify Carlos silently.  
> If moderate/strong cooperation -- go in peace."**

The harness has discipline invariants (contract-first, retro-present, external-libs-cited, etc.). Contributors demonstrate cooperation by following these disciplines. The cooperation tier determines:

1. **Critic policy** — Tier 0/1: opt-in; Tier 2/3: force-on (cannot be disabled)
2. **Notification cadence** — Tier 0: passive; Tier 1: weekly digest; Tier 2: daily digest; Tier 3: immediate ping + auto-issue
3. **Gate composition** — Tier 2: +contribution-coaching-gate; Tier 3: +vision-guardian-gate + auto-draft PR
4. **Velocity access** — Tier 0/1: full velocity mode available; Tier 2/3: full review cycle (no velocity shortcuts)

This skill is the **classification surface** that scores each PR and emits the tier classification event.

---

## Trigger conditions (substrate-evidence only — per ADR-019 §amendment-5)

Per ADR-019 §amendment-5 ("Trigger discipline: substrate-evidence over natural-language"), this skill activates on **deterministic diff/path signals**, never on operator or agent prose. The detector is the GitHub Actions workflow `.github/workflows/cooperation-classifier.yml`, which runs on:

1. **`pull_request` opened**
2. **`pull_request` reopened**  
3. **`pull_request` synchronize** (new commits pushed to PR branch)

The workflow invokes `kit/scripts/cooperation-classifier.py --emit-event`, which:
- Scores the PR across 12 substrate-evidence signals
- Maps total score to cooperation tier (0-3)
- Emits `CooperationTierClassified` event to `.dfg/events.jsonl`

**Explicitly NOT triggers (deleted per §amendment-5):**
- ❌ "Operator asks 'what tier is this PR?'" — the request becomes substrate inspection of events.jsonl, not a skill invocation
- ❌ "Agent decides to check cooperation" — irrelevant until a PR open/sync event fires the workflow

---

## The four cooperation tiers

Per `.dfg/governance/cooperation-tiers.yaml`:

| Tier | Name | Detection rule | Critics | Notifications | Pace |
|------|------|----------------|---------|---------------|------|
| **0** | owner | `author ∈ authority.yaml operators` AND `scope match` | opt-in | passive (dfg status) | go-in-peace |
| **1** | strong-cooperation | `score ≥ 80` AND `no forbidden patterns` AND `author NOT owner` | auto-fire on rule-logic PRs + every 5th PR | weekly digest | go-in-peace |
| **2** | partial-cooperation | `score 40-79` OR `missing required discipline file` | **FORCE-ON** (cannot disable) | daily digest | coached |
| **3** | bypass | `score < 40` OR `any forbidden pattern` OR `edits non-negotiables without authority` | **FORCE-ON** + vision-guardian | immediate ping + auto-issue + auto-draft | held (manual un-block) |

---

## The 12 substrate-evidence signals

Each PR is scored across these 12 signals (total: 100 points):

| Signal | Weight | Pass condition |
|--------|--------|----------------|
| **contract-first-shape** | 10 | First commit is contract-only (`.dfg/agents/W*-*.md`, no impl files) |
| **branch-shape-match** | 5 | Branch matches canonical patterns (`feat/w*`, `chore/`, `docs/`, `fix/`, etc.) |
| **per-unit-retro-present** | 10 | `.dfg/retrospectives/W<N>/W<N>-<M>.md` present in diff |
| **external-libs-cited** | 10 | Every external import has `read_contract.external_libs[]` citation with docs URL + verified_at |
| **required-skills-cited** | 5 | Contract cites required skills when applicable |
| **substrate-evidence-triggers** | 15 | New SKILL.md / check scripts use substrate triggers only (no natural-language anti-patterns) |
| **schema-version-bump-paired** | 10 | Schema changes paired with version bump in `$comment` field |
| **discipline-change-paired** | 10 | Discipline file changes paired with `DISCIPLINE-CHANGELOG.md` entry |
| **modifications-ledger-paired** | 10 | Admin/archetype-07 actions paired with `.dfg/modifications.md` entry |
| **no-forbidden-patterns** | 10 | No `--no-verify`, no `force-push origin main`, no events.jsonl regression |
| **tests-proportional** | 5 | Test coverage proportional to src changes (heuristic: ≥1 test file when src/ modified) |
| **single-wave-pr** | 0 | Boolean gate (enforced by `single-wave-pr-check.py` hook, not scored here) |

**Score-to-tier mapping:**
- ≥ 80 → Tier 1 (strong cooperation)
- 40-79 → Tier 2 (partial cooperation)
- < 40 → Tier 3 (bypass)
- Forbidden pattern (any) → immediate Tier 3 override

---

## Event structure

The emitted `CooperationTierClassified` event (per `kit/SCHEMAS/events.schema.json`):

```json
{
  "type": "CooperationTierClassified",
  "timestamp": "2026-05-06T...",
  "schema_version": "1.7.0",
  "actor": "ci",
  "_source": "kit/scripts/cooperation-classifier.py",
  "detail": {
    "tier": 1,
    "tier_name": "strong-cooperation",
    "total_score": 85,
    "max_score": 100,
    "signals": [
      {
        "signal_id": "contract-first-shape",
        "weight": 10,
        "earned": 10,
        "passed": true,
        "rationale": "First commit is contract-only (.dfg/agents/W26-4-*.md)"
      },
      ...
    ]
  }
}
```

The event is **informational** — it does not block merge. Downstream consumers:
1. **Notification fabric** (`kit/scripts/cooperation-digest.py`, W28-5) — reads tier, emits weekly/daily/immediate pings per tier
2. **Critic auto-fire** (existing harness-critic-* agents) — reads tier, adjusts auto-fire cadence
3. **Coaching gate** (`contribution-coaching-gate`, W28-3) — activates on Tier 2
4. **Vision guardian** (`vision-guardian-gate`, W28-4) — activates on Tier 3
5. **Operator dashboard** (`dfg status --cooperation`) — surfaces tier stats

---

## Composition with other primitives

- **skill-assessment-gate** (W23-6) — same substrate-trigger discipline; this skill is the cooperation-tier analog for skill adoption
- **ADR-019 pain-to-hook ratchet** — each signal is a Layer-1 invariant surfaced via the ratchet (contract-first, retro-present, external-libs-cited, etc.)
- **ADR-022 governance ladder** (ratified W26-1) — ratifies cooperation-tiers.yaml as canonical authority
- **verifying-external-package** (W23-7) — feeds into signal #4 (external-libs-cited)
- **single-wave-pr-check.py** hook — enforces signal #12 (single-wave-PR discipline)

---

## When this skill REFUSES to classify

The classifier (`cooperation-classifier.py`) exits 0 (informational) in all cases — it never blocks. But it logs warnings for:

- **No commits found** (empty PR)
- **Base SHA unresolvable** (malformed PR; falls back to `HEAD~1`)
- **Contract parse failure** (YAML frontmatter malformed; signal #4 scores 0)

The GitHub Actions workflow surfaces these as annotations (workflow warnings, not failures).

---

## Test-of-skill (evaluation cases)

| Scenario | Expected tier | Rationale |
|----------|---------------|-----------|
| Carlos's PR, in-scope subsystem | Tier 0 | Owner always Tier 0 |
| External contributor: contract-first + retro + tests + 85/100 score | Tier 1 | Strong cooperation |
| External contributor: impl-first commit, no retro, 55/100 score | Tier 2 | Partial cooperation → critics force-on |
| External contributor: no retro, `--no-verify` in commit msg, 30/100 | Tier 3 | Forbidden pattern → immediate escalation |
| External contributor: edits `.dfg/governance/non-negotiables.yaml` without authority | Tier 3 | Forbidden pattern (escalation:always subsystem) |

---

## Layer composition

- **L0 (Release):** Cooperation-tiers.yaml frozen at release tag; tier definitions stable across minor versions
- **L1 (Sprint):** Signal weights can be adjusted via operator directive + ADR ratification (e.g., boost retro-present weight 10→15)
- **L2 (Wave):** New signals can be added (e.g., W28 might add "ADR-citation-paired" for ADR edits)
- **L3 (Unit):** This skill classifies per-PR (unit-scoped event)

---

## Manual invocation (opt-in)

The GitHub Actions workflow is the canonical trigger (automatic on PR open/sync). For manual classification (e.g., testing, local dev):

```bash
# From repo root
python kit/scripts/cooperation-classifier.py \
  --base origin/main \
  --repo-root . \
  --emit-event
```

Output:
```
[cooperation-classifier] Tier 1 (strong-cooperation)
Score: 85/100

Signal breakdown:
  ✅ contract-first-shape: 10/10 — First commit is contract-only (.dfg/agents/W26-4-*.md)
  ✅ branch-shape-match: 5/5 — Branch 'feat/w26-4-classifying-contributor-cooperation' matches pattern ^feat/w[0-9]+-[0-9]+-
  ...
  ❌ per-unit-retro-present: 0/10 — No retrospective file in diff (.dfg/retrospectives/W*/W*-*.md)

[cooperation-classifier] Event emitted to .dfg/events.jsonl
```

---

## References

- Operator directive 2026-05-06 — "If contributor bypasses all guidance, notify Carlos / offer to escalate..."
- `.dfg/governance/cooperation-tiers.yaml` — canonical tier definitions (ratified ADR-022, W26-1)
- `.dfg/governance/authority.yaml` — operator authority matrix (who can edit what)
- `kit/scripts/cooperation-classifier.py` — the 12-signal scorer + tier mapper
- ADR-019 §pain-to-hook ratchet — methodology that surfaced the 12 signals as Layer-1 invariants
- ADR-019 §amendment-5 — substrate-evidence trigger discipline (this skill's compliance receipt)
- `docs/_drafts/governance-component-view-2026-05-06.html` — visual component diagram (operator artifact that spawned cooperation-tiers.yaml)
