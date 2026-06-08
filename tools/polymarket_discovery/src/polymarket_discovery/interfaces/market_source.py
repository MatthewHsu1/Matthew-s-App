from __future__ import annotations

from typing import Any, Protocol

from ..contracts import MarketDescriptor


class MarketSource(Protocol):
    def fetch_active_markets(self, config: Any | None = None) -> list[MarketDescriptor]:
        """Return normalized active markets for offline discovery."""
