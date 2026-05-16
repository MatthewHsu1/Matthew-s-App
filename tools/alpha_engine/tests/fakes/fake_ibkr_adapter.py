"""Reusable fake IBKR data + execution clients for paper-mode integration tests.

Mirrors the public surface of Nautilus's `LiveDataClient` / `LiveExecutionClient`
just enough to let `engine/paper.py` boot a TradingNode without real network.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeDataClient:
    venue: str = "IBKR"
    subscriptions: list = field(default_factory=list)
    connected: bool = False

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def subscribe_bars(self, bar_type):
        self.subscriptions.append(bar_type)


@dataclass
class FakeExecClient:
    venue: str = "IBKR"
    submitted: list = field(default_factory=list)
    cancelled: list = field(default_factory=list)
    connected: bool = False

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def submit_order(self, cmd):
        self.submitted.append(cmd)

    def cancel_order(self, cmd):
        self.cancelled.append(cmd)
