---
id: company/layers/testing
version: "1.0"
applies_to: [all]
depends_on: [company/baseline]
tags: [testing]
---

# Testing Standards

## RULE-TST-001: Framework & Coverage

| Layer | Library | Our Decision |
|-------|---------|-------------|
| Framework | pytest 9.x | ONLY framework |
| Coverage | pytest-cov | 80% overall, 90% serving, 85% data |
| Property testing | Hypothesis | DEFAULT for data invariants |
| API testing | httpx + TestClient | DEFAULT for FastAPI |
| Integration testing | Testcontainers-python | DEFAULT for sandboxed tests |
| Load testing | Locust | DEFAULT |
| ML behavioral | Custom (MFT, Invariance, Directional) | MANDATORY for all models |

## RULE-TST-002: Testing Pyramid

| Level | Tool | Speed | Volume |
|-------|------|-------|--------|
| Unit | pytest + hypothesis | Milliseconds | Highest |
| API integration | httpx + TestClient + Testcontainers | Seconds | High |
| E2E | Playwright (if frontend) | 10-30s each | Low |
| Load | Locust | Minutes | Few |

## RULE-TST-003: Integration Testing with Testcontainers

- Spin up real Postgres/Redis/Kafka per test session
- Auto-cleanup; zero test pollution
- Works identically on laptop and CI
- Catches bugs mocks miss: SQL errors, constraint violations, deadlocks

## RULE-TST-004: Test Organization

```
tests/
├── unit/           # Fast, no I/O, no containers
├── integration/    # Real dependencies via Testcontainers
├── e2e/            # Full system tests (Playwright for UI)
└── conftest.py     # Shared fixtures
```

## RULE-TST-005: Test Quality Rules

- Tests must be deterministic — no flaky tests in CI
- Use fixtures for setup/teardown, not setUp/tearDown methods
- One assertion concept per test (multiple asserts OK if same concept)
- Use `pytest.mark.parametrize` for data-driven tests
- Mark slow tests: `@pytest.mark.slow`

## RULE-TST-006: ML Behavioral Testing

Three mandatory categories (Ribeiro et al. CheckList):
1. **MFTs** (Minimum Functionality Tests): basic capability checks
2. **Invariance Tests**: output unchanged when input perturbed irrelevantly
3. **Directional Tests**: output changes predictably with meaningful perturbations

## RULE-TST-007: UI Testing with Playwright

- Playwright + pytest-playwright for all frontends
- Page Object Model: separate locators from test logic
- Session-scoped browser, function-scoped page for isolation
- Mark with `@pytest.mark.playwright`, exclude from default runs
- axe-playwright-python MANDATORY for customer-facing accessibility

### AI-Driven UI Testing via Playwright MCP

- **Default backend:** `microsoft/playwright-mcp` (Playwright MCP server) for all AI-driven UI testing
- The AI agent uses MCP to control a real browser, inspect the accessibility tree, and capture screenshots on failure
- **Self-heal loop:** agent triages failures against the spec, fixes the test or application code, and re-runs until green
- Page Object Model is required so self-healing changes stay localized to page objects, not scattered across tests
- No additional vendor cost beyond LLM tokens — Playwright MCP is free and open source
