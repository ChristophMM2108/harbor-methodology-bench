---
id: company/layers/data_access
version: "1.0"
applies_to: [api_backend, llm_nlp_app, genai_app]
depends_on: [company/baseline]
tags: [implementation, data]
---

# Data Access Standards

## RULE-DA-001: ORM & Database Selection

| Layer | Library | Our Decision |
|-------|---------|-------------|
| ORM | SQLAlchemy 2.x | DEFAULT |
| ORM (simple) | SQLModel | Permitted for CRUD-heavy |
| Primary DB | PostgreSQL | DEFAULT for everything |
| DB Driver | psycopg 3 | DEFAULT |
| DB Driver (async) | asyncpg | Permitted for extreme async |
| Migrations | Alembic | MANDATORY |
| Document DB | PyMongo Async + MongoDB | When document model fits |
| Cache / KV | redis-py + Redis | DEFAULT |

## RULE-DA-002: PostgreSQL First

PostgreSQL handles OLTP, JSON documents (jsonb), full-text search,
vector similarity (pgvector), time-series (TimescaleDB), and geospatial (PostGIS).
Start with PostgreSQL; add other stores only when it demonstrably cannot meet requirements.

## RULE-DA-003: Repository Pattern

- All data access through repository classes in `repositories/`
- No raw SQL queries scattered in routes or services
- Repositories return domain models, not ORM models
- Use SQLAlchemy's `select()` style (not legacy Query API)

## RULE-DA-004: Migration Discipline

- Alembic migrations are mandatory for all schema changes
- Auto-generate migrations; review before applying
- Never edit a migration after it has been applied
- Include both upgrade and downgrade paths
- Run migrations in CI to catch schema drift

## RULE-DA-005: Connection Management

- Use async session factories with dependency injection
- Configure connection pooling (pool_size, max_overflow)
- Always use context managers for sessions
- Set statement timeouts to prevent runaway queries

## RULE-DA-006: Redis Usage

- redis-py is the default client (sync + async APIs)
- Use for caching, session storage, rate limiting, pub/sub
- Set TTLs on all cache keys — never cache indefinitely
- Use key prefixes for namespacing: `app:cache:`, `app:session:`
