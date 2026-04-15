from __future__ import annotations

from typing import Any
from typing import Protocol
from typing import Sequence

from ..contracts import BasketItem


class BasketValidator(Protocol):
    def validate(self, baskets: Sequence[BasketItem], config: Any | None = None) -> None:
        """Raise a ValueError when baskets violate invariants."""
