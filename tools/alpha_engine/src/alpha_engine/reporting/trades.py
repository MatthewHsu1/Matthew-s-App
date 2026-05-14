from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class TradeRecord:
    ts: datetime
    run_id: str
    env_name: str
    strategy_class: str
    instrument_id: str
    side: str
    quantity: float
    price: float
    fees: float


_COLUMNS = (
    "ts",
    "run_id",
    "env_name",
    "strategy_class",
    "instrument_id",
    "side",
    "quantity",
    "price",
    "fees",
)


def write_trades_parquet(path: Path, trades: Iterable[TradeRecord]) -> None:
    rows = [asdict(t) for t in trades]
    df = pd.DataFrame(rows, columns=list(_COLUMNS))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
