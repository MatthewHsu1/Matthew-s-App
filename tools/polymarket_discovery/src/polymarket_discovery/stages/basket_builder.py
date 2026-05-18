from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any

from ..contracts import BasketItem, DependencyEdge, MarketDescriptor
from ..interfaces.basket_builder import BasketBuilder
from ..interfaces.llm_basket_group import LLMBasketGroup
from ..utils.coercion import coerce_bool, coerce_float


@dataclass(slots=True)
class _BasketBuilderSettings:
    confidence_threshold: float = 0.9
    conservative_gating: bool = True


class DefaultBasketBuilder(BasketBuilder):
    """Build minimal basket definitions from inferred dependencies.

    When *basket_groups* are provided (from LLM basket-structure inference),
    those N-way groupings are used directly to form baskets.  Synthetic
    ``DependencyEdge`` records (one per adjacent market pair in the chain)
    are created to satisfy the ``dependency_basis`` serialization constraint.

    If no *basket_groups* are provided, the builder falls back to the original
    pairwise-edge path.
    """

    def build(
        self,
        markets: Sequence[MarketDescriptor],
        dependencies: Sequence[DependencyEdge],
        config: Any | None = None,
        basket_groups: Sequence[LLMBasketGroup] = (),
    ) -> tuple[list[BasketItem], list[DependencyEdge]]:
        """Return ``(baskets, synthetic_edges)``.

        *synthetic_edges* are non-empty only when *basket_groups* are
        consumed; they must be merged into the output document's dependencies
        list so that ``dependency_basis`` references resolve correctly.
        """
        if basket_groups:
            return self._build_from_basket_groups(markets, basket_groups)
        baskets = self._build_from_pairwise_edges(markets, dependencies, config)
        return baskets, []

    # ------------------------------------------------------------------
    # LLM-inferred basket-group path
    # ------------------------------------------------------------------

    def _build_from_basket_groups(
        self,
        markets: Sequence[MarketDescriptor],
        basket_groups: Sequence[LLMBasketGroup],
    ) -> tuple[list[BasketItem], list[DependencyEdge]]:
        """Build baskets directly from LLM-inferred N-way groupings.

        For each group we synthesize a chain of N-1 pairwise ``DependencyEdge``
        records (adjacent pairs) and set the basket's ``dependency_basis`` to
        all those edge IDs.  This satisfies the serialization rule that every
        basis entry must reference a real edge AND that the basket's tokens
        cover all markets referenced by those edges.
        """
        by_market_id = {market.market_id: market for market in markets}
        baskets: list[BasketItem] = []
        synthetic_edges: list[DependencyEdge] = []
        seen_edge_ids: set[str] = set()

        for group in basket_groups:
            resolved_markets = [
                by_market_id[mid]
                for mid in group.market_ids
                if mid in by_market_id
            ]
            if len(resolved_markets) < 2:
                continue

            # Build a spanning chain: m0-m1, m1-m2, ..., m(n-2)-m(n-1)
            chain_edges: list[DependencyEdge] = []
            for i in range(len(resolved_markets) - 1):
                left = resolved_markets[i]
                right = resolved_markets[i + 1]
                edge_id = f"basket-member__{left.market_id}__{right.market_id}"
                if edge_id in seen_edge_ids:
                    # Skip if the same pair appears in multiple groups; the
                    # dependency_basis will still reference the existing edge.
                    chain_edges.append(
                        DependencyEdge(
                            edge_id=edge_id,
                            edge_type="basket_member",
                            from_market_id=left.market_id,
                            to_market_id=right.market_id,
                            confidence=1.0,
                            rationale=group.rationale,
                        )
                    )
                    continue
                seen_edge_ids.add(edge_id)
                edge = DependencyEdge(
                    edge_id=edge_id,
                    edge_type="basket_member",
                    from_market_id=left.market_id,
                    to_market_id=right.market_id,
                    confidence=1.0,
                    rationale=group.rationale,
                )
                chain_edges.append(edge)
                synthetic_edges.append(edge)

            if not chain_edges:
                continue

            # Collect all token IDs from every market in the group.
            all_token_ids: list[str] = []
            for m in resolved_markets:
                all_token_ids.extend(m.token_ids)
            token_ids = self._dedupe_token_ids(all_token_ids)

            if not token_ids:
                continue

            dependency_basis = list({e.edge_id for e in chain_edges})

            baskets.append(
                BasketItem(
                    basket_id=group.basket_id,
                    token_ids=token_ids,
                    dependency_basis=dependency_basis,
                )
            )

        return baskets, synthetic_edges

    # ------------------------------------------------------------------
    # Original pairwise-edge fallback path
    # ------------------------------------------------------------------

    def _build_from_pairwise_edges(
        self,
        markets: Sequence[MarketDescriptor],
        dependencies: Sequence[DependencyEdge],
        config: Any | None,
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
                coerce_float(
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
            conservative_gating=coerce_bool(
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
