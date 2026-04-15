from dataclasses import dataclass

@dataclass(slots=True)
class DependencyEdge:
    edge_id: str
    edge_type: str
    from_market_id: str
    to_market_id: str
    confidence: float
    rationale: str