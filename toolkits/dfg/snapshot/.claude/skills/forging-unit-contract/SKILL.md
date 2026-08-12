---
name: forging-unit-contract
description: Generative skill for authoring a W*-N unit contract from a raw scope
  idea. Walks the contract YAML frontmatter shape, guards the §amendment-trigger discipline,
  and produces a contract ready for `dfg validate`. Used at the start of every unit,
  before any code.
criticality: important
trigger: substrate-evidence
trigger_evidence: "Activate when the operator (or central session) is about to author\
  \ a\nnew contract under .dfg/agents/W*-*.md. Concrete substrate signals:\n- Diff\
  \ stages a NEW .dfg/agents/W*-*.md file.\n- Re-plan ceremony just ratified a wave\
  \ addition (RePlanAccepted with\n  scope.action=add); contracts MUST follow.\n-\
  \ Operator types \"author W*-* contract\" or \"forge contract for ...\"."
---
# Forging unit contracts

## Why this skill exists

Unit contracts are load-bearing substrate. Operator-known pain (W22-8
ratification, W26-1 governance YAML, W29-1 sprint-manifest backfill)
shows that contract drift compounds: missing branch_name → race
condition; missing closes_issues → stale lien; vague acceptance → cycle-
3 boundary. The substrate-evidence-over-natural-language amendment
(ADR-019 §amendment-5) demands this be a skill, not a checklist.

## Inputs

The skill expects, in any order:

- **Wave id** (e.g., W35).
- **Slug** — kebab-case noun phrase, ≤ 40 chars (e.g., `kpi-projectors`).
- **Purpose** — one sentence, ≤ 200 chars after `>` folding.
- **File touchpoints** — the ≤ 8 files this unit will read or write.
- **Acceptance criterion** — one or two sentences, executable in spirit
  (i.e., a reviewer can run a command to check).

## Output (canonical contract YAML)

```yaml
---
id: W<wave>-<n>
role: substrate-author     # or: substrate-doc | code-author | tooling
name: <human title under 60 chars, QUOTE if it contains '#' or ':'>
purpose: >
  <one sentence; folded.>
wave: W<wave>
squad_id: substrate
unit: W<wave>-<n>
depends_on: []             # other unit ids when there is a hard order
blocks: []
governance_tier: VT1       # VT0 (kernel) | VT1 (default) | VT2 (advisory)
sized: S                   # S = ≤ ½ day, M = ≤ 1 day, L = ≥ 1 day
hardening_max_cycles: 2
prompt_version: 1
read_contract:
  must_read:
    - <file paths the unit must consult before writing>
output_contract:
  branch_name: feat/w<wave>-<n>-<slug>     # MANDATORY post-W26 dispatch
  files:
    - <each file the unit produces or modifies>
  pr_title_prefix: "feat(W<wave>):"
  retro_path: .dfg/retrospectives/W<wave>/W<wave>-<n>.md
  closes_issues: []
  acceptance: >
    <executable in spirit; reviewer can verify.>
forged_by: dfg-harness W<wave>-cycle <YYYY-MM-DD> contract-first
---

# W<wave>-<n>

<2-4 paragraphs of body context: why this unit exists, what it
unblocks, any assumptions the contract leaves implicit.>
```

## Discipline checks

Before declaring the contract done, the skill verifies:

1. **YAML safety** — `name` field quoted if it contains `#`, `:`, or
   leading `-`. Receipt: W32-2..W32-5 contracts where `name: Lien #515
   — ...` parsed as just `Lien` (operator-surfaced 2026-05-07).
2. **branch_name regex** — matches `^(feat|fix|chore|docs|refactor)/(w[0-9]+-[0-9]+-[a-z0-9-]+|...)$`
   per the kit/SCHEMAS/agent-spec.schema.json pattern (W26-1 keystone).
3. **closes_issues realism** — only include issue numbers the unit will
   verifiably close in its PR. Forward liens (issues filed during
   cycle-N) do NOT belong here.
4. **acceptance is checkable** — a reviewer can copy-paste a command
   from the acceptance prose and run it. "Add support for X" is not
   acceptance; "tests/test_x.py covers add/remove/malformed" is.
5. **`dfg validate` passes** with the contract in place. Run it before
   the contract is committed.

## §Amendment-trigger guard

If the operator describes pain that ≥ 2 prior contracts have hit (e.g.,
"this is the third contract that forgot branch_name"), this skill MUST
surface the §amendment-trigger pattern and propose a substrate-level
ratchet (Layer-1 invariant + L1 gate script) instead of authoring the
fourth contract that rediscovers the lesson.

## Anti-patterns this skill rejects

- Free-form natural-language `trigger:` field (use substrate-evidence).
- `acceptance: >\n  TBD` — never accept TBD; ask the operator.
- 9+ files in `output_contract.files` — split into two units.
- `governance_tier: VT0` without ADR justification (kernel changes
  require ADR ratification).
