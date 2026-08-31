[← README](../README.md) · [experiments](experiments.md) · [tasks](tasks.md) · [analysis](analysis.md) · [troubleshooting](troubleshooting.md)

# CodeZen vs SDD, across the screened suite

This branch repeats the **prog16** experiment — CodeZen and SDD against a bare
baseline, Claude Code on `claude-sonnet-5` — over every terminal-bench task that
can discriminate between the conditions, rather than over 16 hand-picked
programming tasks. It applies the design changes prog16's own discussion asked
for in [§10, *What to change before the next run*](https://github.com/ChristophMM2108/harbor-methodology-bench/blob/experiment/codezen-vs-sdd-prog16/results/analysis/prog16_discussion.md).

Both toolkits are pinned at the commits prog16 used — `sdd dc4b09e7`,
`codezen cc50eba8` — so the two runs measure the same artefacts and their
results can be read together.

---

## 1. What prog16 found, and what limited it

| prog16 | Consequence for this run |
|---|---|
| 13 of 16 tasks were passed by the bare baseline; 10 were passed by every condition | Those tasks carried no information and consumed 60 % of the spend. The task set here is **screened**, not chosen. |
| 1 attempt per cell, so no within-cell replicate | Nothing could be said about variance. This run uses **2 attempts**. |
| A binary reward per trial | The verifier's own per-test results were already on disk. This run reports **partial credit and test-level pass rate** as headline metrics. |
| Two of five informative outcomes were agent timeouts, counted as failures | Timeouts are now reported as **censored**, and excluded from the success denominator. |
| Adherence was low: SDD invoked a skill in 6 of 16 trials, CodeZen in 9 | This run measures **whether the method was followed** — what happened before the first code edit — not only whether a skill was named. |

The one finding prog16 could support was about cost: at indistinguishable
outcomes, `sdd` cost 25 % more per trial than baseline and `codezen-viable` 54 %
more. That comparison is exactly what a larger, discriminating task set
sharpens.

---

## 2. The design

- **Conditions** — `baseline` (the task and nothing else), `sdd` (as shipped, 7
  skills), `codezen-viable` (the 4-skill subset that can run inside a benchmark
  container). Declared in
  [`config/experiments.codezen-vs-sdd.yaml`](../config/experiments.codezen-vs-sdd.yaml);
  the exclusion list and its reasoning are in that file.
- **Agent** — Claude Code only. Every Codex trial in an earlier run failed with
  `ApiUsageLimitError` before reaching the task, so the agent axis needs a
  working quota before it is worth planning around.
- **Attempts** — 2 per cell.
- **Candidates** — the whole suite at pin `2fd12b88` minus the 6 tasks whose own
  expert estimate is ≥ 32× their agent budget, listed with their numbers in
  [`config/tasks-suite-candidates.txt`](../config/tasks-suite-candidates.txt).
  83 tasks, 39.8 h of declared agent budget for one pass.
- **Measured set** — whatever survives the screen, written to
  `config/tasks-suite.txt` by `hmb screen`.

## 3. The screen, and why it comes first

A task earns a place in the comparison only if it can separate the conditions.
Three checks, in cost order:

| Check | Agent | Cost | Rejects |
|---|---|---|---|
| The task and its verifier work | `oracle` | none | a task whose reference solution does not score 1.0 |
| The task is not self-passing | `nop` | none | a task that scores above 0 with no work done |
| The task can still discriminate | the matrix agent, 1 trial | one baseline trial | a task the bare agent already passes |

The third is the one prog16 lacked. It costs the cheapest cell of the matrix,
run once, and replaces a ceiling effect discovered after the money was spent
with an inclusion criterion applied before it.

`hmb screen` writes the surviving set and keeps every rejected task in the file
as a commented line with its reason, so the selection stays a derivation rather
than an opinion.

The screen's own jobs must not share a prefix with the measurement. Its baseline
stage is a real baseline trial, so a job named `suite-screen-baseline` would be
folded into the `suite-*` report as extra baseline trials and quietly unbalance
the cell. Keep them apart: `screen-*` for the screen, `suite-*` for the run.

## 4. Running it

Every command is safe to re-run. Nothing below re-pays for a trial that already
finished.

```bash
C=config/experiments.codezen-vs-sdd.yaml
CAND=config/tasks-suite-candidates.txt
SET=config/tasks-suite.txt
```

### Step 0 — build and prove every variant (no tokens)

```bash
hmb doctor
hmb generate  --config $C --tasks-file $CAND --force
hmb validate  --config $C --tasks-file $CAND
hmb preflight --config $C --tasks-file $CAND --jobs 4
```

The gate is not optional: it is also what turns the run's own image builds into
cache hits, and `docker build` is the one part of a trial that runs on the
daemon outside any container's cpu allowance.

### Step 1 — screen for solvability (no tokens)

```bash
hmb screen --config $C --tasks-file $CAND --stage solvability --job-prefix screen
```

`oracle` must score 1.0 and `nop` must score 0.0. Anything else is a broken task
or a self-passing one, and neither can measure a methodology.

### Step 2 — screen for the ceiling (~$100)

```bash
hmb screen --config $C --tasks-file $CAND --stage baseline --job-prefix screen --out $SET
```

One bare-agent trial per task. Tasks it already passes cannot discriminate and
are dropped. `$SET` is written with every rejected task kept as a commented line
and its reason.

Re-run the same command after an interruption; it reports the jobs that already
exist and points at `hmb resume` for the one that did not finish.

### Step 3 — the measurement (~$9.4 per surviving task)

```bash
./scripts/run-pilot-experiment.sh --config $C --tasks-file $SET \
    --job-prefix suite --attempts 2 --dry-run     # inspect the plan, spends nothing

./scripts/run-pilot-experiment.sh --config $C --tasks-file $SET \
    --job-prefix suite --attempts 2
```

One job, `jobs/suite-claude-code`, holding every condition and task, up to 9
trials at a time. Progress goes to `jobs/suite-claude-code.log`.

### Step 4 — stopping, and continuing tomorrow

Press **Ctrl+C** in the terminal running the script. Harbor records the trials
that were in flight as `CancelledError` and stops; trials that already finished
keep their results. If the run was started in the background, `kill -TERM <pid>`
does the same thing — Harbor traps it identically. Then check nothing was left
behind:

```bash
docker ps                     # expect none of the task containers
docker ps -q | xargs -r docker rm -f     # only if some survived
```

**Re-running the script does not continue the job.** It sees an unfinished job
directory, refuses to touch it, and names the command that continues it — a bare
re-run would discard trials you have already paid for. Continue with:

```bash
hmb resume jobs/suite-claude-code
```

That classifies every trial first, prints the breakdown, and then re-runs only
the cancelled and infrastructure failures plus the trials that never started.
Finished trials are never re-paid.

| Situation | Command |
|---|---|
| Interrupted, or an infrastructure failure | `hmb resume jobs/suite-claude-code` |
| The account's quota ran out mid-run, and you have topped it up | `hmb resume jobs/suite-claude-code --recharged` |
| See what would happen without running anything | `hmb resume jobs/suite-claude-code --dry-run` |
| The screen's baseline stage was interrupted | `hmb resume jobs/screen-baseline`, then re-run the Step 2 command to write `$SET` |
| Start the whole job again, discarding paid trials | `./scripts/run-pilot-experiment.sh ... --force` |

Two things a resume cannot do. It cannot change concurrency — Harbor refuses to
resume a job whose stored config differs, so `--concurrent` is fixed for the
job's life. And it will not re-run a trial that failed for a reason that is
itself a finding: `OutputTokenExceededError` and timeouts stay in the results.

Check where a partially finished run stands at any time:

```bash
hmb resume jobs/suite-claude-code --dry-run     # per-exception breakdown
hmb report --pattern "suite-*"                  # the results so far
```

### Step 5 — results

```bash
hmb report --pattern "suite-*" --md-out results/suite_report.md \
    --json-out results/suite_summary.json
hmb analysis init suite --pattern "suite-*"
```

Keep the pattern as `suite-*`: it must not match the `screen-*` jobs, whose
baseline stage would otherwise be folded in as extra baseline trials.

## 5. What it costs

prog16's measured per-trial cost, on a harder-than-average task set:
`baseline $1.25`, `sdd $1.56`, `codezen-viable $1.91`.

| Stage | Trials | Estimate |
|---|---:|---|
| Screen, solvability | 166 | $0 |
| Screen, baseline | 83 | ~$100 |
| Measurement, per surviving task | 6 | ~$9.4 |

So a screened set of 40 tasks is roughly $380 of measurement on top of the
screen, and one of 60 is roughly $570. The screen pays for itself whenever it
removes more than ~11 tasks, and prog16 suggests it will remove many more.

Wall-clock is no longer proportional: the runner executes up to 9 trials at
once. The cost is unaffected by that, but `duration_sec` is — see
[troubleshooting § known confounds](troubleshooting.md#known-confounds).

## 6. What is reported

`hmb report` gives the cell-level view: per condition, censored and graded trial
counts, success rate over the graded trials, mean reward, mean partial credit,
pooled test pass rate, cost, and the three adherence strengths.

`hmb analysis extract` goes back to the trial artefacts for the metrics that
answer §10's remaining questions:

| Column | Question |
|---|---|
| `partial_credit`, `tests_passed` / `tests_total` | How much of the task was done, not merely whether it was finished |
| `time_to_first_passing_test_sec`, `steps_to_first_passing_test` | Speed that survives a ceiling: when the work first demonstrably worked |
| `n_test_runs`, `n_passing_test_runs` | Whether the agent verified its own work at all |
| `config_read_before_code`, `skill_before_code`, `doc_written_before_code`, `test_run_before_code`, `compliance_score` | Whether the method was *followed*, not merely available: what happened before the first code edit |
| `agent_timeout`, `budget_used` | Whether an outcome was capability or clock |

`compliance_score` is undefined for a trial that never edited code — nothing can
have happened "first" there — and a passing test run is read from the command's
exit status, not from its output text.

## 7. What this design still cannot answer

Screening removes the ceiling, and two attempts give a variance estimate, but
the population is unchanged: terminal-bench tasks are self-contained,
fully specified and single-session, which is the regime where a specification
process has least to add. A result here is evidence about *this* population.
The open questions prog16 raised in its §11 — primary endpoint, timeout
semantics, method mandated versus method available, equal-task versus
equal-budget — are design choices, and this run only settles the second of them
by reporting both readings.
