from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from ..contracts import MarketDescriptor
from ..interfaces.llm_basket_group import LLMBasketGroup
from ..interfaces.llm_dependency_prediction import LLMDependencyPrediction
from ..interfaces.llm_provider import LLMProvider
from ..net.http_json import request_json
from ..utils.coercion import is_local_endpoint
from .llm_codec import (
    build_basket_prompt,
    build_dependency_prompt,
    parse_llm_basket_groups,
    parse_llm_dependency_prediction,
)
from .settings import LLMProviderSettings

_BASKET_SYSTEM_PROMPT = (
    "You identify basket structure in prediction markets. "
    "Given a list of markets that share a topic and end date, identify subsets "
    "whose YES-token prices sum to 1.0 (complete outcome sets). "
    'Reply with a single JSON object containing a "baskets" array. '
    "Each element must have basket_id (string), market_ids (array of market_id strings), "
    "and rationale (string). Only include markets that genuinely form a complete outcome set. "
    'Return {"baskets": []} if no complete sets are found.'
)


@dataclass(slots=True)
class OpenAICompatibleLLMProvider(LLMProvider):
    settings: LLMProviderSettings

    def __post_init__(self) -> None:
        if not self.settings.base_url:
            raise ValueError("base_url is required for non-stub llm providers")
        if not self.settings.api_key and not is_local_endpoint(self.settings.base_url):
            raise ValueError("api_key is required for non-local llm providers")

    def infer_dependency(
        self,
        left_market: MarketDescriptor,
        right_market: MarketDescriptor,
    ) -> LLMDependencyPrediction:
        payload = request_json(
            url=self.settings.base_url,
            timeout_seconds=self.settings.timeout_seconds,
            retry=self.settings.retry,
            method="POST",
            payload={
                "model": self.settings.model_name,
                "temperature": self.settings.temperature,
                "max_tokens": self.settings.max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You infer market dependencies. Reply with a single JSON object "
                            "containing edge_type, confidence, rationale. edge_type must be one "
                            "of mutually_exclusive, conditional, related. confidence must be a "
                            "number from 0 to 1."
                        ),
                    },
                    {
                        "role": "user",
                        "content": build_dependency_prompt(left_market, right_market),
                    },
                ],
            },
            headers={
                "User-Agent": "polymarket-discovery/0.1",
                **({"Authorization": f"Bearer {self.settings.api_key}"} if self.settings.api_key else {}),
            },
        )
        content = self._extract_message_content(payload)
        return parse_llm_dependency_prediction(content)

    def infer_basket_groups(
        self,
        markets: Sequence[MarketDescriptor],
    ) -> list[LLMBasketGroup]:
        """Ask the LLM to identify N-way basket groupings for the given topic group."""
        if len(markets) < 2:
            return []
        known_ids = frozenset(m.market_id for m in markets)
        payload = request_json(
            url=self.settings.base_url,
            timeout_seconds=self.settings.timeout_seconds,
            retry=self.settings.retry,
            method="POST",
            payload={
                "model": self.settings.model_name,
                "temperature": self.settings.temperature,
                "max_tokens": self.settings.max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": _BASKET_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": build_basket_prompt(markets),
                    },
                ],
            },
            headers={
                "User-Agent": "polymarket-discovery/0.1",
                **({"Authorization": f"Bearer {self.settings.api_key}"} if self.settings.api_key else {}),
            },
        )
        content = self._extract_message_content(payload)
        return parse_llm_basket_groups(content, known_market_ids=known_ids)

    @staticmethod
    def _extract_message_content(payload: Any) -> str:
        if not isinstance(payload, dict):
            raise ValueError("LLM response payload must be a JSON object")

        choices = payload.get("choices")
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
