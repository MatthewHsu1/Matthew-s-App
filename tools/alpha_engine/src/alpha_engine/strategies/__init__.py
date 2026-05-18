"""Strategy registry + built-in strategies.

Importing this package registers all built-in strategies so the engine
can resolve `config.strategy.ref` without separate plumbing.
"""

from alpha_engine.strategies import toy_buy_and_hold
from alpha_engine.strategies.bband_volume_setup import (
    strategy as _bband_volume_setup_strategy,
)
from alpha_engine.strategies.registry import default_registry, strategy
