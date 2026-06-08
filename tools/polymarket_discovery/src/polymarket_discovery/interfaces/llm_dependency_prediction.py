from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LLMDependencyPrediction:
    edge_type: str
    confidence: float
    rationale: str
