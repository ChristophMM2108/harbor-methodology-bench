---
id: company/layers/code_quality
version: "1.0"
applies_to: [all]
depends_on: [company/baseline]
tags: [implementation]
---

# Code Quality Standards

## RULE-CQ-001: Linting & Formatting — Ruff Only

| Layer | Library | Our Decision |
|-------|---------|-------------|
| Linting + Formatting | Ruff | ONLY tool (replaces flake8, pylint, Black, isort) |
| Type check (IDE) | Pyright / Pylance | DEFAULT in VS Code |
| Type check (CI) | mypy | MANDATORY in CI |
| Runtime types | beartype | At pipeline boundaries |
| Security lint | Bandit (via Ruff S rules) | Integrated into Ruff |
| Docstring style | Google style (Ruff D rules) | MANDATORY on public APIs |
| Complexity limit | mccabe (via Ruff C901) | Max 10 per function |
| Notebook quality | nbstripout | MANDATORY pre-commit |

Ruff: Rust-powered, 800+ rules, 10-100x faster than alternatives.
Used by FastAPI, Pydantic, Hugging Face, Airflow, Pandas, SciPy.

## RULE-CQ-002: Ruff Configuration

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "S", "B", "A", "C4", "DTZ", "T20", "ICN", "PIE", "PT", "RSE", "RET", "SIM", "TID", "TCH", "ARG", "ERA", "PGH", "PL", "TRY", "FLY", "PERF", "RUF"]
```

## RULE-CQ-003: Type Checking

- mypy strict mode in CI: `disallow_untyped_defs = true`
- All public function signatures must have type annotations
- Use `from __future__ import annotations` for modern syntax
- Pyright in IDE for real-time feedback

## RULE-CQ-004: Pre-commit Hooks

- Ruff (lint + format)
- mypy (type check)
- nbstripout (notebook outputs)
- Gitleaks (secret detection)
