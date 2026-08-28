# prog16 result analysis

Deep analysis of the `prog16-*` run: 16 programming tasks × 3 conditions × 1 attempt
with Claude Code (`claude-sonnet-5`), executed 2026-08-27. `results/prog16_report.md`
is the aggregated record; this directory re-reads the raw trial artefacts under
`jobs/prog16-*/` and derives what the aggregate cannot carry.

## Layout

```text
results/analysis/
├── prog16_analysis.ipynb      # the analysis, executed, with all figures inline
├── prog16_discussion.md       # section-by-section discussion of the results, figures embedded
├── src/prog16_extract.py      # jobs/prog16-*/ → tidy CSV tables (read-only on jobs/)
├── data/                      # generated tables (see below)
└── figures/                   # 300 dpi PNG + SVG, sized for a 16:9 slide
```

### Generated tables

| File | Grain | Notable columns |
|---|---|---|
| `prog16_trials.csv` | one row per trial (48) | reward, partial credit, phase durations, budget utilisation, token and cost totals, tool-call counts, strict skill invocation, task metadata |
| `prog16_tests.csv` | one row per verifier test (183) | task, condition, test name, status, duration |
| `prog16_steps.csv` | one row per agent step (1,680) | elapsed offset, prompt/completion/cached/thinking tokens, sidechain flag |
| `prog16_tool_calls.csv` | one row per tool call (1,745) | tool, Bash sub-class, elapsed offset |
| `prog16_condition_summary.csv`, `prog16_paired_tests.csv`, `prog16_outcome_matrix.csv`, `prog16_adherence_funnel.csv`, `prog16_tool_mix.csv` | condition / pair / task | the notebook's own summary tables, for slides |

## Running it

The analysis dependencies live in the `analysis` dependency group, separate from the
benchmark's own runtime requirements:

```bash
uv sync --group analysis
uv run --group analysis jupyter lab results/analysis/prog16_analysis.ipynb
```

Or headlessly, which regenerates every figure and CSV:

```bash
uv run --group analysis jupyter execute --inplace results/analysis/prog16_analysis.ipynb
```

The extraction step runs on its own when `data/prog16_trials.csv` is missing or older
than `src/prog16_extract.py`; it can also be run directly:

```bash
python3 results/analysis/src/prog16_extract.py
```

## What the run showed

1. **No outcome difference.** 13 / 12 / 13 of 16 tasks passed for baseline / SDD /
   CodeZen. Every paired McNemar test returns p = 1.0, and partial credit and
   test-level pass rate agree.
2. **The design could not have found one.** 10 tasks passed in all three conditions and
   1 failed in all three, so only 5 tasks discriminate. Simulated power at this design
   is under 20 % even for a lopsided effect.
3. **The cost is real and consistent.** SDD costs 1.25× baseline, CodeZen 1.54×, for
   1.22× and 1.56× the steps. CodeZen's step count is the only paired comparison
   significant at p < 0.05.
4. **Methodology eats budget headroom.** Mean share of the task's declared agent budget:
   44 % baseline, 42 % SDD, 56 % CodeZen — with 5 CodeZen and 1 SDD trials censored by a
   Harbor timeout against 0 for baseline.
5. **Availability is not adherence.** Every toolkit skill registered in every toolkit
   trial; a toolkit skill was actually invoked in 8 of 32 trials, mostly as a post-hoc
   review pass rather than as a method for doing the work.

## Two bugs found in `scripts/report.py` — since fixed

Both were in `parse_adherence`. They were first corrected here in
`src/prog16_extract.py`, and on 2026-08-28 the fix landed in `scripts/report.py`
itself; `results/prog16_report.md` and `results/probe3_report.md` were
regenerated from the same job output, and only the adherence columns moved:

- **`skill_tool_calls` was always 0.** It counted the substring `"name": "Skill"`, but the
  ATIF trajectory names the field `function_name`. The run actually contains 15 `Skill`
  tool calls, all 15 naming a skill the variant installed.
- **`skills_invoked` was too permissive.** It substring-matched skill names anywhere in
  agent-authored trajectory text, so an agent that lists its skills directory scored as
  having used every skill. The strict measure is a `Skill` tool call whose skill name is
  one the variant installed; it is now reported alongside the loose match rather than
  instead of it.

Corrected headline adherence, out of 16 trials each: `sdd` 2 named / 1 invoked,
`codezen-viable` 8 named / 7 invoked.

[`prog16_discussion.md`](prog16_discussion.md) discusses each notebook section in prose with
the figures embedded, and closes with the open questions about the experiment's intent that
change how these numbers should be read.

Section 9 of the notebook holds the full metric catalogue: what `report.py` already
reports, what is derived here from data already on disk, and what is worth instrumenting
before the next run.
