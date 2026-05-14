from __future__ import annotations

import json
from pathlib import Path

from alpha_engine.cli_commands import env_list


def test_lists_envs(tmp_path: Path, capsys):
    envs_root = tmp_path / "envs"
    for n in ("alpha_a", "alpha_b"):
        (envs_root / n).mkdir(parents=True)
        (envs_root / n / "config.json").write_text(
            json.dumps({"mode": "backtest"}), encoding="utf-8"
        )
    rc = env_list.run(envs_root=envs_root)
    assert rc == 0
    captured = capsys.readouterr().out
    assert "alpha_a" in captured
    assert "alpha_b" in captured


def test_lists_nothing_when_empty(tmp_path: Path, capsys):
    envs_root = tmp_path / "envs"
    envs_root.mkdir()
    rc = env_list.run(envs_root=envs_root)
    assert rc == 0
    assert "no envs" in capsys.readouterr().out.lower()
