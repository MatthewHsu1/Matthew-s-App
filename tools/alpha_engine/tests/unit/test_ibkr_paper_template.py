from __future__ import annotations

import json
from importlib import resources
from pathlib import Path


def test_ibkr_paper_template_loadable_by_loader(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IBKR_ACCOUNT_ID", "DU123")
    monkeypatch.setenv("IBKR_USERNAME", "u")
    monkeypatch.setenv("IBKR_PASSWORD", "p")

    template_text = (
        resources.files("alpha_engine.configs.templates")
        .joinpath("ibkr_paper.json")
        .read_text()
    )
    raw = json.loads(template_text)
    # Validate via loader path.
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(raw))

    from alpha_engine.config.loader import load_env_config
    from alpha_engine.contracts.mode import Mode

    cfg = load_env_config(cfg_path)
    assert cfg.mode is Mode.PAPER
    assert cfg.venue.id == "ibkr"
    assert cfg.venue.account_kind == "paper"


def test_compose_yaml_present_and_lists_paper_service():
    compose = Path(__file__).resolve().parents[2] / "docker" / "docker-compose.yml"
    assert compose.exists(), f"missing {compose}"
    text = compose.read_text()
    assert "ib-gateway" in text
    assert "4002" in text  # paper port
    assert "profiles" in text  # live container is behind a profile
