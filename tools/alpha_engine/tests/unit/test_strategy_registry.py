from __future__ import annotations

import pytest

from alpha_engine.strategies.registry import (
    StrategyRegistry,
    UnknownStrategyError,
    strategy,
)


def test_register_and_lookup_via_decorator():
    reg = StrategyRegistry()

    @strategy("alpha_a", registry=reg)
    class A:
        pass

    @strategy("alpha_b", registry=reg)
    class B:
        pass

    assert reg.get("alpha_a") is A
    assert reg.get("alpha_b") is B
    assert sorted(reg.list()) == ["alpha_a", "alpha_b"]


def test_duplicate_ref_raises():
    reg = StrategyRegistry()

    @strategy("alpha_a", registry=reg)
    class A:
        pass

    with pytest.raises(ValueError, match="already registered"):

        @strategy("alpha_a", registry=reg)
        class B:
            pass


def test_unknown_ref_raises():
    reg = StrategyRegistry()
    with pytest.raises(UnknownStrategyError):
        reg.get("no_such_alpha")


def test_module_level_default_registry_present():
    from alpha_engine.strategies.registry import default_registry

    @strategy("test_default_ref")
    class _X:
        pass

    try:
        assert default_registry.get("test_default_ref") is _X
    finally:
        default_registry._classes.pop("test_default_ref", None)  # cleanup
