# Harbor Methodology Bench — Results Report

**Total Trials Collected**: 20
**Generated At**: 2026-08-20 10:55:25 UTC

## 1. Matrix Summary (By Agent & Methodology Condition)

| Agent | Model | Condition | Trials | Successes | Success Rate | Mean Reward | Avg Time (s) | Total Cost ($) | Skills Available | Skills Used | Config Referenced |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `claude-code` | `claude-sonnet-5` | **BASELINE** | 10 | 8 | 80.0% | 0.80 | 659.3s | $8.8538 | 0/10 | 0/10 | 0/10 |
| `claude-code` | `claude-sonnet-5` | **SDD** | 10 | 7 | 70.0% | 0.70 | 846.6s | $10.7135 | 10/10 | 2/10 | 4/10 |

## 2. Per-Task Breakdown

| Task | Condition | Agent | Reward | Success | Duration | Exception |
|---|---|---|---:|:---:|---:|---|
| `distribution-search` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 354.0s | - |
| `distribution-search` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 193.1s | - |
| `hf-model-inference` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 149.0s | - |
| `hf-model-inference` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 159.5s | - |
| `llm-inference-batching-scheduler` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 633.9s | - |
| `llm-inference-batching-scheduler` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 636.1s | - |
| `mcmc-sampling-stan` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 969.0s | - |
| `mcmc-sampling-stan` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 1100.5s | - |
| `mteb-leaderboard` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 1608.3s | - |
| `mteb-leaderboard` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 2976.7s | - |
| `mteb-retrieve` | **baseline** | `claude-code` | 0.00 | ✗ FAIL | 187.8s | - |
| `mteb-retrieve` | **sdd** | `claude-code` | 0.00 | ✗ FAIL | 216.5s | - |
| `query-optimize` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 1072.5s | - |
| `query-optimize` | **sdd** | `claude-code` | 0.00 | ✗ FAIL | 1140.5s | - |
| `reshard-c4-data` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 501.4s | - |
| `reshard-c4-data` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 1260.9s | - |
| `rstan-to-pystan` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 527.6s | - |
| `rstan-to-pystan` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 566.9s | - |
| `sam-cell-seg` | **baseline** | `claude-code` | 0.00 | ✗ FAIL | 589.2s | - |
| `sam-cell-seg` | **sdd** | `claude-code` | 0.00 | ✗ FAIL | 215.5s | - |

## 3. Methodology Adherence (toolkit conditions only)

| Task | Condition | Agent | Skills Available | Skills Invoked | Skill Tool Calls | Config Referenced |
|---|---|---|---:|---|---:|---|
| `distribution-search` | **sdd** | `claude-code` | 7 | - | 0 | - |
| `hf-model-inference` | **sdd** | `claude-code` | 7 | - | 0 | CLAUDE.md, AGENTS.md |
| `llm-inference-batching-scheduler` | **sdd** | `claude-code` | 7 | - | 0 | - |
| `mcmc-sampling-stan` | **sdd** | `claude-code` | 7 | - | 0 | - |
| `mteb-leaderboard` | **sdd** | `claude-code` | 7 | - | 0 | CLAUDE.md, AGENTS.md |
| `mteb-retrieve` | **sdd** | `claude-code` | 7 | - | 0 | - |
| `query-optimize` | **sdd** | `claude-code` | 7 | - | 0 | - |
| `reshard-c4-data` | **sdd** | `claude-code` | 7 | sdd-analyze, sdd-implement, sdd-plan, sdd-specify, sdd-tasks, sdd-verify | 0 | CLAUDE.md, AGENTS.md |
| `rstan-to-pystan` | **sdd** | `claude-code` | 7 | - | 0 | - |
| `sam-cell-seg` | **sdd** | `claude-code` | 7 | sdd-analyze, sdd-clarify, sdd-implement, sdd-plan, sdd-specify, sdd-tasks, sdd-verify | 0 | CLAUDE.md, AGENTS.md |