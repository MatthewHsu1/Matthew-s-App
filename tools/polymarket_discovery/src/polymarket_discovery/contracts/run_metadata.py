from dataclasses import dataclass
from .schema_types import SchemaVersion

@dataclass(slots=True)
class RunMetadata:
    run_id: str
    generated_at_utc: str
    market_source: str
    embedding_model: str
    llm_model: str
    schema_version: SchemaVersion = "v1"
