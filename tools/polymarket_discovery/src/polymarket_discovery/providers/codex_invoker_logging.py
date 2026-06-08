from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from ..interfaces.codex_invoker import CodexInvoker
from .llm_codex import CodexInvocationResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LoggingCodexInvoker:
    """Decorator that wraps any CodexInvoker and emits a usage log record."""

    inner: CodexInvoker

    def run(
        self,
        prompt: str,
        *,
        timeout_seconds: float,
        output_schema_path: Path | None = None,
    ) -> CodexInvocationResult:
        result = self.inner.run(
            prompt,
            timeout_seconds=timeout_seconds,
            output_schema_path=output_schema_path,
        )
        if result.usage is not None:
            u = result.usage
            logger.info(
                "codex_usage",
                extra={
                    "input_tokens": u.input_tokens,
                    "cached_input_tokens": u.cached_input_tokens,
                    "output_tokens": u.output_tokens,
                    "reasoning_output_tokens": u.reasoning_output_tokens,
                },
            )
        return result
