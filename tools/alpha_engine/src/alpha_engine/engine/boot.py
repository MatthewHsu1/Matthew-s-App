from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import subprocess
from pathlib import Path
from typing import Any

from alpha_engine.config.paths import EnvPaths
from alpha_engine.config.run_id import generate_run_id
from alpha_engine.contracts.config import EnvConfig
from alpha_engine.contracts.mode import Mode
from alpha_engine.logging_.bus_subscriber import attach_order_logger_to_msgbus
from alpha_engine.logging_.events import ENGINE_HALTED, ENGINE_STARTED
from alpha_engine.logging_.jsonl import PACKAGE_LOGGER_NAME, setup_jsonl_logging
from alpha_engine.reporting.summary import RunMetadata, write_summary
from alpha_engine.reporting.trades import TradeRecord, write_trades_parquet
from alpha_engine.strategies.registry import default_registry


@dataclass(frozen=True)
class BacktestResult:
    run_id: str
    summary_path: Path
    trades_path: Path
    halt_cause: str | None


def _git_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        )
        return out.strip()
    except Exception:
        return None


def run_backtest(
    *,
    cfg: EnvConfig,
    paths: EnvPaths,
    data_loader,  # callable: (EnvConfig, EnvPaths) -> (engine, instrument_ids)
) -> BacktestResult:
    """Boot a backtest run end-to-end and produce reports.

    `data_loader` is injected so tests can plug a fixture catalog without
    touching the real ParquetDataCatalog. Production callers pass the loader
    from the historical_source registry (deferred to Phase 1.5+).
    """
    if cfg.mode is not Mode.BACKTEST:
        raise ValueError(f"run_backtest called with mode={cfg.mode}")

    paths.ensure_dirs()
    run_id = generate_run_id(env_name=cfg.env_name, config_payload={
        "strategy_ref": cfg.strategy.ref,
        "strategy_params": cfg.strategy.params,
        "instruments": list(cfg.data.instruments),
    })

    engine_log = setup_jsonl_logging(
        path=paths.logs_dir / "engine.jsonl",
        run_id=run_id,
        env_name=cfg.env_name,
        mode=cfg.mode.value,
    )
    log = logging.getLogger(PACKAGE_LOGGER_NAME)
    git_sha = _git_sha()
    start_ts = datetime.now(tz=timezone.utc)
    log.info(
        ENGINE_STARTED,
        extra={
            "strategy_ref": cfg.strategy.ref,
            "instruments": list(cfg.data.instruments),
            "git_sha": git_sha,
        },
    )

    strategy_cls = default_registry.get(cfg.strategy.ref)
    halt_cause: str | None = None
    fills: list[TradeRecord] = []

    try:
        engine, instrument_ids = data_loader(cfg, paths)
        # Wire order logger to the engine's message bus *before* strategy runs.
        attach_order_logger_to_msgbus(
            engine.kernel.msgbus,
            path=paths.logs_dir / "orders.jsonl",
            run_id=run_id,
            env_name=cfg.env_name,
            mode=cfg.mode.value,
        )
        # Subscribe a fills collector for the trades.parquet report.
        def _collect(evt):
            from nautilus_trader.model.events import OrderFilled
            if isinstance(evt, OrderFilled):
                fills.append(
                    TradeRecord(
                        ts=datetime.fromtimestamp(evt.ts_event / 1e9, tz=timezone.utc),
                        run_id=run_id,
                        env_name=cfg.env_name,
                        strategy_class=strategy_cls.__name__,
                        instrument_id=str(evt.instrument_id),
                        side=evt.order_side.name,
                        quantity=float(evt.last_qty),
                        price=float(evt.last_px),
                        fees=float(getattr(evt, "commission", 0.0) or 0.0),
                    )
                )
        engine.kernel.msgbus.subscribe(topic="events.order.*", handler=_collect)

        # Strategy instantiation: Nautilus strategy configs take instrument_id,
        # so we splice it from the env config's first instrument.
        from alpha_engine.strategies.toy_buy_and_hold import ToyBuyAndHoldParams
        if cfg.strategy.ref == "toy_buy_and_hold":
            params = ToyBuyAndHoldParams(
                instrument_id=cfg.data.instruments[0],
                **cfg.strategy.params,
            )
        else:
            # Generic path: hand params straight through. Strategy author owns dataclass.
            params = cfg.strategy.params  # type: ignore[assignment]
        engine.add_strategy(strategy_cls(config=params))

        engine.run()

    except Exception as exc:
        halt_cause = "strategy_bug"
        log.exception("engine_exception", extra={"halt_cause": halt_cause, "error": str(exc)})

    end_ts = datetime.now(tz=timezone.utc)
    log.info(ENGINE_HALTED, extra={"halt_cause": halt_cause})

    # Build pnl_daily from fills (simple realized PnL by date).
    pnl_daily = _build_pnl_daily(fills)

    import pandas as pd
    trades_df = pd.DataFrame([t.__dict__ for t in fills])
    if not trades_df.empty:
        trades_df["ts"] = pd.to_datetime(trades_df["ts"], utc=True)

    summary_path = paths.reports_dir / f"summary_{run_id}.json"
    trades_path = paths.reports_dir / "trades.parquet"
    write_trades_parquet(trades_path, fills)
    write_summary(
        summary_path,
        meta=RunMetadata(
            run_id=run_id,
            env_name=cfg.env_name,
            mode=cfg.mode.value,
            strategy_class=strategy_cls.__name__,
            start_ts=start_ts,
            end_ts=end_ts,
            git_sha=git_sha,
            halt_cause=halt_cause,
        ),
        trades=trades_df if not trades_df.empty else _empty_trades_df(),
        pnl_daily=pnl_daily,
    )

    engine_log.flush()
    logging.getLogger(PACKAGE_LOGGER_NAME).removeHandler(engine_log)

    return BacktestResult(
        run_id=run_id,
        summary_path=summary_path,
        trades_path=trades_path,
        halt_cause=halt_cause,
    )


def _empty_trades_df():
    import pandas as pd
    return pd.DataFrame(
        columns=["ts", "run_id", "env_name", "strategy_class", "instrument_id",
                 "side", "quantity", "price", "fees"]
    )


def _build_pnl_daily(fills: list[TradeRecord]):
    """FIFO realized PnL bucketed by date. Phase 1 simplicity — no unrealized."""
    import pandas as pd
    if not fills:
        return pd.DataFrame(columns=["date", "net_pnl"])
    open_lots: dict[str, list[tuple[float, float]]] = {}
    by_day: dict[Any, float] = {}
    for f in sorted(fills, key=lambda t: t.ts):
        day = pd.Timestamp(f.ts.date())
        by_day.setdefault(day, 0.0)
        if f.side == "BUY":
            open_lots.setdefault(f.instrument_id, []).append((f.quantity, f.price))
        else:
            remaining = f.quantity
            while remaining > 0 and open_lots.get(f.instrument_id):
                buy_qty, buy_px = open_lots[f.instrument_id][0]
                take = min(buy_qty, remaining)
                by_day[day] += (f.price - buy_px) * take
                buy_qty -= take
                remaining -= take
                if buy_qty == 0:
                    open_lots[f.instrument_id].pop(0)
                else:
                    open_lots[f.instrument_id][0] = (buy_qty, buy_px)
    rows = [{"date": k, "net_pnl": v} for k, v in sorted(by_day.items())]
    return pd.DataFrame(rows)
