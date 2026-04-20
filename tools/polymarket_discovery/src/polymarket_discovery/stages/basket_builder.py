from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Sequence

from ..contracts import BasketItem
from ..contracts import DependencyEdge
from ..contracts import MarketDescriptor
from ..interfaces.basket_builder import BasketBuilder


@dataclass(slots=True)
class _BasketBuilderSettings:
    confidence_threshold: float = 0.9
    conservative_gating: bool = True


class DefaultBasketBuilder(BasketBuilder):
    """Build minimal basket definitions from inferred dependencies."""

    def build(
        self,
        markets: Sequence[MarketDescriptor],
        dependencies: Sequence[DependencyEdge],
        config: Any | None = None,
    ) -> list[BasketItem]:
        settings = self._resolve_settings(config)
        by_market_id = {market.market_id: market for market in markets}
        baskets: list[BasketItem] = []
        seen_edge_ids: set[str] = set()

        for edge in dependencies:
            if edge.edge_id in seen_edge_ids:
                continue

            seen_edge_ids.add(edge.edge_id)

            if not isfinite(edge.confidence):
                continue

            edge_type = (
                edge.edge_type.strip().lower()
                if isinstance(edge.edge_type, str)
                else ""
            )

            if settings.conservative_gating and edge_type == "related":
                continue

            if (
                settings.conservative_gating
                and edge.confidence < settings.confidence_threshold
            ):
                continue

            left = by_market_id.get(edge.from_market_id)
            right = by_market_id.get(edge.to_market_id)
            if left is None or right is None:
                continue

            token_ids = self._dedupe_token_ids([*left.token_ids, *right.token_ids])

            if not token_ids:
                continue

            baskets.append(
                BasketItem(
                    basket_id=f"basket-{edge.edge_id}",
                    token_ids=token_ids,
                    dependency_basis=[edge.edge_id],
                ),
            )

        return baskets

    def _resolve_settings(self, config: Any | None) -> _BasketBuilderSettings:
        params = getattr(config, "params", {}) if config is not None else {}
        
        if not isinstance(params, dict):
            params = {}

        basket_params: dict[str, Any] = {}
        for key in ("basket_builder", "basket"):
            candidate = params.get(key)
            if isinstance(candidate, dict):
                basket_params = candidate
                break

        return _BasketBuilderSettings(
            confidence_threshold=self._validate_confidence_threshold(
                self._coerce_float(
                    basket_params.get(
                        "confidence_threshold",
                        params.get(
                            "basket_confidence_threshold",
                            params.get("confidence_threshold"),
                        ),
                    ),
                    0.9,
                ),
            ),
            conservative_gating=self._coerce_bool(
                basket_params.get(
                    "conservative_gating",
                    params.get(
                        "basket_conservative_gating", params.get("conservative_gating")
                    ),
                ),
                True,
            ),
        )

    @staticmethod
    def _dedupe_token_ids(token_ids: Sequence[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for token_id in token_ids:
            if not isinstance(token_id, str):
                continue
            cleaned = token_id.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            deduped.append(cleaned)
        return deduped

    @staticmethod
    def _coerce_float(value: Any, default: float) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _validate_confidence_threshold(value: float) -> float:
        if not isfinite(value):
            raise ValueError(
                "confidence_threshold must be finite and between 0 and 1 inclusive"
            )
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                "confidence_threshold must be finite and between 0 and 1 inclusive"
            )
        return value

    @staticmethod
    def _coerce_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return bool(value)
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"true", "1", "yes", "y", "on"}:
                return True
            if cleaned in {"false", "0", "no", "n", "off"}:
                return False
        return default
