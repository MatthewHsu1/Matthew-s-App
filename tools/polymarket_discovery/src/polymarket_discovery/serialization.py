from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .contracts import ArbitrageOutputDocument


class OutputValidationError(ValueError):
    """Raised when a discovery output document fails validation."""


def _schema_path() -> Path:
    return Path(__file__).parent / "schema" / "baskets.schema.json"


def load_output_schema() -> dict[str, Any]:
    path = _schema_path()
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def to_output_dict(document: ArbitrageOutputDocument | dict[str, Any]) -> dict[str, Any]:
    if isinstance(document, dict):
        return document

    if is_dataclass(document):
        return asdict(document)

    raise TypeError("document must be an ArbitrageOutputDocument or dict")


def to_output_json(
    document: ArbitrageOutputDocument | dict[str, Any],
    *,
    indent: int = 2,
    sort_keys: bool = True,
) -> str:
    payload = to_output_dict(document)
    validate_output_document(payload)
    return json.dumps(payload, indent=indent, sort_keys=sort_keys)


def validate_output_document(document: ArbitrageOutputDocument | dict[str, Any]) -> None:
    payload = to_output_dict(document)
    schema = load_output_schema()

    try:
        import jsonschema

        jsonschema.validate(instance=payload, schema=schema)
    except ImportError:
        _validate_fallback(payload)
    except Exception as exc:
        raise OutputValidationError(f"Schema validation failed: {exc}") from exc

    _validate_cross_entity_consistency(payload)


def _validate_fallback(payload: dict[str, Any]) -> None:
    # Lightweight fallback checks when jsonschema isn't available.
    _require_keys(payload, ["schema_version", "run_metadata", "markets", "dependencies", "baskets"], "root")

    if payload.get("schema_version") != "v1":
        raise OutputValidationError("root.schema_version must equal 'v1'")

    run_metadata = payload.get("run_metadata")
    if not isinstance(run_metadata, dict):
        raise OutputValidationError("run_metadata must be an object")

    _require_keys(
        run_metadata,
        ["schema_version", "run_id", "generated_at_utc", "market_source", "embedding_model", "llm_model"],
        "run_metadata",
    )
    if run_metadata.get("schema_version") != "v1":
        raise OutputValidationError("run_metadata.schema_version must equal 'v1'")

    markets = payload.get("markets")
    if not isinstance(markets, list) or not markets:
        raise OutputValidationError("markets must be a non-empty array")

    for index, market in enumerate(markets):
        if not isinstance(market, dict):
            raise OutputValidationError(f"markets[{index}] must be an object")
        _require_keys(
            market,
            ["market_id", "condition_id", "question", "description", "rules", "end_date", "topic", "token_ids"],
            f"markets[{index}]",
        )
        if not isinstance(market.get("token_ids"), list) or not market["token_ids"]:
            raise OutputValidationError(f"markets[{index}].token_ids must be a non-empty array")

    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, list):
        raise OutputValidationError("dependencies must be an array")

    for index, edge in enumerate(dependencies):
        if not isinstance(edge, dict):
            raise OutputValidationError(f"dependencies[{index}] must be an object")
        _require_keys(
            edge,
            ["edge_id", "edge_type", "from_market_id", "to_market_id", "confidence", "rationale"],
            f"dependencies[{index}]",
        )

    baskets = payload.get("baskets")
    if not isinstance(baskets, list):
        raise OutputValidationError("baskets must be an array")

    for index, basket in enumerate(baskets):
        if not isinstance(basket, dict):
            raise OutputValidationError(f"baskets[{index}] must be an object")
        _require_keys(
            basket,
            ["basket_id", "token_ids", "expected_sum", "dependency_basis"],
            f"baskets[{index}]",
        )
        if not isinstance(basket.get("token_ids"), list) or not basket["token_ids"]:
            raise OutputValidationError(f"baskets[{index}].token_ids must be a non-empty array")


def _validate_cross_entity_consistency(payload: dict[str, Any]) -> None:
    markets = payload.get("markets")
    dependencies = payload.get("dependencies")
    baskets = payload.get("baskets")

    if not isinstance(markets, list):
        raise OutputValidationError("markets must be an array")
    if not isinstance(dependencies, list):
        raise OutputValidationError("dependencies must be an array")
    if not isinstance(baskets, list):
        raise OutputValidationError("baskets must be an array")

    market_ids: set[str] = set()
    market_tokens_by_id: dict[str, set[str]] = {}
    for index, market in enumerate(markets):
        if not isinstance(market, dict):
            raise OutputValidationError(f"markets[{index}] must be an object")
        market_id = _require_non_empty_string(market.get("market_id"), f"markets[{index}].market_id")
        if market_id in market_ids:
            raise OutputValidationError(f"markets[{index}] has duplicate market_id: {market_id}")
        market_ids.add(market_id)
        token_ids = market.get("token_ids")
        if not isinstance(token_ids, list):
            raise OutputValidationError(f"markets[{index}].token_ids must be an array")
        market_tokens_by_id[market_id] = {
            _require_non_empty_string(token_id, f"markets[{index}].token_ids[{token_index}]")
            for token_index, token_id in enumerate(token_ids)
        }

    dependency_ids: set[str] = set()
    dependency_market_refs: dict[str, tuple[str, str]] = {}
    for index, edge in enumerate(dependencies):
        if not isinstance(edge, dict):
            raise OutputValidationError(f"dependencies[{index}] must be an object")
        edge_id = _require_non_empty_string(edge.get("edge_id"), f"dependencies[{index}].edge_id")
        if edge_id in dependency_ids:
            raise OutputValidationError(f"dependencies[{index}] has duplicate edge_id: {edge_id}")
        from_market_id = _require_non_empty_string(edge.get("from_market_id"), f"dependencies[{index}].from_market_id")
        to_market_id = _require_non_empty_string(edge.get("to_market_id"), f"dependencies[{index}].to_market_id")
        missing_refs = [ref for ref in (from_market_id, to_market_id) if ref not in market_ids]
        if missing_refs:
            joined = ", ".join(sorted(set(missing_refs)))
            raise OutputValidationError(
                f"dependencies[{index}] has orphan market refs: {joined}"
            )
        dependency_ids.add(edge_id)
        dependency_market_refs[edge_id] = (from_market_id, to_market_id)

    for basket_index, basket in enumerate(baskets):
        if not isinstance(basket, dict):
            raise OutputValidationError(f"baskets[{basket_index}] must be an object")
        dependency_basis = basket.get("dependency_basis")
        if not isinstance(dependency_basis, list):
            raise OutputValidationError(f"baskets[{basket_index}].dependency_basis must be an array")
        allowed_token_ids: set[str] = set()
        for basis_index, edge_id in enumerate(dependency_basis):
            resolved_edge_id = _require_non_empty_string(
                edge_id,
                f"baskets[{basket_index}].dependency_basis[{basis_index}]",
            )
            if resolved_edge_id not in dependency_ids:
                raise OutputValidationError(
                    f"baskets[{basket_index}].dependency_basis[{basis_index}] references missing dependency edge ID: {resolved_edge_id}"
                )
            from_market_id, to_market_id = dependency_market_refs[resolved_edge_id]
            allowed_token_ids.update(market_tokens_by_id[from_market_id])
            allowed_token_ids.update(market_tokens_by_id[to_market_id])
        token_ids = basket.get("token_ids")
        if not isinstance(token_ids, list):
            raise OutputValidationError(f"baskets[{basket_index}].token_ids must be an array")
        for token_index, token_id in enumerate(token_ids):
            resolved_token_id = _require_non_empty_string(
                token_id,
                f"baskets[{basket_index}].token_ids[{token_index}]",
            )
            if resolved_token_id not in allowed_token_ids:
                raise OutputValidationError(
                    f"baskets[{basket_index}].token_ids[{token_index}] references token outside dependency_basis markets: {resolved_token_id}"
                )


def _require_non_empty_string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise OutputValidationError(f"{path} must be a non-empty string")
    cleaned = value.strip()
    if not cleaned:
        raise OutputValidationError(f"{path} must be a non-empty string")
    return cleaned


def _require_keys(obj: dict[str, Any], keys: list[str], path: str) -> None:
    missing = [key for key in keys if key not in obj]
    if missing:
        joined = ", ".join(missing)
        raise OutputValidationError(f"Missing required fields at {path}: {joined}")
