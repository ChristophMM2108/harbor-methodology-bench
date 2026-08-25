---
id: company/layers/ml_ai
version: "1.0"
applies_to: [llm_nlp_app, genai_app]
depends_on: [company/baseline]
tags: [implementation, llm]
---

# ML / AI Standards

## RULE-ML-001: ML Stack

| Layer | Library | Our Decision |
|-------|---------|-------------|
| Experiment tracking | MLflow 3.x | DEFAULT (30M+ downloads, GenAI support) |
| Data quality | Great Expectations + Soda Core | GX: deep; Soda: lightweight CI |
| DataFrame validation | Pandera | At every pipeline boundary |
| Data versioning | DVC + lakeFS | DVC for Git-based; lakeFS for petabyte |
| Model monitoring | Evidently AI | DEFAULT (25M+ downloads, 100+ metrics) |
| LLM observability | Langfuse + Arize Phoenix | DEFAULT for LLM apps |
| Model export | ONNX Runtime / safetensors | NEVER use pickle |
| Bias auditing | Fairlearn | DEFAULT (Microsoft-backed) |
| Explainability | SHAP (regulated) / LIME (customer) | Context-dependent |
| Model cards | Hugging Face format | MANDATORY for every deployed model |

## RULE-ML-002: Experiment Tracking

- Log all experiments with MLflow (parameters, metrics, artifacts)
- MLflow 3.0 supports GenAI with LLM tracing for 20+ libraries
- Tag experiments with meaningful names and descriptions
- Register production-ready models in the model registry

## RULE-ML-003: Data Validation

- Pandera schemas at every pipeline boundary
- Supports pandas, Polars, PySpark, Dask
- Great Expectations for deep validation (200+ types)
- Soda Core YAML checks in CI before merge

## RULE-ML-004: Model Serialization

- **NEVER use pickle** for model serialization
- Use safetensors for PyTorch/HF models (secure, fast)
- Use ONNX Runtime for cross-platform deployment
- Sign production models with Sigstore

## RULE-ML-005: Model Monitoring

- Evidently AI for drift detection (20+ methods: PSI, KL, Wasserstein, KS)
- Run on schedule AND as CI/CD gate before retraining
- Track data drift, prediction drift, and model quality
- Alert via Prometheus + Grafana dashboards `[INFRA - suggested]`

## RULE-ML-006: Model Cards

- Hugging Face format mandatory for every deployed model
- Document: intended use, evaluation results, bias assessment, limitations
- Version model cards alongside model artifacts
- Review model cards as part of deployment approval
