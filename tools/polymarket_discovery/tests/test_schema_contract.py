from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.stages import validate_output_document as default_validate


def _load_validator():
    """Prefer worker-B serialization validator when available."""
    try:
        module = importlib.import_module("polymarket_discovery.serialization")
        return getattr(module, "validate_output_document")
    except Exception:
        return default_validate


def test_sample_output_matches_schema_contract() -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "sample_output.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    validator = _load_validator()
    validator(payload)


def test_schema_accepts_empty_baskets() -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "sample_output.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["baskets"] = []

    validator = _load_validator()
    validator(payload)
