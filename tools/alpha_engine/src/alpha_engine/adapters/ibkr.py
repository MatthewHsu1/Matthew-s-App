"""IBKR venue shim — translates our VenueConfig → Nautilus IBKR configs.

Field names are pinned by tests/preflight/test_ibkr_config_field_names.py.
If that pre-flight changes, this file must change in lockstep.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from nautilus_trader.adapters.interactive_brokers.config import (
    InteractiveBrokersDataClientConfig,
    InteractiveBrokersExecClientConfig,
    InteractiveBrokersInstrumentProviderConfig,
)
from nautilus_trader.adapters.interactive_brokers.factories import (
    InteractiveBrokersLiveDataClientFactory,
    InteractiveBrokersLiveExecClientFactory,
)

from alpha_engine.adapters.registry import venue_adapter
from alpha_engine.config.secrets import resolve_required_env_vars
from alpha_engine.contracts.config import VenueConfig
from alpha_engine.contracts.mode import Mode


def _port_for(venue_cfg: VenueConfig, mode: Mode) -> int:
    if mode is Mode.LIVE:
        return venue_cfg.gateway_port_live
    return venue_cfg.gateway_port_paper


def _resolve_creds(venue_cfg: VenueConfig) -> dict[str, str]:
    return resolve_required_env_vars({
        "account_id": venue_cfg.account_id_env,
        "username": venue_cfg.username_env,
        "password": venue_cfg.password_env,
    })


@venue_adapter("ibkr")
class IbkrVenueFactory:
    """Builds Nautilus IBKR client configs from our EnvConfig.

    `data_client_factory_cls` / `exec_client_factory_cls` expose the Nautilus
    factory classes the TradingNode needs at registration time (Task 28).
    """

    @property
    def data_client_factory_cls(self) -> type:
        return InteractiveBrokersLiveDataClientFactory

    @property
    def exec_client_factory_cls(self) -> type:
        return InteractiveBrokersLiveExecClientFactory

    def data_client_config(
        self, venue_cfg: VenueConfig, mode: Mode
    ) -> InteractiveBrokersDataClientConfig:
        creds = _resolve_creds(venue_cfg)
        port = _port_for(venue_cfg, mode)
        return InteractiveBrokersDataClientConfig(
            ibg_host=venue_cfg.gateway_host,
            ibg_port=port,
            ibg_client_id=1,
            instrument_provider=InteractiveBrokersInstrumentProviderConfig(),
        )

    def exec_client_config(
        self, venue_cfg: VenueConfig, mode: Mode
    ) -> InteractiveBrokersExecClientConfig:
        creds = _resolve_creds(venue_cfg)
        port = _port_for(venue_cfg, mode)
        return InteractiveBrokersExecClientConfig(
            ibg_host=venue_cfg.gateway_host,
            ibg_port=port,
            ibg_client_id=1,
            account_id=creds["account_id"],
            instrument_provider=InteractiveBrokersInstrumentProviderConfig(),
        )
