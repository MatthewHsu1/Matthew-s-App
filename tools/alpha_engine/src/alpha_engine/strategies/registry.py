from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar


class UnknownStrategyError(KeyError):
    """Raised when a strategy ref does not resolve to a registered class."""


_T = TypeVar("_T", bound=type)


class StrategyRegistry:
    def __init__(self) -> None:
        self._classes: dict[str, type] = {}

    def register(self, ref: str, cls: type) -> None:
        if ref in self._classes:
            raise ValueError(f"strategy ref {ref!r} already registered")
        self._classes[ref] = cls

    def get(self, ref: str) -> type:
        try:
            return self._classes[ref]
        except KeyError as exc:
            raise UnknownStrategyError(ref) from exc

    def list(self) -> list[str]:
        return list(self._classes)


default_registry = StrategyRegistry()


def strategy(ref: str, *, registry: StrategyRegistry | None = None) -> Callable[[_T], _T]:
    target = registry if registry is not None else default_registry

    def _decorator(cls: _T) -> _T:
        target.register(ref, cls)
        return cls

    return _decorator
