from __future__ import annotations

import pandas as pd


def total_pnl(pnl_daily: pd.DataFrame) -> float:
    if pnl_daily.empty:
        return 0.0
    
    return float(pnl_daily["net_pnl"].sum())


def max_drawdown(pnl_daily: pd.DataFrame) -> float:
    if pnl_daily.empty:
        return 0.0
    
    equity = pnl_daily["net_pnl"].cumsum()
    peak = equity.cummax()
    drawdown = equity - peak

    return float(drawdown.min())


def sharpe(pnl_daily: pd.DataFrame, *, periods_per_year: int = 252) -> float:
    if len(pnl_daily) < 2:
        return 0.0
    
    returns = pnl_daily["net_pnl"].astype(float)
    std = returns.std(ddof=1)

    if std == 0 or pd.isna(std):
        return 0.0
    
    mean = returns.mean()

    return float((mean / std) * (periods_per_year**0.5))


def _round_trips(trades: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp, float]]:
    """Pair each SELL with the most recent BUY on the same instrument. Naive FIFO."""

    open_lots: dict[str, list[tuple[pd.Timestamp, float, float]]] = {}
    rts: list[tuple[pd.Timestamp, pd.Timestamp, float]] = []

    for _, row in trades.sort_values("ts").iterrows():
        inst = row["instrument_id"]
        ts = row["ts"]
        qty = float(row["quantity"])
        px = float(row["price"])

        if row["side"] == "BUY":
            open_lots.setdefault(inst, []).append((ts, qty, px))
        else:  # SELL
            remaining = qty

            while remaining > 0 and open_lots.get(inst):
                buy_ts, buy_qty, buy_px = open_lots[inst][0]
                take = min(buy_qty, remaining)
                rts.append((buy_ts, ts, (px - buy_px) * take))
                buy_qty -= take
                remaining -= take

                if buy_qty == 0:
                    open_lots[inst].pop(0)
                else:
                    open_lots[inst][0] = (buy_ts, buy_qty, buy_px)
    return rts


def win_rate(trades: pd.DataFrame) -> float:
    rts = _round_trips(trades)

    if not rts:
        return 0.0
    
    wins = sum(1 for _, _, pnl in rts if pnl > 0)

    return wins / len(rts)


def avg_holding_seconds(trades: pd.DataFrame) -> float:
    rts = _round_trips(trades)

    if not rts:
        return 0.0
    
    total = sum((close - open_).total_seconds() for open_, close, _ in rts)
    
    return total / len(rts)
