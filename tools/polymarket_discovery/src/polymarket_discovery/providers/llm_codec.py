from __future__ import annotations

import json
from math import isfinite
from typing import Any

from ..contracts import MarketDescriptor
from ..interfaces.llm_dependency_prediction import LLMDependencyPrediction


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


def build_dependency_prompt(left_market: MarketDescriptor, right_market: MarketDescriptor) -> str:
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
