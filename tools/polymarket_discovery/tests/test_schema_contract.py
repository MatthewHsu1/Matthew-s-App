from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

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


def test_schema_rejects_orphan_dependency_market_refs() -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "sample_output.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["dependencies"][0]["from_market_id"] = "missing-market"

    validator = _load_validator()
    with pytest.raises(ValueError, match="orphan market"):
        validator(payload)


def test_schema_rejects_missing_dependency_basis_edge_id() -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "sample_output.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["baskets"][0]["dependency_basis"] = ["missing-edge"]

    validator = _load_validator()
    with pytest.raises(ValueError, match="dependency_basis"):
        validator(payload)


def test_schema_rejects_basket_token_outside_dependency_basis_markets() -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "sample_output.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["markets"].append(
        {
            "market_id": "m3",
            "condition_id": "cond-m3",
            "question": "Question m3",
            "description": "Description",
            "end_date": "2026-11-03",
            "topic": "topic-01",
            "token_ids": ["tok-alien-yes"],
        }
    )
    payload["baskets"][0]["token_ids"].append("tok-alien-yes")

    validator = _load_validator()
    with pytest.raises(ValueError, match="token_ids"):
        validator(payload)


def test_schema_rejects_duplicate_market_id() -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "sample_output.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["markets"].append(dict(payload["markets"][0]))

    validator = _load_validator()
    with pytest.raises(ValueError, match="duplicate market_id"):
        validator(payload)


def test_schema_rejects_duplicate_dependency_edge_id() -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "sample_output.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["dependencies"].append(dict(payload["dependencies"][0]))

    validator = _load_validator()
    with pytest.raises(ValueError, match="duplicate edge_id"):
        validator(payload)
