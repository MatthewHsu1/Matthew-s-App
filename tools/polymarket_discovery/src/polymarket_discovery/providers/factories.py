from __future__ import annotations

from typing import Any

from ..interfaces.embedding_provider import EmbeddingProvider
from ..interfaces.llm_provider import LLMProvider
from .embeddings import HTTPEmbeddingProvider, StubEmbeddingProvider
from .llm import DeepSeekLLMProviderStub, OpenAICompatibleLLMProvider
from .settings import resolve_embedding_settings, resolve_llm_settings


def build_embedding_provider(config: Any | None = None) -> EmbeddingProvider:
    """Build the configured embedding provider."""
    settings = resolve_embedding_settings(config)
    if settings.provider_name in {"stub", "deterministic", "hash", "default"}:
        return StubEmbeddingProvider(model_name=settings.model_name, dimensions=settings.dimensions)
    if settings.provider_name in {"tei", "openai-compatible", "openai_compatible", "openai", "http"}:
        return HTTPEmbeddingProvider(settings=settings)
    raise ValueError(f"Unsupported embedding provider: {settings.provider_name}")


def build_llm_provider(config: Any | None = None) -> LLMProvider:
    settings = resolve_llm_settings(config)
    if settings.provider_name in {"stub", "deterministic", "default"}:
        return DeepSeekLLMProviderStub(model_name=settings.model_name)
    if settings.provider_name in {"deepseek", "openai-compatible", "openai_compatible", "vllm_openai", "vllm-openai", "vllm", "http"}:
        return OpenAICompatibleLLMProvider(settings=settings)
    raise ValueError(f"Unsupported llm provider: {settings.provider_name}")


def configures_llm_provider(config: Any | None = None) -> bool:
    params = getattr(config, "params", {}) if config is not None else {}
    if not isinstance(params, dict):
        return False

    if isinstance(params.get("llm_provider"), str) and params["llm_provider"].strip():
        return True

    for key in ("dependency_inferencer", "llm"):
        candidate = params.get(key)
        if not isinstance(candidate, dict):
            continue
        for provider_key in ("llm_provider", "provider", "provider_name", "api_key", "api_key_env", "base_url"):
            value = candidate.get(provider_key)
            if isinstance(value, str) and value.strip():
                return True
    return False
