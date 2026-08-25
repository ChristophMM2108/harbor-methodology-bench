---
id: company/layers/frontend
version: "1.0"
applies_to: [api_backend, llm_nlp_app, genai_app]
depends_on: [company/baseline]
tags: [implementation, ux]
---

# Frontend & UI Standards

## RULE-FE-001: Tier-Based Selection

| Tier | Use Case | Stack | Our Decision |
|------|----------|-------|-------------|
| Internal / Admin | Dashboards, monitoring, admin panels | FastAPI + Jinja2 + HTMX + Tailwind | DEFAULT for internal UIs |
| Demo / Prototype | Client demos, PoC interfaces | Streamlit or Gradio | DEFAULT for demos |
| Customer-facing | Production web apps | React / Next.js (separate repo) | When justified via ADR |

**Rule:** Start with HTMX + Jinja2 for internal tools. Only reach for React when
complex client-side state management is genuinely required.

## RULE-FE-002: HTMX Stack (Tier 1)

| Library | Role | Version |
|---------|------|---------|
| Jinja2 | Server-side templating | >=3.1 (builtin FastAPI) |
| HTMX | Dynamic HTML without JS | >=2.0 (CDN, 10KB) |
| Tailwind CSS | Utility-first styling | >=3.4 (CDN or build) |
| Alpine.js | Lightweight JS reactivity | >=3.14 (CDN, 15KB) |
| fasthx | FastAPI + HTMX integration | >=0.16 |
| sse-starlette | Server-Sent Events | >=2.0 |

## RULE-FE-003: Full-Stack Python Structure

```
src/app/
├── api/v1/endpoints/     # JSON API endpoints
├── views/                # HTML-returning routes (Jinja2 + HTMX)
├── templates/
│   ├── base.html         # Layout with Tailwind + HTMX CDN
│   ├── partials/         # Reusable HTMX fragments
│   └── pages/            # Full page templates
├── static/               # CSS, JS, images
└── main.py
```

views/ returns HTML (TemplateResponse), api/ returns JSON.
Both share services/ and domain/.

## RULE-FE-004: Admin Panel

| Framework | Library | Our Decision |
|-----------|---------|-------------|
| FastAPI | SQLAdmin | DEFAULT — Django-admin-like CRUD |
| Django | Django Admin (built-in) | DEFAULT |
| Any | Streamlit | For data/ML admin dashboards |

Never build custom admin UI from scratch when SQLAdmin or Django Admin covers the need.
