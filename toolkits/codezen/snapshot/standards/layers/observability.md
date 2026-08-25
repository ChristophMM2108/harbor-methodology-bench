---
id: company/layers/observability
version: "1.0"
applies_to: [api_backend, llm_nlp_app, genai_app]
depends_on: [company/baseline]
tags: [implementation]
---

# Observability Standards

## RULE-OB-001: Observability Stack

| Layer | Library | Our Decision |
|-------|---------|-------------|
| Structured logging | structlog | DEFAULT (NOT Loguru in prod) |
| Tracing + metrics | OpenTelemetry Python SDK | DEFAULT (vendor-neutral) |
| Error monitoring | Sentry SDK | DEFAULT `[PAID - suggested]` |
| Dashboards | Grafana + Prometheus | `[INFRA - suggested]` |
| Log aggregation | Grafana Loki | `[INFRA - suggested]` |
| Config | pydantic-settings | DEFAULT |

## RULE-OB-002: Structured Logging with structlog

- Native JSON output for machine parsing
- OTel integration for log-trace correlation
- contextvars for correlation IDs across async handlers
- Processor pipeline for ML-specific enrichment (model version, experiment ID)
- Never use `print()` or `logging.basicConfig()` in production

## RULE-OB-003: OpenTelemetry Tracing

- Auto-instrument FastAPI, SQLAlchemy, Redis, httpx
- Manual spans for business-critical operations
- Propagate trace context across service boundaries
- Export to Tempo/Jaeger for distributed tracing

## RULE-OB-004: Metrics with Prometheus `[INFRA - suggested]`

- Counter: request count, error count, token usage
- Histogram: request latency, inference time
- Gauge: queue depth, active connections, model drift score
- Expose `/metrics` endpoint for Prometheus scraping

## RULE-OB-005: Error Monitoring `[PAID - suggested]`

Sentry SDK provides fastest path to actionable error triage.
Self-hosted Sentry is available as a free alternative.

- Capture unhandled exceptions automatically
- Add breadcrumbs for debugging context
- Configure sampling rate for high-volume services
- Set up alerts for new error patterns and regressions

## RULE-OB-006: Configuration Management

- pydantic-settings for typed, validated configuration
- Environment variables for runtime config
- python-dotenv for local development only (never in prod)
- Fail fast on missing required config at startup
