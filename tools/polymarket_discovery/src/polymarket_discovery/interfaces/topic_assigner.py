from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from ..contracts import MarketDescriptor


class TopicAssigner(Protocol):
    def assign_topics(
        self,
        markets: Sequence[MarketDescriptor],
        config: Any | None = None,
    ) -> list[MarketDescriptor]:
        """Assign or normalize topics on each market descriptor."""
