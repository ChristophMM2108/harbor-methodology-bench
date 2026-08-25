---
id: company/layers/containers
version: "1.0"
applies_to: [all]
depends_on: [company/baseline]
tags: [architecture, implementation]
---

# Container & Infrastructure Standards

Docker and Kubernetes are core infrastructure layers.

## RULE-CT-001: Infrastructure Stack

| Stage | Tool | Our Decision |
|-------|------|-------------|
| Local dev | Docker Compose | MANDATORY for all projects |
| Sandboxed testing | Testcontainers-python | DEFAULT |
| CI artifact | Docker multi-stage build | MANDATORY |
| Container scanning | Trivy | MANDATORY on every build |
| GPU containers | NVIDIA Container Toolkit | For all GPU workloads |
| Production | Kubernetes | DEFAULT for production |
| ML deployment | Argo Rollouts | DEFAULT for model deploys |
| IaC | Pulumi (Python) / Terraform | Pulumi preferred |

## RULE-CT-002: Docker Standards

| Practice | Requirement |
|----------|-------------|
| Base image | Pinned slim Python image (by digest, not tag) |
| Build style | Multi-stage builds ALWAYS |
| Package install | `uv sync --frozen --no-dev` in builder stage |
| Runtime user | Non-root user (appuser) |
| Secrets | Inject at runtime via env vars; NEVER bake into image |
| Health checks | HEALTHCHECK in Dockerfile + /health endpoint |
| .dockerignore | Exclude .venv, .git, __pycache__, tests, notebooks |
| Layer caching | COPY pyproject.toml + uv.lock BEFORE copying src/ |
| GPU images | nvidia/cuda base for inference |
| Model weights | Pre-download into image OR mount as volumes |

## RULE-CT-003: Kubernetes for AI

| Resource | When to Use |
|----------|------------|
| Deployment + Service | Model serving APIs |
| HPA | Auto-scale inference on latency/throughput |
| KEDA | Event-driven scaling (queue depth, cron) |
| Argo Rollouts | Canary: 5%→20%→50%→100% with metric gates |
| CronJob | Scheduled retraining |
| PVC | Model artifacts, datasets |
| NetworkPolicy | Workload isolation |
| ResourceQuota | Cost control per namespace/team |

## RULE-CT-004: Testing Environments

| Tier | Tool | What Gets Tested |
|------|------|-----------------|
| Unit | pytest + hypothesis | Functions, logic (fast <5min) |
| Integration | Testcontainers | Real Postgres, Redis, Kafka |
| E2E | docker-compose + httpx | Full service, API contracts |
| Load | Locust | Throughput, p99, GPU utilization |
| Staging | K8s + Argo Rollouts | Canary, drift detection |
