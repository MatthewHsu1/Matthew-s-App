from dataclasses import dataclass, field

@dataclass(slots=True)
class MarketDescriptor:
    market_id: str
    condition_id: str
    question: str
    description: str
    end_date: str
    topic: str
    token_ids: list[str]
    resolution_source: str = field(default="")
