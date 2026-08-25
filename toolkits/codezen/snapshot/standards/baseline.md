---
id: company/baseline
version: "1.0"
applies_to: [all]
depends_on: []
---

# Company Baseline Standards

Version 1.0 | March 2026 | Status: ENFORCED
For: All teams building AI solutions across ML, NLP, CV, Data, MLOps, and GenAI

## RULE-BL-001: Architecture — Modular Monolith First

Every project starts as a modular monolith. Extract a service only when you can
name the operational or organizational pain it solves (justify via ADR).

| Option | Use When |
|--------|----------|
| Modular monolith (DEFAULT) | Most teams; default start |
| Microservices | Multiple teams need independent scale/release |
| Monolith (simple) | Very small app or prototype |

Reference: Martin Fowler's MonolithFirst principle.

## RULE-BL-002: Naming Conventions

- Python: `snake_case` for functions, variables, modules; `PascalCase` for classes
- Constants: `UPPER_SNAKE_CASE`
- Private: single underscore prefix `_internal_method`
- Abbreviations: avoid unless domain-standard (e.g., `llm`, `nlp`, `api`)

## RULE-BL-003: Modularity

- One responsibility per module/class
- Explicit imports — no wildcard imports
- Circular imports are a design smell; refactor immediately
- Maximum module size: ~500 lines; split if larger

## RULE-BL-004: Error Handling

- Use domain-specific exception hierarchies, not bare `Exception`
- Never silently swallow exceptions (`except: pass`)
- Log errors with structured context before re-raising
- Use `from` for exception chaining: `raise AppError(...) from original`
- Validate at system boundaries; trust internal code

## RULE-BL-005: Logging & Observability

- Use `structlog` for structured JSON logging (NOT print, NOT Loguru in prod)
- Include correlation IDs via `contextvars` in every log entry
- Log at appropriate levels: ERROR for failures, WARNING for degradation, INFO for business events
- Never log secrets, tokens, or PII

## RULE-BL-006: Security Defaults

- OWASP Top 10 defenses are mandatory for all web-facing code
- Never hardcode secrets — use environment variables or secret managers
- TLS 1.3 for all external communication
- Input validation at every system boundary
- Principle of least privilege for all service accounts and users

## RULE-BL-007: Testing Expectations

- Minimum coverage: 80% overall, 90% for serving layer, 85% for data layer
- pytest is the ONLY test framework
- Tests must be deterministic — no flaky tests in CI
- Property-based testing (Hypothesis) for data invariants
- Integration tests use real dependencies via Testcontainers, not mocks

## RULE-BL-008: Documentation Requirements

- Google-style docstrings mandatory on all public APIs
- README.md at repo root with setup, usage, and architecture overview
- ADRs for all significant architectural decisions
- Model cards (Hugging Face format) for every deployed model

## RULE-BL-009: Dependency Hygiene

- `pyproject.toml` is the single config file (PEP 621 + PEP 735)
- **Pin exact versions** in `pyproject.toml` — never use `>=` or `^` ranges in production deps
- **Commit and enforce lockfiles** — `uv.lock` for Python, `package-lock.json` for Node
- **CI must use frozen installs** — `uv sync --frozen` (Python), `npm ci` (Node); never `pip install` or `npm install` in CI
- Run `pip-audit` and OSV-Scanner in CI for vulnerability scanning (both CVE and lockfile-aware)
- Node projects: set `ignore-scripts=true` and `save-exact=true` in `.npmrc`
- Prefer stdlib and well-maintained libraries over niche packages
- Audit new dependencies before adding: license, maintenance, security history, download count

## RULE-BL-010: Code Review & Quality

- All changes via pull request with at least one reviewer
- Ruff is the ONLY linter/formatter (replaces flake8, Black, isort, pylint)
- mypy strict mode mandatory in CI
- Maximum cyclomatic complexity: 10 per function (Ruff C901)
- No TODO/FIXME without a linked issue
