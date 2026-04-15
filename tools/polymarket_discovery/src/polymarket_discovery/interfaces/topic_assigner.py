from __future__ import annotations

from typing import Any
from typing import Protocol
from typing import Sequence

from ..contracts import MarketDescriptor


class TopicAssigner(Protocol):
    def assign_topics(
        self,
        markets: Sequence[MarketDescriptor],
        config: Any | None = None,
    ) -> list[MarketDescriptor]:
        """Assign or normalize topics on each market descriptor."""
