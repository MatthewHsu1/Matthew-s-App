from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Sequence

from ..interfaces.embedding_provider import EmbeddingProvider
from ..net.http_json import request_json
from .settings import EmbeddingProviderSettings


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
class HTTPEmbeddingProvider(EmbeddingProvider):
    settings: EmbeddingProviderSettings

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
            payload = request_json(
                url=self.settings.base_url,
                timeout_seconds=self.settings.timeout_seconds,
                retry=self.settings.retry,
                method="POST",
                payload={
                    "model": self.settings.model_name,
                    "input": batch,
                },
                headers={
                    "User-Agent": "polymarket-discovery/0.1",
                    **({"Authorization": f"Bearer {self.settings.api_key}"} if self.settings.api_key else {}),
                },
            )
            vectors.extend(self._extract_embeddings(payload, len(batch)))
        return vectors

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
            embedding = item.get("embedding") if isinstance(item, dict) else item
            if not isinstance(embedding, list):
                raise ValueError("embedding response payload must include embedding vectors")
            vectors.append([float(value) for value in embedding])
        return vectors
