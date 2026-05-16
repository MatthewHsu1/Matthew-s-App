"""IBKR historical bars source.

The Nautilus IBKR adapter's historical client is wrapped behind a thin protocol
(`_HistoricalClientProto`) so unit tests can inject a fake. The default `_make_client`
constructs Nautilus's real client — that path is only exercised in Phase 3's E2E
recipe (real IBKR Gateway required).
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Protocol

import pandas as pd

from alpha_engine.data.registry import data_source


class IbkrPacingViolation(RuntimeError):
    """Raised when IBKR rejects a request for exceeding pacing limits."""


class _HistoricalClientProto(Protocol):
    def historical_bars(
        self, *, instrument_id: str, bar_spec: str, start: datetime, end: datetime
    ) -> pd.DataFrame: ...


def _make_default_client() -> _HistoricalClientProto:
    """Lazy real-client construction. Only called on first real fetch.

    Phase 2 leaves this as a thin shim around Nautilus's IBKR historical request
    plumbing. The Phase 3 E2E recipe exercises it for real.
    """
    raise NotImplementedError(
        "Real IBKR historical client wiring is Phase 3's E2E recipe. "
        "For unit/integration tests, inject a fake via IbkrHistoricalSource(client=...)."
    )


@data_source("ibkr_historical")
class IbkrHistoricalSource:
    PACING_COOLDOWN_S = 60.0

    def __init__(self, client: _HistoricalClientProto | None = None):
        # Cannot eagerly call _make_default_client in __init__ — that breaks
        # the @data_source registration (instantiated lazily by the cache).
        self._client_factory = _make_default_client
        self._client_override = client

    @property
    def _client(self) -> _HistoricalClientProto:
        if self._client_override is not None:
            return self._client_override
        self._client_override = self._client_factory()
        return self._client_override

    def fetch(
        self,
        instrument_id: str,
        bar_spec: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        try:
            return self._client.historical_bars(
                instrument_id=instrument_id,
                bar_spec=bar_spec,
                start=start,
                end=end,
            )
        except IbkrPacingViolation:
            time.sleep(self.PACING_COOLDOWN_S)
            return self._client.historical_bars(
                instrument_id=instrument_id,
                bar_spec=bar_spec,
                start=start,
                end=end,
            )
