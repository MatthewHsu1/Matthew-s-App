from __future__ import annotations

import json
from collections.abc import Sequence
from math import isfinite
from typing import Any

from ..contracts import MarketDescriptor
from ..interfaces.llm_basket_group import LLMBasketGroup
from ..interfaces.llm_dependency_prediction import LLMDependencyPrediction

ALLOWED_LLM_EDGE_TYPES = frozenset({"mutually_exclusive", "conditional", "related"})

# ---------------------------------------------------------------------------
# Batched dependency-inference codec
# ---------------------------------------------------------------------------
# Default maximum number of market pairs sent in a single LLM prompt.
# Keeps token budgets manageable (~50 pairs x ~200 tokens/pair ~= 10k tokens).
# Callers may override this via DiscoveryConfig.params["dependency_inferencer"]["batch_size"].
DEFAULT_DEPENDENCY_BATCH_SIZE: int = 50


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


def build_batched_dependency_prompt(
    pairs: Sequence[tuple[MarketDescriptor, MarketDescriptor]],
) -> str:
    """Build the JSON payload for a batched pairwise dependency inference call.

    Each pair is assigned a stable ``pair_id`` (``"0"``, ``"1"``, …) that the
    LLM must echo back verbatim.  The response is correlated back to input
    pairs by ``pair_id`` so reordering or omissions are detected immediately.

    The prompt shape is::

        {
          "pairs": [
            {
              "pair_id": "0",
              "left_market": {...},
              "right_market": {...}
            },
            ...
          ]
        }
    """
    pair_list = []
    for idx, (left, right) in enumerate(pairs):
        pair_list.append(
            {
                "pair_id": str(idx),
                "left_market": {
                    "market_id": left.market_id,
                    "question": left.question,
                    "description": left.description,
                    "end_date": left.end_date,
                    "topic": left.topic,
                },
                "right_market": {
                    "market_id": right.market_id,
                    "question": right.question,
                    "description": right.description,
                    "end_date": right.end_date,
                    "topic": right.topic,
                },
            }
        )
    return json.dumps({"pairs": pair_list}, sort_keys=True)


def validate_batched_dependency_predictions(
    predictions: list[tuple[str, LLMDependencyPrediction]],
    expected_count: int,
) -> list[LLMDependencyPrediction]:
    """Validate a list of (pair_id, prediction) tuples from a batched response.

    Checks that:
    - Every expected pair_id (``"0"`` through ``str(expected_count - 1)``) is present.
    - No unexpected pair_ids are present.
    - Each individual prediction passes :func:`validate_llm_dependency_prediction`.

    Returns a list of validated :class:`LLMDependencyPrediction` objects in
    input-index order (index 0 first).

    Raises :class:`ValueError` on any violation.

    Policy rationale: we require the LLM to echo back a stable ``pair_id`` so
    that partial responses (missing pairs) and misordered responses are caught
    immediately rather than silently producing wrong dependency edges.
    """
    expected_ids = {str(i) for i in range(expected_count)}
    seen_ids: set[str] = set()
    by_id: dict[str, LLMDependencyPrediction] = {}

    for pair_id, prediction in predictions:
        if pair_id not in expected_ids:
            raise ValueError(
                f"Batched dependency response contains unexpected pair_id: {pair_id!r}. "
                f"Expected pair_ids: {sorted(expected_ids)}"
            )
        if pair_id in seen_ids:
            raise ValueError(
                f"Batched dependency response contains duplicate pair_id: {pair_id!r}"
            )
        seen_ids.add(pair_id)
        by_id[pair_id] = validate_llm_dependency_prediction(prediction)

    missing = expected_ids - seen_ids
    if missing:
        raise ValueError(
            f"Batched dependency response is missing pair_id(s): {sorted(missing)}. "
            f"Expected {expected_count} results."
        )

    return [by_id[str(i)] for i in range(expected_count)]


def parse_batched_dependency_predictions(
    raw_response: str | dict[str, Any],
    expected_count: int,
) -> list[LLMDependencyPrediction]:
    """Parse and validate a batched pairwise dependency LLM response.

    The LLM is expected to return a JSON object with a ``"predictions"`` array::

        {
          "predictions": [
            {
              "pair_id": "0",
              "edge_type": "mutually_exclusive",
              "confidence": 0.95,
              "rationale": "Only one candidate can win."
            },
            ...
          ]
        }

    Results are returned in ``pair_id`` order (index 0 first), regardless of
    the order the LLM returned them.

    Raises :class:`ValueError` on any parsing or validation failure.
    """
    if isinstance(raw_response, str):
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise ValueError("Batched dependency response must be valid JSON") from exc
    else:
        payload = raw_response

    if not isinstance(payload, dict):
        raise ValueError("Batched dependency response must be a JSON object")

    predictions_raw = payload.get("predictions")
    if not isinstance(predictions_raw, list):
        raise ValueError('Batched dependency response must contain a "predictions" array')

    parsed: list[tuple[str, LLMDependencyPrediction]] = []
    for index, item in enumerate(predictions_raw):
        if not isinstance(item, dict):
            raise ValueError(f'Batched dependency "predictions[{index}]" must be an object')
        pair_id = item.get("pair_id")
        if not isinstance(pair_id, (str, int)):
            raise ValueError(
                f'Batched dependency "predictions[{index}].pair_id" must be a string or integer'
            )
        pair_id_str = str(pair_id).strip()
        if not pair_id_str:
            raise ValueError(
                f'Batched dependency "predictions[{index}].pair_id" must be non-empty'
            )
        prediction = LLMDependencyPrediction(
            edge_type=item.get("edge_type", ""),
            confidence=item.get("confidence"),
            rationale=item.get("rationale", ""),
        )
        parsed.append((pair_id_str, prediction))

    return validate_batched_dependency_predictions(parsed, expected_count)


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
