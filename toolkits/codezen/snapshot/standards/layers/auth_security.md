---
id: company/layers/auth_security
version: "1.0"
applies_to: [api_backend, llm_nlp_app, genai_app]
depends_on: [company/baseline]
tags: [security, implementation]
---

# Authentication & Security Standards

## RULE-AS-001: Authentication Libraries

| Layer | Library | Our Decision |
|-------|---------|-------------|
| JWT tokens | PyJWT | DEFAULT for simple JWT |
| OAuth / OIDC | Authlib | DEFAULT for standards-heavy auth |
| Password hashing | pwdlib[argon2] or argon2-cffi | DEFAULT (Argon2id) |
| Password (legacy) | bcrypt | Compat only — 72-byte limit |
| App crypto | cryptography (pyca) | DEFAULT |
| API rate limiting | slowapi | DEFAULT for FastAPI |

## RULE-AS-002: Password Hashing

- Argon2id is the default (PHC winner, no 72-byte limit)
- Never use MD5, SHA-1, or plain SHA-256 for passwords
- bcrypt only for backward compatibility with existing hashes
- Configure memory cost, time cost, and parallelism per OWASP guidance

## RULE-AS-003: JWT Best Practices

- Short expiry (15min access, 7d refresh)
- Store refresh tokens in Redis with blacklist support
- Include `sub`, `exp`, `iat`, `jti` claims
- Verify signature, expiry, and audience on every request
- Use constant-time comparison (`hmac.compare_digest`) for token validation — never `==`
- Invalidate refresh tokens immediately on logout; invalidate all tokens on password change

## RULE-AS-004: Rate Limiting

- Configure per-endpoint by compute cost
- Stricter limits on auth endpoints (login, register, password reset)
- Use Redis backend for distributed rate limiting
- Return `Retry-After` header on 429 responses

## RULE-AS-005: User Management

| Concern | Library | Our Decision |
|---------|---------|-------------|
| User management | fastapi-users | DEFAULT for FastAPI |
| User management | Django auth + allauth | DEFAULT for Django |
| Session / token store | Redis | DEFAULT |
| Multi-tenancy | Custom middleware + schema-per-tenant | When isolation required |

**Session security (mandatory):**
- Regenerate session ID on login to prevent session fixation (CWE-384)
- Set session cookies with `HttpOnly`, `Secure`, and `SameSite=Lax` (or `Strict`) flags (CWE-614)
- Invalidate server-side session on logout — do not rely on cookie deletion alone
- Session lifetime: idle timeout ≤ 30 min for sensitive operations

**MFA (recommended for sensitive applications):**
- Offer TOTP (e.g. `pyotp`) for high-privilege users and admin roles
- Mandate MFA for any role with `admin:*` permissions

## RULE-AS-006: RBAC Implementation

- Database schema: Users ↔ Roles (M2M), Roles ↔ Permissions (M2M)
- Permissions as strings: `model:deploy`, `data:read`, `admin:manage_users`
- FastAPI dependency: `require_role('admin')` and `require_permission('model:deploy')`
- Principle of least privilege: minimal role for new users
- Audit all role changes in immutable audit log
- Enterprise: Permit.io / Auth0 FGA / Casbin for complex policies
