---
name: diagnosing-ui-render
description: RCA skill for "the UI looks wrong / is empty / has stale data" bugs.
  Forces 5-step bisect (data → markup → layout → style → state) before speculating.
  Authored after operator-surfaced Flow-tab empty bug 2026-05-07 where speculation
  cycled through 3 hotfixes without identifying that 36-wave layout collapsed unit
  boxes to negative X coordinates.
criticality: important
trigger: substrate-evidence
trigger_evidence: "Activate when:\n- Operator reports \"the UI is empty / wrong /\
  \ stale\" against a\n  rendered surface (cockpit, trace-viewer, dashboard).\n- 2+\
  \ hotfix attempts on the same view in a single session WITHOUT\n  a confirmed root\
  \ cause.\n- rca-general fired on a UI symptom but the analyst started\n  proposing\
  \ patches before completing bisect."
---
# Diagnosing UI render bugs

## Why this skill exists

Receipt 2026-05-07: operator surfaced "DFG Flow tab empty" three times
across hotfixes v0.4.10, v0.4.11, v0.4.13. Each cycle the analyst
(Claude) proposed a different fix without first proving where the
render pipeline actually broke. Root cause was eventually found in
flowLayout(): 36 waves crammed into 1200px viewBox → 2.5px columns →
220px unit boxes pushed to **x = -78.8px**, off-screen.

The pattern: the analyst speculated based on what FELT plausible
(missing fields, demo schema, null property), but each speculation
cost a full hotfix cycle. A disciplined bisect would have caught it
in step 3.

## The 5-step bisect

### 1. Data — does the projection emit what the renderer expects?

```bash
curl -s http://localhost:<port>/trace.json | python3 -c "import sys,json; d=json.load(sys.stdin); print({k: type(v).__name__ for k,v in d.items()})"
```

Confirm shape, count, and that fields the renderer dereferences are
present + non-null.

### 2. Markup — does the renderer produce DOM nodes?

Open browser DevTools → Elements panel → search for an expected
element (`<g class="unit-node">`, `<rect class="bg">`). If absent,
the renderer crashed silently. Console reveals which try/catch
swallowed it.

If markup is present but invisible: continue to layout.

### 3. Layout — are coordinates inside the visible viewport?

For SVG: read `viewBox`, then inspect actual element coordinates.
**This is the step the v0.5.x cycle skipped.** Compute, with the
LIVE data shape:

```python
# columns/rows that would render given the data scale
W, marginX, colGap, unitW = 1200, 30, 30, 220
cols = LIVE_WAVE_COUNT  # not the demo's 3
colW = (W - 2*marginX - (cols-1)*colGap) / cols
unit_x = marginX + 0*(colW + colGap) + (colW - unitW)/2
print(f"unit_x = {unit_x}  (negative → off-screen)")
```

If unit_x < 0 OR colW < unitW: the layout was designed for fewer
items than the live data scale. Fix: dynamic viewBox + scroll.

### 4. Style — is the element invisible due to CSS?

`getComputedStyle(el).display`, `.visibility`, `.opacity`,
`.fill`. Common: `opacity:0` from a "future" state class that was
meant to fade in via animation but never triggered.

### 5. State — is the renderer running but with stale state?

`window.state.trace.<field>` in the console. Confirm the renderer's
inputs match what `/trace.json` returned.

## Discipline checks

Before proposing a fix:

1. State which step in the bisect identified the root cause.
2. State the EXACT computation/measurement that proved it (not a
   plausible hypothesis).
3. State what the fix changes about that computation/measurement.

A fix proposal without (1)+(2)+(3) is speculation, not RCA. Reject it.

## Common UI-rendering bug patterns

| Pattern | Step caught | Receipt |
|---|---|---|
| **Layout collapse at scale** | 3 (layout) | 2026-05-07 Flow tab; 36 waves vs demo's 3 |
| **Renderer reads stale demo data** | 1 (data) | 2026-05-07 v0.4.9 fetch path |
| **Field schema mismatch** | 2 (markup, silent crash) | 2026-05-07 v0.4.10 unit.dual_critic |
| **CSS opacity:0 from animation state** | 4 (style) | (no receipt yet) |

## §Amendment-trigger guard

If 3+ UI bugs are diagnosed via this skill in one quarter, the
§amendment trigger fires: ratchet the trace-viewer Flow/Repo/KG
renderers to call a single `safe_render(view_key)` that auto-runs
the 5-step bisect on failure and emits a structured `RenderFailed`
event to events.jsonl.

## Cross-references

- rca-general (universal 5-step RCA workflow this specializes)
- rca-harness-architecture (when the bug is in the projector, not the renderer)
- ADR-019 §amendment-5 substrate-evidence-over-natural-language
- W36 Flow projector enrichment (the substantive root-cause fix)
