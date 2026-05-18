from __future__ import annotations

import pytest

from alpha_engine.config.paths import EnvPaths


def test_env_paths_root_layout(tmp_path):
    root = tmp_path / "envs"
    p = EnvPaths(envs_root=root, env_name="toy")
    assert p.env_dir == root / "toy"
    assert p.config_path == root / "toy" / "config.json"
    assert p.secrets_path == root / "toy" / "secrets.env"
    assert p.state_dir == root / "toy" / "state"
    assert p.logs_dir == root / "toy" / "logs"
    assert p.reports_dir == root / "toy" / "reports"


def test_ensure_dirs_creates_subdirs(tmp_path):
    root = tmp_path / "envs"
    p = EnvPaths(envs_root=root, env_name="toy")
    p.ensure_dirs()
    assert p.state_dir.is_dir()
    assert p.logs_dir.is_dir()
    assert p.reports_dir.is_dir()


def test_rejects_traversal_in_env_name(tmp_path):
    with pytest.raises(ValueError):
        EnvPaths(envs_root=tmp_path / "envs", env_name="../escape")
    with pytest.raises(ValueError):
        EnvPaths(envs_root=tmp_path / "envs", env_name="a/b")
