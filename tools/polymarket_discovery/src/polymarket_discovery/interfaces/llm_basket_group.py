from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class LLMBasketGroup:
    """N-way grouping of markets inferred by the LLM to form a complete outcome set.

    Unlike the pairwise :class:`DependencyEdge`, a basket group captures all
    markets whose YES tokens together cover the full probability space (sum → 1.0).

    Attributes:
        basket_id: Stable identifier for this group (e.g. ``"basket-election-2026"``).
        market_ids: Ordered list of market_ids that belong to this basket.
        rationale: Free-text explanation from the LLM.
    """

    basket_id: str
    market_ids: list[str] = field(default_factory=list)
    rationale: str = ""
