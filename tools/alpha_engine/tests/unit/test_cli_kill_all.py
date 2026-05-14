from __future__ import annotations

from pathlib import Path

from alpha_engine.cli_commands import kill_all


def test_creates_global_kill_file(tmp_path: Path, capsys):
    envs_root = tmp_path / "envs"
    rc = kill_all.run(envs_root=envs_root)
    assert rc == 0
    assert (envs_root / ".KILL").exists()
    assert "kill" in capsys.readouterr().out.lower()


def test_idempotent(tmp_path: Path):
    envs_root = tmp_path / "envs"
    assert kill_all.run(envs_root=envs_root) == 0
    assert kill_all.run(envs_root=envs_root) == 0
    assert (envs_root / ".KILL").exists()
