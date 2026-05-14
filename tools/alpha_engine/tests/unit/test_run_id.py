from __future__ import annotations

import re

from alpha_engine.config.run_id import generate_run_id


def test_run_id_format():
    rid = generate_run_id(env_name="toy", config_payload={"a": 1})
    assert re.match(r"^run_\d{8}T\d{6}Z_[0-9a-f]{12}$", rid), rid


def test_run_id_changes_when_config_changes():
    a = generate_run_id(env_name="toy", config_payload={"a": 1})
    b = generate_run_id(env_name="toy", config_payload={"a": 2})
    # Different hash suffix even if same timestamp.
    assert a.split("_")[-1] != b.split("_")[-1]
