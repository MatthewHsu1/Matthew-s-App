# Polymarket Discovery (Phase 1 Skeleton)

Offline pipeline skeleton for discovering candidate arbitrage baskets before live Nautilus execution.

## Run

```bash
cd tools/polymarket_discovery
PYTHONPATH=src python3 -m polymarket_discovery run --config tests/fixtures/sample_config.json
```

Artifacts are written under `output_root/artifact_subdir/run_<hash>/`:
- `baskets.json` (schema-validated output contract)
- `stages.jsonl` (structured stage logs)

## Local Open-Model Setup

`polymarket_discovery` now supports local-only HTTP model endpoints for both topic assignment embeddings and dependency inference.

Wiring to the local model-serving stack:

See [tools/model-serving/README.md](/mnt/HDD/Projects/Financial%20App/tools/model-serving/README.md) for the companion Docker setup.

```json
{
  "embedding_model": "linq-embed-mistral",
  "llm_model": "<glm-open-weight-model-id>",
  "params": {
    "embeddings": {
      "embedding_provider": "tei",
      "base_url": "http://127.0.0.1:8080/v1/embeddings",
      "embedding_model": "linq-embed-mistral"
    },
    "dependency_inferencer": {
      "provider_name": "vllm_openai",
      "base_url": "http://127.0.0.1:8000/v1/chat/completions",
      "model": "<glm-open-weight-model-id>"
    }
  }
}
```

Preferred config shape for local endpoints:

- `params.embeddings`
  - `embedding_provider` or `provider`: `tei` for a TEI/OpenAI-style embeddings endpoint
  - `embedding_model` or `model`: embedding model name, for example `linq-embed-mistral`
  - `base_url`: full embeddings endpoint URL, for example `http://127.0.0.1:8080/v1/embeddings`
  - `timeout_seconds`: request timeout in seconds
  - `batch_size`: HTTP batch size for embedding requests
- `params.dependency_inferencer`
  - `llm_provider`, `provider`, or `provider_name`: `vllm_openai` for a local OpenAI-compatible vLLM endpoint
  - `base_url`: full chat completions endpoint URL, for example `http://127.0.0.1:8000/v1/chat/completions`
  - `model`: model name exposed by vLLM, for example `<glm-open-weight-model-id>`
  - `temperature`: sampling temperature
  - `max_tokens`: completion token cap
  - `retry`: object with `max_attempts`, `backoff_seconds`, and `backoff_factor`

Older alias locations still work for top-level `embedding_provider` and `embedding_model`, plus the legacy nested `topic_assigner` / `topic_clustering` fields.

Example local-only config:

```json
{
  "output_root": "tmp/polymarket_discovery",
  "artifact_subdir": "runs",
  "market_source": "fixture",
  "embedding_model": "linq-embed-mistral",
  "llm_model": "<glm-open-weight-model-id>",
  "params": {
    "embeddings": {
      "embedding_provider": "tei",
      "base_url": "http://127.0.0.1:8080/v1/embeddings",
      "embedding_model": "linq-embed-mistral",
      "timeout_seconds": 10,
      "batch_size": 16
    },
    "dependency_inferencer": {
      "provider_name": "vllm_openai",
      "base_url": "http://127.0.0.1:8000/v1/chat/completions",
      "model": "<glm-open-weight-model-id>",
      "temperature": 0.0,
      "max_tokens": 256,
      "retry": {
        "max_attempts": 3,
        "backoff_seconds": 0.5,
        "backoff_factor": 2.0
      }
    }
  }
}
```

If your local vLLM deployment cannot host that GLM model, use `DeepSeek-R1-Distill-Qwen-7B` as the fallback recommendation.

`polymarket_discovery` remains client-only: it consumes model endpoints but does not include serving logic.

When the endpoints above are local, inference and embedding requests stay on your machine and do not call external inference APIs.

Public Polymarket market reads can still hit Polymarket public endpoints unless you use `market_source=fixture` or another local source. Those reads do not require market data API keys.

## Test Setup

```bash
cd tools/polymarket_discovery
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```
