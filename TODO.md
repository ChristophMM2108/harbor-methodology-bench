# Harbor Methodology Bench — Action Plan & Next Steps

## Status Summary

- [x] **Phase 1 — Infrastructure & Environment Setup**
  - Docker daemon, bridge networking, and container execution verified.
  - Python 3.12+ and `uv` environment configured.
  - Harbor CLI installed and operational.
  - Container credential forwarding established via `config/local.env`.

- [x] **Phase 2 — Frozen Toolkit Snapshots**
  - SDD Agent Kit and DFG Harness snapshots committed with immutable `GIT_SHA`, `SOURCE`, `BRANCH`, and `VERSION` files.
  - `freeze-verify` command and automated pytest checks passing.

- [x] **Phase 3 & 4 — Task Generation & Strict Isolation Validator**
  - Generation logic preserves source benchmark tasks and injects complete frozen snapshots.
  - Path collisions safely redirected to `.methodology-bench/toolkit-collisions/`.
  - Validator enforces zero cross-contamination and baseline cleanliness.

- [x] **Phase 5 — Smoke Milestone (1 Task × 6 Cells × 1 Rep)**
  - Executed 6 cells for `adaptive-rejection-sampler`:
    - `claude-code` (`claude-sonnet-5`) × [`baseline`, `sdd`, `dfg`]
    - `codex` (`gpt-5.6-terra`) × [`baseline`, `sdd`, `dfg`]
  - All containers initialized, credentials resolved, agents launched, and verifiers executed.
  - Claude completed all 3 trials and reached verifier; Codex baseline completed with reward `1.0`.
  - *Note*: Codex trials hit `ApiUsageLimitError` due to ChatGPT account usage caps (to be renewed/expanded before larger runs).

---

## Next Steps: Phase 6 — Pilot Experiment

The objective of the Pilot Experiment is to validate reproducibility, stability, and metric collection across a multi-task dataset (5 tasks × 6 cells = 30 runs total) before launching full-scale repeated benchmarks.

### 1. Generate & Validate 5 Task Variants
Select the first 5 tasks from `source-tasks/terminal-bench`:
```bash
# Generate 5 tasks across baseline, sdd, and dfg
./scripts/generate-variants.sh --limit 5 --force

# Validate isolation and integrity across all 15 generated task directories
./scripts/validate-variants.sh --limit 5
```

### 2. Implement Pilot Execution Runner (`scripts/run-pilot-experiment.sh`)
Create a dedicated batch execution script that:
- Iterates across all 5 generated tasks for the 6 matrix cells.
- Sets structured job names: `pilot-<agent>-<toolkit>-<task_id>`.
- Passes `config/local.env` to each Harbor invocation.
- Cleans or archives prior runs to avoid resuming outdated configs.
- Supports resuming failed or pending cells gracefully.

### 3. Implement Results Aggregator & Reporter (`scripts/report.py`)
Build a report generator to aggregate outputs from `jobs/pilot-*`:
- **Primary Metric**:
  - Success rate (`mean reward`) per cell: Baseline vs. SDD vs. DFG for Claude Code and Codex.
- **Secondary Metrics**:
  - Total duration / execution time per trial.
  - Token consumption (input, output, cache read/write).
  - Cost in USD.
  - Error and exception classifications (`ApiUsageLimitError`, timeouts, non-zero exits).
- **Output Formats**:
  - Console summary table (via Rich / standard text).
  - Machine-readable JSON summary (`results/pilot_summary.json`).
  - Markdown comparison report (`results/pilot_report.md`).

### 4. Execute the Pilot Matrix
Run the pilot suite and inspect the generated telemetry:
```bash
./scripts/run-pilot-experiment.sh
python scripts/report.py --jobs-dir jobs/ --output results/pilot_report.md
```

---

## Future Milestones

### Phase 7 — Full Repeated Experiment
- Extend task suite to full Terminal-Bench set (or balanced 20–50 task subset).
- Configure multiple repetitions (`repetitions: 3+` in `config/experiments.yaml`) for statistical confidence.
- Parallelize independent trials where API rate limits allow.

### Phase 8 — Methodology Compliance & Deep Analysis
- Measure methodology adherence (e.g. did the agent inspect `CLAUDE.md`/`AGENTS.md`, invoke toolkit skills, or generate workflow artifacts?).
- Correlate performance gains with token overhead and latency tradeoffs.
