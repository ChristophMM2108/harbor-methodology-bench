---
name: skill-assessment-gate
description: 'Required when the diff adds a .claude/skills/*/SKILL.md (or installs
  a plugin skill) without a paired .dfg/skills/assessments/<skill-name>.yaml, OR a
  contract YAML adds read_contract.required_skills naming an unknown skill. Asserts
  six alignment conditions: provenance, discipline-coherence, API-verification, idempotency,
  layer-classification, trigger-discipline. Activated structurally by kit/scripts/skill-assessment-gate-check.py
  — never by natural-language nudges (per ADR-019 §amendment-5).'
criticality: important
sdlc_category: Skills Meta
loop_layer: L2-wave
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill BEFORE accepting an external skill into the dfg-harness
  curated set. The skill is the structural enforcement of the operator directive 2026-05-06:
  "we need to assess them before accepting and using (the external ones) as they cannot
  contradict the harness discipline."

  '
verified_at: 2026-05-06
forged_by: dfg-harness 2026-05-06 operator directive
---
# Skill Assessment Gate — vet before adopt

## Why this skill exists

The Anthropic skill ecosystem is rich and growing. Some skills are excellent. Others embed assumptions that contradict the harness discipline (e.g., a skill that auto-merges PRs without dual-critic review, or one that bypasses contract-first by writing impl-then-contract).

The harness has discipline invariants that MUST hold. External skills must be assessed against those invariants before adoption.

This skill is the gate.

## Trigger conditions (substrate-evidence only — per §amendment-5)

Per ADR-019 §amendment-5 ("Trigger discipline: substrate-evidence over natural-language"), this gate activates on **deterministic diff/path signals**, never on operator or agent prose. The detector is `kit/scripts/skill-assessment-gate-check.py`, run in the pre-pr battery and CI.

Assessment must complete **before merge**, never post-hoc.

Auto-trigger on ANY of:
1. **`git diff --name-only <base>..HEAD`** includes a new `.claude/skills/<skill-name>/SKILL.md` AND no matching `.dfg/skills/assessments/<skill-name>.yaml` is present in the same diff with verdict `ACCEPT` or `CONDITIONAL`
2. **Same shape** for plugin-marketplace installs landing under `.claude/plugins/<plugin>/skills/*/SKILL.md` (plugin manifest path is the substrate signal — no natural-language opt-in)
3. **Contract YAML** (`.dfg/agents/*.md` frontmatter) adds `read_contract.required_skills: [<name>]` where `<name>` is not present as `.claude/skills/<name>/SKILL.md` OR `~/.claude/skills/<name>/SKILL.md` at PR-base SHA — plan-validation BLOCKS until either the skill is added (subject to triggers #1/#2) or the citation is removed
4. **Cross-repo bootstrap** kit copies a new SKILL.md into a downstream repo — same diff-shape rule applies in that repo

Explicitly NOT triggers (deleted per §amendment-5):
- ❌ "Operator says 'let's adopt skill X' or 'import skill Y'" — the request becomes a PR; the PR diff IS the substrate signal (#1/#2)
- ❌ "Agent decides a skill would be useful" — irrelevant until the agent attempts to add it via a SKILL.md file or a contract citation

## The six assessment dimensions

### 1. Provenance

| Question | Pass condition |
|---|---|
| Who authored this skill? | Anthropic-published OR named author OR commit-sha pinned community |
| What's the license? | OSS license declared in SKILL.md frontmatter |
| Is the source repository active? | Last commit <90 days for external skills (per §amendment-4 freshness pattern) |

If FAIL on provenance → reject. Do not adopt skills with unknown origin.

### 2. Discipline coherence

The harness has these invariants. The skill must NOT contradict any:

| Invariant | Skill must NOT |
|---|---|
| Contract-first | Author impl before contract |
| Three-commit pattern | Bundle contract + impl into one commit |
| Retro-present | Skip retros |
| Discipline-change-paired | Modify CI scripts without paired discipline-changelog entry |
| Modifications-ledger | Skip modifications.md for archetype-7 actions |
| Re-plan-first | Modify plan.yaml without RePlanAccepted event |
| Doc-update-paired | Ship a code change touching ADR without updating ADR |
| Backfill-paired | Add new event type without backfill |
| Substrate-derived parallelism | Hand-author parallel_groups |
| External-library API verification | Recommend an import without docs verification |
| Skill-required-declared | Use a skill not declared in contract.required_skills |

Check method: read SKILL.md body. If the skill instructs the agent to do any of the FORBIDDEN actions above, fail.

### 3. API verification

If the skill recommends external libraries:
- Each library must be cited with docs URL + verified_at date
- Per §amendment-4 (W22-8) — same standard applied to skills as to contracts

If the skill embeds CLI invocations:
- The CLI tool must exist on the operator's machine (assess via `which <tool>`)
- Or the skill must declare the install path as a precondition

If the skill calls API endpoints:
- Endpoints must be cited with their canonical docs

### 4. Idempotency contract

The SKILL.md must declare one of:
- `idempotent: true` — running the skill multiple times is safe
- `idempotent: false` — single-shot only; declare the side-effects
- `idempotent: best-effort` — usually safe but document the edge cases

Skills without an idempotency declaration get a stub `unknown` and require operator review before adoption.

### 5. Layer classification

The SKILL.md frontmatter must declare:
- `sdlc_category`: one of {Plan, Design, Implementation, Testing, Review, Release, Operations, Retrospective, Skills-Meta}
- `loop_layer`: one of {L0-strategic, L1-sprint, L2-wave, L3-unit, L4-action}

This locates the skill in the layered hierarchy. Skills without classification cannot be enforced via Layer-1 gate (because contracts cite skills by layer + category).

### 6. Trigger discipline

The `when_to_use` field must be specific. Reject skills that say:
- "Use this for any task" (too broad)
- "Whenever helpful" (useless)
- "When the agent decides" (no discipline)

Pass conditions:
- `when_to_use` enumerates concrete trigger conditions
- Triggers compose with archetype mapping in `kit/agents/dispatcher.md`
- Skill can be auto-triggered (description-match) OR explicit-invoked (`/skill-name`)

## Assessment output (per skill)

After running this gate against a candidate skill:

```yaml
# .dfg/skills/assessments/<skill-name>.yaml
skill_name: <name>
assessed_at: 2026-05-06
verdict: ACCEPT | REJECT | CONDITIONAL
provenance: { author: ..., license: ..., last_commit: ..., status: PASS|FAIL }
discipline_coherence: { invariants_audited: 11, violations: [], status: PASS|FAIL }
api_verification: { external_libs_cited: [...], status: PASS|FAIL }
idempotency: { declared: ..., status: PASS|FAIL }
layer_classification: { sdlc_category: ..., loop_layer: ..., status: PASS|FAIL }
trigger_discipline: { specific: yes|no, status: PASS|FAIL }
recommendations: |
  Operator-readable next steps. If REJECT, why. If CONDITIONAL, what to fix.
```

Emit `SkillAssessmentCompleted` event with the verdict. Add to `.claude/skills/` only if ACCEPT. Reject events filed as v0.x.y liens.

## Composition with other primitives

- `verifying-external-package` runs first if the skill declares external libs
- `harness-pre-pr-checklist` (existing) verifies the assessment file is in the PR adopting the skill
- ADR-033 (forthcoming W25-1) ratifies this gate as Layer-1 invariant #11

## When this skill REFUSES to assess

- The candidate is not a SKILL.md file (wrong format → reject without assessment)
- The candidate is dfg-harness-authored (skip — these are forged not adopted)
- The candidate is missing required frontmatter fields (return the missing-fields list)

## Test-of-skill (evaluation cases)

| Scenario | Expected verdict |
|---|---|
| Anthropic-published `claude-api` skill (verified) | ACCEPT |
| Random GitHub gist skill, no license | REJECT (provenance) |
| Skill that says "auto-merge PRs after 1 hour" | REJECT (contradicts dual-critic) |
| Skill that says "skip retros for trivial changes" | REJECT (contradicts retro-present invariant) |
| Skill missing `loop_layer` field | CONDITIONAL — request layer declaration |
| Skill with `when_to_use: "for general help"` | REJECT (too broad) |

## Layer composition

- L2 (Wave): this skill is wave-level (assess externals as a batch when adopting)
- L1 (Sprint): forge new skills for assessment gaps surfaced this sprint
- L0 (Release): freeze the assessed skill set at release-tag time

## References

- Operator directive 2026-05-06 — "we need to assess them before accepting"
- ADR-019 §amendment-1 through §amendment-4 — invariants the assessment guards
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices — Anthropic authoring discipline (§amendment-4 reference)
- https://github.com/anthropics/skills — official skills (auto-pass provenance for any skill from this repo)
