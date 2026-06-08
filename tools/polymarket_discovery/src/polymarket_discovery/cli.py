from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from .config import ensure_artifact_dir, generate_run_id, load_config
from .pipeline import PipelineComponents, build_default_components, run_pipeline, write_run_artifact
from .utils.jsonl_logging import setup_jsonl_logging

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="polymarket-discovery")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run offline discovery pipeline")
    run_parser.add_argument("--config", required=True, help="Path to JSON config file")

    return parser


def run_command(config_path: str | Path, components: PipelineComponents | None = None) -> int:
    config = load_config(config_path)
    run_id = generate_run_id(config)
    artifact_dir = ensure_artifact_dir(config, run_id)
    setup_jsonl_logging(path=artifact_dir / "stages.jsonl", run_id=run_id)

    logger.info(
        "run_started",
        extra={
            "config_path": str(config_path),
            "artifact_dir": str(artifact_dir),
        },
    )

    output_path = artifact_dir / "baskets.json"
    try:
        resolved_components = components or build_default_components(config)
        result = run_pipeline(config=config, components=resolved_components, run_id=run_id)
        write_run_artifact(result, str(output_path))
    except Exception as exc:
        logger.info(
            "run_failed",
            extra={
                "artifact_dir": str(artifact_dir),
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise

    logger.info(
        "run_completed",
        extra={
            "artifact_dir": str(artifact_dir),
            "output_path": str(output_path),
            "stages": list(config.stages),
            "basket_count": len(result.document.baskets),
        },
    )

    return 0


def main(argv: Sequence[str] | None = None, *, components: PipelineComponents | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return run_command(config_path=args.config, components=components)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
