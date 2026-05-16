"""Pre-flight: verify Nautilus IBKR config field names match what our IBKR shim writes.

If this test fails, the shim (adapters/ibkr.py) cannot be written as planned.
STOP and surface to the user/parent agent. Do not proceed to downstream tasks.
"""
from __future__ import annotations

import msgspec
import pytest

from nautilus_trader.adapters.interactive_brokers.config import (
    InteractiveBrokersDataClientConfig,
    InteractiveBrokersExecClientConfig,
)


# Fields our shim (Task 18) writes. Update this list ONLY if the spec also changes.
REQUIRED_DATA_FIELDS = {
    "ibg_host",
    "ibg_port",
    "ibg_client_id",
    "instrument_provider",
}

REQUIRED_EXEC_FIELDS = {
    "ibg_host",
    "ibg_port",
    "ibg_client_id",
    "account_id",
    "instrument_provider",
}


def _struct_fields(cls) -> set[str]:
    assert issubclass(cls, msgspec.Struct), f"{cls.__name__} is no longer msgspec.Struct"
    return set(cls.__struct_fields__)


def test_data_client_config_has_required_fields():
    fields = _struct_fields(InteractiveBrokersDataClientConfig)
    missing = REQUIRED_DATA_FIELDS - fields
    assert not missing, (
        f"InteractiveBrokersDataClientConfig is missing fields {missing}. "
        f"Available: {sorted(fields)}. The IBKR shim must be adjusted."
    )


def test_exec_client_config_has_required_fields():
    fields = _struct_fields(InteractiveBrokersExecClientConfig)
    missing = REQUIRED_EXEC_FIELDS - fields
    assert not missing, (
        f"InteractiveBrokersExecClientConfig is missing fields {missing}. "
        f"Available: {sorted(fields)}. The IBKR shim must be adjusted."
    )
