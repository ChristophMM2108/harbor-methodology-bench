---
id: company/layers/notifications
version: "1.0"
applies_to: [api_backend, llm_nlp_app, genai_app]
depends_on: [company/baseline, company/layers/background_jobs]
tags: [implementation]
---

# Notification System Standards

Notifications are always sent via background jobs, never synchronously.

## RULE-NT-001: Channel Selection

| Channel | Library | Our Decision |
|---------|---------|-------------|
| Email (transactional) | fastapi-mail + SMTP / Resend / SendGrid | DEFAULT |
| Email (templates) | Jinja2 + MJML | DEFAULT |
| Push (mobile) | firebase-admin (FCM) | DEFAULT for mobile |
| Push (web) | pywebpush | When FCM overhead not needed |
| In-app real-time | SSE via sse-starlette + Redis Pub/Sub | DEFAULT |
| In-app real-time | WebSocket (FastAPI native) | When bidirectional needed |
| Webhooks (outbound) | httpx + Dramatiq | DEFAULT for integrations |
| SMS | twilio / vonage | Critical alerts only |

## RULE-NT-002: Architecture Pattern

- **Event bus**: Redis Pub/Sub as internal event bus
- **Preferences**: Store user notification preferences in database
- **Templates**: All content in `templates/` (Jinja2); no hardcoded text
- **Idempotency**: Unique event ID per dispatch; deduplicate via Redis SET with NX

## RULE-NT-003: Email Standards

- Transactional via SMTP or managed service (Resend/SendGrid)
- Branded HTML templates using MJML for responsive rendering
- Plain-text fallback for all HTML emails
- Unsubscribe links mandatory for non-critical emails

## RULE-NT-004: Real-time Updates

- SSE (sse-starlette) for unidirectional server-to-client
- WebSocket only when client needs to send messages back
- Use Redis Pub/Sub as the backing event bus
- Include event type and timestamp in every message
