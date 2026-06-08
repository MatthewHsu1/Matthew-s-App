"""Unit tests for scripts/backfill_databento.py.

Does not call the real Databento API. Tests the file-finding, dispatch, and
catalog-write logic with a stubbed loader.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def test_load_files_into_catalog_writes_each_dbn(tmp_path: Path) -> None:
    from scripts.backfill_databento import load_files_into_catalog

    dbn_dir = tmp_path / "dbn"
    dbn_dir.mkdir()
    (dbn_dir / "AAPL_2024-01.dbn.zst").write_bytes(b"")
    (dbn_dir / "MSFT_2024-01.dbn.zst").write_bytes(b"")
    (dbn_dir / "ignore.txt").write_text("not a dbn file")

    catalog_root = tmp_path / "catalog"
    catalog_root.mkdir()

    fake_bars = [MagicMock()]
    with patch("scripts.backfill_databento.DatabentoDataLoader") as MockLoader, \
         patch("scripts.backfill_databento.ParquetDataCatalog") as MockCatalog:
        loader_instance = MockLoader.return_value
        loader_instance.from_dbn_file.return_value = fake_bars
        catalog_instance = MockCatalog.return_value

        n = load_files_into_catalog(
            dbn_dir=dbn_dir, catalog_root=catalog_root,
        )

    assert n == 2
    assert loader_instance.from_dbn_file.call_count == 2
    assert catalog_instance.write_data.call_count == 2


def test_load_files_skips_non_dbn(tmp_path: Path) -> None:
    from scripts.backfill_databento import load_files_into_catalog

    dbn_dir = tmp_path / "dbn"
    dbn_dir.mkdir()
    (dbn_dir / "notes.md").write_text("# nope")

    catalog_root = tmp_path / "catalog"
    catalog_root.mkdir()

    with patch("scripts.backfill_databento.DatabentoDataLoader"), \
         patch("scripts.backfill_databento.ParquetDataCatalog"):
        n = load_files_into_catalog(dbn_dir=dbn_dir, catalog_root=catalog_root)

    assert n == 0
