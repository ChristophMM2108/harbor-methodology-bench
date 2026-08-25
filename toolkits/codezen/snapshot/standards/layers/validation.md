---
id: company/layers/validation
version: "1.0"
applies_to: [api_backend, llm_nlp_app, genai_app]
depends_on: [company/baseline]
tags: [implementation, api]
---

# Validation & Data Modeling Standards

## RULE-VL-001: Boundary vs Domain Separation

Pydantic at the edges, lightweight classes inside.

| Library | Best For | Our Decision |
|---------|----------|-------------|
| Pydantic v2 | API payloads, configs, external input | DEFAULT at boundaries |
| dataclasses | Simple internal domain models | DEFAULT inside domain |
| attrs | Rich domain models with validators | Permitted when needed |
| msgspec | Performance-critical serialization | Permitted for hot paths |

**Rule: Never use Pydantic deep inside the domain layer. It creates framework coupling.**

## RULE-VL-002: Pydantic v2 Best Practices

- Use `model_validator` for cross-field validation
- Use `Field(...)` with descriptions for OpenAPI docs
- Prefer `Annotated[str, Field(...)]` over class-level Field
- Pydantic v2 uses Rust core — 5-50x faster than v1
- Always use `model_dump(mode="json")` for serialization

## RULE-VL-003: Domain Models

- Use `@dataclass` (stdlib) for simple value objects
- Use `attrs` when converters/validators are needed without Pydantic coupling
- Domain entities should have behavior (methods), not just data
- Keep domain models framework-independent

## RULE-VL-004: Input Validation Rules

- Validate all external input at API boundaries
- Use Pydantic's built-in validators for common patterns (email, URL, UUID)
- Custom validators for business rules (`@field_validator`)
- Return structured error responses with field-level detail
