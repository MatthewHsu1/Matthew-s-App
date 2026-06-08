from dataclasses import dataclass, field


@dataclass(slots=True)
class BasketItem:
    basket_id: str
    token_ids: list[str]
    expected_sum: float = 1.0
    dependency_basis: list[str] = field(default_factory=list)