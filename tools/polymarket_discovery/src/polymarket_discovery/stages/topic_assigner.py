from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from ..contracts import MarketDescriptor
from ..interfaces.topic_assigner import TopicAssigner
from ..providers.factories import build_embedding_provider
from ..utils.coercion import coerce_float, coerce_int, coerce_str


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
    # Memory guard for the numpy pairwise similarity matrix.  The full
    # similarity matrix is n² float64 values: at n=5 000 that is ~200 MB
    # (fine); at n=20 000 it is ~3.2 GB (unsafe on most machines).  The
    # matrix is dropped immediately after edge extraction, so peak RSS is
    # bounded by this cap.  If this guard fires, add an upstream filter
    # (e.g. restrict the Gamma API call to specific topic tags) or switch
    # _cluster_markets to an ANN-based algorithm (e.g. FAISS) before
    # raising the cap.
    max_markets_for_clustering: int = 5_000


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
            settings.max_markets_for_clustering,
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
            embedding_provider=coerce_str(
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
            embedding_model=coerce_str(
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
            embedding_batch_size=coerce_int(
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
            cluster_threshold=coerce_float(
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
            min_cluster_size=coerce_int(
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
            max_markets_for_clustering=coerce_int(
                self._first_int(
                    (
                        topic_assigner_params,
                        topic_clustering_params,
                        params,
                    ),
                    "max_markets_for_clustering",
                ),
                5_000,
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
        max_markets: int = 5_000,
    ) -> list[list[int]]:
        if len(ordered_markets) != len(embeddings):
            raise ValueError("embedding count does not match market count")

        n = len(ordered_markets)
        if n > max_markets:
            raise ValueError(
                f"_cluster_markets received {n} markets but the configured cap is "
                f"{max_markets} (max_markets_for_clustering={max_markets}). "
                "The full similarity matrix would require ~"
                f"{n * n * 8 // (1024 * 1024)} MB of memory at this scale. "
                "Options: (1) add an upstream filter to reduce the market "
                "count before this stage, (2) raise max_markets_for_clustering in your "
                "DiscoveryConfig params only after confirming memory is available, "
                "or (3) switch _cluster_markets to an ANN-based algorithm (e.g. FAISS)."
            )

        # --- Numpy vectorized pairwise cosine similarity ---
        #
        # Stack embeddings into an (n, d) float64 matrix, L2-normalise each
        # row, then compute the full (n, n) similarity matrix with one BLAS
        # call (E @ E.T).  This runs in microseconds for n≤5 000 where the
        # equivalent pure-Python nested loop took minutes.
        #
        # After thresholding we extract only the upper-triangle indices
        # (k=1 excludes the diagonal) and immediately discard the full
        # matrix, keeping peak memory proportional to the edge list rather
        # than n².

        # Validate and convert to numpy; raises if ragged or empty.
        try:
            E = np.array(embeddings, dtype=np.float64)
        except ValueError as exc:
            raise ValueError("embedding vectors must all have the same length") from exc

        if E.ndim != 2 or E.shape[0] == 0:
            raise ValueError("embeddings must be a non-empty 2-D array")
        if E.shape[1] == 0:
            raise ValueError("embedding vectors must not be empty")

        if not np.all(np.isfinite(E)):
            raise ValueError("embedding vectors must contain finite values")

        # L2-normalise rows in-place (zero-norm rows become zero vectors).
        norms = np.linalg.norm(E, axis=1, keepdims=True)
        # Avoid division by zero: replace zero norms with 1.0 (row stays 0).
        norms[norms == 0.0] = 1.0
        E = E / norms

        # One matrix multiply gives the full cosine similarity matrix.
        S = E @ E.T  # shape (n, n), values in [-1, 1]

        # Extract upper-triangle pairs that meet the threshold (excluding
        # self-similarity on the diagonal).  This is the only data we keep;
        # S is released at the end of this scope.
        pairs = np.argwhere(np.triu(threshold <= S, k=1))
        del S  # free the n² matrix immediately

        # --- Union-Find on the edge list (pure Python, tiny at n≤5 000) ---
        parents = list(range(n))

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

        for left_index, right_index in pairs:
            union(int(left_index), int(right_index))

        grouped: dict[int, list[int]] = defaultdict(list)
        for index in range(n):
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
        parts = [market.question, market.description]
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
            end_date=market.end_date,
            topic=topic,
            token_ids=list(market.token_ids),
            resolution_source=market.resolution_source,
        )

    @staticmethod
    def _fallback_topic(market: MarketDescriptor) -> str:
        topic = (market.topic or "").strip()
        return topic or "unassigned"


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
