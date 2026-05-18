from __future__ import annotations

import pytest

from alpha_engine.adapters.registry import (
    UnknownVenueAdapterError,
    VenueAdapterRegistry,
    venue_adapter,
)


def test_register_and_get():
    reg = VenueAdapterRegistry()

    @venue_adapter("fake", registry=reg)
    class FakeFactory:
        pass

    assert reg.get("fake") is FakeFactory


def test_unknown_raises():
    reg = VenueAdapterRegistry()
    with pytest.raises(UnknownVenueAdapterError):
        reg.get("nothing")


def test_duplicate_raises():
    reg = VenueAdapterRegistry()

    @venue_adapter("dup", registry=reg)
    class A:
        pass

    with pytest.raises(ValueError, match="already registered"):
        @venue_adapter("dup", registry=reg)
        class B:
            pass


def test_default_registry_singleton():
    from alpha_engine.adapters.registry import default_registry
    assert isinstance(default_registry, VenueAdapterRegistry)
