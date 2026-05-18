from __future__ import annotations

import pytest

import alpha_engine.adapters  # noqa: F401
from alpha_engine.adapters.ibkr import IbkrVenueFactory
from alpha_engine.adapters.registry import default_registry
from alpha_engine.contracts.config import VenueConfig
from alpha_engine.contracts.mode import Mode


def _venue(account_kind="paper"):
    return VenueConfig(
        id="ibkr",
        account_kind=account_kind,
        gateway_host="host-gateway",
        gateway_port_paper=4002,
        gateway_port_live=4001,
        account_id_env="IBKR_ACCOUNT_ID",
        username_env="IBKR_USERNAME",
        password_env="IBKR_PASSWORD",
    )


def test_factory_registered_as_ibkr():
    assert "ibkr" in default_registry.list()


def test_paper_mode_selects_paper_port(monkeypatch):
    monkeypatch.setenv("IBKR_ACCOUNT_ID", "DU123456")
    monkeypatch.setenv("IBKR_USERNAME", "u")
    monkeypatch.setenv("IBKR_PASSWORD", "p")
    factory = IbkrVenueFactory()
    cfg = factory.data_client_config(_venue(), Mode.PAPER)
    port_attr = "ibg_port"
    assert getattr(cfg, port_attr) == 4002


def test_live_mode_selects_live_port(monkeypatch):
    monkeypatch.setenv("IBKR_ACCOUNT_ID", "U123456")
    monkeypatch.setenv("IBKR_USERNAME", "u")
    monkeypatch.setenv("IBKR_PASSWORD", "p")
    factory = IbkrVenueFactory()
    cfg = factory.exec_client_config(_venue(account_kind="live"), Mode.LIVE)
    port_attr = "ibg_port"
    assert getattr(cfg, port_attr) == 4001


def test_missing_creds_raises(monkeypatch):
    monkeypatch.delenv("IBKR_ACCOUNT_ID", raising=False)
    factory = IbkrVenueFactory()
    with pytest.raises(Exception, match="IBKR_ACCOUNT_ID"):
        factory.exec_client_config(_venue(), Mode.PAPER)
