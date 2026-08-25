---
id: company/layers/web_framework
version: "1.0"
applies_to: [api_backend, llm_nlp_app, genai_app]
depends_on: [company/baseline]
tags: [implementation, api, architecture]
---

# Web Framework Standards

## RULE-WF-001: Framework Selection

| Library | Best For | Our Decision |
|---------|----------|-------------|
| FastAPI | API-first async services | DEFAULT for APIs |
| Django | Admin, full-stack, sessions | Permitted for full-stack |
| Flask | Minimal internal services | Small internal tools only |

FastAPI: 38% adoption (JetBrains 2025), 91k+ GitHub stars.
Companies: Microsoft, Uber, Netflix, Cisco, Explosion AI.

## RULE-WF-002: Application Factory Pattern

Use the application factory pattern for all FastAPI projects:

```python
def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)
    app.include_router(api_router, prefix="/api/v1")
    return app
```

## RULE-WF-003: Router Organization

- One router per domain (`users.py`, `orders.py`)
- Prefix matches domain name (`/api/v1/users`)
- Max 10 endpoints per router; split if larger
- Group related endpoints with tags for OpenAPI docs

## RULE-WF-004: Route Handler Pattern

Route handlers must be THIN: validate → authorize → call service → return response.
Business logic lives in `services/` and `domain/`, never in routes or ORM models.

```python
@router.post("/items", response_model=ItemResponse)
async def create_item(
    body: ItemCreate,
    user: User = Depends(require_role("editor")),
    service: ItemService = Depends(),
) -> ItemResponse:
    return await service.create(body, user)
```

## RULE-WF-005: API Versioning

Version your API from day one: `api/v1/`, `api/v2/`.
Use URL path versioning (not header-based).

## RULE-WF-006: Async Best Practices

- Never block the event loop in async routes
- Use `asyncio.to_thread()` for sync operations (DB drivers, file I/O)
- Use `httpx.AsyncClient` for outbound HTTP calls
- Heavy compute (LLM inference, image gen) goes to background workers

## Reference Repositories

- Netflix Dispatch — production FastAPI monolith
- FastAPI Full-Stack Template — official starter
- FastAPI Best Practices — battle-tested conventions
