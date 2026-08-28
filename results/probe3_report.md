# Harbor Methodology Bench — Results Report

**Total Trials Collected**: 12
**Generated At**: 2026-08-28 19:04:04 UTC

## 1. Matrix Summary (By Agent & Methodology Condition)

| Agent | Model | Condition | Trials | Successes | Success Rate | Mean Reward | Avg Time (s) | Total Cost ($) | Skills Available | Skills Named | Skills Invoked | Config Referenced |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `claude-code` | `claude-sonnet-5` | **BASELINE** | 3 | 2 | 66.7% | 0.67 | 1821.7s | $5.1253 | 0/3 | 0/3 | 0/3 | 0/3 |
| `claude-code` | `claude-sonnet-5` | **CODEZEN-FULL** | 3 | 2 | 66.7% | 0.67 | 1795.0s | $7.3472 | 3/3 | 2/3 | 1/3 | 2/3 |
| `claude-code` | `claude-sonnet-5` | **CODEZEN-VIABLE** | 3 | 3 | 100.0% | 1.00 | 1779.5s | $7.6770 | 3/3 | 2/3 | 0/3 | 3/3 |
| `claude-code` | `claude-sonnet-5` | **SDD** | 3 | 3 | 100.0% | 1.00 | 1627.5s | $4.7870 | 3/3 | 1/3 | 1/3 | 3/3 |

## 2. Per-Task Breakdown

| Task | Condition | Agent | Reward | Success | Duration | Exception |
|---|---|---|---:|:---:|---:|---|
| `circuit-fibsqrt` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 815.2s | - |
| `circuit-fibsqrt` | **codezen-full** | `claude-code` | 1.00 | ✓ PASS | 721.6s | - |
| `circuit-fibsqrt` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 1581.4s | - |
| `circuit-fibsqrt` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 872.4s | - |
| `fix-ocaml-gc` | **baseline** | `claude-code` | 1.00 | ✓ PASS | 2041.4s | - |
| `fix-ocaml-gc` | **codezen-full** | `claude-code` | 1.00 | ✓ PASS | 2050.6s | - |
| `fix-ocaml-gc` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 1823.9s | - |
| `fix-ocaml-gc` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 2241.4s | - |
| `schemelike-metacircular-eval` | **baseline** | `claude-code` | 0.00 | ✗ FAIL | 2608.7s | `AgentTimeoutError` |
| `schemelike-metacircular-eval` | **codezen-full** | `claude-code` | 0.00 | ✗ FAIL | 2612.7s | `AgentTimeoutError` |
| `schemelike-metacircular-eval` | **codezen-viable** | `claude-code` | 1.00 | ✓ PASS | 1933.1s | - |
| `schemelike-metacircular-eval` | **sdd** | `claude-code` | 1.00 | ✓ PASS | 1768.6s | - |

## 3. Methodology Adherence (toolkit conditions only)

| Task | Condition | Agent | Skills Available | Skills Named (text match) | Skills Invoked (Skill calls) | Skill Calls | Config Referenced |
|---|---|---|---:|---|---|---:|---|
| `circuit-fibsqrt` | **codezen-full** | `claude-code` | 11 | - | - | 0 | - |
| `circuit-fibsqrt` | **codezen-viable** | `claude-code` | 4 | code-review, noc-fix, noc-tdd, security-review | - | 0 | CLAUDE.md, AGENTS.md |
| `circuit-fibsqrt` | **sdd** | `claude-code` | 7 | - | - | 0 | CLAUDE.md, AGENTS.md |
| `fix-ocaml-gc` | **codezen-full** | `claude-code` | 11 | brainstorm, code-review, fix, noc-fix, noc-tdd, security-review, setup, tdd | code-review, noc-tdd | 2 | CLAUDE.md, AGENTS.md |
| `fix-ocaml-gc` | **codezen-viable** | `claude-code` | 4 | - | - | 0 | CLAUDE.md, AGENTS.md |
| `fix-ocaml-gc` | **sdd** | `claude-code` | 7 | - | - | 0 | CLAUDE.md, AGENTS.md |
| `schemelike-metacircular-eval` | **codezen-full** | `claude-code` | 11 | brainstorm, code-review, fix, noc-fix, noc-tdd, security-review, tdd | - | 0 | CLAUDE.md, AGENTS.md |
| `schemelike-metacircular-eval` | **codezen-viable** | `claude-code` | 4 | code-review, noc-fix, noc-tdd, security-review | - | 0 | CLAUDE.md, AGENTS.md |
| `schemelike-metacircular-eval` | **sdd** | `claude-code` | 7 | sdd-analyze, sdd-clarify, sdd-implement, sdd-plan, sdd-specify, sdd-tasks, sdd-verify | sdd-analyze, sdd-clarify, sdd-implement, sdd-plan, sdd-specify, sdd-tasks, sdd-verify | 7 | CLAUDE.md, AGENTS.md |

## 4. Exceptions & Failures

| Job | Task | Agent | Exception Type | Details |
|---|---|---|---|---|
| `probe3-claude-baseline-schemelike-metacircular-eval` | `schemelike-metacircular-eval` | `claude-code` | `AgentTimeoutError` | Agent execution timed out after 2400.0 seconds |
| `probe3-claude-codezen-full-schemelike-metacircular-eval` | `schemelike-metacircular-eval` | `claude-code` | `AgentTimeoutError` | Agent execution timed out after 2400.0 seconds |