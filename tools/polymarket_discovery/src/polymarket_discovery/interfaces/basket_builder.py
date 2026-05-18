from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from ..contracts import BasketItem, DependencyEdge, MarketDescriptor
from .llm_basket_group import LLMBasketGroup


class BasketBuilder(Protocol):
    def build(
        self,
        markets: Sequence[MarketDescriptor],
        dependencies: Sequence[DependencyEdge],
        config: Any | None = None,
        basket_groups: Sequence[LLMBasketGroup] = (),
    ) -> tuple[list[BasketItem], list[DependencyEdge]]:
        """Construct arbitrage baskets from inferred market dependencies.

        When *basket_groups* is non-empty the builder uses the LLM-inferred
        N-way groupings directly, synthesizing any ``DependencyEdge`` records
        needed to satisfy the ``dependency_basis`` serialization contract.

        Returns a 2-tuple ``(baskets, synthetic_edges)`` where
        *synthetic_edges* are new edges that must be merged into the
        document's dependency list.
        """
