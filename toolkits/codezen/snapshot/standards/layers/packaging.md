---
id: company/layers/packaging
version: "1.0"
applies_to: [all]
depends_on: [company/baseline]
tags: [implementation]
---

# Packaging & Environment Standards

## RULE-PK-001: Package Manager Selection

| Library | Best For | Our Decision |
|---------|----------|-------------|
| uv | Package mgmt, venvs, Python versions, lockfiles | DEFAULT for all projects |
| Poetry | Legacy codebases | Permitted (legacy only) |
| conda / mamba | CUDA, cuDNN, non-Python deps | Hybrid with uv |

uv: 10-100x faster than pip; single binary replaces pip+pipx+pyenv+venv.

## RULE-PK-002: pyproject.toml as Single Config

`pyproject.toml` is the single config file for all tools (PEP 621 + PEP 735).
Configure Ruff, mypy, pytest, and all other tools here — no separate config files.

## RULE-PK-003: Lockfile Discipline

- Always commit `uv.lock` (or `poetry.lock` for legacy)
- Use `uv sync --frozen` in CI/Docker for deterministic installs
- Separate dev dependencies: `uv sync --frozen --no-dev` for production

## RULE-PK-004: Python Version

- Python 3.11+ minimum for all new projects
- Pin exact Python version in `.python-version`
- Use `uv python install` for version management

## RULE-PK-005: Virtual Environment

- Always use virtual environments — never install globally
- `uv venv` creates environments 80x faster than `python -m venv`
- `.venv` in project root (convention)
- Add `.venv` to `.gitignore`
