from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ..providers.openai_invoker import OpenAIInvocationResult


class OpenAIInvoker(Protocol):
    def call(self, payload: dict[str, Any]) -> "OpenAIInvocationResult":
        """Issue an OpenAI chat-completions request and return a structured result."""
        ...
