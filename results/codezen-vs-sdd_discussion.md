# CodeZen vs SDD — joint discussion of the `suite` and `ceiling` runs

Two runs finished on 2026-09-01, on the same three conditions, the same agent and the same
model, against two task populations selected on **opposite** criteria. This document reads
them together: what the pair establishes that neither establishes alone, which of `prog16`'s
open questions the second run can now answer, and what the pooled data says about the
hypothesis that methodology enforcement pays off as task length grows.

The per-run readings are
[`analysis-suite/suite_discussion.md`](analysis-suite/suite_discussion.md) and
[`analysis-ceiling/ceiling_discussion.md`](analysis-ceiling/ceiling_discussion.md). Every
number here comes from those executed notebooks or from the pooled tables derived in §5.

| | `suite` | `ceiling` |
|---|---|---|
| Task population | screened **in**: the bare agent must fail | screened **out**: the bare agent already passes |
| Tasks × conditions × attempts | 16 × 3 × 2 = 96 trials | 10 × 3 × 2 = 60 trials |
| Spend | $114.90 | $86.46 |
| Agent wall-clock | 18.3 h | 11.8 h |
| Baseline pass-at-2 | 6/16 = **37.5 %** | 9/10 = **90.0 %** |
| Design defect | floor effect: 7/16 all-fail | ceiling effect **by construction** |
| Effective n per comparison | 4–5 | 1–2 |
| Intended endpoint | outcome | cost and regression |

Pooled: **156 trials, 26 tasks, $201.37.**

---

## 1. What the pair establishes

### The cost finding is now robust, and its size depends on whether the work finishes

This is the one claim that survives both runs, both populations and every metric.

| | `suite` (work mostly aborts) | `ceiling` (work mostly completes) |
|---|---:|---:|
| CodeZen cost ratio | **3.11×** (p = 0.009, dearer on 12/16) | **1.71×** (p = 0.002, dearer on **10/10**) |
| CodeZen output tokens | 3.00× (p = 0.016) | 1.93× (p = 0.002) |
| CodeZen budget consumed | 1.55× (p = 0.093) | 1.90× (p = 0.002) |
| CodeZen sub-agents spawned | 84× | 51× |
| CodeZen partial credit | **0.96×** (p = 1.000) | **0.98×** (p = 0.750) |
| SDD cost ratio | 1.14× (p = 0.82) | 1.10× (p = 0.28) |
| SDD partial credit | 0.83× (p = 0.44) | **0.82×** (p = 0.125) |

Two readings that only the pair supports:

**The 3.11× and the 1.71× are not in conflict — they measure overhead on different things.**
On the floor population, CodeZen's trials frequently run to the budget wall without producing
a passing artefact, so the ratio includes work spent on tasks nothing solved. On the ceiling
population the same machinery runs on tasks that finish, and the overhead settles at 1.71×.
The honest summary for an operator is a range: **CodeZen costs 1.7× on work it completes and
up to 3.1× on work it does not**, and the second number is the one that bites, because the
methodology cannot tell in advance which kind of task it is on.

**The `ceiling` run is the stronger evidence despite being the smaller run.** Ten of ten
tasks dearer on four separate metrics at p = 0.002 — the floor of a two-sided Wilcoxon test at
n = 10 — is a cleaner result than twelve of sixteen at p = 0.009, because there is no task
where the effect is absent and no possibility that a runaway trial carries the mean.

**SDD's cost is not the story; SDD's partial credit is.** 1.10–1.14× spend is
indistinguishable from baseline in both runs. But partial credit lands at 0.83× and 0.82× —
the *same* shortfall in both populations, independently measured. Neither reaches significance
(p = 0.44, p = 0.125), and the consistency across two disjoint task sets is more interesting
than either p-value. On the `ceiling` set it corresponds to a test-level pass rate of 68.5 %
against baseline's 90.7 %, and to **zero** recognised verification commands across 20 trials.

### Methodology can regress a solved task — one clean instance, and a reliability effect

`torch-pipeline-parallelism` (`ceiling`): baseline passes inside 34 % of its budget. CodeZen
invoked `code-review` on one attempt and `noc-tdd` + `code-review` on the other, consumed
100 % of budget both times, and failed both times. The mechanism is in the trajectory, not
inferred.

Beyond that single instance, the *reliability* effect depends on the aggregation and both
readings must be quoted:

| | pass-at-2 (passed ≥ 1 attempt) | pass-both (passed both attempts) |
|---|---|---|
| `ceiling`, CodeZen | lost `torch-pipeline-parallelism`, gained `make-mips-interpreter` | additionally lost `schemelike-metacircular-eval` |
| `ceiling`, SDD | lost **nothing**, gained `make-mips-interpreter` | lost `headless-terminal`, `path-tracing-reverse`, `schemelike-metacircular-eval` |
| `suite`, CodeZen | lost `configure-git-webserver`, gained 3 | — |
| `suite`, SDD | lost `configure-git-webserver`, `path-tracing`, `polyglot-c-py`, gained 2 | — |

The gap between the two SDD columns on the `ceiling` set is entirely tasks SDD passed once and
failed once — tasks it made **less reliable** without making them impossible. For an operator
that is the property that matters, which is why both readings belong in the report rather than
whichever is more flattering. Note that `data/outcome_matrix.csv` currently writes the
pass-both matrix under a name that implies pass-at-2; that is a reporting trap, not a finding.

### Availability is total; invocation is rare in both populations

| | `suite` (32 trials/condition) | `ceiling` (20 trials/condition) |
|---|---|---|
| CodeZen invoked a skill | 12 (38 %) | 7 (35 %) |
| SDD invoked a skill | 7 (22 %) | 4 (20 %) |
| Trials invoking nothing | 45 of 64 toolkit trials | 29 of 40 toolkit trials |

Every skill registered in every toolkit trial and preflight proved every instruction file
present, so this is not an availability problem. Across both runs, **74 of 104 toolkit trials
(71 %) invoked no toolkit skill at all.** Whatever the two runs measured, it was not a
methodology being followed 71 % of the time.

SDD's abandonment pattern repeats across both runs: five trials stop after `sdd-specify` and
`sdd-clarify` having consumed 2–17 % of budget. The agent opens the process, produces a
specification, and does not follow it.

### Human-expert difficulty does not predict agent difficulty

Pooled across 26 tasks, baseline pass-at-2 versus `log10(expert_min)`: **rho = −0.078,
p = 0.704.** Nothing.

The two runs make the same point more starkly. Their median expert estimates are nearly
identical — 150 min (`suite`) and 180 min (`ceiling`) — and their baseline pass rates are
37.5 % and 90.0 %. The metadata that `prog16` used to select "hard" tasks carries essentially
no information about whether this agent will pass them.

That is why the screen exists, and §2 is why the screen is not yet sufficient either.

---

## 2. The methodological finding: both screens overshot

This is the most consequential result of the pair, and it is about the experiment rather than
about the toolkits.

| Run | Selection rule | Baseline pass-at-2 | Result |
|---|---|---:|---|
| `prog16` | human-expert difficulty | 81 % | **ceiling** — 11/16 concordant |
| `suite` | screen: bare agent must fail | 37.5 % | **floor** — 10/16 concordant, 7 all-fail |
| `ceiling` | screen: bare agent must pass | 90 % | ceiling, by design |

The screen was `prog16`'s prescribed fix for its ceiling effect. It ran correctly, excluded 64
of 83 candidates, and produced a set whose effective sample size is 4–5 — no better than the
run it repaired. It traded a ceiling for a floor.

**The defect is in the rule, and it is specific.** The screen includes a task when the bare
agent fails it on **one** trial. One trial cannot distinguish:

- *always fails* — a floor task, concordant, carries no information; and
- *sometimes fails* — the only kind of task that discriminates.

Both runs contain direct evidence that the rule is unreliable in both directions.
`make-mips-interpreter` was excluded as "the bare agent already passes it" and baseline then
failed both attempts of it in the `ceiling` run. Seven tasks were included as "the bare agent
fails it" and then failed under every condition.

**The fix is a two-sided rule on the baseline pass *rate*:** include a task when baseline's
pass rate over ≥ 3 trials is strictly between 0 and 1. That costs roughly 3 baseline trials
per candidate instead of 1 — for 83 candidates, about 2× the screen's original cost — and it
is the only change in this document that would materially improve the next run's power.

**The uncomfortable possibility, stated plainly.** It may be that the discriminating band is
narrow and unstable — that most Terminal-Bench tasks are, for this agent, either reliably
solved or reliably unsolved, with few in between. If so, no screen will produce a
well-powered outcome comparison at affordable cost, and the right response is to promote cost
and conformance to primary endpoints and treat outcome as secondary. Both runs are consistent
with that possibility. Neither establishes it.

---

## 3. Which of `prog16`'s open questions the second run can now answer

`prog16`'s §11 listed seven questions about experimental intent. The `ceiling` run was not
designed to answer them, but it bears on five.

### Q2 — which endpoint is primary: outcome, cost, or conformance? **Substantially answered.**

If the endpoint is **cost at equal outcome**, the question is settled for both populations.
The `ceiling` run delivers it at p = 0.002 with CodeZen dearer on 10 of 10 tasks across four
metrics, on a population where outcome is genuinely equal (every McNemar p = 1.000). That is
as clean a cost-at-equal-outcome measurement as this design can produce.

If the endpoint is **outcome**, neither run can answer it and §2 explains why — one is
floored, one is ceilinged, and the screen that was meant to find the middle produced the
floor.

If the endpoint is **conformance**, both runs answer it and the answer is the same: 71 % of
toolkit trials invoked nothing.

**Consequence for the sequence:** the cost endpoint is done. Spending more on outcome requires
fixing the screen first (§2), and the value of doing so is now questionable (§2, last
paragraph).

### Q3 — should a timeout count as a failure? **Sharpened from theoretical to decisive.**

`prog16` noted the choice moved two of five informative outcomes. The `ceiling` run makes it
change a conclusion:

| Condition | Timeout = censored | Timeout = failure |
|---|---:|---:|
| `baseline` | 89.5 % | 85.0 % |
| `codezen-viable` | **92.9 % (1st)** | **80.0 % (2nd)** |
| `sdd` | 77.8 % | 75.0 % |

CodeZen moves from first to second and loses 12.9 points, because it is censored on 6 of 20
trials against baseline's 1. Four censored trials scored reward 1.0 — the agent finished and
was then killed — so neither convention is straightforwardly correct.

**This must be decided before the next run, in writing.** Choosing after seeing the numbers is
not a defensible order of operations, and this pair of runs is the concrete case that makes it
matter. A third option is better than either: **grade the working directory at the moment of
the kill.** Across both runs, 7 of the 23 censored trials scored reward 1.0 anyway — 3 of 14
in `suite`, 4 of 9 in `ceiling` — which means censoring is currently discarding observations
that already exist on disk.

### Q5 — is low adherence a toolkit property or a harness artefact? **Partially answered, and this is new.**

`prog16` could not separate "the toolkits gate themselves on task size" from "a bare Harbor
prompt gives no reason to consult a process". The pooled data leans toward the first, for SDD:

| | Spearman rho vs `log10(expert_min)` | p | Long-horizon mean calls | Short mean | Mann–Whitney p |
|---|---:|---:|---:|---:|---:|
| SDD toolkit skill calls | **+0.379** | **0.056** | **2.30** | **1.06** | 0.093 |
| CodeZen toolkit skill calls | +0.197 | 0.335 | 2.10 | 1.50 | 0.470 |

SDD invokes its chain more than twice as often on long-horizon tasks as on short ones. That is
the behaviour of a toolkit gating itself on perceived task size, not of a harness suppressing
it — and it is evidence against the "the prompt gives no reason" explanation, at least for
SDD. CodeZen shows the same sign much more weakly.

Neither result reaches p < 0.05, and §5 explains why n = 26 cannot resolve effects of this
size. But the direction is consistent and it is the first quantitative handle on Q5.

### Q6 — equal-task or equal-budget? **Partially answered.**

| Run | Baseline $/pass | CodeZen $/pass | Extra baseline trials at CodeZen's spend |
|---|---:|---:|---:|
| `suite` | $3.12 | $7.57 | ~100 trials instead of 32 |
| `ceiling` | $1.34 | $2.98 | ~34 trials instead of 20 |

On the `ceiling` population the equal-budget comparison resolves without needing to be run:
baseline already passes 89.5 % of trials, so 70 % more attempts would buy almost nothing —
and the methodology's overhead is therefore a pure loss there, not a trade. On the `suite`
population the question stands open and is worth measuring: at 3.1× the spend, baseline gets
three times the attempts on tasks where its pass rate is 25 %, and repeated sampling is
exactly the regime where extra attempts help most.

**Still unmeasured, and now the highest-value open question**: does CodeZen's 3.11× beat
spending the same money on 3× the baseline attempts? Nothing in either run tests it, and it is
the comparison an operator actually faces.

### Q4 — is the target population benchmark tasks or real repository work? **Approached, not answered.** See §5.

### Q1 and Q7 — what decision does this feed, and which toolkit is subject versus control?

Unchanged. These are questions about intent that no amount of data answers. They are recorded
here because the answer to Q1 determines whether §1's cost finding is sufficient: it is
decision-grade for choosing an internal default, and it is not publication-grade for a
methodology comparison.

---

## 4. Two new questions the pair raises

**Is the task-set partition reliable enough to build a design on?** Every design in this
sequence assumes tasks can be sorted into "at ceiling", "discriminating" and "at floor". §2
shows that assignment failing in both directions from a single baseline trial. If the
partition is unreliable, so is every conclusion that depends on which bucket a task was put
in.

**Does invoking the methodology predict failure, and if so why?** Across both runs, of the 30
trials that invoked a toolkit skill, the pass rate is visibly below each run's overall rate —
starkly so in the `ceiling` run, where 4 of 11 skill-using trials passed against a run-wide
77–93 %. The obvious explanation is selection: the toolkits invoke themselves on the tasks
they judge hardest, and §3's Q5 evidence supports exactly that. But selection and effect
cannot be separated in this design, and the alternative — that invoking the chain consumes the
budget that would have solved the task — is supported by the censoring data in both runs. A
design that randomised invocation rather than leaving it to the agent would separate them.

---

## 5. The length hypothesis, tested

> *"Longer horizon tasks are a bit less feasible on account of the cost, but that hypothesis
> about methodology enforcement being more useful at higher task length feels worth
> exploring."*

Two distinct claims. Both are testable on the pooled 26 tasks, whose expert estimates span
5 to 1,440 minutes — a 288× range — with 10 tasks carrying Terminal-Bench's own
`long-horizon` axis. The pooled per-task table is in
[`analysis-suite/data/trials.csv`](analysis-suite/data/trials.csv) and
[`analysis-ceiling/data/trials.csv`](analysis-ceiling/data/trials.csv); the derivation is
reproduced at the end of this section.

**Power first, so the nulls can be read correctly.** At n = 26, a two-sided Spearman test at
alpha = 0.05 has 80 % power only for rho ≥ **0.53**. For rho = 0.4 power is 0.53; for
rho = 0.3 it is 0.32. Every correlation below is therefore reported with its rho, because a
p-value above 0.05 at this n means "not resolved", not "absent".

### Claim 1 — cost makes long tasks less feasible. **Supported in absolute terms, refuted as a multiplier.**

The cost *multiplier* does not grow with task length at all:

| Cost ratio vs baseline | vs `log10(expert_min)` | vs `budget_sec` | vs `instruction_words` |
|---|---:|---:|---:|
| CodeZen | rho = **+0.001** (p = 0.996) | −0.006 (p = 0.979) | +0.324 (p = 0.106) |
| SDD | +0.061 (p = 0.767) | +0.129 (p = 0.529) | +0.254 (p = 0.211) |

A rho of 0.001 against a 288× range of task length is as close to a flat line as this data can
produce. The overhead is **proportional**, not super-proportional: CodeZen costs about 1.7–3.1×
whether the task is 5 minutes of expert time or 24 hours.

But the absolute dollar penalty does grow, because the base cost grows:

| | rho vs `log10(expert_min)` | p |
|---|---:|---:|
| Baseline absolute cost | **+0.695** | **0.0001** |
| CodeZen absolute overhead (Δ$) | +0.337 | 0.093 |
| SDD absolute overhead (Δ$) | +0.155 | 0.448 |

CodeZen's mean overhead is **$0.79 per trial on short-budget tasks (≤ 900 s) and $1.68 on
long-budget tasks** — 2.1× the dollars for the same multiplier.

**So the intuition is right, for a reason worth stating precisely.** Long tasks are not less
feasible because the methodology becomes proportionally greedier — it does not. They are less
feasible because a constant multiplier applied to a larger base is a larger absolute bill, and
because of the second mechanism below.

**The budget mechanism is the sharper half of the feasibility claim.** CodeZen consumes 1.9×
baseline's share of the declared budget (`ceiling`, p = 0.002, higher on 10/10 tasks). Tasks
whose expert estimate is large relative to their budget are where that extra consumption
crosses the wall:

| | rho vs expert/budget ratio | p |
|---|---:|---:|
| CodeZen agent timeouts | +0.304 | 0.131 |
| SDD agent timeouts | +0.246 | 0.225 |

Reading the per-task table directly is more convincing than the correlation: of the six tasks
with an expert/budget ratio ≥ 12×, CodeZen consumed **100 % of budget** on
`adaptive-rejection-sampler`, `torch-pipeline-parallelism` and `make-mips-interpreter`, and
93 % on `torch-tensor-parallelism`. Baseline crossed 75 % on two of the same six. **The
feasibility limit is not the dollar cost — it is the clock.**

### Claim 2 — methodology enforcement is more useful at higher task length. **Not supported.**

The hypothesis predicts that the methodology's outcome advantage grows with task length. Three
outcome measures, two length measures:

| Dependent | Condition | vs `log10(expert_min)` | vs expert/budget ratio |
|---|---|---:|---:|
| Δ pass-at-2 | CodeZen | +0.222 (p = 0.275) | **+0.330 (p = 0.099)** |
| Δ pass-at-2 | SDD | +0.246 (p = 0.225) | **+0.349 (p = 0.081)** |
| Δ pass rate | CodeZen | −0.028 (p = 0.893) | +0.107 (p = 0.602) |
| Δ pass rate | SDD | +0.074 (p = 0.720) | +0.181 (p = 0.376) |
| Δ partial credit | CodeZen | −0.028 (p = 0.891) | −0.020 (p = 0.923) |
| Δ partial credit | SDD | −0.096 (p = 0.642) | +0.023 (p = 0.910) |

There is a **weak positive lean in the predicted direction, and only in the coarsest metric.**
Δ pass-at-2 against the expert/budget ratio gives rho ≈ +0.33 to +0.35 for both toolkits — the
largest effects in the table, both just outside significance, both at roughly 35–40 % power.

That lean does not survive refinement. The same comparison on pass *rate* (which uses both
attempts rather than the best one) drops to +0.11 and +0.18. On partial credit — 519 graded
test outcomes rather than 26 binary ones, the finest instrument available — it is
indistinguishable from zero and, for CodeZen against expert time, faintly negative.

**A real effect should sharpen as the metric sharpens. This one dissolves.** That is the
signature of noise in a coarse metric, and the honest conclusion is that the data does not
support the hypothesis and is not powered to reject it.

Terminal-Bench's own `long-horizon` axis says the same, and adds something:

| | CodeZen: long-horizon vs short | p | SDD: long-horizon vs short | p |
|---|---|---:|---|---:|
| Δ pass-at-2 | +0.100 vs +0.062 | 0.858 | +0.000 vs +0.000 | 1.000 |
| Δ pass rate | **−0.050** vs +0.094 | 0.391 | **−0.100** vs −0.031 | 0.832 |
| Δ partial credit | **−0.057** vs +0.003 | 0.389 | **−0.182** vs −0.080 | 0.303 |
| Cost ratio | 3.098 vs 3.737 | 0.693 | 1.154 vs 1.107 | 0.732 |

On every finer-grained outcome measure, both methodologies do **worse** on long-horizon tasks
than on short ones, not better. The differences are not significant, but they are consistent
across two metrics and two toolkits, and they point the opposite way to the hypothesis. SDD's
partial-credit deficit on long-horizon tasks is −0.182 against −0.080 on short ones: its worst
performance is where its own documentation claims it should be strongest.

### The most interesting result: the toolkits behave as if the hypothesis were true

The strongest length-related signal in the pooled data is not about outcome. It is §3's Q5
finding:

**SDD invokes its skill chain 2.2× more often on long-horizon tasks than on short ones**
(2.30 vs 1.06 calls per task, p = 0.093; rho = +0.379 against log expert time, p = 0.056).

So the hypothesis is *already encoded in the toolkit's behaviour*. SDD gates itself on
perceived task size and engages its process where the hypothesis says it should pay off. The
data then shows that engagement producing no outcome benefit — and on long-horizon tasks
specifically, the largest partial-credit deficit in either run.

That is a much more pointed result than a null correlation. It is not "we could not find the
effect where we looked". It is "the toolkit looked in the same place, acted on the same
belief, and the belief did not pay".

### Why this analysis is confounded, and what would fix it

**The pooled sample mixes two populations selected on baseline outcome**, which is the single
strongest confound available:

| | `ceiling` run | `suite` run |
|---|---:|---:|
| Baseline pass-at-2, short tasks | 1.000 (n = 5) | 0.455 (n = 11) |
| Baseline pass-at-2, long-horizon tasks | 0.800 (n = 5) | 0.200 (n = 5) |

Run membership dominates baseline pass rate far more than long-horizon status does. Because
the two runs were selected on opposite baseline criteria, any pooled regression on task
properties partly measures *which screen bucket a task fell into*. Long-horizon tasks are
split 5/5 between the runs, so the confound does not align perfectly with the predictor — but
it is not orthogonal to it either.

Within-run analysis would be clean, and is not possible: n = 16 and n = 10 give 80 % power
only for rho ≥ 0.64 and rho ≥ 0.80 respectively.

**Three further limits.**

- **The range is not the range the hypothesis is about.** These tasks top out at 1,440 min of
  expert time in a *single autonomous session* with a fully specified instruction. The
  hypothesis is about multi-session work with ambiguous requirements and a human in the loop.
  Nothing here reaches that regime, which is `prog16`'s Q4 restated: the length axis available
  in this benchmark is not the length axis that matters.
- **The budget wall censors the long end.** On the longest, tightest tasks the methodology
  conditions are frequently killed before finishing, so the outcome measure on exactly the
  tasks the hypothesis cares about most is the least reliable one in the data. Grading at kill
  time (§3, Q3) would partly repair this.
- **`expert_min` is a poor predictor of anything about this agent** (rho = −0.078 against
  baseline pass, §1). Using it as the length axis is defensible — it is the benchmark's own
  metadata — but it is measuring human effort, not agent horizon.

**What would actually test the hypothesis**, in increasing order of cost:

1. **Re-analyse with `steps_to_first_passing_test` as the length axis.** It is already derived
   in both notebooks, it measures the agent's own horizon rather than a human's, and it costs
   nothing. It is only available on tasks that produce a passing test, which is its limitation.
2. **Grade the workdir at kill time** so the long end stops being censored.
3. **Randomise invocation** — mandate the methodology in half the trials — so §4's
   selection/effect confound is broken and "enforcement" becomes a manipulated variable rather
   than an observed one. This is what "methodology *enforcement*" in the hypothesis literally
   requires, and no run in this sequence has done it.
4. **Build a task set stratified on agent horizon**, with the two-sided screen from §2, and
   ≥ 3 attempts. At the rates observed here, roughly 40 discriminating tasks × 3 conditions ×
   3 attempts ≈ 360 trials ≈ $450–700. That is what an adequately powered test of this
   hypothesis costs.

### Derivation

The pooled table is built from the two runs' `trials` tables joined to
`results/task_catalogue.json`, aggregated per task × condition (`pass_any = max(success)`,
`pass_rate = mean(success)`, means for the continuous quantities), then differenced against
the baseline column of the same task. Length predictors: `expert_min` (log10),
`budget_sec`, `instruction_words`, `expert_min ÷ (budget_sec/60)`, and membership of the
`long-horizon` axis. Tests: Spearman rank correlation for the continuous predictors,
Mann–Whitney U for the binary axis split, both two-sided. Power from the Fisher
z-transformation at n = 26.

---

## 6. Where the sequence stands

**Settled.**

1. CodeZen costs 1.7× on work that completes and up to 3.1× on work that does not, for
   0.96–0.98× the partial credit. Significant on two independent populations.
2. SDD costs ~1.1× and is behaviourally near-invisible, but satisfies 0.82–0.83× of each
   verifier's tests — consistently, across both runs, without reaching significance.
3. Methodology can regress a solved task, and can make a solved task less reliable.
4. 71 % of toolkit trials invoke no toolkit skill.
5. Human-expert difficulty does not predict agent difficulty.
6. The screen's single-trial inclusion rule is unreliable in both directions, and both screens
   overshot.

**Open, in priority order.**

1. **Does the overhead beat 3× the baseline attempts at equal budget?** (§3, Q6.) The
   comparison an operator faces, cheap to run, and untested.
2. **Fix the screen to a two-sided pass-rate rule, or abandon outcome as a primary endpoint.**
   (§2.) Everything about outcome power depends on this.
3. **Settle the censoring convention in writing, and grade at kill time.** (§3, Q3.) It changes
   a conclusion in the `ceiling` run.
4. **Randomise methodology invocation** to separate selection from effect and to make
   "enforcement" a manipulated variable. (§4, §5.)
5. **Test the length hypothesis on an agent-horizon axis**, not a human-effort one. (§5.)

**Not worth more spend on the current design.** Another run on either of these task
populations would reproduce §1 and add nothing, because both populations are concordant for
opposite reasons and the cost finding is already significant on both.
