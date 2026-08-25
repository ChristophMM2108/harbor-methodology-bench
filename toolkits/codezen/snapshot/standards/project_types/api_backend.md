---
id: company/project_types/api_backend
version: "1.0"
applies_to: [api_backend]
depends_on: [company/baseline, company/layers/web_framework, company/layers/validation, company/layers/data_access, company/layers/auth_security]
---

# Project Type A: API Backend Service

**Use when:** Any FastAPI-based backend, REST API, or modular monolith.

## Technology Stack

FastAPI + Pydantic v2 + SQLAlchemy + Alembic + psycopg3 + Redis
+ Dramatiq + structlog + OpenTelemetry + Sentry `[PAID - suggested]`

## RULE-API-001: Directory Structure

```
repo/
├── src/app/
│   ├── api/v1/endpoints/     # Thin route handlers
│   ├── schemas/              # Pydantic request/response models
│   ├── services/             # Business logic / orchestration
│   ├── domain/               # Entities (dataclasses), enums, exceptions
│   ├── repositories/         # Data access (SQLAlchemy queries)
│   ├── db/                   # ORM models, session factory, base
│   ├── clients/              # Redis, S3, external API wrappers
│   ├── workers/              # Dramatiq background tasks
│   ├── core/                 # config.py, logging.py, security.py
│   └── main.py
├── tests/ (unit/, integration/, e2e/)
├── alembic/
├── .github/workflows/
└── Dockerfile, docker-compose.yml, pyproject.toml
```

## RULE-API-002: Thin Route Handlers

Route handlers: validate → authorize → call service → return response.

```python
@router.post("/items", response_model=ItemResponse)
async def create_item(
    body: ItemCreate,
    user: User = Depends(require_role("editor")),
    service: ItemService = Depends(),
) -> ItemResponse:
    return await service.create(body, user)
```

## RULE-API-003: Service Layer

- Business logic lives in `services/` and `domain/`, never in routes or ORM models
- Services orchestrate repositories and domain logic
- Services are stateless and injectable via FastAPI Depends()

## RULE-API-004: Repository Pattern

- Repositories handle all data access
- No raw queries scattered in routes or services
- Return domain models, not ORM models
- Use SQLAlchemy `select()` style

## RULE-API-005: API Versioning

- Version from day one: `api/v1/`, `api/v2/`
- Breaking changes require new version
- Deprecation period before removing old versions

## RULE-API-006: Async Event Loop Safety

- Never block the event loop in async routes
- Use `asyncio.to_thread()` for sync operations
- Heavy compute goes to Dramatiq workers

## Reference Repositories

- Netflix Dispatch — production FastAPI monolith
- FastAPI Full-Stack Template — official starter
- FastAPI Best Practices — battle-tested conventions

**Companies:** Netflix, Microsoft, Uber, Cisco
