from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite
from typing import Any

from ..contracts import MarketDescriptor
from ..interfaces.llm_dependency_prediction import LLMDependencyPrediction
from ..interfaces.llm_provider import LLMProvider
from ..net.http_json import request_json
from ..utils.coercion import is_local_endpoint
from .settings import LLMProviderSettings


ALLOWED_LLM_EDGE_TYPES = frozenset({"mutually_exclusive", "conditional", "related"})


def validate_llm_dependency_prediction(prediction: LLMDependencyPrediction) -> LLMDependencyPrediction:
    edge_type = prediction.edge_type.strip().lower() if isinstance(prediction.edge_type, str) else ""
    if edge_type not in ALLOWED_LLM_EDGE_TYPES:
        raise ValueError(
            "edge_type must be one of: conditional, mutually_exclusive, related",
        )

    confidence_raw = prediction.confidence
    if isinstance(confidence_raw, bool) or not isinstance(confidence_raw, (int, float)):
        raise ValueError("confidence must be a numeric value between 0 and 1 inclusive")
    confidence = float(confidence_raw)
    if not isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1 inclusive")

    rationale = prediction.rationale.strip() if isinstance(prediction.rationale, str) else ""
    if not rationale:
        raise ValueError("rationale must be a non-empty string")

    return LLMDependencyPrediction(
        edge_type=edge_type,
        confidence=confidence,
        rationale=rationale,
    )


def parse_llm_dependency_prediction(raw_response: str | dict[str, Any]) -> LLMDependencyPrediction:
    if isinstance(raw_response, str):
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM dependency response must be valid JSON") from exc
    else:
        payload = raw_response

    if not isinstance(payload, dict):
        raise ValueError("LLM dependency response must be a JSON object")

    return validate_llm_dependency_prediction(
        LLMDependencyPrediction(
            edge_type=payload.get("edge_type", ""),
            confidence=payload.get("confidence"),
            rationale=payload.get("rationale", ""),
        ),
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
                        "content": self._build_user_prompt(left_market, right_market),
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

    @staticmethod
    def _build_user_prompt(left_market: MarketDescriptor, right_market: MarketDescriptor) -> str:
        return json.dumps(
            {
                "left_market": {
                    "market_id": left_market.market_id,
                    "question": left_market.question,
                    "description": left_market.description,
                    "rules": left_market.rules,
                    "end_date": left_market.end_date,
                    "topic": left_market.topic,
                },
                "right_market": {
                    "market_id": right_market.market_id,
                    "question": right_market.question,
                    "description": right_market.description,
                    "rules": right_market.rules,
                    "end_date": right_market.end_date,
                    "topic": right_market.topic,
                },
            },
            sort_keys=True,
        )

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


