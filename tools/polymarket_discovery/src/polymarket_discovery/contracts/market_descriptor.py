from dataclasses import dataclass

@dataclass(slots=True)
class MarketDescriptor:
    market_id: str
    condition_id: str
    question: str
    description: str
    rules: str
    end_date: str
    topic: str
    token_ids: list[str]
