from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from math import isfinite
from typing import Any
from typing import Sequence
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.request import Request
import urllib.request

from .contracts import MarketDescriptor
from .interfaces.embedding_provider import EmbeddingProvider
from .interfaces.llm_dependency_prediction import LLMDependencyPrediction
from .interfaces.llm_provider import LLMProvider

ALLOWED_LLM_EDGE_TYPES = frozenset({"mutually_exclusive", "conditional", "related"})


def _coerce_int(value: Any, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_str(value: Any, default: str) -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or default
    return default


def _is_local_endpoint(url: str) -> bool:
    if not url:
        return False

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return False

    return hostname.lower() in {"localhost", "127.0.0.1", "::1"}


@dataclass(slots=True)
class StubEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding stub for local tests and interface plumbing."""

    model_name: str = "stub-embed"
    dimensions: int = 8

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            values = [digest[i] / 255.0 for i in range(self.dimensions)]
            vectors.append(values)
        return vectors


@dataclass(slots=True)
class _EmbeddingRetrySettings:
    max_attempts: int = 3
    backoff_seconds: float = 0.5
    backoff_factor: float = 2.0


@dataclass(slots=True)
class _EmbeddingProviderSettings:
    provider_name: str = "stub"
    model_name: str = "stub-embed"
    dimensions: int = 8
    base_url: str = ""
    timeout_seconds: float = 10.0
    batch_size: int = 16
    api_key: str = ""
    retry: _EmbeddingRetrySettings = field(default_factory=_EmbeddingRetrySettings)


@dataclass(slots=True)
class HTTPEmbeddingProvider(EmbeddingProvider):
    settings: _EmbeddingProviderSettings

    def __post_init__(self) -> None:
        if not self.settings.base_url:
            raise ValueError("base_url is required for non-stub embedding providers")
        if self.settings.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.settings.batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        if self.settings.retry.max_attempts <= 0:
            raise ValueError("retry.max_attempts must be greater than zero")
        if self.settings.retry.backoff_seconds < 0:
            raise ValueError("retry.backoff_seconds must be zero or greater")
        if self.settings.retry.backoff_factor <= 0:
            raise ValueError("retry.backoff_factor must be greater than zero")

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.settings.batch_size):
            batch = list(texts[start : start + self.settings.batch_size])
            payload = self._request_json(
                {
                    "model": self.settings.model_name,
                    "input": batch,
                },
            )
            vectors.extend(self._extract_embeddings(payload, len(batch)))
        return vectors

    def _request_json(self, payload: dict[str, Any]) -> Any:
        encoded_payload = json.dumps(payload).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(self.settings.retry.max_attempts):
            headers = {
                "User-Agent": "polymarket-discovery/0.1",
                "Content-Type": "application/json",
            }
            if self.settings.api_key:
                headers["Authorization"] = f"Bearer {self.settings.api_key}"

            request = Request(
                self.settings.base_url,
                data=encoded_payload,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                return json.loads(raw)
            except HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt >= self.settings.retry.max_attempts - 1:
                    raise
                last_error = exc
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                if attempt >= self.settings.retry.max_attempts - 1:
                    raise
                last_error = exc

            sleep_seconds = self.settings.retry.backoff_seconds * (self.settings.retry.backoff_factor**attempt)
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        if last_error is not None:
            raise last_error
        raise RuntimeError("embedding request retry loop exited unexpectedly")

    @staticmethod
    def _extract_embeddings(payload: Any, expected_count: int) -> list[list[float]]:
        if not isinstance(payload, dict):
            raise ValueError("embedding response payload must be a JSON object")

        data = payload.get("data")
        if not isinstance(data, list):
            raise ValueError("embedding response payload must include data")
        if len(data) != expected_count:
            raise ValueError("embedding response payload returned a mismatched number of vectors")

        vectors: list[list[float]] = []
        for item in data:
            if isinstance(item, dict):
                embedding = item.get("embedding")
            else:
                embedding = item
            if not isinstance(embedding, list):
                raise ValueError("embedding response payload must include embedding vectors")
            vectors.append([float(value) for value in embedding])
        return vectors


def _resolve_embedding_settings(config: Any | None = None) -> _EmbeddingProviderSettings:
    params = getattr(config, "params", {}) if config is not None else {}
    if not isinstance(params, dict):
        params = {}

    embedding_params: dict[str, Any] = {}
    for key in ("embeddings", "topic_assigner", "topic_clustering"):
        candidate = params.get(key)
        if isinstance(candidate, dict):
            embedding_params = candidate
            break

    explicit_provider_name = _coerce_str(
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
    base_url = _coerce_str(
        embedding_params.get("base_url", params.get("base_url", "")),
        "",
    )
    batch_size = _coerce_int(
        embedding_params.get(
            "batch_size",
            embedding_params.get(
                "embedding_batch_size",
                params.get("batch_size", params.get("embedding_batch_size")),
            ),
        ),
        16,
    )
    retry_params = embedding_params.get("retry")
    if not isinstance(retry_params, dict):
        retry_params = {}
    settings = _EmbeddingProviderSettings(
        provider_name=(
            explicit_provider_name.lower()
            if explicit_provider_name
            else ("tei" if base_url else "stub")
        ),
        model_name=_coerce_str(model_name, "stub-embed"),
        dimensions=_coerce_int(
            embedding_params.get("embedding_dimensions", params.get("embedding_dimensions")),
            8,
        ),
        base_url=base_url,
        timeout_seconds=_coerce_float(
            embedding_params.get("timeout_seconds", params.get("timeout_seconds")),
            10.0,
        ),
        batch_size=batch_size,
        api_key=_coerce_str(
            embedding_params.get("api_key", params.get("api_key")),
            "",
        ),
        retry=_EmbeddingRetrySettings(
            max_attempts=_coerce_int(
                retry_params.get("max_attempts", embedding_params.get("retries", params.get("retries"))),
                3,
            ),
            backoff_seconds=_coerce_float(
                retry_params.get("backoff_seconds", embedding_params.get("backoff_seconds", params.get("backoff_seconds"))),
                0.5,
            ),
            backoff_factor=_coerce_float(
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


def build_embedding_provider(config: Any | None = None) -> EmbeddingProvider:
    """Build the configured embedding provider."""
    params = getattr(config, "params", {}) if config is not None else {}
    if not isinstance(params, dict):
        params = {}

    settings = _resolve_embedding_settings(config)
    if settings.provider_name in {"stub", "deterministic", "hash", "default"}:
        return StubEmbeddingProvider(model_name=settings.model_name, dimensions=settings.dimensions)
    if settings.provider_name in {"tei", "openai-compatible", "openai_compatible", "openai", "http"}:
        return HTTPEmbeddingProvider(settings=settings)
    raise ValueError(f"Unsupported embedding provider: {settings.provider_name}")


@dataclass(slots=True)
class _LLMRetrySettings:
    max_attempts: int = 3
    backoff_seconds: float = 0.5
    backoff_factor: float = 2.0


@dataclass(slots=True)
class _LLMProviderSettings:
    provider_name: str = "stub"
    model_name: str = "deepseek-stub"
    base_url: str = ""
    api_key: str = ""
    timeout_seconds: float = 10.0
    temperature: float = 0.0
    max_tokens: int = 256
    retry: _LLMRetrySettings = field(default_factory=_LLMRetrySettings)


def _resolve_llm_settings(config: Any | None = None) -> _LLMProviderSettings:
    params = getattr(config, "params", {}) if config is not None else {}
    if not isinstance(params, dict):
        params = {}

    inferencer_params: dict[str, Any] = {}
    for key in ("dependency_inferencer", "llm"):
        candidate = params.get(key)
        if isinstance(candidate, dict):
            inferencer_params = candidate
            break

    retry_params = inferencer_params.get("retry")
    if not isinstance(retry_params, dict):
        retry_params = {}

    explicit_provider_name = _coerce_str(
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
    base_url = _coerce_str(
        inferencer_params.get("base_url"),
        "https://api.deepseek.com/chat/completions" if explicit_provider_name.lower() == "deepseek" else "",
    )
    has_real_provider_settings = any(
        _coerce_str(inferencer_params.get(key), "")
        for key in ("api_key", "api_key_env", "base_url")
    )
    if explicit_provider_name:
        normalized_provider_name = explicit_provider_name.lower()
    elif has_real_provider_settings and base_url and _is_local_endpoint(base_url):
        normalized_provider_name = "vllm_openai"
    elif has_real_provider_settings:
        normalized_provider_name = "deepseek"
    else:
        normalized_provider_name = "stub"
    normalized_model_name = _coerce_str(model_name, "deepseek-stub")

    api_key = _coerce_str(inferencer_params.get("api_key"), "")
    api_key_env = _coerce_str(
        inferencer_params.get("api_key_env"),
        "DEEPSEEK_API_KEY" if normalized_provider_name == "deepseek" else "",
    )
    if not api_key and api_key_env:
        api_key = _coerce_str(os.getenv(api_key_env), "")

    if not base_url and normalized_provider_name == "deepseek":
        base_url = "https://api.deepseek.com/chat/completions"
    settings = _LLMProviderSettings(
        provider_name=normalized_provider_name,
        model_name=normalized_model_name,
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=_coerce_float(inferencer_params.get("timeout_seconds"), 10.0),
        temperature=_coerce_float(inferencer_params.get("temperature"), 0.0),
        max_tokens=_coerce_int(
            inferencer_params.get("max_tokens", inferencer_params.get("max_output_tokens")),
            256,
        ),
        retry=_LLMRetrySettings(
            max_attempts=_coerce_int(
                retry_params.get("max_attempts", inferencer_params.get("retries")),
                3,
            ),
            backoff_seconds=_coerce_float(
                retry_params.get("backoff_seconds", inferencer_params.get("backoff_seconds")),
                0.5,
            ),
            backoff_factor=_coerce_float(
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


def validate_llm_dependency_prediction(prediction: LLMDependencyPrediction) -> LLMDependencyPrediction:
    edge_type = prediction.edge_type.strip().lower() if isinstance(prediction.edge_type, str) else ""
    if edge_type not in ALLOWED_LLM_EDGE_TYPES:
        raise ValueError(
            "edge_type must be one of: conditional, mutually_exclusive, related",
        )

    confidence_raw = prediction.confidence
    if isinstance(confidence_raw, bool) or not isinstance(confidence_raw, (int, float)):
        raise ValueError("confidence must be a numeric value between 0 and 1 inclusive")
    confidence = float(confidence_raw)
    if not isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1 inclusive")

    rationale = prediction.rationale.strip() if isinstance(prediction.rationale, str) else ""
    if not rationale:
        raise ValueError("rationale must be a non-empty string")

    return LLMDependencyPrediction(
        edge_type=edge_type,
        confidence=confidence,
        rationale=rationale,
    )


def parse_llm_dependency_prediction(raw_response: str | dict[str, Any]) -> LLMDependencyPrediction:
    if isinstance(raw_response, str):
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM dependency response must be valid JSON") from exc
    else:
        payload = raw_response

    if not isinstance(payload, dict):
        raise ValueError("LLM dependency response must be a JSON object")

    return validate_llm_dependency_prediction(
        LLMDependencyPrediction(
            edge_type=payload.get("edge_type", ""),
            confidence=payload.get("confidence"),
            rationale=payload.get("rationale", ""),
        ),
    )


def build_llm_provider(config: Any | None = None) -> LLMProvider:
    settings = _resolve_llm_settings(config)
    if settings.provider_name in {"stub", "deterministic", "default"}:
        return DeepSeekLLMProviderStub(model_name=settings.model_name)
    if settings.provider_name in {"deepseek", "openai-compatible", "openai_compatible", "vllm_openai", "vllm-openai", "vllm", "http"}:
        return OpenAICompatibleLLMProvider(settings=settings)
    raise ValueError(f"Unsupported llm provider: {settings.provider_name}")


@dataclass(slots=True)
class _PolymarketSourceSettings:
    gamma_base_url: str = "https://gamma-api.polymarket.com"
    clob_base_url: str = "https://clob.polymarket.com"
    timeout_seconds: float = 10.0
    retries: int = 3
    backoff_seconds: float = 0.5
    backoff_factor: float = 2.0
    page_size: int = 100
    max_markets: int | None = None


@dataclass(slots=True)
class _NormalizedCLOBMarket:
    condition_id: str
    token_ids: list[str] = field(default_factory=list)
    active: bool = True
    closed: bool = False
    archived: bool = False
    accepting_orders: bool = True


@dataclass(slots=True)
class PolymarketMarketSource:
    """Fetch and normalize active markets from Gamma plus CLOB metadata."""

    def fetch_active_markets(self, config: Any | None = None) -> list[MarketDescriptor]:
        settings = self._resolve_settings(config)
        gamma_markets = self._fetch_gamma_markets(settings)
        clob_markets = self._fetch_clob_markets(settings)
        clob_by_condition_id = {market.condition_id: market for market in clob_markets}

        normalized: list[MarketDescriptor] = []
        seen_market_ids: set[str] = set()
        for raw_market in gamma_markets:
            market = self._normalize_market(raw_market, clob_by_condition_id.get(raw_market.get("conditionId") or raw_market.get("condition_id")))
            if market is None or market.market_id in seen_market_ids:
                continue
            seen_market_ids.add(market.market_id)
            normalized.append(market)

        normalized.sort(key=self._sort_key)
        if settings.max_markets is not None:
            return normalized[: settings.max_markets]
        return normalized

    def _resolve_settings(self, config: Any | None) -> _PolymarketSourceSettings:
        params = getattr(config, "params", {}) if config is not None else {}
        if not isinstance(params, dict):
            params = {}

        source_params: dict[str, Any] = params
        for key in ("polymarket", "market_source", "polymarket_api"):
            candidate = params.get(key)
            if isinstance(candidate, dict):
                source_params = candidate
                break

        settings = _PolymarketSourceSettings(
            gamma_base_url=self._coerce_str(source_params.get("gamma_base_url"), "https://gamma-api.polymarket.com"),
            clob_base_url=self._coerce_str(source_params.get("clob_base_url"), "https://clob.polymarket.com"),
            timeout_seconds=self._coerce_float(source_params.get("timeout_seconds"), 10.0),
            retries=self._coerce_int(source_params.get("retries"), 3),
            backoff_seconds=self._coerce_float(source_params.get("backoff_seconds"), 0.5),
            backoff_factor=self._coerce_float(source_params.get("backoff_factor"), 2.0),
            page_size=self._coerce_int(source_params.get("page_size"), 100),
            max_markets=self._coerce_optional_int(source_params.get("max_markets")),
        )
        if settings.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if settings.retries < 0:
            raise ValueError("retries must be zero or greater")
        if settings.backoff_seconds < 0:
            raise ValueError("backoff_seconds must be zero or greater")
        if settings.backoff_factor <= 0:
            raise ValueError("backoff_factor must be greater than zero")
        if settings.page_size <= 0:
            raise ValueError("page_size must be greater than zero")
        if settings.max_markets is not None and settings.max_markets < 0:
            raise ValueError("max_markets must be zero or greater")
        return settings

    def _fetch_gamma_markets(self, settings: _PolymarketSourceSettings) -> list[dict[str, Any]]:
        markets: list[dict[str, Any]] = []
        offset = 0
        seen_fingerprints: set[tuple[str, ...]] = set()
        while True:
            payload = self._request_json(
                settings.gamma_base_url,
                "/markets",
                settings,
                params={
                    "active": "true",
                    "closed": "false",
                    "order": "endDate",
                    "ascending": "true",
                    "limit": str(settings.page_size),
                    "offset": str(offset),
                },
            )
            page = payload if isinstance(payload, list) else payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(page, list) or not page:
                break
            fingerprint = tuple(self._string_field(item, "id", "market_id") for item in page if isinstance(item, dict))
            if fingerprint and fingerprint in seen_fingerprints:
                break
            if fingerprint:
                seen_fingerprints.add(fingerprint)
            for item in page:
                if isinstance(item, dict):
                    markets.append(item)
            if offset == 0 and len(page) > settings.page_size:
                break
            if len(page) < settings.page_size:
                break
            offset += len(page)
        return markets

    def _fetch_clob_markets(self, settings: _PolymarketSourceSettings) -> list[_NormalizedCLOBMarket]:
        markets: list[_NormalizedCLOBMarket] = []
        next_cursor: str | None = None
        seen_cursors: set[str] = set()
        seen_pages: set[tuple[str, ...]] = set()
        while True:
            params: dict[str, str] = {"limit": str(settings.page_size)}
            if next_cursor:
                params["next_cursor"] = next_cursor
            payload = self._request_json(settings.clob_base_url, "/simplified-markets", settings, params=params)
            if not isinstance(payload, dict):
                break
            page = payload.get("data")
            if not isinstance(page, list) or not page:
                break
            page_fingerprint = tuple(
                self._string_field(item, "condition_id", "conditionId")
                for item in page
                if isinstance(item, dict)
            )
            if page_fingerprint and page_fingerprint in seen_pages:
                break
            if page_fingerprint:
                seen_pages.add(page_fingerprint)
            for item in page:
                normalized = self._normalize_clob_market(item)
                if normalized is not None:
                    markets.append(normalized)
            next_cursor = payload.get("next_cursor")
            if not isinstance(next_cursor, str) or not next_cursor.strip():
                break
            if next_cursor in seen_cursors:
                break
            seen_cursors.add(next_cursor)
        return markets

    def _request_json(
        self,
        base_url: str,
        path: str,
        settings: _PolymarketSourceSettings,
        *,
        params: dict[str, str] | None = None,
    ) -> Any:
        query = urlencode(params or {})
        url = f"{base_url.rstrip('/')}{path}"
        if query:
            url = f"{url}?{query}"

        last_error: Exception | None = None
        for attempt in range(settings.retries + 1):
            request = Request(url, headers={"User-Agent": "polymarket-discovery/0.1"})
            try:
                with urllib.request.urlopen(request, timeout=settings.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                return json.loads(raw)
            except HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt >= settings.retries:
                    raise
                last_error = exc
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                if attempt >= settings.retries:
                    raise
                last_error = exc

            sleep_seconds = settings.backoff_seconds * (settings.backoff_factor**attempt)
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        if last_error is not None:
            raise last_error
        raise RuntimeError("request retry loop exited unexpectedly")

    def _normalize_market(
        self,
        raw_market: dict[str, Any],
        clob_market: _NormalizedCLOBMarket | None,
    ) -> MarketDescriptor | None:
        if not self._is_active(raw_market, clob_market):
            return None

        market_id = self._string_field(raw_market, "id", "market_id")
        condition_id = self._string_field(raw_market, "conditionId", "condition_id")
        if not condition_id and clob_market is not None:
            condition_id = clob_market.condition_id
        question = self._string_field(raw_market, "question", "title")
        end_date = self._string_field(raw_market, "endDate", "end_date", "endDateIso", "umaEndDateIso")
        if not market_id or not condition_id or not question or not end_date:
            return None

        token_ids = self._collect_token_ids(raw_market, clob_market)
        if not token_ids:
            return None

        description = self._string_field(raw_market, "description", "subtitle")
        rules = self._string_field(raw_market, "resolutionSource")
        topic = self._string_field(raw_market, "category", "subcategory")
        if not topic:
            topic = "unassigned"

        return MarketDescriptor(
            market_id=market_id,
            condition_id=condition_id,
            question=question,
            description=description,
            rules=rules,
            end_date=end_date,
            topic=topic,
            token_ids=token_ids,
        )

    def _normalize_clob_market(self, raw_market: Any) -> _NormalizedCLOBMarket | None:
        if not isinstance(raw_market, dict):
            return None

        condition_id = self._string_field(raw_market, "condition_id", "conditionId")
        if not condition_id:
            return None

        token_ids: list[str] = []
        raw_tokens = raw_market.get("tokens")
        if isinstance(raw_tokens, list):
            for token in raw_tokens:
                token_id = self._string_field(token, "token_id", "tokenId") if isinstance(token, dict) else self._coerce_token_id(token)
                if token_id:
                    token_ids.append(token_id)

        return _NormalizedCLOBMarket(
            condition_id=condition_id,
            token_ids=self._dedupe_preserve_order(token_ids),
            active=self._coerce_bool(raw_market.get("active"), True),
            closed=self._coerce_bool(raw_market.get("closed"), False),
            archived=self._coerce_bool(raw_market.get("archived"), False),
            accepting_orders=self._coerce_bool(raw_market.get("accepting_orders"), True),
        )

    def _collect_token_ids(self, raw_market: dict[str, Any], clob_market: _NormalizedCLOBMarket | None) -> list[str]:
        token_ids: list[str] = []
        if clob_market is not None:
            token_ids.extend(clob_market.token_ids)
        token_ids.extend(self._token_ids_from_value(raw_market.get("clobTokenIds")))
        return self._dedupe_preserve_order(token_ids)

    def _token_ids_from_value(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            token_ids: list[str] = []
            for item in value:
                if isinstance(item, dict):
                    token_id = self._string_field(item, "token_id", "tokenId")
                else:
                    token_id = self._coerce_token_id(item)
                if token_id:
                    token_ids.append(token_id)
            return token_ids
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return []
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return self._token_ids_from_value(parsed)
            if cleaned.startswith("[") and cleaned.endswith("]"):
                inner = cleaned[1:-1].strip()
                if not inner:
                    return []
                return [token.strip().strip('"').strip("'") for token in inner.split(",") if token.strip().strip('"').strip("'")]
            return [cleaned]
        return []

    @staticmethod
    def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered

    @staticmethod
    def _is_active(raw_market: dict[str, Any], clob_market: _NormalizedCLOBMarket | None) -> bool:
        if not PolymarketMarketSource._coerce_bool(raw_market.get("active"), False):
            return False
        if PolymarketMarketSource._coerce_bool(raw_market.get("closed"), False):
            return False
        if PolymarketMarketSource._coerce_bool(raw_market.get("archived"), False):
            return False
        if clob_market is None:
            return True
        if not clob_market.active or clob_market.closed or clob_market.archived:
            return False
        if not clob_market.accepting_orders:
            return False
        return True

    @staticmethod
    def _sort_key(market: MarketDescriptor) -> tuple[str, str]:
        normalized_end_date = PolymarketMarketSource._sort_timestamp(market.end_date)
        if normalized_end_date is not None:
            return (normalized_end_date.isoformat(), market.market_id)
        return ("~" + (market.end_date or ""), market.market_id)

    @staticmethod
    def _sort_timestamp(value: str) -> datetime | None:
        cleaned = (value or "").strip()
        if not cleaned:
            return None
        try:
            if len(cleaned) == 10 and cleaned.count("-") == 2 and "T" not in cleaned:
                normalized = f"{cleaned}T00:00:00+00:00"
            else:
                normalized = cleaned[:-1] + "+00:00" if cleaned.endswith("Z") else cleaned

            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).replace(tzinfo=None)
        except ValueError:
            return None

    @staticmethod
    def _string_field(raw: Any, *keys: str) -> str:
        if not isinstance(raw, dict):
            return ""
        for key in keys:
            value = raw.get(key)
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    return cleaned
        return ""

    @staticmethod
    def _coerce_token_id(value: Any) -> str:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned
        return ""

    @staticmethod
    def _coerce_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return default

    @staticmethod
    def _coerce_str(value: Any, default: str) -> str:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or default
        return default

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_float(value: Any, default: float) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default


@dataclass(slots=True)
class OpenAICompatibleLLMProvider(LLMProvider):
    settings: _LLMProviderSettings

    def __post_init__(self) -> None:
        if not self.settings.base_url:
            raise ValueError("base_url is required for non-stub llm providers")
        if not self.settings.api_key and not _is_local_endpoint(self.settings.base_url):
            raise ValueError("api_key is required for non-local llm providers")

    def infer_dependency(
        self,
        left_market: MarketDescriptor,
        right_market: MarketDescriptor,
    ) -> LLMDependencyPrediction:
        payload = self._request_json(
            {
                "model": self.settings.model_name,
                "temperature": self.settings.temperature,
                "max_tokens": self.settings.max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You infer market dependencies. Reply with a single JSON object "
                            "containing edge_type, confidence, rationale. edge_type must be one "
                            "of mutually_exclusive, conditional, related. confidence must be a "
                            "number from 0 to 1."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_user_prompt(left_market, right_market),
                    },
                ],
            },
        )
        content = self._extract_message_content(payload)
        return parse_llm_dependency_prediction(content)

    def _request_json(self, payload: dict[str, Any]) -> Any:
        encoded_payload = json.dumps(payload).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(self.settings.retry.max_attempts):
            request = Request(
                self.settings.base_url,
                data=encoded_payload,
                headers={
                    "User-Agent": "polymarket-discovery/0.1",
                    "Content-Type": "application/json",
                    **({"Authorization": f"Bearer {self.settings.api_key}"} if self.settings.api_key else {}),
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                return json.loads(raw)
            except HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt >= self.settings.retry.max_attempts - 1:
                    raise
                last_error = exc
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                if attempt >= self.settings.retry.max_attempts - 1:
                    raise
                last_error = exc

            sleep_seconds = self.settings.retry.backoff_seconds * (self.settings.retry.backoff_factor**attempt)
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        if last_error is not None:
            raise last_error
        raise RuntimeError("llm request retry loop exited unexpectedly")

    @staticmethod
    def _build_user_prompt(left_market: MarketDescriptor, right_market: MarketDescriptor) -> str:
        return json.dumps(
            {
                "left_market": {
                    "market_id": left_market.market_id,
                    "question": left_market.question,
                    "description": left_market.description,
                    "rules": left_market.rules,
                    "end_date": left_market.end_date,
                    "topic": left_market.topic,
                },
                "right_market": {
                    "market_id": right_market.market_id,
                    "question": right_market.question,
                    "description": right_market.description,
                    "rules": right_market.rules,
                    "end_date": right_market.end_date,
                    "topic": right_market.topic,
                },
            },
            sort_keys=True,
        )

    @staticmethod
    def _extract_message_content(payload: Any) -> str:
        if not isinstance(payload, dict):
            raise ValueError("LLM response payload must be a JSON object")

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("LLM response payload must include choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("LLM response payload has an invalid first choice")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("LLM response payload must include message content")

        content = message.get("content")
        if isinstance(content, str):
            cleaned = content.strip()
            if cleaned:
                return cleaned
        raise ValueError("LLM response payload must include a non-empty string content field")


@dataclass(slots=True)
class DeepSeekLLMProviderStub(LLMProvider):
    """DeepSeek-oriented stub that returns deterministic edge predictions."""

    model_name: str = "deepseek-stub"

    def infer_dependency(
        self,
        left_market: MarketDescriptor,
        right_market: MarketDescriptor,
    ) -> LLMDependencyPrediction:
        left = left_market.question.lower()
        right = right_market.question.lower()
        if self._looks_mutually_exclusive(left, right):
            return LLMDependencyPrediction(
                edge_type="mutually_exclusive",
                confidence=0.95,
                rationale=f"{self.model_name}: lexical exclusivity heuristic matched",
            )

        return LLMDependencyPrediction(
            edge_type="related",
            confidence=0.6,
            rationale=f"{self.model_name}: default related classification",
        )

    @staticmethod
    def _looks_mutually_exclusive(left: str, right: str) -> bool:
        conflict_terms = (
            ("yes", "no"),
            ("win", "lose"),
            ("democrat", "republican"),
            ("candidate a", "candidate b"),
        )
        for a, b in conflict_terms:
            if (a in left and b in right) or (b in left and a in right):
                return True
        return False
