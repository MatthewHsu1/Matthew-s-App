from __future__ import annotations

import os
from pathlib import Path

import pytest

from alpha_engine.config.secrets import (
    SecretsError,
    load_secrets_file,
    resolve_required_env_vars,
)


def test_load_secrets_basic(tmp_path: Path, monkeypatch):
    f = tmp_path / "secrets.env"
    f.write_text("IBKR_USERNAME=alice\nIBKR_PASSWORD=hunter2\n")
    monkeypatch.delenv("IBKR_USERNAME", raising=False)
    load_secrets_file(f)
    assert os.environ["IBKR_USERNAME"] == "alice"
    assert os.environ["IBKR_PASSWORD"] == "hunter2"


def test_load_secrets_ignores_comments_and_blanks(tmp_path: Path, monkeypatch):
    f = tmp_path / "secrets.env"
    f.write_text("# comment\n\nIBKR_USERNAME=bob\n")
    monkeypatch.delenv("IBKR_USERNAME", raising=False)
    load_secrets_file(f)
    assert os.environ["IBKR_USERNAME"] == "bob"


def test_load_secrets_strips_quotes(tmp_path: Path, monkeypatch):
    f = tmp_path / "secrets.env"
    f.write_text('IBKR_USERNAME="quoted"\n')
    monkeypatch.delenv("IBKR_USERNAME", raising=False)
    load_secrets_file(f)
    assert os.environ["IBKR_USERNAME"] == "quoted"


def test_load_secrets_missing_file_is_ok(tmp_path: Path):
    # Loader should be a no-op (paper trades can rely on already-set env vars).
    load_secrets_file(tmp_path / "absent.env")


def test_resolve_required_env_vars_all_present(monkeypatch):
    monkeypatch.setenv("A", "1")
    monkeypatch.setenv("B", "2")
    out = resolve_required_env_vars({"a": "A", "b": "B"})
    assert out == {"a": "1", "b": "2"}


def test_resolve_required_env_vars_missing(monkeypatch):
    monkeypatch.delenv("MISSING_X", raising=False)
    with pytest.raises(SecretsError, match="MISSING_X"):
        resolve_required_env_vars({"x": "MISSING_X"})
