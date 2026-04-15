from __future__ import annotations

from typing import Any
from typing import Protocol
from typing import Sequence

from ..contracts import BasketItem
from ..contracts import DependencyEdge
from ..contracts import MarketDescriptor


class BasketBuilder(Protocol):
    def build(
        self,
        markets: Sequence[MarketDescriptor],
        dependencies: Sequence[DependencyEdge],
        config: Any | None = None,
    ) -> list[BasketItem]:
        """Construct arbitrage baskets from inferred market dependencies."""
