from __future__ import annotations

import json
from pathlib import Path

from alpha_engine.cli_commands import report as report_cmd


def _write_summary(reports_dir: Path, run_id: str, total_pnl: float) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / f"summary_{run_id}.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "env_name": "toy",
                "mode": "backtest",
                "strategy_class": "ToyBuyAndHold",
                "start_ts": "2026-01-02T14:30:00+00:00",
                "end_ts": "2026-01-02T15:30:00+00:00",
                "git_sha": "abc",
                "halt_cause": None,
                "metrics": {
                    "total_pnl": total_pnl,
                    "sharpe": 0.5,
                    "max_drawdown": -50.0,
                    "trades": 4,
                    "win_rate": 0.5,
                    "avg_holding_sec": 1800.0,
                },
            }
        ),
        encoding="utf-8",
    )


def test_prints_latest_summary(tmp_path: Path, capsys):
    envs_root = tmp_path / "envs"
    reports = envs_root / "toy" / "reports"
    _write_summary(reports, "run_20260102T143000Z_a", 50.0)
    _write_summary(reports, "run_20260102T153000Z_b", 75.0)

    rc = report_cmd.run(envs_root=envs_root, name="toy", run=None)
    assert rc == 0
    out = capsys.readouterr().out
    assert "run_20260102T153000Z_b" in out
    assert "75.0" in out or "75.00" in out


def test_prints_specific_run(tmp_path: Path, capsys):
    envs_root = tmp_path / "envs"
    reports = envs_root / "toy" / "reports"
    _write_summary(reports, "run_a", 50.0)
    _write_summary(reports, "run_b", 75.0)

    rc = report_cmd.run(envs_root=envs_root, name="toy", run="run_a")
    assert rc == 0
    out = capsys.readouterr().out
    assert "run_a" in out
    assert "50.0" in out or "50.00" in out


def test_unknown_env(tmp_path: Path, capsys):
    rc = report_cmd.run(envs_root=tmp_path / "envs", name="missing", run=None)
    assert rc != 0
