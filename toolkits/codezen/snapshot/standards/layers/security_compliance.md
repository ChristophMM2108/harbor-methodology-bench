---
id: company/layers/security_compliance
version: "1.0"
applies_to: [all]
depends_on: [company/baseline]
tags: [security, implementation]
---

# Security & Compliance Standards

## RULE-SC-001: Security Tooling

| Layer | Library | Our Decision |
|-------|---------|-------------|
| Dependency scanning | pip-audit | MANDATORY in CI |
| Container scanning | Trivy | MANDATORY on image build |
| Secret detection | Gitleaks | Pre-commit + CI |
| Model signing | Sigstore model-signing | MANDATORY for production models |
| PII detection | Microsoft Presidio | DEFAULT for PHI/PII |
| Supply chain | CycloneDX AI-BOM | For regulated clients |

## RULE-SC-002: OWASP Top 10 LLM Defenses

Mandatory for all LLM applications:
1. **Prompt injection**: Input sanitization, system prompt isolation
2. **Output validation**: Never trust model output; validate before action
3. **Training data poisoning**: Verify data provenance
4. **Model denial of service**: Rate limiting, token budgets
5. **Supply chain**: Verify model signatures, scan dependencies
6. **Sensitive information disclosure**: PII detection in outputs
7. **Insecure plugin design**: Validate tool call parameters
8. **Excessive agency**: Require human approval for destructive actions
9. **Overreliance**: Document limitations, add confidence scores
10. **Model theft**: Access controls, audit logging

## RULE-SC-003: Compliance Frameworks

| Framework | Scope | Key AI Requirements | Deadline |
|-----------|-------|-------------------|----------|
| SOC 2 Type II | Enterprise | Audit logs, RBAC, AES-256, TLS 1.3 | Ongoing |
| HIPAA | Healthcare | BAA, PHI encryption, de-identification | Pre-deployment |
| GDPR | EU data | Data minimization, right to erasure, DPIA | Pre-deployment |
| EU AI Act | All AI | Risk classification, model cards | Aug 2, 2026 |
| PCI-DSS | Payments | Segmentation, encryption, ASV scans | Pre-deployment |
| OWASP Top 10 LLM | LLM apps | Prompt injection, output validation | Pre-deployment |

## RULE-SC-004: Audit Trail

- Immutable audit log for all security-relevant actions
- Use structlog + OpenTelemetry for unified observability
- Log: who (user ID), what (action + resource), when (timestamp), from where (IP/service), outcome
- Retain logs per compliance requirements (SOC 2: 1 year minimum)
- **User context propagation (mandatory):** bind authenticated user identity to `contextvars` in
  request middleware so every logging call in the call stack can access it without explicit passing.
  Background/async tasks must copy context at dispatch time.
- **Audit mixin pattern:** models with compliance-critical mutations (`save`, `delete`, bulk updates)
  must use an audit mixin that writes an audit record automatically — do not rely on call-site logging alone.
- **Critical operations that require audit records:** authentication events, permission/role changes,
  data exports, PII access, financial transactions, admin actions, and any destructive operation.
- **Scope note:** application-level audit logging covers the app layer only. DB-level audit
  (pgaudit), infrastructure access (CloudTrail, VPN), and host-level events (auditd, Falco)
  must be addressed at the deployment level — they are outside CodeZen's scope.

## RULE-SC-005: Data Protection

- Encrypt at rest (AES-256) and in transit (TLS 1.3)
- Use Microsoft Presidio for PII/PHI detection and anonymization
- Data minimization: collect only what's needed
- Right to erasure: implement data deletion workflows
- Never log PII in application logs

## RULE-SC-006: CORS Policy

- Never use wildcard `Access-Control-Allow-Origin: *` on any authenticated endpoint
- Maintain an explicit allowlist of permitted origins; validate against it on every request
- `Access-Control-Allow-Credentials: true` only when strictly required; never combined with `*`
- Allowlist must be environment-specific (dev / staging / prod origins differ)

## RULE-SC-007: Secret Rotation & Key Expiry

- All API keys, signing keys, and service credentials must have a defined maximum lifetime
- Rotate secrets on a schedule: API keys ≤ 90 days, signing keys ≤ 1 year
- Use a secret manager (AWS Secrets Manager, HashiCorp Vault) — no long-lived secrets in env files
- Revoke and rotate immediately on any suspected exposure
- Systems must tolerate secret rotation without downtime (dual-key overlap period)

## RULE-SC-008: HTTP Security Headers

All HTTP responses from web-facing services must include:

| Header | Required Value |
|--------|---------------|
| `Content-Security-Policy` | Explicit policy; no `unsafe-inline` or `unsafe-eval` without justification |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `X-Frame-Options` | `DENY` (or use CSP `frame-ancestors 'none'`) |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | Restrict unused browser features |

Use framework middleware (e.g. `django-csp`, `secure` for FastAPI, `helmet` for Node) — do not
set headers manually per route.
