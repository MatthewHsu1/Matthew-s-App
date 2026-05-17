"""Tests for engine.cache_loader.build_engine_from_cache.

Pins the contract:
  - Uses HistoricalDataCache to fetch both 1-DAY-LAST and 1-MINUTE-LAST bars.
  - Translates DataFrame rows into Nautilus Bar objects per BarType.
  - Returns a BacktestEngine with venue + Equity + bars wired in.
  - Multi-instrument: every instrument's BarTypes are loaded.
  - Second invocation with the same dates hits the cache (no source recall).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from alpha_engine.config.paths import EnvPaths
from alpha_engine.contracts.config import (
    DataConfig,
    EnvConfig,
    ReportingConfig,
    RiskConfig,
    StrategyConfig,
    VenueConfig,
)
from alpha_engine.contracts.mode import Mode
from alpha_engine.data.registry import DataSourceRegistry


def _make_cfg(
    *,
    instruments: tuple[str, ...] = ("MSFT.NASDAQ",),
    start: str = "2025-01-02",
    end: str = "2025-01-05",
) -> EnvConfig:
    return EnvConfig(
        env_name="cache_loader_test",
        mode=Mode.BACKTEST,
        strategy=StrategyConfig(
            ref="bband_volume_setup",
            params={"tranche_size_qty": 10, "minute_bar_step": 1},
        ),
        venue=VenueConfig(id="nasdaq_sim", account_kind="paper"),
        data=DataConfig(
            live_source="venue",
            historical_source="alpaca_historical",
            instruments=instruments,
            bar_spec="1-DAY-LAST",
            start_date=start,
            end_date=end,
        ),
        risk=RiskConfig(),
        reporting=ReportingConfig(timezone="UTC"),
    )


class _CountingStubSource:
    """A registered fake `alpaca_historical` source.

    Returns deterministic OHLCV for daily and minute bar_specs. Tracks calls.
    """

    instances: list["_CountingStubSource"] = []

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        _CountingStubSource.instances.append(self)

    def fetch(self, instrument_id, bar_spec, start, end):
        self.calls.append((instrument_id, bar_spec))
        spec_upper = bar_spec.upper()
        if "DAY" in spec_upper:
            ts_index = pd.date_range(start=start, end=end, freq="1D", tz="UTC")
        else:
            ts_index = pd.date_range(start=start, end=end, freq="1min", tz="UTC")
        n = len(ts_index)
        if n == 0:
            return _empty_bars()
        base = 100.0 + np.arange(n, dtype="float64") * 0.1
        return pd.DataFrame({
            "ts": ts_index.view("int64"),
            "open": base,
            "high": base + 0.5,
            "low": base - 0.5,
            "close": base + 0.1,
            "volume": np.full(n, 1000, dtype="int64"),
        })


def _empty_bars() -> pd.DataFrame:
    return pd.DataFrame({
        "ts": pd.Series([], dtype="int64"),
        "open": pd.Series([], dtype="float64"),
        "high": pd.Series([], dtype="float64"),
        "low": pd.Series([], dtype="float64"),
        "close": pd.Series([], dtype="float64"),
        "volume": pd.Series([], dtype="int64"),
    })


@pytest.fixture
def stub_registered(monkeypatch):
    """Register a fresh stub source class into the default registry per test."""
    from alpha_engine.data import registry as registry_mod

    # Use a temp instance and patch _resolve_source by injecting into the cache.
    # We register a class that returns a fresh instance each construction.
    _CountingStubSource.instances = []
    cls = type("StubSourceCls", (_CountingStubSource,), {})
    saved = registry_mod.default_registry.get("alpaca_historical") \
        if "alpaca_historical" in registry_mod.default_registry.list() else None
    registry_mod.default_registry.replace("alpaca_historical", cls)
    yield cls
    if saved is not None:
        registry_mod.default_registry.replace("alpaca_historical", saved)


def test_builds_engine_with_one_instrument_two_bar_streams(
    tmp_path: Path, stub_registered, monkeypatch,
) -> None:
    from alpha_engine.engine import cache_loader

    monkeypatch.setattr(cache_loader, "_cache_root", lambda: tmp_path / "cache")

    paths = EnvPaths(envs_root=tmp_path / "envs", env_name="cache_loader_test")
    cfg = _make_cfg()

    engine, instrument_ids = cache_loader.build_engine_from_cache(cfg, paths)
    assert len(instrument_ids) == 1
    assert str(instrument_ids[0]) == "MSFT.NASDAQ"

    # The stub was called once per bar_spec for the one instrument.
    assert len(_CountingStubSource.instances) >= 1
    all_calls = [c for inst in _CountingStubSource.instances for c in inst.calls]
    specs_called = {spec for (_iid, spec) in all_calls}
    assert specs_called == {"1-DAY-LAST", "1-MINUTE-LAST"}
    # Bare symbol passed to source (not full instrument_id with venue).
    assert all(iid == "MSFT" for (iid, _spec) in all_calls)


def test_multi_instrument_loads_all_bar_types(
    tmp_path: Path, stub_registered, monkeypatch,
) -> None:
    from alpha_engine.engine import cache_loader

    monkeypatch.setattr(cache_loader, "_cache_root", lambda: tmp_path / "cache")

    paths = EnvPaths(envs_root=tmp_path / "envs", env_name="cache_loader_test")
    cfg = _make_cfg(instruments=("MSFT.NASDAQ", "AAPL.NASDAQ"))

    engine, instrument_ids = cache_loader.build_engine_from_cache(cfg, paths)
    assert {str(i) for i in instrument_ids} == {"MSFT.NASDAQ", "AAPL.NASDAQ"}

    all_calls = [c for inst in _CountingStubSource.instances for c in inst.calls]
    symbols_called = {iid for (iid, _spec) in all_calls}
    assert symbols_called == {"MSFT", "AAPL"}


def test_second_call_hits_cache_no_resource_recall(
    tmp_path: Path, stub_registered, monkeypatch,
) -> None:
    from alpha_engine.engine import cache_loader

    monkeypatch.setattr(cache_loader, "_cache_root", lambda: tmp_path / "cache")

    paths = EnvPaths(envs_root=tmp_path / "envs", env_name="cache_loader_test")
    cfg = _make_cfg()

    cache_loader.build_engine_from_cache(cfg, paths)
    first_call_count = sum(len(i.calls) for i in _CountingStubSource.instances)
    assert first_call_count > 0

    # Reset; second build with same dates should not hit the stub at all.
    _CountingStubSource.instances = []
    cache_loader.build_engine_from_cache(cfg, paths)
    second_call_count = sum(len(i.calls) for i in _CountingStubSource.instances)
    assert second_call_count == 0, (
        f"Second build should hit cache; saw {second_call_count} source calls"
    )


def test_bare_symbol_for_source_unknown_raises_not_implemented() -> None:
    """An unwired source must fail loud rather than silently passing the wrong string."""
    from nautilus_trader.model.identifiers import InstrumentId

    from alpha_engine.engine.cache_loader import _bare_symbol_for_source

    iid = InstrumentId.from_str("MSFT.NASDAQ")
    with pytest.raises(NotImplementedError, match="ibkr_historical"):
        _bare_symbol_for_source("ibkr_historical", iid)


def test_bare_symbol_for_source_alpaca_returns_bare_ticker() -> None:
    from nautilus_trader.model.identifiers import InstrumentId

    from alpha_engine.engine.cache_loader import _bare_symbol_for_source

    iid = InstrumentId.from_str("MSFT.NASDAQ")
    assert _bare_symbol_for_source("alpaca_historical", iid) == "MSFT"


def test_dataframe_to_bar_preserves_ohlcv_and_ts(
    tmp_path: Path, stub_registered, monkeypatch,
) -> None:
    """Spot-check a single converted Bar matches its source DataFrame row."""
    from alpha_engine.engine import cache_loader

    monkeypatch.setattr(cache_loader, "_cache_root", lambda: tmp_path / "cache")

    paths = EnvPaths(envs_root=tmp_path / "envs", env_name="cache_loader_test")
    cfg = _make_cfg()

    engine, _ids = cache_loader.build_engine_from_cache(cfg, paths)

    # Inspect engine data: Nautilus stores it on engine.data property.
    # We use the engine's data buffer to verify at least one daily bar landed.
    bars = list(engine.data)
    # Some bars must exist (sum across daily + minute streams).
    assert len(bars) > 0
    # Pick a daily bar and verify O/H/L/C/V round-trip from the stub source.
    from nautilus_trader.model.enums import BarAggregation

    daily_bars = [
        b for b in bars
        if b.bar_type.spec.aggregation == BarAggregation.DAY
    ]
    assert len(daily_bars) > 0
    sample = daily_bars[0]
    # Stub source: open == 100.0 for first bar.
    assert float(sample.open) == pytest.approx(100.0, abs=0.01)
    assert float(sample.high) == pytest.approx(100.5, abs=0.01)
    assert float(sample.low) == pytest.approx(99.5, abs=0.01)
    assert float(sample.close) == pytest.approx(100.1, abs=0.01)
    assert int(sample.volume) == 1000
    assert sample.ts_event > 0
