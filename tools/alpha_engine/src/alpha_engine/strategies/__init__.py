"""Strategy registry + built-in strategies.

Importing this package registers all built-in strategies so the engine
can resolve `config.strategy.ref` without separate plumbing.
"""

from alpha_engine.strategies.registry import default_registry, strategy  # noqa: F401
from alpha_engine.strategies import toy_buy_and_hold  # noqa: F401  (side-effect: registration)
