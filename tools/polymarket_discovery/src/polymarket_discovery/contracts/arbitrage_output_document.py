from dataclasses import asdict, dataclass

from .basket_item import BasketItem
from .dependency_edge import DependencyEdge
from .market_descriptor import MarketDescriptor
from .run_metadata import RunMetadata
from .schema_types import SchemaVersion


@dataclass(slots=True)
class ArbitrageOutputDocument:
    run_metadata: RunMetadata
    markets: list[MarketDescriptor]
    dependencies: list[DependencyEdge]
    baskets: list[BasketItem]
    schema_version: SchemaVersion = "v1"

    def to_dict(self) -> dict:
        return asdict(self)