from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from ..contracts import DependencyEdge
from .market_pair import MarketPair


class DependencyInferencer(Protocol):
    def infer_dependencies(
        self,
        market_pairs: Sequence[MarketPair],
        config: Any | None = None,
    ) -> list[DependencyEdge]:
        """Infer dependency edges for candidate market pairs."""
