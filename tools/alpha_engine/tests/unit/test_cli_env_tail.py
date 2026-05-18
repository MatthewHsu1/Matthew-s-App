from __future__ import annotations

from pathlib import Path

from alpha_engine.cli_commands.env_tail import run as env_tail


def test_unknown_stream_returns_nonzero(tmp_path: Path):
    code = env_tail(envs_root=tmp_path, name="e", stream="garbage", follow=False)
    assert code != 0


def test_missing_log_returns_nonzero(tmp_path: Path):
    code = env_tail(envs_root=tmp_path, name="e", stream="engine", follow=False)
    assert code != 0


def test_tail_prints_existing_content_when_follow_false(tmp_path: Path, capsys):
    logs = tmp_path / "e" / "logs"
    logs.mkdir(parents=True)
    (logs / "engine.jsonl").write_text('{"event":"engine_started"}\n{"event":"engine_halted"}\n')
    code = env_tail(envs_root=tmp_path, name="e", stream="engine", follow=False)
    assert code == 0
    out = capsys.readouterr().out
    assert "engine_started" in out
    assert "engine_halted" in out
