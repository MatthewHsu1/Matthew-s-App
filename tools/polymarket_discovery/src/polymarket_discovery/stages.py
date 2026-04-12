from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping, Sequence

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


class DefaultTopicAssigner(TopicAssigner):
    """Minimal topic assigner that normalizes empty topics."""

    def assign_topics(
        self,
        markets: Sequence[MarketDescriptor],
        config: Any | None = None,
    ) -> list[MarketDescriptor]:
        assigned: list[MarketDescriptor] = []
        for market in markets:
            topic = (market.topic or "").strip() or "unassigned"
            assigned.append(
                MarketDescriptor(
                    market_id=market.market_id,
                    condition_id=market.condition_id,
                    question=market.question,
                    description=market.description,
                    rules=market.rules,
                    end_date=market.end_date,
                    topic=topic,
                    token_ids=list(market.token_ids),
                ),
            )
        return assigned


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
    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm_provider = llm_provider

    def infer_dependencies(
        self,
        market_pairs: Sequence[MarketPair],
        config: Any | None = None,
    ) -> list[DependencyEdge]:
        edges: list[DependencyEdge] = []
        for left, right in market_pairs:
            prediction = self._llm_provider.infer_dependency(left, right)
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


class DefaultBasketBuilder(BasketBuilder):
    """Build minimal basket definitions from inferred dependencies."""

    def build(
        self,
        markets: Sequence[MarketDescriptor],
        dependencies: Sequence[DependencyEdge],
        config: Any | None = None,
    ) -> list[BasketItem]:
        by_market_id = {market.market_id: market for market in markets}
        baskets: list[BasketItem] = []

        for edge in dependencies:
            left = by_market_id.get(edge.from_market_id)
            right = by_market_id.get(edge.to_market_id)
            if left is None or right is None:
                continue

            token_ids = list(dict.fromkeys([*left.token_ids, *right.token_ids]))
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


class DefaultBasketValidator(BasketValidator):
    def validate(self, baskets: Sequence[BasketItem], config: Any | None = None) -> None:
        for basket in baskets:
            if not basket.token_ids:
                raise ValueError(f"basket {basket.basket_id} has no token ids")
            if len(set(basket.token_ids)) != len(basket.token_ids):
                raise ValueError(f"basket {basket.basket_id} has duplicate token ids")
            if basket.expected_sum <= 0:
                raise ValueError(f"basket {basket.basket_id} expected_sum must be > 0")


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
