from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from ..interfaces.openai_invoker import OpenAIInvoker
from .openai_invoker import OpenAIInvocationResult


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LoggingOpenAIInvoker:
    """Decorator that wraps any OpenAIInvoker and emits a usage log record."""

    inner: OpenAIInvoker

    def call(self, payload: dict[str, Any]) -> OpenAIInvocationResult:
        result = self.inner.call(payload)
        if result.usage is not None:
            u = result.usage
            logger.info(
                "openai_usage",
                extra={
                    "prompt_tokens": u.prompt_tokens,
                    "completion_tokens": u.completion_tokens,
                    "total_tokens": u.total_tokens,
                },
            )
        return result
