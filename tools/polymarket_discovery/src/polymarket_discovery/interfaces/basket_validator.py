from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from ..contracts import BasketItem


class BasketValidator(Protocol):
    def validate(self, baskets: Sequence[BasketItem], config: Any | None = None) -> None:
        """Raise a ValueError when baskets violate invariants."""
