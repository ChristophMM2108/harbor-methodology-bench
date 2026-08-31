# Experiments

[← README](../README.md) · [setup](setup.md) · [architecture](architecture.md) · [tasks](tasks.md) · [analysis](analysis.md) · [reference](reference.md) · [troubleshooting](troubleshooting.md)

An experiment is one file plus one task set. This page covers declaring
conditions, four worked scenarios, and running the matrix.

---

## 1. Scaffolding one

```bash
hmb experiment new my-run \
    --toolkit my-kit --agent claude-code \
    --suite spec-dense --difficulty medium
```

Writes two files, both named after the experiment:

- `config/experiments.my-run.yaml` — conditions, models, matrix, attempts;
- `config/tasks-my-run.txt` — the resolved task ids, one per line.

Any task-selection flag is resolved **now** and written out as explicit ids, so
the experiment records the task set it measured rather than a query whose result
can change when the task-suite pin moves.

`hmb experiment list` shows the configurations in a checkout with their cell
counts and conditions.

---

## 2. The configuration file

```yaml
source_root: source-tasks/terminal-bench   # where tasks are read from
generated_root: generated                  # where variants are written
repetitions: 3                             # documents the design

models:
  claude-code: claude-sonnet-5
  codex: gpt-5.6-terra

# Names dropped from every toolkit payload before it enters a container.
snapshot_excludes: [".git", ".venv", "node_modules", "__pycache__", ".DS_Store"]

# Directories holding installable skills, in precedence order.
skill_sources: [".claude/skills", ".agents/skills", "skills"]

toolkits:                                  # one entry per condition
  - id: my-kit
    snapshot: toolkits/my-kit/snapshot

matrix:                                    # the cells the runner executes
  - {id: claude-baseline, agent: claude-code, toolkit: baseline}
  - {id: claude-my-kit,   agent: claude-code, toolkit: my-kit}
```

Every command takes `--config <path>`, so an alternative experiment is a separate
file rather than an edit. `hmb matrix-plan --config <path>` prints the cells a
configuration resolves to.

`repetitions` is **documentary**: the runner takes the real count from
`--attempts`, and omitting the flag silently gives you one attempt per cell. Keep
the two equal, and state the number in the write-up.

---

## 3. Declaring a condition

A condition is an entry under `toolkits:`:

| Key | Meaning |
|---|---|
| `id` | condition name; becomes `generated/<id>/`. `baseline` is reserved |
| `snapshot` | path to the frozen repository snapshot |
| `exclude` | names dropped from the payload at any depth (defaults to `snapshot_excludes`) |
| `include` | allowlist of top-level snapshot entries; everything else is dropped |
| `expect_instructions` | must a `CLAUDE.md` / `AGENTS.md` reach the agent's workdir? Default `true` |
| `expect_skills` | must the toolkit's skills be installed for the agent? Default `true` |
| `skill_sources` | override the global skill source directories for this toolkit |

`expect_instructions` and `expect_skills` are asserted in **both** directions by
`validate` and `preflight`. That is what makes subtractive conditions safe: the
gates enforce absence just as strictly as presence.

---

## 4. Worked scenarios

`config/experiments.scenarios.yaml` runs B, C and D against the vendored
`demo-kit`, so it works with no external access.

### A — pure agent, no repository configuration

Nothing to configure. `baseline` is generated for every task and contains the
benchmark task only; preflight proves its workdir is byte-identical to the base
image. This is a genuine no-methodology control — no dummy repository and no
hand-built image needed.

### B — repository present, instructions removed

You cannot instruct an agent to disregard a `CLAUDE.md` it has already been
given: Claude Code loads project memory silently into its system prompt, and
Codex does the same with `AGENTS.md`. Telling it to ignore them is unverifiable
and not a controlled condition.

The controlled way is subtractive — deploy the **same** snapshot with the
methodology surface filtered out:

```yaml
  - id: my-kit-content-only
    snapshot: toolkits/my-kit/snapshot
    exclude: [".git", ".venv", "__pycache__",
              "CLAUDE.md", "AGENTS.md", ".claude", ".agents", "skills", ".my-kit"]
    expect_instructions: false
    expect_skills: false
```

The agent gets the repository's code, docs and tests, but no instruction files,
no skills and no kit templates. Preflight asserts the absence:

```text
ok  my-kit-content-only: workdir=/app markers=- skills=0 payload_files=25
    expects(instructions=False,skills=False)
```

Note that the `exclude` list **is** the operational definition of "methodology
surface" for your experiment. Choose it deliberately — leaving a kit directory in
hands the agent the method by another route.

### C — instructions only, no repository bulk

The inverse control. `include` is an allowlist over the snapshot's top-level
entries:

```yaml
  - id: my-kit-instructions-only
    snapshot: toolkits/my-kit/snapshot
    include: ["CLAUDE.md", "AGENTS.md", ".claude", ".agents", ".my-kit"]
```

Comparing B and C against the full condition separates "the methodology text and
skills" from "the repository the toolkit happens to live in".

### D — the toolkit as shipped

```yaml
  - id: my-kit-full
    snapshot: toolkits/my-kit/snapshot
```

**Deploying in full is a design decision, not a neutral default.** A toolkit's
`src/`, `tests/`, `docs/` and lockfiles land in the agent's working directory
alongside the benchmark task, which changes what the agent sees when it explores
the repository. That is a confound distinct from the methodology instructions.
Either accept it — the condition is then "the agent works in a repository
configured with this toolkit", which is what the toolkit looks like in real use —
or restrict the payload with `include`. State which you chose.

### E — comparing two toolkits

Declare both; the matrix crosses them with your agents. Keep the agent name in
each cell id: job directories are named after it, so two agents can share one job
prefix and one report.

### F — two variants of one repository

The common case in practice: you rewrote a `CLAUDE.md`, added a skill, tightened
a skill's trigger, or dropped one. Freeze the repository twice at the two commits
and declare each as its own condition — see
[setup.md § 6](setup.md#6-adding-your-own-toolkit) for the `config/sources.yaml`
shape:

```yaml
toolkits:
  - id: my-kit-before
    snapshot: toolkits/my-kit-before/snapshot
  - id: my-kit-after
    snapshot: toolkits/my-kit-after/snapshot

matrix:
  - {id: claude-baseline, agent: claude-code, toolkit: baseline}
  - {id: claude-before,   agent: claude-code, toolkit: my-kit-before}
  - {id: claude-after,    agent: claude-code, toolkit: my-kit-after}
```

Keep `baseline` in the matrix even when the question is only before-versus-after.
Without it, a change that made both variants worse than no configuration at all
looks like a tie.

To isolate a single skill inside one snapshot, use `include` / `exclude` rather
than a second commit — `exclude: ["my-skill"]` drops that skill's directory at
any depth, and preflight reports the resulting skill count so the subtraction is
visible in the record.

### G — one skill, does it earn its place?

The question this framework exists for. The recipe:

1. **Write down the skill's claim** in one sentence, in outcome terms: "it makes
   the agent root-cause before patching", "it stops the agent declaring done
   without running tests".
2. **Pick the axis that tests that claim** and one control axis — see
   [tasks.md § 2](tasks.md#2-two-orthogonal-classifications). A skill for
   diagnosis is tested on `diagnose-first`, not on the whole suite; the control
   is where its overhead should show up as pure cost.
3. **Screen the tasks** so the bare agent does not already pass them
   ([tasks.md § 1](tasks.md#1-choosing-tasks-that-can-discriminate)). This is the
   step that decides whether the run can answer anything.
4. **Run three conditions**: baseline, the configuration with the skill, the same
   configuration without it. The third is what separates "the skill helped" from
   "the repository configuration helped".
5. **Gate on adherence before reading the outcome.** If the skill was never
   invoked, the comparison measured its presence, not its effect — and that is
   itself the finding, usually about the skill's trigger wording rather than its
   content. See [analysis.md § 2](analysis.md#2-reading-adherence).
6. **Report cost next to outcome.** A skill that changes nothing and costs 50 %
   more is a decision; a skill that changes nothing and costs nothing is a
   different one.

---

## 5. Running the matrix

```bash
C=config/experiments.my-run.yaml
T=config/tasks-my-run.txt

hmb generate  --config $C --tasks-file $T --force
hmb validate  --config $C --tasks-file $T
hmb preflight --config $C --tasks-file $T          # builds every image, spends no tokens

./scripts/run-pilot-experiment.sh --config $C --tasks-file $T \
    --job-prefix my-run --attempts 3 --dry-run     # inspect the plan
./scripts/run-pilot-experiment.sh --config $C --tasks-file $T \
    --job-prefix my-run --attempts 3

hmb report --pattern "my-run-*" \
    --md-out results/my-run_report.md \
    --json-out results/my-run_summary.json
```

The runner resolves its task list and its cells through the same code as the
generator, so leftover directories under `generated/` from an earlier selection
can never join a run. It refuses to start if a selected variant has not been
generated, and names the command that would fix it.

It runs **one Harbor job per agent**, holding every condition and every task.
Harbor gives each trial a random directory suffix and records its condition
under `config.task.path`, so conditions cannot collide and `hmb report` still
separates them. Within a job the dataset list is task-major — every condition of
one task, then the next task — so conditions run side by side instead of one
whole condition after another. That keeps host contention symmetric across
conditions, which `duration_sec` would otherwise absorb. `hmb plan-job` writes
those job configs and can be inspected on its own:

```bash
hmb plan-job --config $C --tasks-file $T --job-prefix my-run --attempts 3
```

Because trials run concurrently, `duration_sec` is contention-affected and is
not comparable with the serially-run numbers already in `results/`. Cost and
token metrics are unaffected. Every report records the concurrency the run used.

### Choosing a concurrency

Docker's `auto` resource mode resolves to hard limits, so each trial container is
capped at the `cpus` and `memory_mb` its task declares regardless of its
neighbours. Concurrency is therefore bounded by the host, not by the risk of one
trial starving another: sum the declarations of the tasks you selected and keep
the total inside the machine. In the terminal-bench suite 84 of 89 tasks declare
`cpus = 1` and 69 declare `memory_mb = 2048`, so nine concurrent trials is about
nine cores and, worst case, some 49 GB.

Two things the sum does not cover:

- **`docker build` runs on the daemon**, outside every container's cpu
  allowance. The preflight gate is what keeps it out of the run: it builds every
  image first, so the run's own builds are cache hits.
- **The agent's credential is shared.** `agents[].n_concurrent` caps the agent
  phase below the trial concurrency, so builds and verifiers keep using the
  machine while agent runs wait on the provider. Harbor pools agent configs that
  are byte-identical under one limit automatically, so every condition running
  the same agent shares one throttle.

A job's concurrency is fixed for its whole life: Harbor refuses to resume a job
whose stored `config.json` differs from the one it was created with. Choose it at
creation; changing it means a new job.

| Flag | Effect |
|---|---|
| `--config PATH` | the experiment configuration |
| `--job-prefix NAME` | job name prefix, and the `hmb report --pattern` to use afterwards |
| `--attempts N` | repetitions per cell, passed to `harbor --n-attempts` (`-k`) |
| `--concurrent N` | concurrent trials per job over the whole lifecycle — build, agent, verify (default 9) |
| `--concurrent-agents N` | concurrent agent phases per job (default 6, must not exceed `--concurrent`) |
| `--preflight-jobs N` | parallel image builds in the preflight gate (default 4) |
| `--timeout-multiplier F` | scale every task timeout by `F`, for every cell in the run. Record the value with the result: it changes the budget the benchmark declares, and only a run-wide value keeps conditions comparable |
| `--force` | delete and re-run jobs that already have results |
| `--dry-run` | print the job configs and the Harbor invocations without executing them |
| `--skip-preflight` | skip the validate/preflight gate — debugging only |

`--attempts` is Harbor's `-k` / `--n-attempts`. Harbor's `-n` is
`--n-concurrent`, a different setting: passing an attempt count to `-n` runs
**one** trial per cell at that concurrency.

`./scripts/run-smoke-experiment.sh [--task ID]` is the same runner pinned to a
single task with the `smoke` job prefix.

To reproduce one cell by hand:

```bash
harbor run \
  -p generated/my-kit/sqlite-db-truncate \
  -a claude-code -m claude-sonnet-5 -k 3 \
  --env-file config/local.env \
  --job-name manual-my-kit-sqlite-db-truncate
```

---

## 6. Attempts, and why one is not enough

Agents are stochastic — reasoning paths and tool choices differ between runs — so
a single attempt per cell cannot separate a methodology effect from noise. Three
or more is the practical minimum, for three distinct reasons:

- **Confidence intervals** — a mean success rate is only reportable with a
  standard error across attempts.
- **Flakiness detection** — repetitions separate a deterministic tool failure
  from a transient rate limit or timeout.
- **Cost and latency distribution** — median, p90 and outlier spend are
  properties of a distribution, not of one trial.

All attempts land in the same job directory with per-trial metrics (`trial_1`,
`trial_2`, …), and both `hmb report` and `hmb analysis` fold them together.

There is a real trade-off against task count. For detecting a difference
*between conditions*, task-to-task variance usually dominates
attempt-to-attempt variance, so more tasks beat more attempts at equal cost —
**but only for tasks that can discriminate at all**. Spending three attempts on a
task every condition passes buys nothing three times over. Read
[tasks.md](tasks.md#1-choosing-tasks-that-can-discriminate) before choosing the
split.

---

## 7. Budgeting a run

Multiply: `tasks × cells × attempts`. Use the catalogue's `expert` and `budget`
columns to estimate wall-clock — the agent timeout is the worst case per trial.

Two measured reference points with Claude Code:

| Run | Shape | Trials | Cost | Serial wall-clock |
|---|---|---:|---:|---:|
| Probe | 3 tasks × 4 conditions × 1 | 12 | $24.94 | ~5.9 h |
| Measurement | 16 hard tasks × 3 conditions × 1 | 48 | $75.49 | ~11.8 h |

That is roughly $1.5–2.1 per trial on hard, long-horizon tasks; cheap tasks run
an order of magnitude below it. Start with `--suite quick --limit 3` while you are
still shaking out configuration, and always `--dry-run` first.

Run a cheap **probe** before an expensive measurement, with the probe's task set
a strict subset of the measurement's. Its job is to answer questions that do not
need statistical power: does the payload arrive, does the agent engage with the
methodology at all, do the verifiers behave. A probe that finds zero adherence
tells you the expensive run would have measured nothing.
