from __future__ import annotations

from typing import TypeAlias

from ..contracts import MarketDescriptor

MarketPair: TypeAlias = tuple[MarketDescriptor, MarketDescriptor]
