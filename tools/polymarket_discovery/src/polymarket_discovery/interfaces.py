from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from .contracts import BasketItem
from .contracts import DependencyEdge
from .contracts import MarketDescriptor


MarketPair = tuple[MarketDescriptor, MarketDescriptor]


@dataclass(slots=True)
class LLMDependencyPrediction:
    edge_type: str
    confidence: float
    rationale: str


class MarketSource(Protocol):
    def fetch_active_markets(self, config: Any | None = None) -> list[MarketDescriptor]:
        """Return normalized active markets for offline discovery."""


class TopicAssigner(Protocol):
    def assign_topics(
        self,
        markets: Sequence[MarketDescriptor],
        config: Any | None = None,
    ) -> list[MarketDescriptor]:
        """Assign or normalize topics on each market descriptor."""


class CandidateReducer(Protocol):
    def reduce(
        self,
        markets: Sequence[MarketDescriptor],
        config: Any | None = None,
    ) -> list[MarketPair]:
        """Return candidate market pairs for dependency inference."""


class DependencyInferencer(Protocol):
    def infer_dependencies(
        self,
        market_pairs: Sequence[MarketPair],
        config: Any | None = None,
    ) -> list[DependencyEdge]:
        """Infer dependency edges for candidate market pairs."""


class BasketBuilder(Protocol):
    def build(
        self,
        markets: Sequence[MarketDescriptor],
        dependencies: Sequence[DependencyEdge],
        config: Any | None = None,
    ) -> list[BasketItem]:
        """Construct arbitrage baskets from inferred market dependencies."""


class BasketValidator(Protocol):
    def validate(self, baskets: Sequence[BasketItem], config: Any | None = None) -> None:
        """Raise a ValueError when baskets violate invariants."""


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return embedding vectors in input order."""


class LLMProvider(Protocol):
    def infer_dependency(
        self,
        left_market: MarketDescriptor,
        right_market: MarketDescriptor,
    ) -> LLMDependencyPrediction:
        """Infer dependency metadata for a pair of markets."""
