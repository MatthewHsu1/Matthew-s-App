from __future__ import annotations

from typing import Any
from typing import Protocol
from typing import Sequence

from ..contracts import DependencyEdge

from .market_pair import MarketPair


class DependencyInferencer(Protocol):
    def infer_dependencies(
        self,
        market_pairs: Sequence[MarketPair],
        config: Any | None = None,
    ) -> list[DependencyEdge]:
        """Infer dependency edges for candidate market pairs."""
