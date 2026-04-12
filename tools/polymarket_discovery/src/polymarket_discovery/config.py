from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


DEFAULT_STAGES: tuple[str, ...] = (
    "market_source",
    "topic_assigner",
    "candidate_reducer",
    "dependency_inferencer",
    "basket_builder",
    "basket_validator",
)


@dataclass(frozen=True)
class DiscoveryConfig:
    """Runtime config for offline discovery pipeline execution."""

    output_root: Path
    artifact_subdir: str = "runs"
    market_source: str = "polymarket-api"
    embedding_provider: str = "stub"
    embedding_model: str = "linq-embed-mistral-stub"
    llm_model: str = "deepseek-stub"
    stages: tuple[str, ...] = DEFAULT_STAGES
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def artifact_root(self) -> Path:
        return self.output_root / self.artifact_subdir

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "output_root": str(self.output_root),
            "artifact_subdir": self.artifact_subdir,
            "market_source": self.market_source,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "llm_model": self.llm_model,
            "stages": list(self.stages),
            "params": self.params,
        }


def load_config(config_path: str | Path) -> DiscoveryConfig:
    path = Path(config_path)
    raw = json.loads(path.read_text(encoding="utf-8"))

    output_root_value = raw.get("output_root")
    if not isinstance(output_root_value, str) or not output_root_value.strip():
        raise ValueError("Config field 'output_root' is required and must be a non-empty string.")

    artifact_subdir = raw.get("artifact_subdir", "runs")
    if not isinstance(artifact_subdir, str) or not artifact_subdir.strip():
        raise ValueError("Config field 'artifact_subdir' must be a non-empty string when provided.")

    raw_stages = raw.get("stages", list(DEFAULT_STAGES))
    if not isinstance(raw_stages, list) or not all(isinstance(x, str) and x.strip() for x in raw_stages):
        raise ValueError("Config field 'stages' must be a list of non-empty strings.")
    unknown_stages = sorted(set(raw_stages) - set(DEFAULT_STAGES))
    if unknown_stages:
        joined = ", ".join(unknown_stages)
        allowed = ", ".join(DEFAULT_STAGES)
        raise ValueError(f"Unknown stage(s): {joined}. Allowed stages: {allowed}.")

    params = raw.get("params", {})
    if not isinstance(params, dict):
        raise ValueError("Config field 'params' must be an object when provided.")

    return DiscoveryConfig(
        output_root=Path(output_root_value),
        artifact_subdir=artifact_subdir,
        market_source=str(raw.get("market_source", "polymarket-api")),
        embedding_provider=str(raw.get("embedding_provider", "stub")),
        embedding_model=str(raw.get("embedding_model", "linq-embed-mistral-stub")),
        llm_model=str(raw.get("llm_model", "deepseek-stub")),
        stages=tuple(raw_stages),
        params=params,
    )


def generate_run_id(config: DiscoveryConfig) -> str:
    """Deterministic run id based on canonicalized config payload."""

    payload = json.dumps(config.to_canonical_dict(), sort_keys=True, separators=(",", ":"))
    digest = sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"run_{digest}"


def ensure_artifact_dir(config: DiscoveryConfig, run_id: str) -> Path:
    artifact_dir = config.artifact_root / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir
