---
id: company/layers/llm_providers
version: "1.0"
applies_to: [llm_nlp_app, genai_app]
depends_on: [company/baseline]
tags: [implementation, llm]
---

# LLM Provider SDK Standards

All SDK usage MUST go through a wrapper service (`services/llm_service.py`)
for testability, provider-switching, and cost tracking.
Never call SDKs directly from routes or chains.

## RULE-LLM-001: Provider Selection

| Provider | SDK | Key Models | Our Decision |
|----------|-----|-----------|-------------|
| Anthropic (Claude) | anthropic >=0.40 | claude-sonnet-4-20250514, claude-opus-4-20250514 | DEFAULT for reasoning-heavy tasks; best tool use |
| OpenAI | openai >=1.50 | gpt-4o, gpt-4o-mini, o3, o4-mini | DEFAULT for broad compatibility |
| Google (Gemini) | google-genai >=1.0 | gemini-2.5-flash, gemini-2.5-pro | DEFAULT for Google Cloud clients |

**CRITICAL:** The old `google-generativeai` package is DEPRECATED (EOL Nov 2025).
Use `google-genai` (unified SDK, GA May 2025).

## RULE-LLM-002: Provider Abstraction Pattern

- Wrapper service: `services/llm_service.py` wraps all provider SDKs
- Unified interface: `generate(system, messages, model, max_tokens)`
- Routes and chains call the service, never the SDK directly
- Provider config: model name, API key, provider in pydantic-settings
- Switching providers is a config change, not a code change

## RULE-LLM-003: Streaming

- All SDKs support async streaming — use async generators to yield tokens
- Return via SSE (`sse-starlette`) to the frontend
- Include `model_version` in stream metadata for cache keying

## RULE-LLM-004: Tool Use / Function Calling

- Define tools as Pydantic models
- Wrapper translates to provider-specific format
- Validate tool call results before returning to the model
- Log all tool invocations for observability

## RULE-LLM-005: Cost Tracking

- Log `input_tokens`, `output_tokens`, `model`, `provider` on every call via structlog
- Aggregate in Prometheus for cost dashboards
- Set per-request and per-user token budgets
- Alert on cost anomalies

## RULE-LLM-006: Fallback & Reliability

- Configure retry + fallback chains across providers
- Circuit breaker pattern for provider outages
- Cache responses: `llm:{version}:{input_hash}`

## References

- Anthropic SDK: https://github.com/anthropics/anthropic-sdk-python
- OpenAI SDK: https://github.com/openai/openai-python
- Google GenAI SDK: https://github.com/googleapis/python-genai
