---
name: shipping-wave-close-gate
description: Layer-shaped skill teaching the wave-gate authorship recipe. Covers `dfg
  gate template` (scaffold checkpoint from plan.yaml), `dfg gate validate` (refuses
  pytest-style criteria), the allowed verify shapes (test -f / grep -q / gh pr view
  ... MERGED / dfg validate / dfg index --verify / dfg version verify / dfg retro
  validate), the explicitly forbidden pytest verify criteria (W61/W63 gate-timeout
  scar retirement), `dfg wave close --no-hygiene --json` emission of WaveGatePass,
  and the `chore/w<n>-gate` branch convention. Used at end-of-wave when all units
  have merged and the gate needs to close.
criticality: important
trigger: substrate-evidence
trigger_evidence: "Activate when:\n- Operator types \"close wave W<n>\", \"author\
  \ gate checkpoint\", or invokes\n  `dfg gate template` / `dfg gate validate` / `dfg\
  \ wave close`.\n- Diff stages a new `.dfg/checkpoints/W<n>-gate.md` file.\n- All\
  \ units of an in-flight wave show MERGED state and active_wave still\n  points at\
  \ that wave.\n- A `dfg run wave-close` ceremony is at the pause-for-operator step.\n"
sdlc_category: Release
loop_layer: L2-wave
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill BEFORE authoring a `.dfg/checkpoints/W<n>-gate.md` file

  or running `dfg wave close`. The skill prevents the W61/W63 scar where

  agents put `uv run pytest` or `make test` in the gate `verify:` block,

  which times out the gate ceremony (full pytest is ~18-21 min; gate

  authority requires sub-10s checks). The skill also pins the

  composition-only allowed verify shapes so wave gates stay fast.

  '
verified_at: 2026-05-17
forged_by: dfg-harness W67-2 layer-shaped-skills
---
# Shipping the wave-close gate

## Why this skill exists

The wave gate is the substrate's authority record that a wave shipped.
W61 and W63 both produced the same scar: agents tried to assert "all
tests pass" by putting `uv run pytest` directly in the gate `verify:`
block, which timed out the gate ceremony because full pytest is ~18-21
minutes wall-clock and gate checks should be sub-10s composition checks.

W65-5 retired that scar structurally by shipping `dfg gate template`
and `dfg gate validate`. `dfg gate validate` REFUSES any verify shape
matching pytest / pytest-style invocations. The template ships only
allowed shapes. This skill teaches the recipe so future agents don't
reinvent the gate by hand.

## The recipe

```bash
# 1. Scaffold the checkpoint from plan.yaml — pulls unit list automatically
uv run dfg gate template W<n>

# 2. Edit .dfg/checkpoints/W<n>-gate.md — populate verify: with allowed shapes
#    (see "Allowed verify shapes" below)

# 3. Validate the checkpoint — refuses pytest-style criteria
uv run dfg gate validate .dfg/checkpoints/W<n>-gate.md

# 4. Commit the gate on a chore/w<n>-gate branch (NOT gate/)
git checkout -b chore/w<n>-gate
git add .dfg/checkpoints/W<n>-gate.md
git commit -m "chore(W<n>): wave gate checkpoint"

# 5. Open the gate PR — separate from any release-prep PR per W52 discipline
gh pr create --title "chore(W<n>): wave gate"

# 6. After the gate PR merges, close the wave (emits WaveGatePass)
uv run dfg wave close W<n> --no-hygiene --json
```

## Allowed verify shapes

The `verify:` block in `.dfg/checkpoints/W<n>-gate.md` accepts ONLY
composition checks that complete in <10s. Allowed shapes:

| Shape | Purpose |
|---|---|
| `test -f <path>` | File-presence |
| `grep -q '<pattern>' <path>` | Line-presence in a tracked file |
| `gh pr view <N> --json state --jq '.state' \| grep -q MERGED` | PR-merged confirmation |
| `uv run dfg validate` | Substrate-shape validation |
| `uv run dfg index --verify` | Projector-vs-events parity |
| `uv run dfg version verify` | Version coherence (single source of truth) |
| `uv run dfg substrate check --no-emit` | Substrate coherence |
| `uv run dfg doc coherence --fail-on-finding` | Doc-vs-substrate coherence |
| `uv run dfg retro validate --wave W<N>` | All retros have ADR-004 frontmatter |
| `uv run dfg lane status --json` | W66 lane projection smoke |

## FORBIDDEN verify shapes (W61/W63 scar retirement)

`dfg gate validate` REJECTS the gate if `verify:` contains ANY of:

| Forbidden shape | Why |
|---|---|
| `uv run pytest` | ~18-21 min wall-clock; times out gate ceremony |
| `pytest` (bare) | Same — gate ceremony budget is sub-10s per check |
| `make test` | Wraps pytest |
| `make ci` | Wraps pytest + lint + ci-validate; same timeout class |
| `tox` | Same family — long-running test harness |
| `python -m pytest` | Same |
| `uv run pytest tests/...` | Even targeted test invocations exceed budget |

Tests belong in PR CI (the PRs that landed each unit ran the full
pytest suite). The wave gate is a COMPOSITION receipt — it asserts
"the units are MERGED, the substrate is COHERENT, the artifacts EXIST".
It does not re-run the suite. The receipt that pytest passed lives in
the per-unit PR's CI run history.

If you find yourself reaching for pytest in the gate, you have either
(a) caught a real bug — file an issue and a follow-up unit, OR
(b) misframed the gate as test-running rather than receipt-of-tests-ran.

## Branch + PR convention

The gate PR branch is `chore/w<n>-gate` (NOT `gate/`, NOT `feat/w<n>-gate`).
The gate PR title is `chore(W<n>): wave gate`. The gate PR is ALWAYS
separate from any release-prep PR (W52 discipline; two-PR P11 pattern).

## Wave-close emission

`dfg wave close W<n> --no-hygiene --json` emits the `WaveGatePass` event
and reprojects state. The `--no-hygiene` flag skips housekeeping (the
event emission is the load-bearing step). The `--json` flag returns
verdict + events_emitted on stdout for programmatic verification.

Idempotency: re-running `dfg wave close` on a wave that already has
WaveGatePass returns `idempotent: true, verdict: PASS, events_emitted:
[]` — safe to invoke from a ceremony resume.

## Composing with the wave-close ceremony

`dfg run wave-close --input CURRENT_WAVE=W<n>` is the operator-handoff
wrapper. It runs `dfg validate` + pre-close substrate check (expected
FAIL — the checkpoint exists but WaveGatePass hasn't emitted yet),
pauses for operator to run `dfg wave close W<n>`, then resumes with
post-close index + substrate check.

The skill `running-ceremony-workflows` covers the `dfg run` mechanics;
this skill covers the gate-file authorship that the ceremony orchestrates.

## Authority

- `dfg gate --help` is canonical CLI shape.
- W65-5 keystone — `dfg gate template` + `dfg gate validate` primitives.
- W61/W63 receipts — gate-timeout scar that forced the forbidden-pytest
  rule.
- `.dfg/checkpoints/W66-gate.md` is a reference example (composition-only
  verify block; 22 criteria; all sub-10s).
