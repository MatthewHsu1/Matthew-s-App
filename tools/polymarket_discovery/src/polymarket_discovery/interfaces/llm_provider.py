from __future__ import annotations

from typing import Protocol, Sequence

from ..contracts import MarketDescriptor

from .llm_basket_group import LLMBasketGroup
from .llm_dependency_prediction import LLMDependencyPrediction


class LLMProvider(Protocol):
    def infer_dependency(
        self,
        left_market: MarketDescriptor,
        right_market: MarketDescriptor,
    ) -> LLMDependencyPrediction:
        """Infer dependency metadata for a pair of markets."""

    def infer_basket_groups(
        self,
        markets: Sequence[MarketDescriptor],
    ) -> list[LLMBasketGroup]:
        """Infer N-way basket groupings for a topic group of markets.

        Returns a list of :class:`LLMBasketGroup` objects, each identifying a
        set of markets whose combined YES tokens form a complete outcome set
        (probabilities summing toward 1.0).

        Providers that do not support basket inference should return ``[]``.
        """
        return []
