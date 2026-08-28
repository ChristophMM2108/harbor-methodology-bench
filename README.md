# Harbor Methodology Bench

Measure what a repository's **agent configuration** actually does to a coding
agent — not what its documentation claims.

You give it a benchmark suite (Terminal-Bench 2.0) and one or more repositories
that carry an agent methodology: a `CLAUDE.md` or `AGENTS.md`, skills, slash
commands, kit directories. It builds one Docker image per (task × condition),
proves from inside each container that the condition is what you declared, runs
coding agents against them in isolated [Harbor](https://github.com/harbor-framework/terminal-bench)
containers, and aggregates rewards, cost, telemetry and methodology adherence.

The framework is toolkit-agnostic and pins everything external by commit, so a
result is reproducible from a clone.

```bash
git clone git@github.com:ChristophMM2108/harbor-methodology-bench.git
cd harbor-methodology-bench
./bootstrap.sh                       # installs uv, the Harbor CLI, `hmb`, and every pinned source
hmb doctor                           # what is still missing, and the command that fixes it
```

---

## Documentation

| Read this | For |
|---|---|
| [docs/setup.md](docs/setup.md) | Installing, credentials, pinned sources, adding your own toolkit, updating a pin |
| [docs/architecture.md](docs/architecture.md) | How the methodology reaches the container, the payload layer, and the invariants that make a comparison valid |
| [docs/experiments.md](docs/experiments.md) | Declaring conditions, worked scenarios, running a matrix, attempts and budget |
| [docs/tasks.md](docs/tasks.md) | Choosing a task set that can actually discriminate, the axis catalogue, authoring your own task |
| [docs/analysis.md](docs/analysis.md) | Reading the report, what adherence does and does not prove, the analysis notebook and its derived metrics |
| [docs/reference.md](docs/reference.md) | Every command, every flag, and the repository layout |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Symptoms, causes, and the current limitations |
| [docs/evaluation-pipeline.md](docs/evaluation-pipeline.md) | The evaluation process end to end: how a trial becomes a reward, a duration and a cost, and the measurement hazards in each |

External: [Harbor framework](https://github.com/harbor-framework/terminal-bench) ·
[Terminal-Bench 2.0 tasks](https://github.com/harbor-framework/terminal-bench-2) ·
[what Terminal-Bench 2.0 measures](https://snorkel.ai/blog/terminal-bench-2-0-raising-the-bar-for-ai-agent-evaluation/) ·
[Claude Code](https://claude.com/claude-code)

---

## The core idea

Two questions have to be kept apart, and the framework measures them separately:

| Question | Answered by |
|---|---|
| Was the methodology **available** to the agent? | `hmb preflight` — an assertion made inside the container |
| Did the agent **use** it? | `hmb report` — adherence read from the agent's own trajectory |

A condition with a passing preflight and zero adherence is a finding about the
toolkit. A condition with a failing preflight is a broken experiment, and the
runners refuse to execute it.

An experiment is a matrix of **agents × conditions** run over a task set:

| Agent | `baseline` | `your-kit` | `their-kit` |
|---|:---:|:---:|:---:|
| **Claude Code** | Cell 1 | Cell 2 | Cell 3 |
| **OpenAI Codex** | Cell 4 | Cell 5 | Cell 6 |

`baseline` is always generated and means *the benchmark task and nothing else* —
the pure agent, with a working directory proven byte-identical to the task's own
base image. Every other condition you declare yourself.

```text
        Terminal-Bench tasks            your methodology repositories
        source-tasks/<suite>/                  toolkits/<id>/snapshot/
                  │                                     │
                  └──────────────┬──────────────────────┘
                                 │  hmb generate  (one Docker layer per condition)
                    generated/<condition>/<task>/
                                 │
                     hmb validate  →  hmb preflight
                    (host hashes)     (in-container proof)
                                 │
                   ┌─────────────┴─────────────┐
              Claude Code                  Codex CLI
                   └─────────────┬─────────────┘
                                 ▼
                          jobs/  →  hmb report  →  hmb analysis
```

Read [docs/architecture.md](docs/architecture.md) for why the payload layer is
necessary: Harbor copies only `instruction.md`, `tests/` and `solution/` into a
container, so a `CLAUDE.md` placed next to `task.toml` never reaches the agent.

---

## Your first experiment

The default configuration uses `demo-kit`, a tiny methodology vendored in this
repository, so everything below runs immediately after `./bootstrap.sh` with no
access to any private toolkit.

```bash
# 0. Work on a branch: an experiment's results belong with the run that made them
git switch -c experiment/my-first-run

# 1. What could run, and which tasks can discriminate
hmb catalogue --suite quick --ids-only

# 2. Scaffold a scenario: a config and a pinned task set, both named after it
hmb experiment new my-run --toolkit demo-kit --agent claude-code --suite quick --limit 3

# 3. Build the variants, check them on the host, prove them in the container
hmb generate  --config config/experiments.my-run.yaml --tasks-file config/tasks-my-run.txt --force
hmb validate  --config config/experiments.my-run.yaml --tasks-file config/tasks-my-run.txt
hmb preflight --config config/experiments.my-run.yaml --tasks-file config/tasks-my-run.txt

# 4. Run the matrix (re-runs the gate; --dry-run prints the plan and spends nothing)
./scripts/run-pilot-experiment.sh --config config/experiments.my-run.yaml \
    --tasks-file config/tasks-my-run.txt --job-prefix my-run --attempts 1 --dry-run

# 5. Read the results, then analyse them properly
hmb report --pattern "my-run-*" --md-out results/my-run_report.md --json-out results/my-run_summary.json
hmb analysis init my-run --pattern "my-run-*"
```

Step 3 is the one that matters. It builds every image, probes each container
from the inside, and fails closed:

```text
preflight sqlite-db-truncate ...
  ok    baseline: workdir=/app markers=- skills=0 payload_files=0
  ok    demo-kit: workdir=/app markers=CLAUDE.md,AGENTS.md skills=1 payload_files=4
preflight passed for 1 tasks
```

To measure your own methodology instead, add it to
[`config/sources.yaml`](config/sources.yaml) with its repository URL and a commit
SHA, run `hmb setup`, and name it with `--toolkit`. See
[docs/setup.md](docs/setup.md#6-adding-your-own-toolkit).

---

## What it costs, and what to expect

A trial is one (task × condition × attempt). Multiply: `tasks × cells ×
attempts`. A measured example — 16 hard programming tasks × 3 conditions × 1
attempt with Claude Code — was 48 trials, $75 and about 12 hours of serial
wall-clock.

Two lessons from that run, both in [docs/tasks.md](docs/tasks.md#1-choosing-tasks-that-can-discriminate)
and worth knowing before you spend anything:

- **A task every condition passes carries no information** about the comparison
  and still costs a full trial. In that run 11 of 16 tasks were like that, which
  consumed 60 % of the budget and left an effective sample size of 2–5.
- **Cost separates conditions long before outcome does.** Methodology overhead is
  a continuous per-trial quantity, so it is measurable at sample sizes where a
  rare binary outcome is not.

---

## Prerequisites

`./bootstrap.sh` installs what it can and `hmb doctor` reports the rest:

- Linux or macOS, `git` and `curl`
- **Docker** with a running daemon
- **uv** (installed by the bootstrap if missing) and Python 3.12+
- The agent CLIs you intend to benchmark — `claude`, `codex`
- Roughly 20 GB of free disk for task images

---

## Development

```bash
uv sync                  # runtime + dev dependencies
uv run pytest            # the test suite
uv sync --group analysis  # pandas, matplotlib, scipy, jupyterlab, for notebooks
```

`CHANGELOG.md` records notable changes. Contributions should keep the invariants
in [docs/architecture.md](docs/architecture.md#6-invariants) intact — they are what
makes a result trustworthy, and each one has a test.
