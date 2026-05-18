from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar


class UnknownVenueAdapterError(KeyError):
    """Raised when a venue id does not resolve to a registered factory."""


_T = TypeVar("_T", bound=type)


class VenueAdapterRegistry:
    def __init__(self) -> None:
        self._classes: dict[str, type] = {}

    def register(self, venue_id: str, cls: type) -> None:
        if venue_id in self._classes:
            raise ValueError(f"venue_adapter id {venue_id!r} already registered")
        self._classes[venue_id] = cls

    def get(self, venue_id: str) -> type:
        try:
            return self._classes[venue_id]
        except KeyError as exc:
            raise UnknownVenueAdapterError(venue_id) from exc

    def list(self) -> list[str]:
        return list(self._classes)


default_registry = VenueAdapterRegistry()


def venue_adapter(
    venue_id: str, *, registry: VenueAdapterRegistry | None = None
) -> Callable[[_T], _T]:
    target = registry if registry is not None else default_registry

    def _decorator(cls: _T) -> _T:
        target.register(venue_id, cls)
        return cls

    return _decorator
