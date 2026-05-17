"""Integration test: BBand+Volume strategy boots and runs to completion.

Uses the synthetic-fixture engine builder to feed a single instrument with
1-minute bars. The strategy subscribes to both daily and minute bars but
will only see minute data — it should stay IDLE and submit zero orders,
proving the wrapper plumbs into Nautilus without raising.
"""

from __future__ import annotations

from alpha_engine.data.sources.synthetic_fixture import build_engine_with_synthetic_bars
from alpha_engine.strategies.bband_volume_setup.strategy import (
    BBandVolumeSetupNautilusParams,
    BBandVolumeSetupStrategy,
)


def test_strategy_boots_with_synthetic_minute_data_no_crash() -> None:
    engine, instrument_ids = build_engine_with_synthetic_bars(n_bars=30)
    params = BBandVolumeSetupNautilusParams(
        instrument_ids=[str(instrument_ids[0])],
        tranche_size_qty=10,
    )
    strategy = BBandVolumeSetupStrategy(config=params)
    engine.add_strategy(strategy)
    engine.run()
    # Strategy must reach the end of the bar stream without raising.
    # No assertions on trades — the synthetic fixture has no daily bars,
    # so the state machine never trips. This test pins the plumbing only.
