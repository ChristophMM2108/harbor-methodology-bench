---
id: company/design_cheatsheet
version: "1.0"
applies_to: [all]
depends_on: [company/baseline]
---

# System Design Cheatsheet

Reference for architecture and design decisions. Apply these patterns during planning and implementation. Each section covers the pattern, when to use it, common tradeoffs, and anti-patterns to avoid.

## Architectural Patterns

### Monolith vs Microservices

| Factor | Monolith first | Microservices |
|---|---|---|
| **When** | Default. Most projects. <10 devs. | Multiple teams need independent deploy/scale. |
| **Tradeoff** | Simple to deploy, debug, test. Hard to scale one piece. | Independent scaling. Complex to operate, debug, deploy. |
| **Decision rule** | Start monolith. Extract a service only when you can name the operational pain it solves. |
| **Anti-pattern** | Premature microservices. "We might need to scale" is not a reason. |

### Synchronous vs Asynchronous

| Factor | Sync (request/response) | Async (queue/events) |
|---|---|---|
| **When** | User is waiting for the response. Simple CRUD. | Work can be deferred. Long-running tasks. External API calls. |
| **Tradeoff** | Simple. Easy to debug. User waits. | Resilient. Decoupled. Hard to debug. Eventual consistency. |
| **Decision rule** | If the user needs the result now → sync. If it can happen in the background → async. |
| **Anti-pattern** | Sync calls to slow external APIs in request handlers. |

### Event-Driven vs Direct Calls

| Factor | Direct calls (API/RPC) | Event-driven (pub/sub) |
|---|---|---|
| **When** | Caller needs to know if it succeeded. | Multiple consumers. Caller doesn't care about downstream. |
| **Tradeoff** | Strong consistency. Tight coupling. | Loose coupling. Eventual consistency. Harder to trace. |
| **Decision rule** | Payments, auth → direct. Notifications, analytics, audit → events. |

## API Design

### REST Conventions

- Use nouns, not verbs: `/appointments`, not `/getAppointments`
- Plural resource names: `/patients/123`, not `/patient/123`
- HTTP methods carry the verb: GET (read), POST (create), PUT (full update), PATCH (partial), DELETE
- Status codes matter: 200 (ok), 201 (created), 400 (bad request), 401 (unauthorized), 403 (forbidden), 404 (not found), 409 (conflict), 422 (validation), 429 (rate limited), 500 (server error)
- Pagination: cursor-based for real-time data, offset-based for reports
- Versioning: URL path (`/v1/`) for breaking changes, not headers

### API Rate Limiting

- Always rate limit external-facing APIs
- Use token bucket algorithm (allows bursts, smooths over time)
- Return `429 Too Many Requests` with `Retry-After` header
- Rate limit per: API key, user, IP — in that order of preference
- Log rate limit hits — they signal either abuse or a client that needs a higher tier

## Data Design

### Database Selection

| Need | Choose | Why |
|---|---|---|
| Structured data, transactions, joins | PostgreSQL | ACID, mature, extensible (pgvector for embeddings) |
| Document store, flexible schema | MongoDB | Schema-less, good for prototypes. But loses joins/transactions. |
| Time-series metrics | TimescaleDB (on Postgres) | SQL + time-series optimizations |
| Full-text search | PostgreSQL (tsvector) or Elasticsearch | Postgres is simpler; ES for heavy search workloads |
| Vector search (embeddings) | pgvector or Milvus | pgvector if already on Postgres; Milvus for dedicated vector workload |
| Cache / session store | Redis | Fast, simple, expiry built-in |
| Message queue | Redis Streams or RabbitMQ | Redis if already using it; RabbitMQ for complex routing |

### Migrations

- Always use a migration tool (Alembic, Knex, Prisma). Never manual DDL.
- Migrations are forward-only in production. Never edit a deployed migration.
- Backwards-compatible changes: add columns (nullable or with default), add tables, add indexes
- Breaking changes: split into deploy + migrate + deploy (expand-contract pattern)

### Data Model Principles

- Every table has: `id` (UUID or auto-increment), `created_at`, `updated_at`
- Soft delete (`deleted_at`) for audit trails. Hard delete only for GDPR/compliance.
- Optimistic locking: `version` column on mutable tables. Prevents lost updates.
- Denormalize for read performance only after proving the join is the bottleneck. Not before.

## External Integrations

### Webhooks & Ingress

- No outbound network calls in webhook handlers. Validate → write → enqueue → return 200.
- Idempotent handlers. Use message ID as dedup key. Already processed → return 200.
- Store raw payload before processing. If parsing fails, you can replay.

### Outbound API Calls

- All outbound calls through a shared, rate-limited client
- Timeouts on every call: 15s reads, 30s writes
- Retry with exponential backoff: 1s → 2s → 4s. Max 3 attempts.
- Distinguish retriable (5xx, timeout) from permanent (4xx) errors
- Circuit breaker: after N consecutive failures, stop calling for M seconds
- Re-read before every write. Never trust cache for critical state.

## State Management

### State Machines

- All state in the database, never in memory. Workers are stateless.
- Log every state transition to an audit table.
- Define valid transitions explicitly. Reject invalid ones.
- Stuck state recovery: tasks in `processing` for >N minutes → reset to `pending`

### Locking

- Locks have expiry: `locked_until`, not just `locked_at`
- Check locks at every decision point, not just at the start
- Use database-level locks (SELECT FOR UPDATE) for critical sections
- Distributed locks (Redis): only for cross-service coordination

## Caching

### Cache Strategy

| Pattern | When | Tradeoff |
|---|---|---|
| Cache-aside (lazy) | Read-heavy, tolerates stale | Simple. Cache miss = slow first read. |
| Write-through | Need consistency between cache and DB | Every write hits both. Slower writes. |
| Write-behind | High write throughput | Risk of data loss if cache fails before flush. |
| TTL-based expiry | Most cases | Simple. Stale for TTL duration. |

### Cache Rules

- Cache keys must be deterministic and include version: `v1:user:123:profile`
- Always set TTL. No infinite caches. Production bugs from stale cache are hard to diagnose.
- Cache invalidation: prefer TTL over explicit invalidation. If you must invalidate, use pub/sub.
- Never cache auth tokens or session data with long TTL

## Security

### Authentication

| Method | When | Tradeoff |
|---|---|---|
| JWT | Stateless APIs, mobile | No server-side state. Can't revoke without blocklist. |
| OAuth2 + PKCE | Third-party login, SPAs | Industry standard. Complex to implement from scratch. |
| Session cookies | Traditional web apps | Simple. Requires server-side state. |
| API keys | Service-to-service, CLI tools | Simple. No user identity. Rotate regularly. |

### Security Defaults

- Hash passwords with Argon2id (not bcrypt, not SHA)
- Encrypt at rest (database, backups, object storage)
- TLS everywhere. No exceptions.
- Never log secrets, tokens, PII, or credentials
- Input validation at every boundary. Don't trust internal services either.
- CORS: explicit allowlist of origins. Never `*` in production.

## Observability

### The Three Pillars

| Pillar | Tool | What it tells you |
|---|---|---|
| Logs | structlog (JSON) | What happened, in order |
| Metrics | Prometheus + Grafana | How the system behaves over time |
| Traces | OpenTelemetry | How a request flows across services |

### Logging Rules

- Structured JSON logs. Never `print()` in production.
- Correlation ID in every log entry (propagated via context)
- Log levels: ERROR (action needed), WARN (degraded), INFO (business events), DEBUG (dev only)
- Never log PII, credentials, or full request/response bodies

## Testing

### Test Pyramid

| Layer | Ratio | Speed | What it catches |
|---|---|---|---|
| Unit | 70% | Fast | Logic errors, edge cases |
| Integration | 20% | Medium | DB queries, API contracts, auth flows |
| E2E | 10% | Slow | User flows, system integration |

### Testing Rules

- Tests must be deterministic. No flaky tests in CI.
- Test behavior, not implementation. Don't test private methods.
- Integration tests use a real database (not mocks). Mocks hide real bugs.
- E2E tests on critical paths only. Not every feature needs E2E.
- Coverage target: 80% overall, 90% for critical paths (auth, payments, data mutations)

## AI/ML Specific

### LLM Integration

- Wrap LLM provider in an abstraction layer. Never call SDK directly from routes.
- All prompts version-controlled. Every change is a PR.
- Implement fallback: if LLM fails/times out, graceful degradation (not a crash)
- Stream responses for real-time UX. Batch for background processing.
- Log: input tokens, output tokens, latency, model version, prompt version per request
- Rate limit LLM calls separately from other API calls
- Budget ceiling: alert when daily/monthly spend exceeds threshold

### RAG Patterns

- Chunk strategy matters more than embedding model. Test different chunk sizes.
- Hybrid search (keyword + semantic) outperforms either alone
- Re-rank results before sending to LLM. Don't trust raw similarity scores.
- Refresh embeddings on a schedule. Stale embeddings = stale answers.
- Include metadata (source, date, section) with each chunk for citations

### Model Evaluation

- Define metrics before building: accuracy, latency, cost per request, user satisfaction
- A/B test model changes. Don't ship without comparing to baseline.
- LLM-as-judge for automated evaluation, human eval for ground truth
- Track drift: if accuracy drops over time, embeddings or data may be stale

## Common Tradeoffs Cheat Card

| Decision | Option A | Option B | Rule of Thumb |
|---|---|---|---|
| Build vs buy | Custom code | Third-party service | Buy if it's not your core differentiator |
| SQL vs NoSQL | PostgreSQL | MongoDB | SQL unless you need schema flexibility for prototyping |
| REST vs GraphQL | REST | GraphQL | REST for services, GraphQL for complex frontends with many queries |
| Server vs serverless | Containers (ECS/K8s) | Lambda/Cloud Functions | Containers for sustained load, serverless for spiky/infrequent |
| Monorepo vs multi-repo | One repo | Repo per service | Monorepo until 3+ teams need independent releases |
| Polling vs webhooks | Poll on schedule | Receive push events | Webhooks if available. Poll as fallback with adaptive frequency. |
| Optimistic vs pessimistic locking | Version column check | SELECT FOR UPDATE | Optimistic for low contention. Pessimistic for critical sections. |
| Cache vs no cache | Redis/Memcached | Direct DB reads | Cache when read:write ratio >10:1 and stale is acceptable |
| TDD vs test-after | Write tests first | Write tests after code | TDD for complex logic. Test-after for UI/prototype/spike. |
