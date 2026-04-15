from dataclasses import asdict, dataclass

from .schema_types import SchemaVersion
from .run_metadata import RunMetadata
from .market_descriptor import MarketDescriptor
from .dependency_edge import DependencyEdge
from .basket_item import BasketItem

@dataclass(slots=True)
class ArbitrageOutputDocument:
    run_metadata: RunMetadata
    markets: list[MarketDescriptor]
    dependencies: list[DependencyEdge]
    baskets: list[BasketItem]
    schema_version: SchemaVersion = "v1"

    def to_dict(self) -> dict:
        return asdict(self)