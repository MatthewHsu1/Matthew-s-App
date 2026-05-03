from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from ..net.http_json import RetrySettings
from ..utils.coercion import coerce_float, coerce_int, coerce_str, is_local_endpoint


@dataclass(slots=True)
class EmbeddingProviderSettings:
    provider_name: str = "stub"
    model_name: str = "stub-embed"
    dimensions: int = 8
    base_url: str = ""
    timeout_seconds: float = 10.0
    batch_size: int = 16
    api_key: str = ""
    retry: RetrySettings = field(default_factory=RetrySettings)


@dataclass(slots=True)
class LLMProviderSettings:
    provider_name: str = "stub"
    model_name: str = "deepseek-stub"
    base_url: str = ""
    api_key: str = ""
    timeout_seconds: float = 10.0
    temperature: float = 0.0
    max_tokens: int = 256
    retry: RetrySettings = field(default_factory=RetrySettings)


def resolve_embedding_settings(config: Any | None = None) -> EmbeddingProviderSettings:
    params = getattr(config, "params", {}) if config is not None else {}
    if not isinstance(params, dict):
        params = {}

    embedding_params: dict[str, Any] = {}
    for key in ("embeddings", "topic_assigner", "topic_clustering"):
        candidate = params.get(key)
        if isinstance(candidate, dict):
            embedding_params = candidate
            break

    explicit_provider_name = coerce_str(
        embedding_params.get(
            "embedding_provider",
            embedding_params.get(
                "provider",
                embedding_params.get(
                    "provider_name",
                    params.get("embedding_provider", getattr(config, "embedding_provider", "") if config is not None else ""),
                ),
            ),
        ),
        "",
    )
    model_name = embedding_params.get(
        "embedding_model",
        embedding_params.get("model", params.get("embedding_model", getattr(config, "embedding_model", "stub-embed") if config is not None else "stub-embed")),
    )
    base_url = coerce_str(
        embedding_params.get("base_url", params.get("base_url", "")),
        "",
    )
    retry_params = embedding_params.get("retry")

    if not isinstance(retry_params, dict):
        retry_params = {}

    settings = EmbeddingProviderSettings(
        provider_name=(explicit_provider_name.lower() if explicit_provider_name else ("tei" if base_url else "stub")),
        model_name=coerce_str(model_name, "stub-embed"),
        dimensions=coerce_int(
            embedding_params.get("embedding_dimensions", params.get("embedding_dimensions")),
            8,
        ),
        base_url=base_url,
        timeout_seconds=coerce_float(
            embedding_params.get("timeout_seconds", params.get("timeout_seconds")),
            10.0,
        ),
        batch_size=coerce_int(
            embedding_params.get(
                "batch_size",
                embedding_params.get(
                    "embedding_batch_size",
                    params.get("batch_size", params.get("embedding_batch_size")),
                ),
            ),
            16,
        ),
        api_key=coerce_str(
            embedding_params.get("api_key", params.get("api_key")),
            "",
        ),
        retry=RetrySettings(
            max_attempts=coerce_int(
                retry_params.get("max_attempts", embedding_params.get("retries", params.get("retries"))),
                3,
            ),
            backoff_seconds=coerce_float(
                retry_params.get("backoff_seconds", embedding_params.get("backoff_seconds", params.get("backoff_seconds"))),
                0.5,
            ),
            backoff_factor=coerce_float(
                retry_params.get("backoff_factor", embedding_params.get("backoff_factor", params.get("backoff_factor"))),
                2.0,
            ),
        ),
    )

    if settings.timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    if settings.batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    if settings.retry.max_attempts <= 0:
        raise ValueError("retry.max_attempts must be greater than zero")
    if settings.retry.backoff_seconds < 0:
        raise ValueError("retry.backoff_seconds must be zero or greater")
    if settings.retry.backoff_factor <= 0:
        raise ValueError("retry.backoff_factor must be greater than zero")
    return settings


def get_inferencer_params(config: Any | None = None) -> dict[str, Any]:
    params = getattr(config, "params", {}) if config is not None else {}
    if not isinstance(params, dict):
        return {}
    for key in ("dependency_inferencer", "llm"):
        candidate = params.get(key)
        if isinstance(candidate, dict):
            return candidate
    return {}


_CODEX_PROVIDER_ALIASES = frozenset({"codex", "codex_cli", "codex-cli"})


def resolve_llm_settings(config: Any | None = None) -> LLMProviderSettings:
    params = getattr(config, "params", {}) if config is not None else {}
    if not isinstance(params, dict):
        params = {}

    inferencer_params = get_inferencer_params(config)

    retry_params = inferencer_params.get("retry")
    if not isinstance(retry_params, dict):
        retry_params = {}

    explicit_provider_name = coerce_str(
        inferencer_params.get(
            "llm_provider",
            inferencer_params.get(
                "provider",
                inferencer_params.get(
                    "provider_name",
                    params.get("llm_provider", getattr(config, "llm_provider", "") if config is not None else ""),
                ),
            ),
        ),
        "",
    )
    model_name = inferencer_params.get(
        "llm_model",
        inferencer_params.get("model", params.get("llm_model", getattr(config, "llm_model", "deepseek-stub") if config is not None else "deepseek-stub")),
    )
    base_url = coerce_str(
        inferencer_params.get("base_url"),
        "https://api.deepseek.com/chat/completions" if explicit_provider_name.lower() == "deepseek" else "",
    )
    has_real_provider_settings = any(
        coerce_str(inferencer_params.get(key), "")
        for key in ("api_key", "api_key_env", "base_url")
    )

    if explicit_provider_name:
        normalized_provider_name = explicit_provider_name.lower()
    elif has_real_provider_settings and base_url and is_local_endpoint(base_url):
        normalized_provider_name = "vllm_openai"
    elif has_real_provider_settings:
        normalized_provider_name = "deepseek"
    else:
        normalized_provider_name = "stub"

    if normalized_provider_name in _CODEX_PROVIDER_ALIASES:
        normalized_provider_name = "codex"
    normalized_model_name = coerce_str(model_name, "deepseek-stub")

    api_key = coerce_str(inferencer_params.get("api_key"), "")

    api_key_env = coerce_str(
        inferencer_params.get("api_key_env"),
        "DEEPSEEK_API_KEY" if normalized_provider_name == "deepseek" else "",
    )

    if not api_key and api_key_env:
        api_key = coerce_str(os.getenv(api_key_env), "")

    if not base_url and normalized_provider_name == "deepseek":
        base_url = "https://api.deepseek.com/chat/completions"
        
    settings = LLMProviderSettings(
        provider_name=normalized_provider_name,
        model_name=normalized_model_name,
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=coerce_float(inferencer_params.get("timeout_seconds"), 10.0),
        temperature=coerce_float(inferencer_params.get("temperature"), 0.0),
        max_tokens=coerce_int(
            inferencer_params.get("max_tokens", inferencer_params.get("max_output_tokens")),
            256,
        ),
        retry=RetrySettings(
            max_attempts=coerce_int(
                retry_params.get("max_attempts", inferencer_params.get("retries")),
                3,
            ),
            backoff_seconds=coerce_float(
                retry_params.get("backoff_seconds", inferencer_params.get("backoff_seconds")),
                0.5,
            ),
            backoff_factor=coerce_float(
                retry_params.get("backoff_factor", inferencer_params.get("backoff_factor")),
                2.0,
            ),
        ),
    )

    if settings.timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    if settings.max_tokens <= 0:
        raise ValueError("max_tokens must be greater than zero")
    if settings.retry.max_attempts <= 0:
        raise ValueError("retry.max_attempts must be greater than zero")
    if settings.retry.backoff_seconds < 0:
        raise ValueError("retry.backoff_seconds must be zero or greater")
    if settings.retry.backoff_factor <= 0:
        raise ValueError("retry.backoff_factor must be greater than zero")
    return settings
