# Command reference

[← README](../README.md) · [setup](setup.md) · [architecture](architecture.md) · [experiments](experiments.md) · [tasks](tasks.md) · [analysis](analysis.md) · [troubleshooting](troubleshooting.md)

`hmb` is the CLI; `harbor-methodology-bench` is the same command under its long
name, and `uv run hmb ...` works without installing it. Every command accepts
`--config <path>` where it needs an experiment configuration, and resolves paths
against the repository root rather than your shell's working directory — set
`HMB_ROOT` to run from outside a checkout.

---

## Setup and environment

| Command | Purpose |
|---|---|
| `./bootstrap.sh [--no-uv-install] [--no-harbor] [--no-tool] [--no-fetch]` | install uv, the Harbor CLI and `hmb`, fetch every pinned source, then run `doctor` |
| `hmb doctor [--strict]` | check whether this machine can run an experiment; names the fix for each problem. Changes nothing |
| `hmb setup [--only ID] [--force] [--skip-credentials]` | materialise pinned sources and write the credentials template. Idempotent |
| `hmb sources` | list every pinned source and whether it is present at its pin |
| `hmb freeze-verify [--config PATH] [--sources PATH]` | verify each condition's snapshot and provenance files |

## Tasks

| Command | Purpose |
|---|---|
| `hmb catalogue [SELECTION] [--md-out F] [--json-out F] [--ids-only]` | classify tasks, preview a selection, write the catalogue |

## Building variants

| Command | Purpose |
|---|---|
| `hmb generate [SELECTION] [--force]` | build the task variants, one per condition |
| `hmb validate [SELECTION]` | host-side reproducibility and benchmark-integrity check |
| `hmb preflight [SELECTION] [--jobs N] [--max-probe-files N] [--build-timeout-sec N] [--run-timeout-sec N]` | build every image and assert the conditions from inside the containers; `--jobs` builds several at once (default 4) |

## Experiments

| Command | Purpose |
|---|---|
| `hmb experiment new NAME [--toolkit ID] [--agent ID] [SELECTION] [--force]` | scaffold `config/experiments.NAME.yaml` and `config/tasks-NAME.txt` |
| `hmb experiment list` | list the experiment configurations in this checkout |
| `hmb matrix-plan [--config PATH]` | print the configured cells as `id⇥variant⇥agent⇥model` |
| `hmb smoke-plan --task-id ID` | print the Harbor invocations without executing them |
| `hmb plan-job [SELECTION] [--job-prefix NAME] [--attempts N] [--n-concurrent N] [--n-concurrent-agents N] [--max-retries N] [--out-dir D]` | emit one Harbor job config per agent, spanning every condition in task-major order. Prints unless `--out-dir` is given; executes nothing |
| `./scripts/run-pilot-experiment.sh [SELECTION] [OPTIONS]` | run a task group across the matrix |
| `./scripts/run-smoke-experiment.sh [--task ID]` | the same runner pinned to one task, with the `smoke` job prefix |

## Results

| Command | Purpose |
|---|---|
| `hmb resume JOB_DIR [--recharged] [--filter TYPE] [--env-file PATH] [--dry-run]` | classify a job's failed trials, then re-run only those unrelated to the task |
| `hmb report [--jobs-dir D] [--pattern GLOB] [--md-out F] [--json-out F]` | aggregate trial results into a comparison table and a JSON summary; records each job's concurrency |
| `hmb analysis init NAME --pattern GLOB [--no-extract] [--force]` | scaffold an analysis notebook and derive its tables |
| `hmb analysis extract --pattern GLOB [--jobs-dir D] [--out-dir D] [--catalogue-json F]` | derive the per-trial, per-test, per-step and per-tool-call tables |

`SELECTION` is any combination of `--task ID`, `--tasks-file PATH`,
`--suite NAME`, `--category NAME`, `--difficulty LEVEL` and `--limit N`, as
described in [tasks.md](tasks.md#4-selecting-tasks).

## Harbor's own agents, useful without spending tokens

| Command | Purpose |
|---|---|
| `harbor run -p <task> -a oracle` | run a task's reference solution; must score 1.0 |
| `harbor run -p <task> -a nop` | do nothing; must score 0.0 |

Harbor's `-n` is `--n-concurrent`, not an attempt count; repetitions are `-k` /
`--n-attempts`.

---

## Repository layout

```text
harbor-methodology-bench/
├── bootstrap.sh                    # one-command setup
├── config/
│   ├── sources.yaml                # every pinned external input
│   ├── experiments.yaml            # the default experiment (vendored demo-kit)
│   ├── experiments.scenarios.yaml  # worked four-condition example
│   ├── benchmark.env.example       # environment template
│   └── local.env                   # host credentials (git-ignored, mode 600)
├── source-tasks/<suite>/           # benchmark tasks (fetched; git-ignored)
├── toolkits/<id>/                  # SOURCE, GIT_SHA, BRANCH, VERSION, snapshot/
│   └── demo-kit/                   # the one vendored toolkit, so a clone runs
├── generated/<condition>/<task>/   # generated Harbor tasks (git-ignored)
├── jobs/                           # raw Harbor execution output (git-ignored)
├── results/                        # reports, summaries, analyses (git-ignored)
├── docs/                           # this documentation set
├── scripts/
│   ├── run-pilot-experiment.sh     # the matrix runner
│   ├── run-smoke-experiment.sh     # one task, same runner
│   └── report.py                   # backwards-compatible shim for `hmb report`
├── src/harbor_methodology_bench/   # the package (see architecture.md § 8)
│   └── templates/                  # experiment, task-set and notebook scaffolds
├── tests/                          # the test suite
├── CHANGELOG.md
└── README.md
```

Every script resolves the repository root from its own location, so it can be
invoked by any path from any working directory. Path arguments and the paths
inside a configuration file are interpreted relative to the repository root, never
to your shell's current directory, so a command line means the same thing wherever
it is run. No script, configuration file or generated artefact contains an
absolute host path.
