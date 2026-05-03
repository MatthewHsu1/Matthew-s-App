from __future__ import annotations

from typing import Protocol


class CodexInvoker(Protocol):
    def run(self, prompt: str, *, timeout_seconds: float) -> str:
        """Run the Codex CLI with the given prompt and return raw stdout."""
