from __future__ import annotations

import json
from math import isfinite
from typing import Any, Sequence

from ..contracts import MarketDescriptor
from ..interfaces.llm_basket_group import LLMBasketGroup
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
                "end_date": left_market.end_date,
                "topic": left_market.topic,
            },
            "right_market": {
                "market_id": right_market.market_id,
                "question": right_market.question,
                "description": right_market.description,
                "end_date": right_market.end_date,
                "topic": right_market.topic,
            },
        },
        sort_keys=True,
    )


# ---------------------------------------------------------------------------
# Basket-group inference codec
# ---------------------------------------------------------------------------


def build_basket_prompt(markets: Sequence[MarketDescriptor]) -> str:
    """Build the JSON payload sent to the LLM for N-way basket inference.

    The prompt describes all markets in a topic group and asks the model to
    identify which subsets form complete outcome sets (probabilities → 1.0).
    """
    market_list = [
        {
            "market_id": m.market_id,
            "question": m.question,
            "description": m.description,
            "end_date": m.end_date,
            "topic": m.topic,
        }
        for m in markets
    ]
    return json.dumps({"markets": market_list}, sort_keys=True)


def validate_llm_basket_groups(
    groups: list[LLMBasketGroup],
    known_market_ids: frozenset[str] | None = None,
) -> list[LLMBasketGroup]:
    """Validate a list of LLMBasketGroup objects.

    Each group must have:
    - a non-empty ``basket_id``
    - at least two distinct ``market_ids`` (a basket of one makes no sense)
    - a non-empty ``rationale``
    - ``market_ids`` that are all present in *known_market_ids* (when provided)

    Returns a new list with whitespace stripped from string fields.
    Raises ``ValueError`` on the first invalid group.
    """
    validated: list[LLMBasketGroup] = []
    seen_basket_ids: set[str] = set()

    for index, group in enumerate(groups):
        basket_id = group.basket_id.strip() if isinstance(group.basket_id, str) else ""
        if not basket_id:
            raise ValueError(f"basket_groups[{index}].basket_id must be a non-empty string")
        if basket_id in seen_basket_ids:
            raise ValueError(f"basket_groups[{index}].basket_id is a duplicate: {basket_id!r}")
        seen_basket_ids.add(basket_id)

        market_ids = group.market_ids
        if not isinstance(market_ids, list):
            raise ValueError(f"basket_groups[{index}].market_ids must be a list")
        cleaned_ids: list[str] = []
        seen_in_group: set[str] = set()
        for mid in market_ids:
            if not isinstance(mid, str):
                raise ValueError(f"basket_groups[{index}].market_ids contains a non-string entry")
            mid_clean = mid.strip()
            if not mid_clean:
                raise ValueError(f"basket_groups[{index}].market_ids contains an empty entry")
            if mid_clean in seen_in_group:
                raise ValueError(
                    f"basket_groups[{index}].market_ids has duplicate market_id: {mid_clean!r}"
                )
            seen_in_group.add(mid_clean)
            cleaned_ids.append(mid_clean)

        if len(cleaned_ids) < 2:
            raise ValueError(
                f"basket_groups[{index}].market_ids must contain at least 2 distinct market IDs"
            )

        if known_market_ids is not None:
            unknown = [mid for mid in cleaned_ids if mid not in known_market_ids]
            if unknown:
                joined = ", ".join(unknown)
                raise ValueError(
                    f"basket_groups[{index}].market_ids references unknown market IDs: {joined}"
                )

        rationale = group.rationale.strip() if isinstance(group.rationale, str) else ""
        if not rationale:
            raise ValueError(f"basket_groups[{index}].rationale must be a non-empty string")

        validated.append(LLMBasketGroup(basket_id=basket_id, market_ids=cleaned_ids, rationale=rationale))

    return validated


def parse_llm_basket_groups(
    raw_response: str | dict[str, Any],
    known_market_ids: frozenset[str] | None = None,
) -> list[LLMBasketGroup]:
    """Parse and validate an LLM basket-group response.

    The LLM is expected to return a JSON object with a ``"baskets"`` array:

    .. code-block:: json

        {
          "baskets": [
            {
              "basket_id": "election-2026",
              "market_ids": ["m1", "m2", "m3", "m4"],
              "rationale": "Four candidates; exactly one wins"
            }
          ]
        }

    Raises ``ValueError`` on any parsing or validation failure.
    """
    if isinstance(raw_response, str):
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM basket-group response must be valid JSON") from exc
    else:
        payload = raw_response

    if not isinstance(payload, dict):
        raise ValueError("LLM basket-group response must be a JSON object")

    baskets_raw = payload.get("baskets")
    if not isinstance(baskets_raw, list):
        raise ValueError('LLM basket-group response must contain a "baskets" array')

    groups: list[LLMBasketGroup] = []
    for index, item in enumerate(baskets_raw):
        if not isinstance(item, dict):
            raise ValueError(f'LLM basket-group response "baskets[{index}]" must be an object')
        groups.append(
            LLMBasketGroup(
                basket_id=item.get("basket_id", ""),
                market_ids=item.get("market_ids", []),
                rationale=item.get("rationale", ""),
            )
        )

    return validate_llm_basket_groups(groups, known_market_ids=known_market_ids)
