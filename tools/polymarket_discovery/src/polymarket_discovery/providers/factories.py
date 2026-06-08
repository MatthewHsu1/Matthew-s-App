from __future__ import annotations

from typing import Any

from ..interfaces.embedding_provider import EmbeddingProvider
from ..interfaces.llm_provider import LLMProvider
from .codex_invoker_logging import LoggingCodexInvoker
from .embeddings import HTTPEmbeddingProvider, StubEmbeddingProvider
from .llm_codex import CodexCliLLMProvider, SubprocessCodexInvoker
from .llm_openai import OpenAICompatibleLLMProvider
from .llm_stub import DeepSeekLLMProviderStub
from .openai_invoker import RequestJsonOpenAIInvoker
from .openai_invoker_logging import LoggingOpenAIInvoker
from .settings import (
    get_inferencer_params,
    resolve_embedding_settings,
    resolve_llm_settings,
)


def build_embedding_provider(config: Any | None = None) -> EmbeddingProvider:
    """Build the configured embedding provider.
    """
    settings = resolve_embedding_settings(config)
    if not settings.provider_name:
        raise ValueError(
            "No embedding provider configured. "
            "Set 'embedding_provider' in your config (e.g. 'tei' with a 'base_url') "
            "or use 'stub' explicitly for local testing. "
            "Running without a configured provider would produce semantically random clusters."
        )
    if settings.provider_name in {"stub", "deterministic", "hash"}:
        return StubEmbeddingProvider(model_name=settings.model_name, dimensions=settings.dimensions)
    if settings.provider_name in {"tei", "openai-compatible", "openai_compatible", "openai", "http"}:
        return HTTPEmbeddingProvider(settings=settings)
    raise ValueError(f"Unsupported embedding provider: {settings.provider_name}")


def build_llm_provider(
    config: Any | None = None,
) -> LLMProvider:
    settings = resolve_llm_settings(config)
    if settings.provider_name in {"stub", "deterministic"}:
        return DeepSeekLLMProviderStub(model_name=settings.model_name)
    if settings.provider_name in {"deepseek", "openai-compatible", "openai_compatible", "vllm_openai", "vllm-openai", "vllm", "http"}:
        return OpenAICompatibleLLMProvider(
            settings=settings,
            invoker=LoggingOpenAIInvoker(inner=RequestJsonOpenAIInvoker(settings=settings)),
        )
    if settings.provider_name == "codex":
        return CodexCliLLMProvider(
            settings=settings,
            invoker=LoggingCodexInvoker(inner=_build_subprocess_codex_invoker(config)),
        )
    raise ValueError(f"Unsupported llm provider: {settings.provider_name}")


def _build_subprocess_codex_invoker(config: Any | None) -> SubprocessCodexInvoker:
    inferencer_params = get_inferencer_params(config)
    binary = inferencer_params.get("codex_binary", "codex")
    raw_args = inferencer_params.get("codex_args", ("exec",))
    use_json_flag = inferencer_params.get("codex_use_json_flag", True)

    if isinstance(raw_args, (list, tuple)):
        base_args = tuple(str(arg) for arg in raw_args)
    else:
        base_args = ("exec",)

    return SubprocessCodexInvoker(
        binary=str(binary),
        base_args=base_args,
        use_json_flag=bool(use_json_flag),
    )


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
