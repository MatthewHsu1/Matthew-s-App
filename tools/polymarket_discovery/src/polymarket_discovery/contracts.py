from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


SchemaVersion = Literal["v1"]


@dataclass(slots=True)
class RunMetadata:
    run_id: str
    generated_at_utc: str
    market_source: str
    embedding_model: str
    llm_model: str
    schema_version: SchemaVersion = "v1"


@dataclass(slots=True)
class MarketDescriptor:
    market_id: str
    condition_id: str
    question: str
    description: str
    rules: str
    end_date: str
    topic: str
    token_ids: list[str]


@dataclass(slots=True)
class DependencyEdge:
    edge_id: str
    edge_type: str
    from_market_id: str
    to_market_id: str
    confidence: float
    rationale: str


@dataclass(slots=True)
class BasketItem:
    basket_id: str
    token_ids: list[str]
    expected_sum: float = 1.0
    dependency_basis: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ArbitrageOutputDocument:
    run_metadata: RunMetadata
    markets: list[MarketDescriptor]
    dependencies: list[DependencyEdge]
    baskets: list[BasketItem]
    schema_version: SchemaVersion = "v1"

    def to_dict(self) -> dict:
        return asdict(self)
