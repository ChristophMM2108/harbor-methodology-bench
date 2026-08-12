# Harbor Methodology Bench

A reproducible framework for benchmarking coding/terminal agents with and without a project-level methodology or toolkit.

The repository is intentionally **toolkit-agnostic**. It can be used to compare any two repository-level toolkits with any supported agents, while preserving each toolkit's native `AGENTS.md`, `CLAUDE.md`, skills, commands, agents, documentation, and supporting files.

## 1. Experiment model

The fundamental experiment matrix is:

| Agent | Baseline | Toolkit A | Toolkit B |
|---|---:|---:|---:|
| Claude Code | ✓ | ✓ | ✓ |
| Codex CLI | ✓ | ✓ | ✓ |

For example:

```text
                 baseline       Toolkit A       Toolkit B
Claude Code          ✓              ✓                ✓
Codex CLI            ✓              ✓                ✓
```

The baseline contains only the original benchmark task.

Toolkit A and Toolkit B variants contain the complete frozen snapshots of their respective toolkits.

The benchmark task prompt should not be rewritten to tell the agent which methodology to use. Instead, the methodology is exposed through the repository files and directory structure available to the agent.

## 2. Design principles

### Experiment Workflow

```text
                    ┌──────────────────┐
                    │ Terminal-Bench   │
                    │ source tasks     │
                    └────────┬─────────┘
                             │
                  ┌──────────┼──────────┐
                  │          │          │
                  ▼          ▼          ▼
             baseline       sdd        dfg
                  │          │          │
                  │     frozen SDD   frozen DFG
                  │       snapshot     snapshot
                  │          │          │
                  └──────────┼──────────┘
                             │
                    generated Harbor
                         tasks
                             │
                    ┌────────┴────────┐
                    │                 │
               Claude Code        Codex CLI
                    │                 │
                    ▼                 ▼
                 results           results
```

### Keep benchmark tasks unchanged

The original benchmark task is the source of truth.

```text
original benchmark task
        |
        +---- baseline
        |
        +---- Toolkit A
        |
        +---- Toolkit B
```

Only the methodology/toolkit condition should intentionally differ.

### Freeze toolkit versions

Never benchmark against an unrecorded moving branch.

Record:

- repository source
- Git commit SHA
- branch/tag
- toolkit version, if available
- benchmark version
- Harbor version
- agent version
- model identifier

### Keep methodology variants isolated

A Toolkit A task must not accidentally contain Toolkit B files, and vice versa.

### Keep the baseline clean

The baseline must not contain methodology-specific:

```text
AGENTS.md
CLAUDE.md
.agents/
.claude/
skills/
commands/
agents/
documentation
manifests
```

unless those files were already part of the original benchmark task.

### Treat toolkits as experimental inputs

Do not modify source toolkit repositories during the experiment.

```text
source toolkit repository
        |
        v
frozen snapshot
        |
        v
generated Harbor task
```

---

## 3. Repository architecture

A recommended repository structure is:

```text
harbor-methodology-bench/
|
├── README.md
|
├── config/
│   ├── experiments.yaml
│   ├── benchmark.env.example
│   └── benchmark.env
|
├── kits/
│   ├── toolkit-a/
│   │   ├── SOURCE
│   │   ├── GIT_SHA
│   │   ├── VERSION
│   │   └── snapshot/
│   │
│   └── toolkit-b/
│       ├── SOURCE
│       ├── GIT_SHA
│       ├── VERSION
│       └── snapshot/
|
├── adapters/
│   └── harbor-methodology-bench/
|
├── datasets/
│   └── benchmark-source/
|
├── generated/
│   ├── baseline/
│   ├── toolkit-a/
│   └── toolkit-b/
|
├── experiments/
│   ├── smoke/
│   ├── pilot/
│   └── full/
|
├── results/
│   ├── raw/
│   ├── normalized/
│   ├── artifacts/
│   └── reports/
|
└── scripts/
    ├── doctor.sh
    ├── freeze-kits.sh
    ├── generate-variants.sh
    ├── run-experiment.sh
    ├── collect-results.sh
    └── report.py
```

`toolkit-a` and `toolkit-b` are placeholders. Replace them with neutral names appropriate to the experiment, for example:

```text
kits/sdd/
kits/dfg/
```

or:

```text
kits/methodology-a/
kits/methodology-b/
```

The benchmark infrastructure itself should not hard-code a particular toolkit name.

---

## 4. Toolkit contract

A toolkit is treated as a repository-level capability package.

It may contain:

```text
Toolkit
├── AGENTS.md
├── CLAUDE.md
├── skills/
├── commands/
├── agents/
├── documentation/
└── metadata/
```

Not every toolkit needs every category.

**Preserve the toolkit's native structure.**

If Toolkit A uses:

```text
.agents/skills/
```

do not rename it to:

```text
skills/
```

If Toolkit B uses:

```text
.claude/skills/
```

preserve that structure as well.

The benchmark should test the toolkit as it is actually used.

---

## 5. `AGENTS.md` and `CLAUDE.md`

The framework supports both instruction mechanisms.

A toolkit may provide different files:

```text
AGENTS.md
CLAUDE.md
```

Do not assume they are identical.

Preserve the actual files supplied by the toolkit.

For example:

### Claude Code

The agent should encounter the toolkit's:

```text
CLAUDE.md
```

and its Claude-specific resources.

### Codex CLI

The agent should encounter:

```text
AGENTS.md
```

and the toolkit's Codex-compatible resources.

This is intentional: the benchmark measures the toolkit's real integration with each agent rather than forcing an artificial common instruction file.

---

## 6. Source toolkit repositories

A toolkit can be supplied from a local repository such as:

```text
${HOME}/GitRepos/my-toolkit
```

or another reproducible source.

Preferred workflow:

```bash
git clone <toolkit-repository>
git -C <toolkit-directory> rev-parse HEAD
```

For formal experiments, record the selected commit.

If the toolkit has local modifications, create and record a commit before benchmarking.

---

## 7. Git branching

Branches are useful for developing independent experiments, but **branches should not select the toolkit**.

Recommended:

```text
main
 |
 +-- experiment/<name>
```

For example:

```bash
git fetch --all
git checkout main
git pull
git checkout -b experiment/methodology-comparison
```

The experiment branch can contain:

- benchmark configuration
- adapter implementation
- analysis code
- documentation
- toolkit references
- frozen version metadata

Toolkit selection belongs in the experiment configuration.

A colleague can therefore compare multiple toolkits in one experiment branch.

---

## 8. Local configuration

Create:

```text
config/benchmark.env.example
```

with generic values such as:

```bash
BENCHMARK_ROOT="${HOME}/GitRepos/harbor-methodology-bench"

TOOLKIT_A_NAME="methodology-a"
TOOLKIT_A_SOURCE="${HOME}/GitRepos/methodology-a"

TOOLKIT_B_NAME="methodology-b"
TOOLKIT_B_SOURCE="${HOME}/GitRepos/methodology-b"

DATASET_SOURCE="${HOME}/GitRepos/benchmark-source"

RESULTS_DIR="results"
GENERATED_DIR="generated"
```

Copy it locally:

```bash
cp config/benchmark.env.example config/benchmark.env
```

Then edit the paths and names.

Do not commit machine-specific paths or credentials.

---

## 9. Freezing toolkit versions

A generic freezing script should record:

```bash
git -C "$TOOLKIT_A_SOURCE" rev-parse HEAD
git -C "$TOOLKIT_B_SOURCE" rev-parse HEAD
```

and copy the selected repositories into:

```text
kits/toolkit-a/snapshot/
kits/toolkit-b/snapshot/
```

Each toolkit should have:

```text
SOURCE
GIT_SHA
BRANCH
VERSION
snapshot/
```

The source repositories remain untouched.

---

## 10. Benchmark variants

Every benchmark task should produce three variants:

```text
generated/
├── baseline/
│   └── <task-id>/
├── toolkit-a/
│   └── <task-id>/
└── toolkit-b/
    └── <task-id>/
```

Conceptually:

```text
                 Original Task
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
       baseline   toolkit-a   toolkit-b
          |           |           |
          v           v           v
       Harbor      Harbor      Harbor
          |           |           |
          v           v           v
       Agent       Agent       Agent
```

Each generated directory must remain a valid Harbor task.

---

## 11. Baseline variant

The baseline should be a faithful copy of the original benchmark task.

Do not inject:

```text
AGENTS.md
CLAUDE.md
.agents/
.claude/
toolkit documentation
toolkit commands
toolkit agents
toolkit manifests
```

unless they were already part of the source benchmark.

---

## 12. Toolkit variants

Toolkit A:

```text
generated/toolkit-a/<task-id>/
```

receives the complete frozen Toolkit A snapshot while preserving its native paths.

Toolkit B follows the same rule:

```text
generated/toolkit-b/<task-id>/
```

receives the complete frozen Toolkit B snapshot.

Do not manually flatten or rename toolkit directories unless a documented toolkit-specific transformation is required.

---

## 13. Harbor execution

The generic execution model is:

```bash
harbor run   -p generated/<variant>/<task-id>   -a <agent>   -m <model>
```

For example:

```bash
harbor run   -p generated/toolkit-a/<task-id>   -a claude-code   -m <model>
```

and:

```bash
harbor run   -p generated/toolkit-a/<task-id>   -a codex   -m <model>
```

The runner should translate experiment configuration into Harbor invocations.

Do not manually modify generated tasks between runs.

---

## 14. Six fundamental experiment cells

The initial experiment consists of:

```text
Claude Code + baseline
Claude Code + Toolkit A
Claude Code + Toolkit B

Codex CLI + baseline
Codex CLI + Toolkit A
Codex CLI + Toolkit B
```

Represent these explicitly in:

```text
config/experiments.yaml
```

Example:

```yaml
matrix:
  - id: claude-baseline
    agent: claude
    toolkit: baseline

  - id: claude-toolkit-a
    agent: claude
    toolkit: toolkit-a

  - id: claude-toolkit-b
    agent: claude
    toolkit: toolkit-b

  - id: codex-baseline
    agent: codex
    toolkit: baseline

  - id: codex-toolkit-a
    agent: codex
    toolkit: toolkit-a

  - id: codex-toolkit-b
    agent: codex
    toolkit: toolkit-b
```

The exact Harbor agent identifiers should be confirmed against the installed Harbor version.

---

## 15. Repetitions

A pilot can use:

```yaml
repetitions: 1
```

A stronger experiment should normally use multiple repetitions:

```yaml
repetitions: 3
```

or more.

Use exactly the same task set across every cell.

---

## 16. Pilot experiment

Start with a small task set.

For example:

```text
5 tasks
×
6 experiment cells
×
1 repetition
=
30 runs
```

The pilot validates:

- task generation
- toolkit injection
- instruction discovery
- agent startup
- Harbor execution
- verifier behavior
- result collection
- artifact collection
- reproducibility metadata

Do not launch a large experiment until all six cells pass the pilot.

---

## 17. Toolkit discovery smoke test

Before measuring benchmark performance, run a dedicated discovery test.

Verify that:

1. the agent starts in the expected working directory;
2. `AGENTS.md` is available where expected;
3. `CLAUDE.md` is available where expected;
4. the expected toolkit skill directories exist;
5. the expected toolkit mechanisms are accessible;
6. the other toolkit is absent.

The discovery test should produce machine-readable artifacts such as:

```json
{
  "agent": "claude-code",
  "toolkit": "toolkit-a",
  "agents_md_visible": true,
  "claude_md_visible": true,
  "expected_skills_visible": true,
  "unexpected_toolkit_visible": false
}
```

This is a validation test, not a benchmark score.

---

## 18. Toolkit isolation checks

Before Harbor executes a generated task, validate:

```text
Baseline:
  no Toolkit A markers
  no Toolkit B markers

Toolkit A:
  Toolkit A markers present
  Toolkit B markers absent

Toolkit B:
  Toolkit B markers present
  Toolkit A markers absent
```

Use explicit marker lists or manifests rather than fuzzy assumptions.

The validator should fail closed: if the expected structure cannot be verified, do not run the benchmark.

---

## 19. Container/environment isolation

The agent should receive the methodology files inside the isolated Harbor task environment.

Preferred model:

```text
Host
 |
 | frozen toolkit
 | benchmark task
 |
 v
Harbor
 |
 v
isolated task environment
 |
 +-- benchmark repository
 +-- toolkit files
 +-- AGENTS.md
 +-- CLAUDE.md
 |
 v
Claude Code / Codex
 |
 v
tests / verifier
```

Do not rely on the developer's host checkout being visible to the container.

---

## 20. Results

Keep raw results separate from derived analysis:

```text
results/
├── raw/
├── normalized/
├── artifacts/
└── reports/
```

Never modify raw Harbor output during analysis.

A normalized result should contain at least:

```json
{
  "experiment_id": "claude-toolkit-a",
  "agent": "claude-code",
  "model": "<model>",
  "toolkit": "toolkit-a",
  "toolkit_sha": "<sha>",
  "task_id": "<task>",
  "benchmark": "<benchmark>",
  "benchmark_version": "<version>",
  "harbor_version": "<version>",
  "success": true,
  "duration_seconds": null,
  "tokens": null,
  "cost": null
}
```

Unavailable fields should remain `null`.

---

## 21. Primary metric

The primary metric is benchmark task success:

```text
success_rate =
successful_tasks / completed_tasks
```

Compare:

```text
Claude baseline
Claude Toolkit A
Claude Toolkit B

Codex baseline
Codex Toolkit A
Codex Toolkit B
```

---

## 22. Secondary metrics

Where available, collect:

- execution time
- token usage
- cost
- agent turns
- test failures
- retries
- verifier results
- termination reason
- generated artifacts

This allows conclusions such as:

```text
success improvement
        versus
additional cost / time / tokens
```

rather than using success alone.

---

## 23. Methodology compliance

Task success and methodology compliance are separate measurements.

Where possible, collect methodology-specific telemetry:

```text
expected instruction file discovered
expected skill discovered
expected workflow artifact created
verification performed
```

Do not force these behaviors into the benchmark prompt merely to make them measurable.

The benchmark should measure the toolkit's natural behavior.

---

## 24. Benchmark contamination

Do not add benchmark-specific instructions to the toolkit's:

```text
AGENTS.md
CLAUDE.md
```

such as:

```text
For Terminal-Bench tasks, always...
```

unless those instructions genuinely belong to the toolkit.

Otherwise the experiment would measure a benchmark-specific prompt modification rather than the toolkit.

---

## 25. Generalization

Core framework terminology should remain generic:

```text
benchmark
agent
toolkit
variant
task
experiment
model
```

Avoid hard-coding:

```text
sdd
dfg
claude
codex
terminal-bench
```

into core adapter logic.

These are configuration values.

For example:

```yaml
toolkits:
  - id: toolkit-a
    name: "Example Methodology"
    source: "${TOOLKIT_A_SOURCE}"

  - id: toolkit-b
    name: "Example Harness"
    source: "${TOOLKIT_B_SOURCE}"
```

Another colleague should be able to replace both toolkits without rewriting the framework.

---

## 26. Installation baseline

A Linux developer should have:

```text
Git
Git LFS
Python
uv
Docker
Harbor
Claude Code
Codex CLI
```

Verify:

```bash
git --version
python --version
uv --version
docker --version
harbor --version
claude --version
codex --version
```

Also verify:

```bash
docker run --rm hello-world
```

before running Harbor.

Installation instructions should be maintained in the setup documentation and should not depend on a developer-specific home directory.

---

## 27. Reproducibility manifest

Every full experiment should record:

```text
experiment ID
date/time
Git commit of harbor-methodology-bench
benchmark dataset/version
benchmark task IDs
Toolkit A source
Toolkit A SHA
Toolkit B source
Toolkit B SHA
Harbor version
Claude Code version
Codex version
model identifiers
experiment configuration
runtime information
```

Generate this automatically.

Do not rely on manually maintained notes.

---

## 28. Recommended colleague workflow

A colleague should be able to start from a clean clone:

```bash
git clone <harbor-methodology-bench>
cd harbor-methodology-bench

git checkout -b experiment/<name>

cp config/benchmark.env.example config/benchmark.env

# Edit toolkit and dataset paths.

./scripts/doctor.sh

./scripts/freeze-kits.sh

./scripts/generate-variants.sh --limit 5

./scripts/run-experiment.sh     --experiment pilot

./scripts/collect-results.sh

python scripts/report.py
```

The exact options become part of the benchmark runner's stable CLI once implemented.

---

## 29. Development phases

### Phase 1 — Infrastructure

Validate:

```text
Docker
Harbor
Claude Code
Codex CLI
```

### Phase 2 — Toolkit freezing

Validate:

```text
Toolkit A snapshot
Toolkit B snapshot
Git SHA recording
```

### Phase 3 — Task generation

Validate:

```text
original
baseline
Toolkit A
Toolkit B
```

### Phase 4 — Discovery

Validate that Claude Code and Codex see the correct toolkit.

### Phase 5 — One-task execution

Run:

```text
1 task × 6 cells × 1 repetition
```

### Phase 6 — Pilot

Run:

```text
5 tasks × 6 cells × 1 repetition
```

### Phase 7 — Repeated experiment

Run:

```text
N tasks × 6 cells × 3+ repetitions
```

### Phase 8 — Analysis

Calculate:

```text
success rate
time
tokens
cost
methodology compliance
```

---

## 30. What this repository is not

This repository does not:

- modify benchmark datasets permanently;
- modify toolkit source repositories;
- create benchmark-specific versions of toolkits;
- prescribe one particular methodology;
- assume only one agent;
- replace Harbor's verifier;
- treat methodology compliance as task success.

It is an experiment harness around Harbor.

---

## 31. Core experimental invariant

The most important invariant is:

> For a given benchmark task, the only intentional difference between baseline, Toolkit A, and Toolkit B is the methodology/toolkit condition.

The agent, model, benchmark task, verifier, and execution environment should otherwise be controlled as tightly as practical.

Likewise:

> For a given methodology condition, Claude Code and Codex should receive the same toolkit repository snapshot, while retaining the toolkit's native `AGENTS.md` / `CLAUDE.md` integration.

This makes the experiment interpretable.

---

## 32. Example instantiation

The first experiment can instantiate:

```text
Toolkit A = SDD Agent Kit
Toolkit B = DFG Harness
```

producing:

```text
Claude Code + no toolkit
Claude Code + SDD Agent Kit
Claude Code + DFG Harness

Codex CLI + no toolkit
Codex CLI + SDD Agent Kit
Codex CLI + DFG Harness
```

The benchmark infrastructure remains generic.

Another colleague can instead configure:

```text
Toolkit A = Methodology X
Toolkit B = Methodology Y
```

without changing the architecture.

---

## 33. Final validation checklist

Before interpreting results:

- [ ] benchmark task integrity verified
- [ ] Toolkit A Git SHA recorded
- [ ] Toolkit B Git SHA recorded
- [ ] baseline cleanliness verified
- [ ] Toolkit A isolation verified
- [ ] Toolkit B isolation verified
- [ ] Claude instruction discovery verified
- [ ] Codex instruction discovery verified
- [ ] expected skills visible
- [ ] unexpected skills absent
- [ ] Harbor verifier working
- [ ] result collection working
- [ ] reproducibility manifest generated

Only after these checks pass should the experiment be considered valid.

---

## Status

This repository is a general-purpose starting point for controlled Harbor-based methodology experiments.

The first concrete instantiation may use:

```text
Toolkit A = SDD Agent Kit
Toolkit B = DFG Harness
```

but the benchmark framework itself should remain independent of those names and structures.
