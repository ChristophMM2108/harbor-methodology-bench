# Harbor Methodology Bench — Results Report

> **VOID — superseded.** These trials ran before the toolkit reached the
> container; all three conditions were effectively the baseline. See TODO.md.


**Total Trials Collected**: 30
**Generated At**: 2026-08-13 22:36:33 UTC

## 1. Matrix Summary (By Agent & Methodology Condition)

| Agent | Model | Condition | Trials | Successes | Success Rate | Mean Reward | Avg Time (s) | Total Cost ($) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `claude-code` | `claude-sonnet-5` | **BASELINE** | 5 | 4 | 80.0% | 0.80 | 445.9s | $6.2624 |
| `claude-code` | `claude-sonnet-5` | **DFG** | 5 | 4 | 80.0% | 0.80 | 447.3s | $5.4119 |
| `claude-code` | `claude-sonnet-5` | **SDD** | 5 | 3 | 60.0% | 0.60 | 551.2s | $5.4358 |
| `codex` | `gpt-5.6-terra` | **BASELINE** | 5 | 0 | 0.0% | 0.00 | 99.4s | $0.0000 |
| `codex` | `gpt-5.6-terra` | **DFG** | 5 | 0 | 0.0% | 0.00 | 83.0s | $0.0000 |
| `codex` | `gpt-5.6-terra` | **SDD** | 5 | 0 | 0.0% | 0.00 | 89.0s | $0.0000 |

## 2. Per-Task Breakdown

| Task | Condition | Agent | Reward | Success | Duration | Exception |
|---|---|---|---:|:---:|---:|---|
| `adaptive-rejection-sampler` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 567.7s | - |
| `adaptive-rejection-sampler` | **dfg** | `claude-code` | 0.00 | ✗ FAIL | 664.0s | - |
| `adaptive-rejection-sampler` | **sdd** | `claude-code` | 0.00 | ✗ FAIL | 468.3s | - |
| `adaptive-rejection-sampler` | **baseline** | `codex` | 0.00 | ✗ FAIL | 204.9s | `ApiUsageLimitError` |
| `adaptive-rejection-sampler` | **dfg** | `codex` | 0.00 | ✗ FAIL | 114.1s | `ApiUsageLimitError` |
| `adaptive-rejection-sampler` | **sdd** | `codex` | 0.00 | ✗ FAIL | 119.1s | `ApiUsageLimitError` |
| `bn-fit-modify` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 252.7s | - |
| `bn-fit-modify` | **dfg** | `claude-code` | 1.00 | ✓ PASS | 221.6s | - |
| `bn-fit-modify` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 232.7s | - |
| `bn-fit-modify` | **baseline** | `codex` | 0.00 | ✗ FAIL | 76.9s | `ApiUsageLimitError` |
| `bn-fit-modify` | **dfg** | `codex` | 0.00 | ✗ FAIL | 87.7s | `ApiUsageLimitError` |
| `bn-fit-modify` | **sdd** | `codex` | 0.00 | ✗ FAIL | 107.7s | `ApiUsageLimitError` |
| `break-filter-js-from-html` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 782.6s | - |
| `break-filter-js-from-html` | **dfg** | `claude-code` | 1.00 | ✓ PASS | 678.4s | - |
| `break-filter-js-from-html` | **sdd** | `claude-code` | 0.00 | ✗ FAIL | 1271.6s | `AgentTimeoutError` |
| `break-filter-js-from-html` | **baseline** | `codex` | 0.00 | ✗ FAIL | 65.4s | `ApiUsageLimitError` |
| `break-filter-js-from-html` | **dfg** | `codex` | 0.00 | ✗ FAIL | 64.5s | `ApiUsageLimitError` |
| `break-filter-js-from-html` | **sdd** | `codex` | 0.00 | ✗ FAIL | 63.7s | `ApiUsageLimitError` |
| `build-cython-ext` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 417.7s | - |
| `build-cython-ext` | **dfg** | `claude-code` | 1.00 | ✓ PASS | 444.5s | - |
| `build-cython-ext` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 597.8s | - |
| `build-cython-ext` | **baseline** | `codex` | 0.00 | ✗ FAIL | 62.6s | `ApiUsageLimitError` |
| `build-cython-ext` | **dfg** | `codex` | 0.00 | ✗ FAIL | 61.7s | `ApiUsageLimitError` |
| `build-cython-ext` | **sdd** | `codex` | 0.00 | ✗ FAIL | 67.7s | `ApiUsageLimitError` |
| `build-pmars` | **baseline** | `claude-code` | 0.00 | ✗ FAIL | 209.0s | - |
| `build-pmars` | **dfg** | `claude-code` | 1.00 | ✓ PASS | 228.3s | - |
| `build-pmars` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 185.7s | - |
| `build-pmars` | **baseline** | `codex` | 0.00 | ✗ FAIL | 87.2s | `ApiUsageLimitError` |
| `build-pmars` | **dfg** | `codex` | 0.00 | ✗ FAIL | 87.0s | `ApiUsageLimitError` |
| `build-pmars` | **sdd** | `codex` | 0.00 | ✗ FAIL | 86.6s | `ApiUsageLimitError` |

## 3. Exceptions & Failures

| Job | Task | Agent | Exception Type | Details |
|---|---|---|---|---|
| `pilot-claude-sdd-break-filter-js-from-html` | `break-filter-js-from-html` | `claude-code` | `AgentTimeoutError` | Agent execution timed out after 1200.0 seconds |
| `pilot-codex-baseline-adaptive-rejection-sampler` | `adaptive-rejection-sampler` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-baseline-bn-fit-modify` | `bn-fit-modify` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-baseline-break-filter-js-from-html` | `break-filter-js-from-html` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-baseline-build-cython-ext` | `build-cython-ext` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-baseline-build-pmars` | `build-pmars` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-dfg-adaptive-rejection-sampler` | `adaptive-rejection-sampler` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-dfg-bn-fit-modify` | `bn-fit-modify` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-dfg-break-filter-js-from-html` | `break-filter-js-from-html` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-dfg-build-cython-ext` | `build-cython-ext` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-dfg-build-pmars` | `build-pmars` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-sdd-adaptive-rejection-sampler` | `adaptive-rejection-sampler` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-sdd-bn-fit-modify` | `bn-fit-modify` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-sdd-break-filter-js-from-html` | `break-filter-js-from-html` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-sdd-build-cython-ext` | `build-cython-ext` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |
| `pilot-codex-sdd-build-pmars` | `build-pmars` | `codex` | `ApiUsageLimitError` | Command failed (exit 1): if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; code |