"""Floor Trading strategy package.

A 2-tranche staggered dip-buy on heavy-volume capitulation below the lower
Bollinger Band. See tools/alpha_engine/CONTEXT.md "Floor Trading" entry for
the domain definition. Implementation is split:

- params.py            — strategy tunables (frozen dataclass)
- detection.py         — pure Day-1 setup rule
- spike_detector.py    — 10x rolling-rate spike detection on trade prints
- state_machine.py     — Day 2/3/4 progression + intent emission
- strategy.py          — Nautilus Strategy wrapper
"""
from alpha_engine.strategies.floor_trading.params import FloorTradingParams

__all__ = ["FloorTradingParams"]
