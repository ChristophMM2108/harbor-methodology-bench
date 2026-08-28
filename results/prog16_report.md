# Harbor Methodology Bench — Results Report

**Total Trials Collected**: 48
**Generated At**: 2026-08-28 01:23:26 UTC

## 1. Matrix Summary (By Agent & Methodology Condition)

| Agent | Model | Condition | Trials | Successes | Success Rate | Mean Reward | Avg Time (s) | Total Cost ($) | Skills Available | Skills Used | Config Referenced |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `claude-code` | `claude-sonnet-5` | **BASELINE** | 16 | 13 | 81.2% | 0.81 | 970.9s | $19.9296 | 0/16 | 0/16 | 1/16 |
| `claude-code` | `claude-sonnet-5` | **CODEZEN-VIABLE** | 16 | 13 | 81.2% | 0.81 | 1219.3s | $30.6147 | 16/16 | 8/16 | 12/16 |
| `claude-code` | `claude-sonnet-5` | **SDD** | 16 | 12 | 75.0% | 0.75 | 1036.8s | $24.9426 | 16/16 | 2/16 | 11/16 |

## 2. Per-Task Breakdown

| Task | Condition | Agent | Reward | Success | Duration | Exception |
|---|---|---|---:|:---:|---:|---|
| `build-cython-ext` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 350.5s | - |
| `build-cython-ext` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 971.9s | `AgentTimeoutError` |
| `build-cython-ext` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 359.9s | - |
| `build-pmars` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 237.3s | - |
| `build-pmars` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 230.4s | - |
| `build-pmars` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 279.0s | - |
| `cancel-async-tasks` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 344.0s | - |
| `cancel-async-tasks` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 698.8s | - |
| `cancel-async-tasks` | **sdd** | `claude-code` | 0.00 | ✗ FAIL | 167.2s | - |
| `circuit-fibsqrt` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 1413.4s | - |
| `circuit-fibsqrt` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 820.1s | - |
| `circuit-fibsqrt` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 1272.6s | - |
| `custom-memory-heap-crash` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 790.2s | - |
| `custom-memory-heap-crash` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 738.6s | - |
| `custom-memory-heap-crash` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 662.5s | - |
| `fix-ocaml-gc` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 855.5s | - |
| `fix-ocaml-gc` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 1376.4s | - |
| `fix-ocaml-gc` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 1398.8s | - |
| `kv-store-grpc` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 125.8s | - |
| `kv-store-grpc` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 177.7s | - |
| `kv-store-grpc` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 120.2s | - |
| `make-mips-interpreter` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 1337.3s | - |
| `make-mips-interpreter` | **codezen-viable** | `claude-code` | 0.00 | ✗ FAIL | 1899.5s | `AgentTimeoutError` |
| `make-mips-interpreter` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 1057.9s | - |
| `path-tracing` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 1904.4s | - |
| `path-tracing` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 1920.3s | `AgentTimeoutError` |
| `path-tracing` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 1615.0s | - |
| `path-tracing-reverse` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 1618.4s | - |
| `path-tracing-reverse` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 951.3s | - |
| `path-tracing-reverse` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 1119.0s | - |
| `polyglot-rust-c` | **baseline** | `claude-code` | 0.00 | ✗ FAIL | 839.1s | - |
| `polyglot-rust-c` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 598.1s | - |
| `polyglot-rust-c` | **sdd** | `claude-code` | 0.00 | ✗ FAIL | 731.6s | - |
| `regex-chess` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 3275.9s | - |
| `regex-chess` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 3828.3s | `AgentTimeoutError` |
| `regex-chess` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 3734.9s | - |
| `schemelike-metacircular-eval` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 933.3s | - |
| `schemelike-metacircular-eval` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 2599.9s | - |
| `schemelike-metacircular-eval` | **sdd** | `claude-code` | 0.00 | ✗ FAIL | 2844.0s | `AgentTimeoutError` |
| `sqlite-db-truncate` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 178.0s | - |
| `sqlite-db-truncate` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 157.0s | - |
| `sqlite-db-truncate` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 148.5s | - |
| `torch-pipeline-parallelism` | **baseline** | `claude-code` | 0.00 | ✗ FAIL | 881.7s | - |
| `torch-pipeline-parallelism` | **codezen-viable** | `claude-code` | 0.00 | ✗ FAIL | 1845.2s | `VerifierTimeoutError` |
| `torch-pipeline-parallelism` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 526.8s | - |
| `torch-tensor-parallelism` | **baseline** | `claude-code` | 0.00 | ✗ FAIL | 450.0s | - |
| `torch-tensor-parallelism` | **codezen-viable** | `claude-code` | 0.00 | ✗ FAIL | 695.7s | - |
| `torch-tensor-parallelism` | **sdd** | `claude-code` | 0.00 | ✗ FAIL | 550.2s | - |

## 3. Methodology Adherence (toolkit conditions only)

| Task | Condition | Agent | Skills Available | Skills Invoked | Skill Tool Calls | Config Referenced |
|---|---|---|---:|---|---:|---|
| `build-cython-ext` | **codezen-viable** | `claude-code` | 4 | code-review, noc-fix, noc-tdd, security-review | 0 | CLAUDE.md, AGENTS.md |
| `build-cython-ext` | **sdd** | `claude-code` | 7 | - | 0 | CLAUDE.md, AGENTS.md |
| `build-pmars` | **codezen-viable** | `claude-code` | 4 | - | 0 | CLAUDE.md, AGENTS.md |
| `build-pmars` | **sdd** | `claude-code` | 7 | - | 0 | CLAUDE.md, AGENTS.md |
| `cancel-async-tasks` | **codezen-viable** | `claude-code` | 4 | code-review, noc-fix, noc-tdd, security-review | 0 | CLAUDE.md, AGENTS.md |
| `cancel-async-tasks` | **sdd** | `claude-code` | 7 | - | 0 | - |
| `circuit-fibsqrt` | **codezen-viable** | `claude-code` | 4 | - | 0 | - |
| `circuit-fibsqrt` | **sdd** | `claude-code` | 7 | - | 0 | CLAUDE.md, AGENTS.md |
| `custom-memory-heap-crash` | **codezen-viable** | `claude-code` | 4 | - | 0 | CLAUDE.md, AGENTS.md |
| `custom-memory-heap-crash` | **sdd** | `claude-code` | 7 | - | 0 | CLAUDE.md, AGENTS.md |
| `fix-ocaml-gc` | **codezen-viable** | `claude-code` | 4 | code-review, noc-fix, noc-tdd, security-review | 0 | CLAUDE.md, AGENTS.md |
| `fix-ocaml-gc` | **sdd** | `claude-code` | 7 | - | 0 | CLAUDE.md, AGENTS.md |
| `kv-store-grpc` | **codezen-viable** | `claude-code` | 4 | code-review, noc-fix, noc-tdd, security-review | 0 | CLAUDE.md, AGENTS.md |
| `kv-store-grpc` | **sdd** | `claude-code` | 7 | - | 0 | - |
| `make-mips-interpreter` | **codezen-viable** | `claude-code` | 4 | code-review, noc-fix, noc-tdd, security-review | 0 | CLAUDE.md, AGENTS.md |
| `make-mips-interpreter` | **sdd** | `claude-code` | 7 | - | 0 | CLAUDE.md, AGENTS.md |
| `path-tracing` | **codezen-viable** | `claude-code` | 4 | - | 0 | - |
| `path-tracing` | **sdd** | `claude-code` | 7 | - | 0 | - |
| `path-tracing-reverse` | **codezen-viable** | `claude-code` | 4 | - | 0 | CLAUDE.md, AGENTS.md |
| `path-tracing-reverse` | **sdd** | `claude-code` | 7 | - | 0 | CLAUDE.md, AGENTS.md |
| `polyglot-rust-c` | **codezen-viable** | `claude-code` | 4 | - | 0 | - |
| `polyglot-rust-c` | **sdd** | `claude-code` | 7 | - | 0 | - |
| `regex-chess` | **codezen-viable** | `claude-code` | 4 | - | 0 | CLAUDE.md, AGENTS.md |
| `regex-chess` | **sdd** | `claude-code` | 7 | - | 0 | CLAUDE.md, AGENTS.md |
| `schemelike-metacircular-eval` | **codezen-viable** | `claude-code` | 4 | code-review, noc-fix, noc-tdd, security-review | 0 | CLAUDE.md, AGENTS.md |
| `schemelike-metacircular-eval` | **sdd** | `claude-code` | 7 | sdd-analyze, sdd-clarify, sdd-implement, sdd-plan, sdd-specify, sdd-tasks, sdd-verify | 0 | CLAUDE.md, AGENTS.md |
| `sqlite-db-truncate` | **codezen-viable** | `claude-code` | 4 | - | 0 | - |
| `sqlite-db-truncate` | **sdd** | `claude-code` | 7 | - | 0 | - |
| `torch-pipeline-parallelism` | **codezen-viable** | `claude-code` | 4 | code-review, noc-fix, noc-tdd, security-review | 0 | CLAUDE.md, AGENTS.md |
| `torch-pipeline-parallelism` | **sdd** | `claude-code` | 7 | sdd-analyze, sdd-clarify, sdd-implement, sdd-plan, sdd-specify, sdd-tasks, sdd-verify | 0 | CLAUDE.md, AGENTS.md |
| `torch-tensor-parallelism` | **codezen-viable** | `claude-code` | 4 | code-review, noc-fix, noc-tdd, security-review | 0 | CLAUDE.md, AGENTS.md |
| `torch-tensor-parallelism` | **sdd** | `claude-code` | 7 | - | 0 | CLAUDE.md, AGENTS.md |

## 4. Exceptions & Failures

| Job | Task | Agent | Exception Type | Details |
|---|---|---|---|---|
| `prog16-claude-codezen-viable-build-cython-ext` | `build-cython-ext` | `claude-code` | `AgentTimeoutError` | Agent execution timed out after 900.0 seconds |
| `prog16-claude-codezen-viable-make-mips-interpreter` | `make-mips-interpreter` | `claude-code` | `AgentTimeoutError` | Agent execution timed out after 1800.0 seconds |
| `prog16-claude-codezen-viable-path-tracing` | `path-tracing` | `claude-code` | `AgentTimeoutError` | Agent execution timed out after 1800.0 seconds |
| `prog16-claude-codezen-viable-regex-chess` | `regex-chess` | `claude-code` | `AgentTimeoutError` | Agent execution timed out after 3600.0 seconds |
| `prog16-claude-codezen-viable-torch-pipeline-parallelism` | `torch-pipeline-parallelism` | `claude-code` | `VerifierTimeoutError` | Verifier execution timed out after 900.0 seconds |
| `prog16-claude-sdd-schemelike-metacircular-eval` | `schemelike-metacircular-eval` | `claude-code` | `AgentTimeoutError` | Agent execution timed out after 2400.0 seconds |