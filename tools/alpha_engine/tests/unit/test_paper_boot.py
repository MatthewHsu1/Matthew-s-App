"""Paper-boot unit tests.

These verify the boot module's public functions WITHOUT actually starting a
TradingNode (which would require Nautilus's full async runtime). The full
integration test is Task 37 (test_paper_mode_with_mock_ibkr.py).
"""
from __future__ import annotations

from alpha_engine.engine import paper as paper_mod


def test_paper_run_callable_exists():
    """run_paper exists and is callable. Full execution tested in Task 37."""
    assert callable(paper_mod.run_paper)
