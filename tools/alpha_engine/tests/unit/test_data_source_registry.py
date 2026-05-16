from __future__ import annotations

import pytest

from alpha_engine.data.registry import (
    DataSourceRegistry,
    UnknownDataSourceError,
    data_source,
)


def test_register_and_get():
    reg = DataSourceRegistry()

    @data_source("foo", registry=reg)
    class FooSource:
        pass

    assert reg.get("foo") is FooSource


def test_unknown_raises():
    reg = DataSourceRegistry()
    with pytest.raises(UnknownDataSourceError):
        reg.get("missing")


def test_duplicate_raises():
    reg = DataSourceRegistry()

    @data_source("dup", registry=reg)
    class A:
        pass

    with pytest.raises(ValueError, match="already registered"):
        @data_source("dup", registry=reg)
        class B:
            pass


def test_list_returns_registered_ids():
    reg = DataSourceRegistry()

    @data_source("a", registry=reg)
    class A:
        pass

    @data_source("b", registry=reg)
    class B:
        pass

    assert sorted(reg.list()) == ["a", "b"]


def test_default_registry_is_module_level_singleton():
    from alpha_engine.data.registry import default_registry
    assert isinstance(default_registry, DataSourceRegistry)
