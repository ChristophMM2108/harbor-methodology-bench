# Harbor Methodology Bench

A reproducible benchmarking framework for measuring coding and terminal agents (such as **Claude Code** and **OpenAI Codex CLI**) with and without project-level methodology toolkits (such as **SDD Agent Kit** and **DFG Harness**) inside isolated Harbor Docker containers.

The framework is **toolkit-agnostic**: it injects native frozen toolkit snapshots into standard benchmark tasks (from Terminal-Bench) while preserving native `AGENTS.md`, `CLAUDE.md`, skills, commands, and directory layouts without contaminating the source tasks or benchmark prompts.

---

## 1. Experiment Matrix & Model

The core experiment matrix evaluates agents across three methodology conditions:

| Agent | Baseline | Toolkit A (SDD) | Toolkit B (DFG) |
|---|:---:|:---:|:---:|
| **Claude Code** (`claude-sonnet-5`) | Cell 1 | Cell 2 | Cell 3 |
| **OpenAI Codex** (`gpt-5.6-terra`) | Cell 4 | Cell 5 | Cell 6 |

### Core Invariants

1. **Benchmark Integrity**: Original benchmark tasks from Terminal-Bench remain unmodified.
2. **Clean Baseline**: Baseline variants contain only the benchmark task (no methodology files or instructions).
3. **Frozen Snapshots**: Toolkits are pinned via immutable Git commit SHAs in `toolkits/<id>/` and copied directly from frozen snapshots.
4. **Collision Avoidance**: If a toolkit defines a top-level path already present in the benchmark task, that toolkit path is preserved under `.methodology-bench/toolkit-collisions/` rather than overwriting task code.
5. **Harbor Isolation**: Agents execute inside isolated Docker containers where credentials and environment variables are explicitly forwarded.

```text
                    ┌────────────────────────┐
                    │ Terminal-Bench Sources │
                    │ source-tasks/          │
                    └───────────┬────────────┘
                                │
                   ┌────────────┼────────────┐
                   ▼            ▼            ▼
               baseline        sdd          dfg
                   │      (frozen SDD) (frozen DFG)
                   │            │            │
                   └────────────┼────────────┘
                                │
                    generated Harbor Tasks
                    generated/<variant>/<task>/
                                │
                       ┌────────┴────────┐
                       ▼                 ▼
                  Claude Code        Codex CLI
                       │                 │
                       ▼                 ▼
                    results           results
                    jobs/             jobs/
```

---

## 2. Repository Architecture

```text
harbor-methodology-bench/
├── pyproject.toml              # Project dependencies & CLI entrypoints
├── TODO.md                     # Roadmap and milestone tracking
├── config/
│   ├── experiments.yaml        # Matrix definition (models, toolkits, repetitions)
│   ├── benchmark.env.example   # Environment template
│   └── local.env               # Host credentials forwarded to containers (git-ignored)
├── source-tasks/
│   └── terminal-bench/         # Source benchmark tasks with pinned metadata
├── toolkits/
│   ├── sdd/                    # SDD toolkit: SOURCE, GIT_SHA, BRANCH, snapshot/
│   └── dfg/                    # DFG toolkit: SOURCE, GIT_SHA, BRANCH, snapshot/
├── generated/
│   ├── baseline/               # Clean benchmark tasks
│   ├── sdd/                    # Benchmark tasks + SDD toolkit snapshot
│   └── dfg/                    # Benchmark tasks + DFG toolkit snapshot
├── jobs/                       # Raw Harbor execution outputs and result.json files
├── results/                    # Aggregated reports, summaries, and telemetry
├── scripts/
│   ├── freeze-kits.sh          # Verify frozen snapshots and immutable SHA metadata
│   ├── generate-variants.sh    # Generate baseline, SDD, and DFG task variants
│   ├── validate-variants.sh    # Strict isolation and collision validation
│   ├── run-smoke-plan.sh       # Print dry-run Harbor execution commands
│   ├── run-smoke-experiment.sh # Execute the 6-cell smoke matrix
│   ├── run-pilot-experiment.sh # Execute the 30-trial pilot matrix
│   └── report.py               # Results aggregator & report generator
├── src/
│   └── harbor_methodology_bench/
│       ├── cli.py              # CLI entry point (harbor-methodology-bench)
│       ├── config.py           # Experiment configuration parser
│       ├── inject.py           # Toolkit snapshot injector & collision handler
│       ├── manifest.py         # Per-task variant manifest generator
│       ├── source.py           # Task source discovery
│       └── validate.py         # Variant validator and isolation verifier
└── tests/
    └── test_variants.py        # Automated test suite
```

---

## 3. Prerequisites & Credentials

### Host Requirements

- **Linux / macOS**
- **Docker** (active daemon, healthy network bridge)
- **Python 3.12+** & **uv** (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Harbor** CLI (`uv tool install harbor` or equivalent)
- **Claude Code** (`claude` CLI)
- **OpenAI Codex** (`codex` CLI)

Verify tools on host:
```bash
docker run --rm hello-world
uv run pytest
claude --version
codex --version
```

### Credentials Setup (`config/local.env`)

Harbor executes agents in isolated Docker containers. To enable CLI authentication inside containers without exposing API keys:

1. Generate your Claude setup token:
   ```bash
   claude setup-token
   ```
2. Create `config/local.env` (kept strictly git-ignored):
   ```bash
   CLAUDE_FORCE_OAUTH=1
   CLAUDE_CODE_OAUTH_TOKEN="<your-single-line-token-here>"
   CODEX_FORCE_AUTH_JSON=1
   ```
3. Set secure file permissions:
   ```bash
   chmod 700 config
   chmod 600 config/local.env
   ```

---

## 4. Smoke Experiment (1 Task × 6 Cells)

The smoke experiment validates that all 6 cells run end-to-end, credentials forward properly, containers start up, and verifiers output rewards.

```bash
# 1. Generate 1 task variant
./scripts/generate-variants.sh --limit 1 --force

# 2. Validate isolation
./scripts/validate-variants.sh --limit 1

# 3. Execute smoke matrix
./scripts/run-smoke-experiment.sh

# 4. View results
python3 scripts/report.py --pattern "smoke-*"
```

---

## 5. Pilot Experiment (5 Tasks × 6 Cells = 30 Trials)

The pilot experiment tests multi-task stability, variance, and pipeline robustness across 5 representative benchmark tasks:

### Step 1: Generate & Validate 5 Task Variants
```bash
./scripts/generate-variants.sh --limit 5 --force
./scripts/validate-variants.sh --limit 5
```

### Step 2: Run Pilot Matrix
Use the dedicated pilot execution runner:
```bash
# Optional: test in dry-run mode first
./scripts/run-pilot-experiment.sh --dry-run

# Run all 30 trials (supports --limit N, --force to re-run completed jobs)
./scripts/run-pilot-experiment.sh
```

### Step 3: Generate Summary & Detailed Telemetry Report
```bash
python3 scripts/report.py \
  --pattern "pilot-*" \
  --md-out results/pilot_report.md \
  --json-out results/pilot_summary.json
```

---

## 6. Configuring a Full Experiment

A full experiment scales the benchmark across more tasks and multiple repetitions to establish statistically significant comparisons.

### Step 1: Configure `config/experiments.yaml`
Edit `config/experiments.yaml` to specify experiment parameters:

```yaml
source_root: source-tasks/terminal-bench
generated_root: generated
repetitions: 3                     # Number of repetitions per cell

models:
  claude-code: claude-sonnet-5
  codex: gpt-5.6-terra

toolkits:
  - id: sdd
    snapshot: toolkits/sdd/snapshot
  - id: dfg
    snapshot: toolkits/dfg/snapshot

matrix:
  - {id: claude-baseline, agent: claude-code, toolkit: baseline}
  - {id: claude-sdd, agent: claude-code, toolkit: sdd}
  - {id: claude-dfg, agent: claude-code, toolkit: dfg}
  - {id: codex-baseline, agent: codex, toolkit: baseline}
  - {id: codex-sdd, agent: codex, toolkit: sdd}
  - {id: codex-dfg, agent: codex, toolkit: dfg}
```

### Step 2: Task Selection Strategies
You can select tasks from `source-tasks/terminal-bench/` using several strategies:

1. **All Available Tasks**:
   ```bash
   ./scripts/generate-variants.sh --force
   ./scripts/validate-variants.sh
   ```
2. **Fixed Task Limit** (e.g., 20 tasks):
   ```bash
   ./scripts/generate-variants.sh --limit 20 --force
   ./scripts/validate-variants.sh --limit 20
   ```
3. **Domain-Specific Subset**:
   Select tasks based on languages (Python, R, C/C++, Shell) or task categories by generating targeted tasks.

---

## 7. Handling Repetitions & Statistical Reliability

Because LLM agents have stochastic reasoning paths and tool choices, a single run per task cannot establish conclusive performance differences.

### Why Repetitions Matter
- **Confidence Intervals**: Measuring mean success rate $\pm$ standard error across $N \ge 3$ repetitions.
- **Flakiness Detection**: Separating deterministic tool failures from transient token/rate limits.
- **Cost & Latency Distribution**: Capturing median, p90, and outlier token expenditures.

### Execution with Multiple Repetitions
Harbor natively supports multiple attempts per trial via `-n <repetitions>` or `--n-attempts <repetitions>`:

```bash
harbor run \
  -p generated/sdd/adaptive-rejection-sampler \
  -a claude-code \
  -m claude-sonnet-5 \
  -n 3 \
  --env-file config/local.env \
  --job-name full-claude-sdd-adaptive-rejection-sampler
```

Harbor runs all 3 repetitions inside the designated job directory and records per-trial metrics (`trial_1`, `trial_2`, `trial_3`).

---

## 8. Results Reporting & Telemetry Aggregation

The aggregator script `scripts/report.py` handles multi-task, multi-repetition, and multi-job collections automatically:

### Aggregator Capabilities
- **Multi-Job Matching**: Matches jobs by glob pattern (`--pattern "full-*"` or `--pattern "*"`).
- **Per-Cell Metrics**:
  - Success Rate (%) and Mean Verifier Reward
  - Average Trial Duration (seconds)
  - Total and Average Token Consumption (input, output, cache read/write)
  - Cost in USD
- **Per-Task Breakdowns**: Inspect which specific tasks passed or failed under each methodology condition.
- **Exception Telemetry**: Highlights exact error causes (such as rate limits, non-zero exits, timeouts).

### Generating & Archiving Reports
```bash
# Generate full markdown comparison
python3 scripts/report.py --jobs-dir jobs/ --pattern "full-*" --md-out results/full_report.md

# Generate machine-readable JSON for downstream data analysis / plotting
python3 scripts/report.py --jobs-dir jobs/ --pattern "full-*" --json-out results/full_summary.json
```

---

## 9. Experiment Phases & Roadmap

| Phase | Description | Status |
|---|---|:---:|
| **Phase 1: Infrastructure** | Docker, uv, Harbor, Claude & Codex CLI validation | **Complete** |
| **Phase 2: Toolkit Freezing** | Pinned SDD and DFG snapshots with Git SHA verification | **Complete** |
| **Phase 3: Task Generation** | Task copier, snapshot injector, collision tracker | **Complete** |
| **Phase 4: Validation** | Strict isolation validator & automated tests | **Complete** |
| **Phase 5: Smoke Test** | 1 task (`adaptive-rejection-sampler`) × 6 cells × 1 rep | **Complete** |
| **Phase 6: Pilot Experiment** | 5 tasks × 6 cells × 1 rep (30 runs total) | **Ready** |
| **Phase 7: Full Experiment** | Pinned tasks × 6 cells × 3+ repetitions | **Documented** |
| **Phase 8: Deep Analysis** | Methodology adherence telemetry, token overhead vs gain | Planned |
