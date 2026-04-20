from __future__ import annotations

import json
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
from ..interfaces.market_pair import MarketPair
from ..interfaces.topic_assigner import TopicAssigner
from ..serialization import validate_output_document as validate_serialized_output


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
