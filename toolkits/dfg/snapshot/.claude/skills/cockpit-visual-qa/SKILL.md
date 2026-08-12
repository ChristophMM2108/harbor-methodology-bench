---
name: cockpit-visual-qa
description: >
  Reusable Playwright (headless Chromium) visual-QA walk for the dfg-harness
  cockpit. Drives a real browser through every interactive surface — the 7 zones
  (Z1–Z7), the Plain⇄Precise vocabulary toggle, the entity browser
  (release/milestone/sprint/wave/work-unit/component tabs + drill-in), the Z4 DFG
  work-graph + wave selector, and the Calm Spine Timeline — clicks each meaningful
  element, and records the OBSERVED EFFECT of every click so a human (or a fix
  agent) can judge SITUATION + PRESCRIPTION. Produces evidence (per-surface
  screenshots, captured console-errors + failed-network log, machine-readable
  findings JSON). Read-only by construction — every action is a GET / client-side
  click; it never mutates the cockpit. Wraps `scripts/cockpit_visual_qa.py`.
criticality: important
forged_by: dfg-harness W123 (skills library)
trigger: substrate-evidence
trigger_evidence: >
  Activate when:
  - A cockpit change (src/dfg_harness/cockpit/**) is on the diff and the unit
    needs to confirm the rendered surfaces still render (no blank zone, no raw
    JSON dump, no dead click) before the PR ships.
  - The operator asks to "QA the cockpit", "screenshot the zones", or surface a
    legibility / UX regression with evidence.
  - A unit contract declares `required_skills: [cockpit-visual-qa]` (the per-unit
    selection mechanism) — the dispatched session MUST run this walk and capture
    a `docs/reports/cockpit-qa-<date>.md` report.
sdlc_category: Verification
loop_layer: L0-unit
license: dfg-harness internal (Korza)
idempotent: true
when_to_use: >
  Use this skill whenever a unit touches the cockpit's served surfaces and you
  need browser-level evidence that the change renders. It complements (does not
  replace) the conformance test battery (tests/test_cockpit_*.py) — the
  conformance tests pin the mechanically-checkable contract (read-only routes,
  evidence chips, no-hardcoded-color), while this walk produces the human-judged
  EFFECT evidence (a screenshot per surface + a findings JSON) the conformance
  tests cannot. It needs a LIVE server + a browser, so it is NOT a pytest test.
---
# Cockpit visual-QA walk

## What this skill is

A parameterized browser-automation QA harness for the dfg-harness cockpit
(`dfg cockpit serve`), implemented in `scripts/cockpit_visual_qa.py`. It is the
first registered entry in the dfg-harness **skills library** — a reusable
capability a unit can select via its contract's `required_skills`.

It applies an **effect / situation / prescription** QA mindset:

- **EFFECT** — what actually happened when an element was triggered (opened an
  inline drawer? navigated to raw JSON? dead-end? console error? blank panel? a
  literal `{...}` dump?).
- **SITUATION** — is that acceptable, or a legibility / UX failure? (judged by
  the human reading the report; the script captures the raw evidence the
  judgement rests on).
- **PRESCRIPTION** — the concrete fix (a human / report concern).

The script's job is to produce *evidence*, not to pass/fail. It never mutates the
cockpit (every action is a GET / a client-side click — DD-1).

## How to invoke

Start the cockpit, then run the walk against it:

```bash
# 1. serve the cockpit (from the repo / worktree under QA)
uv run dfg cockpit serve --port 4566 &

# 2. run the walk (headless Chromium)
uv run python scripts/cockpit_visual_qa.py --base-url http://127.0.0.1:4566

# optional flags
#   --out DIR     screenshot + findings output dir
#                 (default: docs/reports/cockpit-qa-<today>/)
#   --headed      run with a visible browser (debugging)
```

Outputs (under `--out`):

| File | Content |
|---|---|
| `*.png` | one screenshot per walked surface |
| `findings.json` | structured `{surface, action, effect, evidence, …}` rows |
| `console.log` | captured console messages + page errors |
| `network-failures.log` | non-2xx / failed requests observed during the walk |

Capture the human-readable summary in `docs/reports/cockpit-qa-<date>.md`
(SITUATION + PRESCRIPTION per finding) — that markdown report is the durable
artifact a wave gate / PR review reads.

## The CLI surfaces it exercises

The walk drives these served surfaces and `/api/*` endpoints (read-only):

- The shell + status spine (evidence chips → inline drawer; definition tokens →
  gloss popover).
- The **Plain ⇄ Precise** vocabulary toggle (`#mode-plain` / `#mode-precise`).
- All **7 zones** (`Z1`…`Z7`) via the left nav — detecting empty / error /
  raw-JSON-dump failure modes per zone body.
- The **entity browser** (release / milestone / sprint / wave / work-unit /
  component tabs + drill-in to the inline About card).
- The **Z4 DFG work-graph** (SVG node–edge graph + wave selector + node click).
- The **Calm Spine Timeline** (Roadmap / Milestones / Components zooms).
- Direct probes of every `/api/*` endpoint (`/api/status`, `/api/zones`,
  `/api/glossary`, `/api/timeline`, `/api/composition`, `/api/skills`,
  `/api/intent-assets`, the entity routes, plus deliberate error-state probes for
  a nonexistent zone / missing entity / 404).

## Fallback

If Playwright / Chromium is unavailable in the environment, the script exits
non-zero with a clear message; the QA report then documents the static-analysis
fallback (fetch served assets + every `/api/*` endpoint via curl/urllib and read
the click handlers). The walk is therefore safe to select as a `required_skill`
even on a host without a browser — the dispatched session falls back to the
static census and records that honestly in the report.

## §Amendment-trigger guard

If the same cockpit surface regresses (blank zone / raw-JSON dump / dead click)
across 2+ QA walks in one quarter, the §amendment trigger fires: ratchet the
regressed surface into the mechanically-checkable conformance battery
(`tests/test_cockpit_principles_conformance.py`) so the next regression fails CI
*before* it reaches a human QA walk — never write another QA-report scar.

## Cross-references

- `scripts/cockpit_visual_qa.py` — the script this skill wraps.
- `dfg skill list` — the read-only skills-library surface that enumerates this
  skill (name + purpose + deprecated-status).
- `docs/cockpit-design/PRINCIPLES-LEDGER.md` — the cockpit conformance rubric the
  QA report measures against.
- diagnosing-ui-render — the RCA skill to compose with when the walk surfaces a
  blank / wrong / stale render (it forces the 5-step data→markup→layout→style→state
  bisect before speculating on a fix).
