from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from math import sqrt
from pathlib import Path
from typing import Any, Sequence
from collections import defaultdict

from ..contracts import MarketDescriptor
from ..interfaces.topic_assigner import TopicAssigner
from ..providers import build_embedding_provider


def canonicalize_end_date(value: str) -> str:
    """Convert end date values to canonical YYYY-MM-DD for gating."""
    if not value:
        return ""

    cleaned = value.strip()
    try:
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        return datetime.fromisoformat(cleaned).date().isoformat()
    except ValueError:
        return cleaned[:10]


@dataclass(slots=True)
class _TopicAssignerSettings:
    embedding_provider: str = "stub"
    embedding_model: str = "linq-embed-mistral-stub"
    embedding_batch_size: int = 16
    cluster_threshold: float = 0.82
    min_cluster_size: int = 2


class DefaultTopicAssigner(TopicAssigner):
    """Assign topics from embedding clusters, with deterministic fallback."""

    def __init__(self, embedding_provider: Any | None = None) -> None:
        self._embedding_provider = embedding_provider

    def assign_topics(
        self,
        markets: Sequence[MarketDescriptor],
        config: Any | None = None,
    ) -> list[MarketDescriptor]:
        if not markets:
            return []

        settings = self._resolve_settings(config)
        if settings.embedding_batch_size <= 0:
            raise ValueError("embedding_batch_size must be greater than zero")
        provider = self._embedding_provider or build_embedding_provider(config)
        ordered_markets = sorted(
            enumerate(markets),
            key=lambda item: (item[1].market_id, item[1].condition_id, item[0]),
        )
        texts = [self._build_embedding_text(market) for _, market in ordered_markets]

        try:
            embeddings = self._embed_texts(
                provider, texts, settings.embedding_batch_size
            )
        except Exception:
            return [
                self._copy_market(market, self._fallback_topic(market))
                for market in markets
            ]

        clusters = self._cluster_markets(
            ordered_markets,
            embeddings,
            settings.cluster_threshold,
        )
        topics_by_market_id = self._build_cluster_topics(
            ordered_markets,
            clusters,
            settings.min_cluster_size,
        )
        return [
            self._copy_market(
                market,
                topics_by_market_id.get(market.market_id, self._fallback_topic(market)),
            )
            for market in markets
        ]

    def _resolve_settings(self, config: Any | None) -> _TopicAssignerSettings:
        params = getattr(config, "params", {}) if config is not None else {}
        if not isinstance(params, dict):
            params = {}

        embeddings_params = (
            params.get("embeddings")
            if isinstance(params.get("embeddings"), dict)
            else {}
        )
        topic_assigner_params = (
            params.get("topic_assigner")
            if isinstance(params.get("topic_assigner"), dict)
            else {}
        )
        topic_clustering_params = (
            params.get("topic_clustering")
            if isinstance(params.get("topic_clustering"), dict)
            else {}
        )

        embedding_provider = (
            getattr(config, "embedding_provider", "stub")
            if config is not None
            else "stub"
        )
        embedding_model = (
            getattr(config, "embedding_model", "linq-embed-mistral-stub")
            if config is not None
            else "linq-embed-mistral-stub"
        )
        return _TopicAssignerSettings(
            embedding_provider=self._coerce_str(
                self._first_str(
                    (
                        embeddings_params,
                        topic_assigner_params,
                        topic_clustering_params,
                        params,
                    ),
                    "embedding_provider",
                    "provider",
                    "provider_name",
                ),
                str(embedding_provider),
            ),
            embedding_model=self._coerce_str(
                self._first_str(
                    (
                        embeddings_params,
                        topic_assigner_params,
                        topic_clustering_params,
                        params,
                    ),
                    "embedding_model",
                    "model",
                ),
                str(embedding_model),
            ),
            embedding_batch_size=self._coerce_int(
                self._first_int(
                    (
                        topic_assigner_params,
                        topic_clustering_params,
                        embeddings_params,
                        params,
                    ),
                    "embedding_batch_size",
                    "batch_size",
                ),
                16,
            ),
            cluster_threshold=self._coerce_float(
                self._first_float(
                    (
                        topic_assigner_params,
                        topic_clustering_params,
                        embeddings_params,
                        params,
                    ),
                    "cluster_threshold",
                    "embedding_cluster_threshold",
                ),
                0.82,
            ),
            min_cluster_size=self._coerce_int(
                self._first_int(
                    (
                        topic_assigner_params,
                        topic_clustering_params,
                        embeddings_params,
                        params,
                    ),
                    "min_cluster_size",
                ),
                2,
            ),
        )

    def _embed_texts(
        self,
        provider: Any,
        texts: Sequence[str],
        batch_size: int,
    ) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = list(texts[start : start + batch_size])
            batch_vectors = provider.embed_texts(batch)
            if len(batch_vectors) != len(batch):
                raise ValueError(
                    "embedding provider returned a mismatched number of vectors"
                )
            embeddings.extend(batch_vectors)
        return embeddings

    def _cluster_markets(
        self,
        ordered_markets: Sequence[tuple[int, MarketDescriptor]],
        embeddings: Sequence[Sequence[float]],
        threshold: float,
    ) -> list[list[int]]:
        if len(ordered_markets) != len(embeddings):
            raise ValueError("embedding count does not match market count")

        normalized = [self._normalize_embedding(vector) for vector in embeddings]
        parents = list(range(len(normalized)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            root_left = find(left)
            root_right = find(right)
            if root_left == root_right:
                return
            if root_left < root_right:
                parents[root_right] = root_left
            else:
                parents[root_left] = root_right

        for left_index in range(len(normalized)):
            for right_index in range(left_index + 1, len(normalized)):
                if (
                    self._cosine_similarity(
                        normalized[left_index], normalized[right_index]
                    )
                    >= threshold
                ):
                    union(left_index, right_index)

        grouped: dict[int, list[int]] = defaultdict(list)
        for index in range(len(normalized)):
            grouped[find(index)].append(index)

        clusters = [sorted(indices) for indices in grouped.values()]
        clusters.sort(
            key=lambda indices: tuple(
                ordered_markets[index][1].market_id for index in indices
            )
        )
        return clusters

    def _build_cluster_topics(
        self,
        ordered_markets: Sequence[tuple[int, MarketDescriptor]],
        clusters: Sequence[Sequence[int]],
        min_cluster_size: int,
    ) -> dict[str, str]:
        topics_by_market_id: dict[str, str] = {}
        cluster_number = 1
        for cluster in clusters:
            if len(cluster) < min_cluster_size:
                continue
            topic = f"topic-{cluster_number:02d}"
            cluster_number += 1
            for index in cluster:
                topics_by_market_id[ordered_markets[index][1].market_id] = topic
        return topics_by_market_id

    @staticmethod
    def _build_embedding_text(market: MarketDescriptor) -> str:
        parts = [market.question, market.description, market.rules]
        cleaned = [
            part.strip() for part in parts if isinstance(part, str) and part.strip()
        ]
        return "\n".join(cleaned)

    @staticmethod
    def _copy_market(market: MarketDescriptor, topic: str) -> MarketDescriptor:
        return MarketDescriptor(
            market_id=market.market_id,
            condition_id=market.condition_id,
            question=market.question,
            description=market.description,
            rules=market.rules,
            end_date=market.end_date,
            topic=topic,
            token_ids=list(market.token_ids),
        )

    @staticmethod
    def _fallback_topic(market: MarketDescriptor) -> str:
        topic = (market.topic or "").strip()
        return topic or "unassigned"

    @staticmethod
    def _normalize_embedding(vector: Sequence[float]) -> list[float]:
        values = [float(value) for value in vector]
        if not values:
            raise ValueError("embedding vectors must not be empty")
        if not all(isfinite(value) for value in values):
            raise ValueError("embedding vectors must contain finite values")
        norm = sqrt(sum(value * value for value in values))
        if norm <= 0:
            return [0.0 for _ in values]
        return [value / norm for value in values]

    @staticmethod
    def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
        if len(left) != len(right):
            raise ValueError("embedding vectors must have the same length")
        if not left:
            return 0.0
        return sum(
            left_value * right_value for left_value, right_value in zip(left, right)
        )

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_float(value: Any, default: float) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_str(value: Any, default: str) -> str:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or default
        return default

    @staticmethod
    def _first_str(sources: Sequence[Any], *keys: str) -> Any:
        for source in sources:
            if not isinstance(source, dict):
                continue
            for key in keys:
                value = source.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return None

    @staticmethod
    def _first_int(sources: Sequence[Any], *keys: str) -> Any:
        for source in sources:
            if not isinstance(source, dict):
                continue
            for key in keys:
                if key in source:
                    return source.get(key)
        return None

    @staticmethod
    def _first_float(sources: Sequence[Any], *keys: str) -> Any:
        for source in sources:
            if not isinstance(source, dict):
                continue
            for key in keys:
                if key in source:
                    return source.get(key)
        return None
