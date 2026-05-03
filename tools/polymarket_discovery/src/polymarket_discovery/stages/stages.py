from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..contracts import ArbitrageOutputDocument
from ..contracts import BasketItem
from ..contracts import DependencyEdge
from ..contracts import MarketDescriptor
from ..contracts import RunMetadata
from ..interfaces.basket_builder import BasketBuilder
from ..interfaces.basket_validator import BasketValidator
from ..interfaces.candidate_reducer import CandidateReducer
from ..interfaces.dependency_inferencer import DependencyInferencer
from ..interfaces.llm_basket_group import LLMBasketGroup
from ..interfaces.market_pair import MarketPair
from ..interfaces.topic_assigner import TopicAssigner
from ..serialization import validate_output_document as validate_serialized_output
from .dependency_inferencer import LLMDependencyInferencer
from .topic_assigner import canonicalize_end_date


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
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return output_path


def _group_markets_for_basket_inference(
    markets: Sequence[MarketDescriptor],
) -> list[list[MarketDescriptor]]:
    """Group markets by (topic, canonical_end_date) for per-bucket basket inference.

    Basket constituents must all resolve at the same time so that their prices
    can sum to 1.00 in a tradeable way.  Grouping only by topic (ignoring the
    end date) would let the LLM form baskets whose members resolve at different
    times — violating the convergence-to-1.00 invariant.
    """
    buckets: dict[tuple[str, str], list[MarketDescriptor]] = defaultdict(list)
    for market in markets:
        topic_key = (market.topic or "").strip().lower()
        end_date_key = canonicalize_end_date(market.end_date)
        if topic_key and end_date_key:
            buckets[(topic_key, end_date_key)].append(market)
    return [group for group in buckets.values() if len(group) >= 2]


def run_pipeline(
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

    # Basket-structure inference: ask the LLM to identify N-way groupings
    # per topic group.  This path is exercised only when the inferencer
    # supports it (i.e. is an LLMDependencyInferencer); otherwise basket
    # construction falls back to the pairwise-edge path.
    basket_groups: list[LLMBasketGroup] = []
    if isinstance(dependency_inferencer, LLMDependencyInferencer):
        topic_groups = _group_markets_for_basket_inference(assigned_markets)
        for topic_group in topic_groups:
            basket_groups.extend(dependency_inferencer.infer_basket_groups(topic_group))

    baskets, synthetic_edges = basket_builder.build(
        assigned_markets, dependencies, basket_groups=basket_groups
    )
    basket_validator.validate(baskets)

    all_dependencies = list(dependencies) + synthetic_edges

    output_document = ArbitrageOutputDocument(
        run_metadata=run_metadata,
        markets=list(assigned_markets),
        dependencies=all_dependencies,
        baskets=baskets,
    )

    write_output_artifacts(output_document, output_path)
    return output_document


def document_to_json(document: ArbitrageOutputDocument) -> str:
    payload = asdict(document)
    validate_output_document(payload)
    return json.dumps(payload, indent=2, sort_keys=True)
