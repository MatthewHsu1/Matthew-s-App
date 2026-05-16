from __future__ import annotations

from typing import Callable, TypeVar


class UnknownDataSourceError(KeyError):
    """Raised when a data_source id does not resolve to a registered class."""


_T = TypeVar("_T", bound=type)


class DataSourceRegistry:
    def __init__(self) -> None:
        self._classes: dict[str, type] = {}

    def register(self, source_id: str, cls: type) -> None:
        if source_id in self._classes:
            raise ValueError(f"data_source id {source_id!r} already registered")
        self._classes[source_id] = cls

    def get(self, source_id: str) -> type:
        try:
            return self._classes[source_id]
        except KeyError as exc:
            raise UnknownDataSourceError(source_id) from exc

    def list(self) -> list[str]:
        return list(self._classes)


default_registry = DataSourceRegistry()


def data_source(
    source_id: str, *, registry: DataSourceRegistry | None = None
) -> Callable[[_T], _T]:
    target = registry if registry is not None else default_registry

    def _decorator(cls: _T) -> _T:
        target.register(source_id, cls)
        return cls

    return _decorator
