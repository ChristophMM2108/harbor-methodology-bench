---
id: company/project_types/llm_nlp_app
version: "1.0"
applies_to: [llm_nlp_app]
depends_on: [company/baseline, company/layers/llm_providers, company/layers/web_framework, company/layers/testing]
---

# Project Type C: LLM / NLP Application

**Use when:** RAG, chatbots, agents, document processing, text generation,
document data extraction, semantic search.

## Technology Stack

LangChain + LlamaIndex + Anthropic/OpenAI SDK + ChromaDB/pgvector
+ Langfuse + NeMo Guardrails

## RULE-LNL-001: Directory Structure

```
llm-app/
├── app/api/routes/              # chat.py, documents.py, health.py
├── app/chains/                  # retrieval.py, summarization.py, conversation.py
├── app/prompts/                 # system.py, templates.py — EVERY change is a PR
├── app/vectorstore/             # embeddings.py, indexer.py, retriever.py
├── app/document_processing/     # loaders.py, chunkers.py, parsers.py
├── app/agents/tools/            # web_search.py, code_executor.py
├── app/memory/                  # conversation.py (state management)
├── app/services/                # llm_service.py (wraps SDK), cache_service.py
├── tests/, scripts/, docker-compose.yaml
```

## RULE-LNL-002: Chain Isolation

- `chains/` isolate LLM logic from API plumbing
- Never call LLM SDKs directly from routes
- Each chain is a composable, testable unit
- Chains accept structured input and return structured output

## RULE-LNL-003: Prompt Management

- All prompts centralized in `prompts/`
- Version-controlled: every template change is a PR
- Use Jinja2 or f-string templates with typed variables
- Track prompt versions in experiment metadata

## RULE-LNL-004: Provider Abstraction

- Wrap LLM provider SDKs in `services/llm_service.py`
- Unified interface for testability and provider-switching
- Never import SDK directly in routes or chains
- See `company/layers/llm_providers.md` for full pattern

## RULE-LNL-005: LLM Security (OWASP Top 10 LLM)

MANDATORY defenses:
- Input sanitization (prompt injection prevention)
- Output validation (never trust model output)
- Rate limiting (per-user, per-endpoint)
- Token budgets (prevent cost explosions)
- See `company/layers/security_compliance.md` for full list

## RULE-LNL-006: Response Caching

- Cache with model version in key: `llm:{version}:{input_hash}`
- TTL based on content freshness requirements
- Invalidate on model version change

## RULE-LNL-007: Streaming

- Use SSE (`sse-starlette`) or WebSocket for streaming responses
- Include model version in stream metadata
- Handle client disconnects gracefully

## RULE-LNL-008: Document Processing

- Loaders: support PDF, DOCX, HTML, plain text at minimum
- Chunking: configurable strategy (fixed-size, semantic, recursive)
- Embeddings: batch for efficiency, cache for cost savings
- Vector store: ChromaDB for dev, pgvector for production

## Reference Repositories

- LangChain — LLM orchestration
- LlamaIndex — RAG pipelines
- Langfuse — LLM observability

**Companies:** Anthropic, OpenAI, Cohere, Notion, Dropbox
