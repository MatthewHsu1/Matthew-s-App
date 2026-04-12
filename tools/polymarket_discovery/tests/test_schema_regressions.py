from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.serialization import validate_output_document


def _load_fixture(name: str) -> dict[str, object]:
    path = ROOT / "tests" / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("fixture_name", "expected_message"),
    [
        ("invalid_output_orphan_dependency_refs.json", "orphan market refs"),
        ("invalid_output_missing_basket_dependency_ref.json", "missing dependency edge ID"),
    ],
)
def test_invalid_output_fixtures_are_rejected(
    fixture_name: str,
    expected_message: str,
) -> None:
    payload = _load_fixture(fixture_name)

    with pytest.raises(ValueError, match=expected_message):
        validate_output_document(payload)
