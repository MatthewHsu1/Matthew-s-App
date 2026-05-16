from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


DEFAULT_ENVS_ROOT = Path(__file__).resolve().parent.parent.parent / "envs"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alpha-engine")
    parser.add_argument(
        "--envs-root",
        default=str(DEFAULT_ENVS_ROOT),
        help="Path to the envs/ directory (default: tools/alpha_engine/envs).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    env = subparsers.add_parser("env", help="Env lifecycle")
    env_sub = env.add_subparsers(dest="env_command", required=True)

    new = env_sub.add_parser("new", help="Create a new env from a template")
    new.add_argument("name", help="Env name (alphanumerics, _, -)")
    new.add_argument("--from-template", required=True, help="Template name (e.g. 'backtest')")

    env_sub.add_parser("list", help="List envs")

    start = env_sub.add_parser("start", help="Start an env run")
    start.add_argument("name", help="Env name")

    stop = env_sub.add_parser("stop", help="Stop a running env")
    stop.add_argument("name", help="Env name")
    stop.add_argument("--timeout", type=float, default=30.0, help="SIGTERM timeout (s)")

    status = env_sub.add_parser("status", help="Show env status")
    status.add_argument("name", help="Env name")

    tail = env_sub.add_parser("tail", help="Tail a JSONL log stream")
    tail.add_argument("name", help="Env name")
    tail.add_argument("--stream", choices=["engine", "orders", "risk"], default="engine")
    tail.add_argument("--no-follow", dest="follow", action="store_false")
    tail.set_defaults(follow=True)

    report = subparsers.add_parser("report", help="Print a run summary")
    report.add_argument("name", help="Env name")
    report.add_argument("--run", default=None, help="Specific run_id (defaults to latest)")

    subparsers.add_parser("kill-all", help="Touch the global .KILL file")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    envs_root = Path(args.envs_root).resolve()
    envs_root.mkdir(parents=True, exist_ok=True)

    if args.command == "env":
        if args.env_command == "new":
            from alpha_engine.cli_commands import env_new
            return env_new.run(envs_root=envs_root, name=args.name, template=args.from_template)
        if args.env_command == "list":
            from alpha_engine.cli_commands import env_list
            return env_list.run(envs_root=envs_root)
        if args.env_command == "start":
            from alpha_engine.cli_commands import env_start
            return env_start.run(envs_root=envs_root, name=args.name)
        if args.env_command == "stop":
            from alpha_engine.cli_commands import env_stop
            return env_stop.run(envs_root=envs_root, name=args.name, timeout_s=args.timeout)
        if args.env_command == "status":
            from alpha_engine.cli_commands import env_status
            return env_status.run(envs_root=envs_root, name=args.name)
        if args.env_command == "tail":
            from alpha_engine.cli_commands import env_tail
            return env_tail.run(
                envs_root=envs_root, name=args.name, stream=args.stream, follow=args.follow,
            )

    if args.command == "report":
        from alpha_engine.cli_commands import report as report_cmd
        return report_cmd.run(envs_root=envs_root, name=args.name, run=args.run)

    if args.command == "kill-all":
        from alpha_engine.cli_commands import kill_all
        return kill_all.run(envs_root=envs_root)

    parser.error(f"unhandled command: {args.command}")
    return 2
