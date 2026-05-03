from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..providers.llm_codex import CodexInvocationResult


class CodexInvoker(Protocol):
    def run(
        self,
        prompt: str,
        *,
        timeout_seconds: float,
        output_schema_path: Path | None = None,
    ) -> "CodexInvocationResult":
        """Run the Codex CLI with the given prompt and return a structured result."""
        ...
