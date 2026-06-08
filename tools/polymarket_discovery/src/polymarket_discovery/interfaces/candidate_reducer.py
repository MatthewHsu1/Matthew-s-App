from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from ..contracts import MarketDescriptor
from .market_pair import MarketPair


class CandidateReducer(Protocol):
    def reduce(
        self,
        markets: Sequence[MarketDescriptor],
        config: Any | None = None,
    ) -> list[MarketPair]:
        """Return candidate market pairs for dependency inference."""
