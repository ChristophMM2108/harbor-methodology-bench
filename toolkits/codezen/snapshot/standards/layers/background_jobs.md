---
id: company/layers/background_jobs
version: "1.0"
applies_to: [api_backend, llm_nlp_app, genai_app]
depends_on: [company/baseline]
tags: [implementation]
---

# Background Jobs & Task Queue Standards

LLM inference, image generation, report building, and data pipeline steps
MUST run as background jobs. Never block the request-response cycle with heavy compute.

## RULE-BJ-001: Task Queue Selection

| Concern | Library | Our Decision |
|---------|---------|-------------|
| Task queue (greenfield) | Dramatiq + Redis/RabbitMQ | DEFAULT |
| Task queue (enterprise) | Celery + Redis/RabbitMQ | Permitted for complex workflows |
| Lightweight queue | RQ | Small internal tools only |
| Async lightweight | FastAPI BackgroundTasks | ONLY for <5s tasks |
| Job monitoring | Flower / Redis CLI | Required for production |
| Scheduling | APScheduler / Celery Beat | For periodic tasks |

## RULE-BJ-002: Queue Architecture for AI Workloads

| Queue Name | Priority | Workers | Use Cases |
|------------|----------|---------|-----------|
| high-priority | Urgent | 8 threads, prefork | Real-time chat, urgent predictions |
| default | Normal | 4 threads, prefork | Standard inference, embeddings |
| low-priority | Background | 2 threads | Reports, batch retraining |
| bulk | Deferred | 1 thread | Bulk imports, re-indexing |
| gpu | GPU-bound | 1 per GPU | LLM inference, image generation |

## RULE-BJ-003: GPU Worker Rules

- GPU-bound tasks use prefork pool (NOT gevent/eventlet) — CPU/GPU-bound, not I/O-bound
- Use `asyncio.to_thread()` in FastAPI endpoint to submit without blocking
- One worker per GPU to prevent memory contention
- Pre-load models at worker startup, not per-task

## RULE-BJ-004: Progress Tracking

- Emit progress via Redis Pub/Sub for long-running jobs
- Client subscribes via SSE endpoint
- Include: job_id, progress_pct, status, estimated_remaining
- Dramatiq's `store_results=True` for result retrieval

## RULE-BJ-005: Job Pattern

```python
# FastAPI endpoint — returns immediately
@router.post("/generate")
async def generate(body: GenerateRequest) -> JobResponse:
    job = generate_task.send(body.model_dump())
    return JobResponse(job_id=job.message_id, status="queued")

# Dramatiq worker — runs async
@dramatiq.actor(queue_name="gpu")
def generate_task(params: dict) -> dict:
    result = model.generate(**params)
    return {"output": result}
```
