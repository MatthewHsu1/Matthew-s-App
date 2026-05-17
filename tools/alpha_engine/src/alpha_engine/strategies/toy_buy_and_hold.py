from __future__ import annotations

from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import AggregationSource, BarAggregation, OrderSide, PriceType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy, StrategyConfig

from alpha_engine.strategies.registry import strategy


# StrategyConfig is a msgspec.Struct — do NOT apply @dataclass; just subclass directly.
class ToyBuyAndHoldParams(StrategyConfig):
    instrument_id: str
    qty: int = 10
    buy_on_bar: int = 5


@strategy("toy_buy_and_hold")
class ToyBuyAndHold(Strategy):
    def __init__(self, config: ToyBuyAndHoldParams) -> None:
        super().__init__(config=config)
        self._params = config
        self._bar_count = 0
        self._instrument_id = InstrumentId.from_str(config.instrument_id)
        self._last_bar: Bar | None = None
        self._bought = False

    def on_start(self) -> None:
        # subscribe_bars requires a BarType (not just instrument_id) in Nautilus 1.226.0.
        # Use 1-MINUTE-LAST-EXTERNAL to match the synthetic catalog builder.
        spec = BarSpecification(1, BarAggregation.MINUTE, PriceType.LAST)
        bar_type = BarType(
            instrument_id=self._instrument_id,
            bar_spec=spec,
            aggregation_source=AggregationSource.EXTERNAL,
        )
        self.subscribe_bars(bar_type)

    def on_bar(self, bar: Bar) -> None:
        self._bar_count += 1
        self._last_bar = bar
        if not self._bought and self._bar_count >= self._params.buy_on_bar:
            self._submit_market(OrderSide.BUY, self._params.qty)
            self._bought = True

    def on_stop(self) -> None:
        # Flatten on shutdown so backtests close out positions deterministically.
        if self._bought:
            self._submit_market(OrderSide.SELL, self._params.qty)

    def _submit_market(self, side: OrderSide, qty: int) -> None:
        order = self.order_factory.market(
            instrument_id=self._instrument_id,
            order_side=side,
            quantity=Quantity.from_int(qty),
        )
        self.submit_order(order)
