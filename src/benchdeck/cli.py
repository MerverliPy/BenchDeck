from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from .config import load_config
from .inspect import inspect_run
from .models import RunStatus
from .tui import BenchDeckTUI

logger = logging.getLogger("benchdeck")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchdeck", description="Agent benchmark harness and TUI"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to a TOML configuration file",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: WARNING)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a benchmark")
    run.add_argument("--agent-a", type=Path, required=True)
    run.add_argument("--agent-b", type=Path)
    run.add_argument("--plan", type=Path, help="Use a pre-generated benchmark plan")
    run.add_argument("--output-dir", type=Path, default=Path("benchmark_out"))
    run.add_argument("--model", default="gpt-4o-mini")
    run.add_argument("--judge-model", default="gpt-4o-mini")

    tui = sub.add_parser("tui", help="Open the live terminal dashboard")
    tui.add_argument("run_dir", type=Path)
    tui.add_argument("--refresh", type=float, default=1.0)

    inspect_cmd = sub.add_parser("inspect", help="Audit an existing output directory")
    inspect_cmd.add_argument("run_dir", type=Path)
    inspect_cmd.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    cfg = load_config(args.config if hasattr(args, "config") else None)
    if cfg:
        logger.debug("Loaded config: %s", cfg)

    if args.command == "run":
        if not os.environ.get("OPENAI_API_KEY"):
            print("Error: OPENAI_API_KEY environment variable is not set.", file=sys.stderr)
            print("Set it with: export OPENAI_API_KEY='sk-...'", file=sys.stderr)
            return 1
        from .runner import BenchmarkRunner

        runner = BenchmarkRunner(
            agent_a_path=args.agent_a,
            agent_b_path=args.agent_b,
            output_dir=args.output_dir,
            model=args.model,
            judge_model=args.judge_model,
            plan_path=args.plan,
        )
        status = runner.run()
        print(status.value)
        if status == RunStatus.COMPLETED:
            return 0
        return 2
    if args.command == "tui":
        BenchDeckTUI(args.run_dir, args.refresh).run()
        return 0
    if args.command == "inspect":
        result = inspect_run(args.run_dir)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Status: {result['status']}")
            print(f"Coverage: {result['judged_cases']}/{result['planned_cases']}")
            print(f"Policy blocks: {result['policy_blocks']}")
            for warning in result["warnings"]:
                print(f"- {warning}")
        return 1 if result["warnings"] else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
