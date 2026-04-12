from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from math import sqrt
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping, Sequence
from collections import defaultdict

from .contracts import ArbitrageOutputDocument
from .contracts import BasketItem
from .contracts import DependencyEdge
from .contracts import MarketDescriptor
from .contracts import RunMetadata
from .interfaces import BasketBuilder
from .interfaces import BasketValidator
from .interfaces import CandidateReducer
from .interfaces import DependencyInferencer
from .interfaces import LLMProvider
from .interfaces import MarketPair
from .interfaces import TopicAssigner
from .providers import build_embedding_provider
from .providers import build_llm_provider
from .providers import configures_llm_provider
from .providers import validate_llm_dependency_prediction
from .serialization import validate_output_document as validate_serialized_output


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


@dataclass(slots=True)
class _BasketBuilderSettings:
    confidence_threshold: float = 0.9
    conservative_gating: bool = True


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
            embeddings = self._embed_texts(provider, texts, settings.embedding_batch_size)
        except Exception:
            return [self._copy_market(market, self._fallback_topic(market)) for market in markets]

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
            self._copy_market(market, topics_by_market_id.get(market.market_id, self._fallback_topic(market)))
            for market in markets
        ]

    def _resolve_settings(self, config: Any | None) -> _TopicAssignerSettings:
        params = getattr(config, "params", {}) if config is not None else {}
        if not isinstance(params, dict):
            params = {}

        topic_params: dict[str, Any] = {}
        for key in ("topic_assigner", "topic_clustering", "embeddings"):
            candidate = params.get(key)
            if isinstance(candidate, dict):
                topic_params = candidate
                break

        embedding_provider = getattr(config, "embedding_provider", "stub") if config is not None else "stub"
        embedding_model = getattr(config, "embedding_model", "linq-embed-mistral-stub") if config is not None else "linq-embed-mistral-stub"
        return _TopicAssignerSettings(
            embedding_provider=self._coerce_str(
                topic_params.get("embedding_provider", params.get("embedding_provider")),
                str(embedding_provider),
            ),
            embedding_model=self._coerce_str(
                topic_params.get("embedding_model", params.get("embedding_model")),
                str(embedding_model),
            ),
            embedding_batch_size=self._coerce_int(
                topic_params.get(
                    "embedding_batch_size",
                    topic_params.get("batch_size", params.get("embedding_batch_size", params.get("batch_size"))),
                ),
                16,
            ),
            cluster_threshold=self._coerce_float(
                topic_params.get(
                    "cluster_threshold",
                    topic_params.get(
                        "embedding_cluster_threshold",
                        params.get("cluster_threshold", params.get("embedding_cluster_threshold")),
                    ),
                ),
                0.82,
            ),
            min_cluster_size=self._coerce_int(
                topic_params.get("min_cluster_size", params.get("min_cluster_size")),
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
                raise ValueError("embedding provider returned a mismatched number of vectors")
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
                if self._cosine_similarity(normalized[left_index], normalized[right_index]) >= threshold:
                    union(left_index, right_index)

        grouped: dict[int, list[int]] = defaultdict(list)
        for index in range(len(normalized)):
            grouped[find(index)].append(index)

        clusters = [sorted(indices) for indices in grouped.values()]
        clusters.sort(key=lambda indices: tuple(ordered_markets[index][1].market_id for index in indices))
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
        cleaned = [part.strip() for part in parts if isinstance(part, str) and part.strip()]
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
        return sum(left_value * right_value for left_value, right_value in zip(left, right))

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


class TopicEndDateCandidateReducer(CandidateReducer):
    """Paper-aligned reducer: only compare markets sharing topic and end date."""

    def reduce(
        self,
        markets: Sequence[MarketDescriptor],
        config: Any | None = None,
    ) -> list[MarketPair]:
        buckets: dict[tuple[str, str], list[MarketDescriptor]] = {}
        for market in markets:
            topic_key = (market.topic or "").strip().lower()
            end_date_key = canonicalize_end_date(market.end_date)
            if not topic_key or not end_date_key:
                continue
            bucket_key = (topic_key, end_date_key)
            buckets.setdefault(bucket_key, []).append(market)

        pairs: list[MarketPair] = []
        for bucket_markets in buckets.values():
            for left, right in combinations(bucket_markets, 2):
                pairs.append((left, right))
        return pairs


class LLMDependencyInferencer(DependencyInferencer):
    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self._llm_provider = llm_provider

    def infer_dependencies(
        self,
        market_pairs: Sequence[MarketPair],
        config: Any | None = None,
    ) -> list[DependencyEdge]:
        provider = self._resolve_provider(config)
        edges: list[DependencyEdge] = []
        for left, right in market_pairs:
            prediction = validate_llm_dependency_prediction(provider.infer_dependency(left, right))
            edges.append(
                DependencyEdge(
                    edge_id=f"{left.market_id}__{right.market_id}",
                    edge_type=prediction.edge_type,
                    from_market_id=left.market_id,
                    to_market_id=right.market_id,
                    confidence=prediction.confidence,
                    rationale=prediction.rationale,
                ),
            )
        return edges

    def _resolve_provider(self, config: Any | None) -> LLMProvider:
        if self._llm_provider is not None and not configures_llm_provider(config):
            return self._llm_provider
        return build_llm_provider(config)


class DefaultBasketBuilder(BasketBuilder):
    """Build minimal basket definitions from inferred dependencies."""

    def build(
        self,
        markets: Sequence[MarketDescriptor],
        dependencies: Sequence[DependencyEdge],
        config: Any | None = None,
    ) -> list[BasketItem]:
        settings = self._resolve_settings(config)
        by_market_id = {market.market_id: market for market in markets}
        baskets: list[BasketItem] = []
        seen_edge_ids: set[str] = set()

        for edge in dependencies:
            if edge.edge_id in seen_edge_ids:
                continue
            seen_edge_ids.add(edge.edge_id)

            if not isfinite(edge.confidence):
                continue
            edge_type = edge.edge_type.strip().lower() if isinstance(edge.edge_type, str) else ""
            if settings.conservative_gating and edge_type == "related":
                continue
            if settings.conservative_gating and edge.confidence < settings.confidence_threshold:
                continue

            left = by_market_id.get(edge.from_market_id)
            right = by_market_id.get(edge.to_market_id)
            if left is None or right is None:
                continue

            token_ids = self._dedupe_token_ids([*left.token_ids, *right.token_ids])
            if not token_ids:
                continue
            baskets.append(
                BasketItem(
                    basket_id=f"basket-{edge.edge_id}",
                    token_ids=token_ids,
                    dependency_basis=[edge.edge_id],
                ),
            )

        return baskets

    def _resolve_settings(self, config: Any | None) -> _BasketBuilderSettings:
        params = getattr(config, "params", {}) if config is not None else {}
        if not isinstance(params, dict):
            params = {}

        basket_params: dict[str, Any] = {}
        for key in ("basket_builder", "basket"):
            candidate = params.get(key)
            if isinstance(candidate, dict):
                basket_params = candidate
                break

        return _BasketBuilderSettings(
            confidence_threshold=self._validate_confidence_threshold(
                self._coerce_float(
                    basket_params.get(
                        "confidence_threshold",
                        params.get("basket_confidence_threshold", params.get("confidence_threshold")),
                    ),
                    0.9,
                ),
            ),
            conservative_gating=self._coerce_bool(
                basket_params.get(
                    "conservative_gating",
                    params.get("basket_conservative_gating", params.get("conservative_gating")),
                ),
                True,
            ),
        )

    @staticmethod
    def _dedupe_token_ids(token_ids: Sequence[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for token_id in token_ids:
            if not isinstance(token_id, str):
                continue
            cleaned = token_id.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            deduped.append(cleaned)
        return deduped

    @staticmethod
    def _coerce_float(value: Any, default: float) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _validate_confidence_threshold(value: float) -> float:
        if not isfinite(value):
            raise ValueError("confidence_threshold must be finite and between 0 and 1 inclusive")
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence_threshold must be finite and between 0 and 1 inclusive")
        return value

    @staticmethod
    def _coerce_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return bool(value)
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"true", "1", "yes", "y", "on"}:
                return True
            if cleaned in {"false", "0", "no", "n", "off"}:
                return False
        return default


class DefaultBasketValidator(BasketValidator):
    def validate(self, baskets: Sequence[BasketItem], config: Any | None = None) -> None:
        for basket in baskets:
            if not basket.token_ids:
                raise ValueError(f"basket {basket.basket_id} has no token ids")
            normalized_token_ids = self._normalize_required_strings(basket.token_ids, f"basket {basket.basket_id} has invalid token ids")
            if len(set(normalized_token_ids)) != len(normalized_token_ids):
                raise ValueError(f"basket {basket.basket_id} has duplicate token ids")
            if not basket.dependency_basis:
                raise ValueError(f"basket {basket.basket_id} dependency_basis must not be empty")
            normalized_dependency_basis = self._normalize_required_strings(
                basket.dependency_basis,
                f"basket {basket.basket_id} has invalid dependency basis",
            )
            if len(set(normalized_dependency_basis)) != len(normalized_dependency_basis):
                raise ValueError(f"basket {basket.basket_id} has duplicate dependency basis entries")
            if not isfinite(basket.expected_sum) or basket.expected_sum <= 0:
                raise ValueError(f"basket {basket.basket_id} expected_sum must be > 0")

    @staticmethod
    def _normalize_required_strings(values: Sequence[str], error_message: str) -> list[str]:
        normalized: list[str] = []
        for value in values:
            if not isinstance(value, str):
                raise ValueError(error_message)
            cleaned = value.strip()
            if not cleaned:
                raise ValueError(error_message)
            normalized.append(cleaned)
        return normalized



def validate_output_document(payload: Mapping[str, Any]) -> None:
    """Compatibility wrapper around schema-backed validation."""
    validate_serialized_output(dict(payload))


def write_output_artifacts(
    output_document: ArbitrageOutputDocument,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = output_document.to_dict()
    validate_output_document(payload)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def run_phase1_pipeline(
    *,
    markets: Sequence[MarketDescriptor],
    run_metadata: RunMetadata,
    topic_assigner: TopicAssigner,
    candidate_reducer: CandidateReducer,
    dependency_inferencer: DependencyInferencer,
    basket_builder: BasketBuilder,
    basket_validator: BasketValidator,
    output_path: Path,
) -> ArbitrageOutputDocument:
    assigned_markets = topic_assigner.assign_topics(markets)
    candidate_pairs = candidate_reducer.reduce(assigned_markets)
    dependencies = dependency_inferencer.infer_dependencies(candidate_pairs)
    baskets = basket_builder.build(assigned_markets, dependencies)
    basket_validator.validate(baskets)

    output_document = ArbitrageOutputDocument(
        run_metadata=run_metadata,
        markets=list(assigned_markets),
        dependencies=dependencies,
        baskets=baskets,
    )

    write_output_artifacts(output_document, output_path)
    return output_document


def document_to_json(document: ArbitrageOutputDocument) -> str:
    payload = asdict(document)
    validate_output_document(payload)
    return json.dumps(payload, indent=2, sort_keys=True)
