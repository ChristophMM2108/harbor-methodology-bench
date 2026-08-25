---
id: company/project_types/genai_app
version: "1.0"
applies_to: [genai_app]
depends_on: [company/baseline, company/layers/llm_providers, company/layers/background_jobs]
---

# Project Type F: Generative AI Application

**Use when:** Image generation, multi-modal, AI agents with tools,
audio/video synthesis, creative AI applications.

## Technology Stack

Diffusers + CrewAI + Anthropic/OpenAI SDK + Dramatiq + WebSocket + S3

## RULE-GAI-001: Directory Structure

```
genai-app/
├── app/api/routes/              # generate.py, agents.py, gallery.py
├── app/agents/                  # base_agent.py + tools/ (composable)
├── app/generation/text/         # completions.py, structured_output.py
├── app/generation/image/        # diffusion.py, controlnet.py
├── app/generation/audio/        # tts.py
├── app/pipelines/               # text_to_image.py, multimodal.py
├── app/storage/                 # object_store.py (S3), vector_store.py
├── app/workers/                 # Dramatiq async tasks for heavy generation
├── models/checkpoints/, tests/, docker-compose.yaml
```

## RULE-GAI-002: Modality Separation

- Split `generation/` by modality: text, image, audio
- Never mix modalities in a single module
- Each modality has its own pipeline configuration
- Common interfaces for unified generation API

## RULE-GAI-003: Agent Architecture

- Agents use composable tools — each tool is a standalone function
- Tools have typed input/output schemas (Pydantic models)
- Tool results are validated before returning to the agent
- Log all tool invocations for observability and debugging

## RULE-GAI-004: Async Worker Pattern

- Heavy generation runs via Dramatiq workers, NOT in request handlers
- Return job ID immediately; client polls or subscribes via SSE/WebSocket
- Use GPU-dedicated queue (1 worker per GPU)
- Pre-load models at worker startup

## RULE-GAI-005: Streaming Progress

- Use WebSocket for streaming generation progress to frontend
- Include: step count, preview images, estimated time remaining
- SSE acceptable for simpler unidirectional progress
- Handle client disconnects to free GPU resources

## RULE-GAI-006: Model Weight Management

- Pre-download weights into Docker image OR mount as volumes
- Never download weights at request time (cold start)
- Version model weights alongside code
- Use Hugging Face Hub for weight management

## RULE-GAI-007: Storage

- S3-compatible storage for generated artifacts
- Use pre-signed URLs for client downloads
- Implement retention policies (auto-delete after N days)
- Track generation metadata alongside artifacts

## Reference Repositories

- Hugging Face Diffusers — image generation
- CrewAI — multi-agent orchestration
- Anthropic SDK — streaming + tool use

**Companies:** Midjourney, Stability AI, Jasper AI, Runway, Anthropic, OpenAI
