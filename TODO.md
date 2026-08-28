# Harbor Methodology Bench — where we left off

**Last updated:** 2026-08-26
**Branch:** `feat/container-payload-layer-and-task-catalogue`
**State:** Experiment A (the probe) has been run and reported. The decision gate in
front of experiment B1 is now answerable. Nothing is committed yet.

---

## 1. What happened today (2026-08-26)

### The probe ran, and it succeeded

```bash
./scripts/run-pilot-experiment.sh --config config/experiments.codezen-probe.yaml \
  --tasks-file config/tasks-programming-probe.txt \
  --job-prefix probe3 --attempts 1
```

All 12 trials completed — 3 tasks × 4 conditions, one attempt, Claude Code only.
Job output is in `jobs/probe3-*`. The report was generated afterwards:

```bash
python3 scripts/report.py --pattern "probe3-*" \
  --md-out results/probe3_report.md --json-out results/probe3_summary.json
```

Both result files are new and uncommitted. `results/probe3_report.md` is the
authoritative record; the summary below is a reading of it, not a substitute.

| Condition | Trials | Success | Mean reward | Avg duration | Cost | Skills available | Skills named | Config named |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline` | 3 | 2 | 0.67 | 1822 s | $5.13 | 0/3 | 0/3 | 0/3 |
| `sdd` | 3 | 3 | 1.00 | 1628 s | $4.79 | 3/3 | 1/3 | 3/3 |
| `codezen-full` | 3 | 2 | 0.67 | 1795 s | $7.35 | 3/3 | 2/3 | 2/3 |
| `codezen-viable` | 3 | 3 | 1.00 | 1780 s | $7.68 | 3/3 | 2/3 | 3/3 |

Total: **$24.94 for 12 trials** (~$2.08 per trial), ~5.9 h of serial wall-clock.

Per task, the whole difference sits on one task:

- `circuit-fibsqrt` — all four conditions passed.
- `fix-ocaml-gc` — all four conditions passed.
- `schemelike-metacircular-eval` — `sdd` and `codezen-viable` passed;
  `baseline` and `codezen-full` both hit `AgentTimeoutError` at the task's
  2400 s agent budget.

### How to read that, honestly

Three things the probe settled, and one it did not:

1. **The pipeline holds end to end.** Payload delivery, preflight, the runner,
   the verifier and the reporter all worked across all four conditions with no
   collisions and no infrastructure failures. This was the primary thing the
   probe was for.
2. **The predicted null did not happen.** The runbook's stated most-likely
   outcome was zero adherence — nothing in a bare Harbor prompt asking the agent
   to use a method. Instead the toolkit conditions referenced `CLAUDE.md` /
   `AGENTS.md` in 8 of 9 trials, and named toolkit skills in 5 of 9. So the
   decision gate resolves to *run B1*.
3. **There is a direction, but it is not a result.** Both toolkit-with-usable-skills
   conditions went 3/3 while baseline went 2/3, and the one differentiating task
   was the longest-horizon one in the probe set. With 3 tasks and 1 attempt this
   is a hypothesis, not a finding — one flaky trial moves a rate by 33 points.

**What it did not settle — and this is the important caveat for B1:**
`skill_tool_calls` is **0 in every single trial**. `report.py` derives
"skills named" by substring-matching skill names in agent-authored trajectory
text, which is not the same as the agent invoking the `Skill` tool. In
`codezen-full` the "named" set is 7–8 skills at once, which reads much more like
the agent enumerating its own skills directory than like it choosing a method.
So the honest current statement is: **the instruction files are being read, and
no toolkit skill was actually invoked in 12 trials.** Whether the methodology is
*working* through `CLAUDE.md` alone, or the adherence metric is simply too weak
to tell, is unresolved.

### Documentation reconciliation (same day, before the run)

`docs/experiment-codezen-vs-sdd.html` had fallen out of step with the
configuration files during the 2026-08-25 session and was retired rather than
rewritten:

- It now carries a superseded banner naming
  `docs/experiment-programming-tasks.html` as the experiment of record, with a
  table contrasting the retired design (33 suite-selected tasks, 8 cells,
  3 attempts, 792 trials) against the current one (16-task explicit set, 3 cells
  per agent half, 2 attempts, 12 probe + 96 per half). Its §1, §6 and §7 are
  marked as the retired design; §2 (how the CodeZen plugin was reprojected as a
  repository), §3 (why CodeZen appears twice), §5 and §8 still stand and are not
  duplicated anywhere else.
- `config/tasks-programming-probe.txt` and `config/tasks-programming.txt` now
  each carry the full command sequence for their own experiment as a trailing
  comment block, so a task file states which config and which flags it belongs
  with. `read_task_ids` strips `#` comments, so the blocks are inert — but note
  that an editing pass stripped the leading `#` from the continuation lines at
  one point, which made the parser read nine flag fragments as task ids. If a run
  ever fails on an unknown task name that looks like a CLI flag, that is the
  cause. Both files were repaired and verified to resolve to 3 and 16 ids.
- `README.md` doc table and tree comments updated to match; the stale "12-task
  programming run" wording is gone.
- One stale claim fixed in `docs/experiment-programming-tasks.html`: the design
  is 2 attempts, so B1's reportability rests on paired comparison across the
  16 tasks, not on a per-cell standard error over attempts.

`uv run pytest` → 38 passed.

---

## 2. Next steps, in order

### Step 1 — Commit the current working tree

Uncommitted right now: `README.md`, `config/tasks-programming.txt`,
`config/tasks-programming-probe.txt`, `docs/experiment-codezen-vs-sdd.html`,
`docs/experiment-programming-tasks.html`, plus untracked
`results/probe3_report.md` and `results/probe3_summary.json`.

Two commits are cleaner than one: the documentation reconciliation, then the
probe result.

### Step 2 — Decide the adherence question before spending $200

This is the one genuine decision waiting, and it is worth resolving first
because B1's headline metric depends on it. `used_toolkit_skill` currently
returns true on a name mention. Either:

- **Accept it and report it as such** — rename the reported column so it reads
  "referenced the methodology" rather than "used a skill", and treat
  `skill_tool_calls` as the strict measure. Cheap; no re-run.
- **Or tighten the extraction** in `scripts/report.py::adherence` — require a
  `Skill` tool call, or a skill name inside a tool-use step rather than anywhere
  in the trajectory text. The probe trajectories in `jobs/probe3-*/agent/` are
  already on disk, so a tightened extractor can be validated against them for
  free, with no new trials.

The second option is the better spend: 12 trajectories are enough to see whether
the metric distinguishes anything, and B1 is 96 trials with the same
instrumentation.

### Step 3 — Run B1, the Claude measurement

Nothing blocks it. The commands are in `config/tasks-programming.txt` and in
`docs/experiment-programming-tasks.html` §6. Preflight the full 16 before
walking away — it builds all 64 images and spends no tokens:

```bash
./scripts/preflight-variants.sh --config config/experiments.codezen-claude.yaml \
  --tasks-file config/tasks-programming.txt

./scripts/run-pilot-experiment.sh --config config/experiments.codezen-claude.yaml \
  --tasks-file config/tasks-programming.txt \
  --job-prefix prog16 --attempts 2 --dry-run     # expect 48 invocations

./scripts/run-pilot-experiment.sh --config config/experiments.codezen-claude.yaml \
  --tasks-file config/tasks-programming.txt \
  --job-prefix prog16 --attempts 2

python3 scripts/report.py --pattern "prog16-*" \
  --md-out results/prog16_report.md --json-out results/prog16_summary.json
```

`--attempts 2` is not optional — `repetitions:` in the config is documentary and
the runner's default is 1, so omitting the flag silently yields 48 trials instead
of 96.

**Revised budget, from the probe's actuals rather than the estimate:** at
$2.08 per trial and ~1756 s per trial, B1 is roughly **$200 and ~47 h of serial
wall-clock**. That is inside the runbook's $96–288 band but near its top. Plan
for it running overnight across two nights, or parallelize if the quota allows.

### Step 4 — Watch `schemelike-metacircular-eval` in B1

It is the only probe task that produced a failure, and both failures were
timeouts at the 2400 s budget rather than wrong answers. It is not a floor
effect — two conditions passed it — so it stays in the set. But if B1 shows the
same task timing out across most conditions, the honest reading is that the task
is budget-bound rather than methodology-sensitive, and it should be reported
separately rather than folded into the success rate.

### Step 5 — B2 (Codex) only if the quota is real

Still optional and still gated on the same failure as before: every Codex trial
in an earlier matrix run failed with `ApiUsageLimitError` before reaching the
task. Canary first, on the cheapest task in the set:

```bash
codex --version
./scripts/run-pilot-experiment.sh --config config/experiments.codezen-codex.yaml \
  --task kv-store-grpc --job-prefix quotacheck --attempts 1
```

If that returns `ApiUsageLimitError`, stop — B1 alone is a complete, publishable
Claude-only result, which is exactly why the matrix was split.

---

## 3. Open items carried forward

These were open before today and remain open.

### Payload breadth — a confound not yet settled

A toolkit is deployed in full, so a snapshot's non-methodology files land in the
agent's working directory alongside the benchmark task: `docs/`, `tools/`,
`kits/`, `tests/` for SDD; `standards/`, `plugin/` for CodeZen. Preflight
confirms no collisions, but the extra content still changes what the agent sees
when it explores the repository, which is a confound distinct from the
methodology instructions.

1. **Deploy in full** (current behaviour) — the condition under test is "the
   agent works in a repository configured with this toolkit", which is what the
   toolkit looks like in real use.
2. **Deploy the methodology surface only** — restrict the payload to `CLAUDE.md`,
   `AGENTS.md`, `.claude/`, `.agents/` and the toolkit's kit directories.

Option 2 needs a per-toolkit `include:` list in the experiment config; the
staging code already supports name-based filtering via `exclude:`. Settling this
*after* B1 means B1 measures position 1 — which is defensible, but should be
stated in the write-up rather than left implicit.

### `codezen-viable` is a curated subset, and that is a stated confound

The measurement compares SDD-as-shipped against a four-skill CodeZen subset
(`noc-tdd`, `noc-fix`, `code-review`, `security-review`). The seven dropped
skills cannot run in a benchmark container — they need a Docker daemon, a human,
a system under test, or the Notion MCP server. `codezen-full` remains declared
and the probe runs it, so the full-vs-viable comparison survives as a three-task
signal; today it went 2/3 against `codezen-viable`'s 3/3, with the
`codezen-full` failure being a timeout.

### DFG snapshot has a dead entry point

`toolkits/dfg/snapshot/CLAUDE.md` routes agents to `MASTER_CONTEXT_INDEX.md`,
`DFG.md` and `PROVENANCE_INDEX.md`, none of which exist in the snapshot — they
appear to be git-ignored in the source repository. DFG is not part of the CodeZen
experiment, so this does not block anything now, but the toolkit's own entry
point is a dead link inside the container and any DFG result would be invalid
until it is fixed.

### Earlier pilot numbers are void

`results/pilot_report.md` predates the container payload layer. Harbor copies
only `instruction.md`, `tests/` and `solution/` into the environment, so files at
the generated task root were inert and all three conditions were effectively the
baseline. Those numbers must be discarded, not compared. `results/ds-ml_report.md`
(SDD vs baseline on data-science / machine-learning) ran after the payload layer
and is valid.

---

## 4. Orientation for a fresh session

| Read this | For |
|---|---|
| `docs/experiment-programming-tasks.html` | The experiment of record: probe, decision gate, B1, B2, budget |
| `config/tasks-programming-probe.txt` | The 3 probe tasks *and* the exact probe command sequence |
| `config/tasks-programming.txt` | The 16 measurement tasks *and* the B1/B2 command sequences |
| `results/probe3_report.md` | What the probe actually produced |
| `docs/experiment-codezen-vs-sdd.html` §2–§3 | How CodeZen was reprojected as a repository, and why it appears twice |
| `docs/evaluation-pipeline.md` | How a trial becomes reward / duration / cost, and the hazards in each metric |
| `tests/test_configs.py` | The invariants holding the four CodeZen configs comparable |

Configs, at a glance:

- `experiments.codezen-probe.yaml` — 4 cells, 1 attempt, Claude only (experiment A, **run**)
- `experiments.codezen-claude.yaml` — 3 cells, 2 attempts (experiment B1, **next**)
- `experiments.codezen-codex.yaml` — the same 3 cells for Codex (experiment B2, optional)
- `experiments.codezen.yaml` — all 8 cells in one matrix; still valid, no longer the plan
