"""Backfill the shared ParquetDataCatalog from Databento .dbn.zst files.

Usage:
    python -m scripts.backfill_databento \
        --dbn-dir /path/to/dbn_downloads \
        --catalog /mnt/HDD/Projects/Financial_App/catalog

The script is idempotent: re-running with overlapping date ranges is safe
because Nautilus's ParquetDataCatalog de-duplicates by (instrument_id, ts_event).

Operational notes:
- Acquire Databento data via their web UI or API. This script consumes the
  raw .dbn.zst files; it does not call the Databento API itself (keeps the
  script offline-runnable and avoids embedding credentials).
- Required Databento schemas: ohlcv-1d (daily bars), ohlcv-5m (5-minute bars).
- Recommended dataset: XNAS.ITCH for S&P 500 names on NASDAQ.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from nautilus_trader.adapters.databento.loaders import DatabentoDataLoader
from nautilus_trader.persistence.catalog import ParquetDataCatalog


def load_files_into_catalog(*, dbn_dir: Path, catalog_root: Path) -> int:
    """Load every .dbn.zst file under dbn_dir into the catalog at catalog_root.

    Returns the number of files processed. Files not matching the .dbn.zst
    suffix are skipped silently (so the directory can hold notes, logs, etc.).
    """
    loader = DatabentoDataLoader()
    catalog = ParquetDataCatalog(path=str(catalog_root))

    files = sorted(p for p in dbn_dir.iterdir() if p.name.endswith(".dbn.zst"))
    for f in files:
        bars = loader.from_dbn_file(path=str(f), as_legacy_cython=False)
        catalog.write_data(bars)
    return len(files)


def _cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dbn-dir", required=True, type=Path,
                        help="Directory containing .dbn.zst files")
    parser.add_argument("--catalog", required=True, type=Path,
                        help="ParquetDataCatalog root directory")
    args = parser.parse_args()

    if not args.dbn_dir.is_dir():
        raise SystemExit(f"--dbn-dir not a directory: {args.dbn_dir}")
    args.catalog.mkdir(parents=True, exist_ok=True)

    n = load_files_into_catalog(dbn_dir=args.dbn_dir, catalog_root=args.catalog)
    print(f"loaded {n} .dbn.zst files into {args.catalog}")


if __name__ == "__main__":
    _cli()
