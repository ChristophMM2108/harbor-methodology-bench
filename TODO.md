# Harbor Methodology Bench — Action Plan & Next Steps

## Open: Re-run the Pilot

Every trial recorded before the payload layer landed ran against a container that
never received the toolkit — Harbor copies only `instruction.md`, `tests/` and
`solution/` into the environment, so files at the generated task root were inert.
All three conditions in `results/pilot_report.md` were therefore the baseline, and
those numbers must be discarded rather than compared.

```bash
./scripts/generate-variants.sh --limit 5 --force
./scripts/validate-variants.sh --limit 5
./scripts/preflight-variants.sh --limit 5
./scripts/run-pilot-experiment.sh --force
python3 scripts/report.py --pattern "pilot-*" \
  --md-out results/pilot_report.md --json-out results/pilot_summary.json
```

Also open, independent of the payload layer:

- **Codex authentication**: all 15 Codex trials failed with `ApiUsageLimitError`
  before reaching the task. Renew the account/quota before the next matrix run.
- **DFG snapshot completeness**: `toolkits/dfg/snapshot/CLAUDE.md` routes agents to
  `MASTER_CONTEXT_INDEX.md`, `DFG.md` and `PROVENANCE_INDEX.md`, none of which exist
  in the snapshot (they appear to be git-ignored in the source repository). The
  toolkit's own entry point is therefore a dead link inside the container.

## Open Design Question: Payload Breadth

A toolkit is deployed in full, natively, so a snapshot's non-methodology files land
in the agent's working directory alongside the benchmark task — `src/`, `tests/`,
`Makefile`, `pyproject.toml` and `uv.lock` for DFG; `docs/`, `tools/`, `kits/` and
`tests/` for SDD. Preflight confirms none of them collided with benchmark files in
the five pilot tasks, but they still change what the agent sees when it explores the
repository, which is a confound distinct from the methodology instructions.

Two defensible positions, to be settled before the full experiment:

1. **Deploy in full** (current behaviour): the condition under test is "the agent
   works in a repository configured with this toolkit", which is what the toolkit
   looks like in real use.
2. **Deploy the methodology surface only**: restrict the payload to `CLAUDE.md`,
   `AGENTS.md`, `.claude/`, `.agents/` and the toolkit's own kit directories. This
   isolates the instructions from unrelated repository content.

Option 2 needs a per-toolkit `include:` list in `config/experiments.yaml`; the
staging code already supports name-based filtering via `exclude:`.

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
  - Path collisions safely redirected to the in-container collision archive.
  - Validator enforces zero cross-contamination and baseline cleanliness.
  - Generated Dockerfile layer carries the toolkit into the container; `preflight`
    proves it from inside the container before any trial may run.

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
