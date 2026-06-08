from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..net.http_json import request_json
from ..utils.coercion import is_local_endpoint
from .settings import LLMProviderSettings


@dataclass(slots=True, frozen=True)
class OpenAIUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(slots=True, frozen=True)
class OpenAIInvocationResult:
    content: str
    usage: OpenAIUsage | None


@dataclass(slots=True)
class RequestJsonOpenAIInvoker:
    """Concrete OpenAIInvoker that issues HTTP calls via request_json."""

    settings: LLMProviderSettings

    def __post_init__(self) -> None:
        if not self.settings.base_url:
            raise ValueError("base_url is required for non-stub llm providers")
        if not self.settings.api_key and not is_local_endpoint(self.settings.base_url):
            raise ValueError("api_key is required for non-local llm providers")

    def call(self, payload: dict[str, Any]) -> OpenAIInvocationResult:
        response = request_json(
            url=self.settings.base_url,
            timeout_seconds=self.settings.timeout_seconds,
            retry=self.settings.retry,
            method="POST",
            payload=payload,
            headers=self._headers(),
        )
        content = self._extract_message_content(response)
        usage = self._extract_usage(response)
        return OpenAIInvocationResult(content=content, usage=usage)

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": "polymarket-discovery/0.1"}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        return headers

    @staticmethod
    def _extract_message_content(response: Any) -> str:
        if not isinstance(response, dict):
            raise ValueError("LLM response payload must be a JSON object")

        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("LLM response payload must include choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("LLM response payload has an invalid first choice")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("LLM response payload must include message content")

        content = message.get("content")
        if isinstance(content, str):
            cleaned = content.strip()
            if cleaned:
                return cleaned
        raise ValueError("LLM response payload must include a non-empty string content field")

    @staticmethod
    def _extract_usage(response: dict[str, Any]) -> OpenAIUsage | None:
        usage = response.get("usage")
        if not isinstance(usage, dict):
            return None
        try:
            return OpenAIUsage(
                prompt_tokens=int(usage["prompt_tokens"]),
                completion_tokens=int(usage["completion_tokens"]),
                total_tokens=int(usage["total_tokens"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
