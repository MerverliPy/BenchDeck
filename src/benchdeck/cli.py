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
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Write JSON-structured logs to a file",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a benchmark")
    run.add_argument("--agent-a", type=Path, required=True)
    run.add_argument("--agent-b", type=Path)
    run.add_argument("--plan", type=Path, help="Use a pre-generated benchmark plan")
    run.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmark_out"),
        help="Parent directory where timestamped run subdirectories accumulate",
    )
    run.add_argument("--model", default=None)
    run.add_argument(
        "--planner-model",
        default=None,
        help="Model for plan generation (defaults to --model)",
    )
    run.add_argument("--judge-model", default=None)
    run.add_argument("--timeout", type=float, default=None, help="API timeout in seconds")
    run.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="Maximum retry attempts per call",
    )
    run.add_argument(
        "--max-output-tokens-planner",
        type=int,
        default=None,
    )
    run.add_argument(
        "--max-output-tokens-agent",
        type=int,
        default=None,
    )
    run.add_argument(
        "--max-output-tokens-judge",
        type=int,
        default=None,
    )
    run.add_argument(
        "--max-logical-requests",
        type=int,
        default=None,
    )
    run.add_argument(
        "--max-http-attempts",
        type=int,
        default=None,
    )
    run.add_argument(
        "--max-total-input-tokens",
        type=int,
        default=None,
    )
    run.add_argument(
        "--max-total-output-tokens",
        type=int,
        default=None,
    )
    run.add_argument(
        "--capture-level",
        choices=["minimal", "standard", "full"],
        default=None,
    )
    run.add_argument(
        "--judges",
        type=int,
        default=1,
        help="Number of independent judge calls per case (default: 1)",
    )
    run.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="Resume an interrupted run from the given run directory",
    )
    run.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite if a prior run exists at the exact output path (rarely needed; "
        "--output-dir is a parent accumulation directory)",
    )

    tui = sub.add_parser("tui", help="Open the live terminal dashboard")
    tui.add_argument("run_dir", type=Path)
    tui.add_argument("--refresh", type=float, default=1.0)

    inspect_cmd = sub.add_parser("inspect", help="Audit an existing output directory")
    inspect_cmd.add_argument("run_dir", type=Path)
    inspect_cmd.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from .logging_config import configure_logging

    configure_logging(
        level=args.log_level,
        log_file=args.log_file if hasattr(args, "log_file") else None,
        json_format=bool(args.log_file if hasattr(args, "log_file") else None),
    )
    cfg = load_config(args.config if hasattr(args, "config") else None)
    if cfg:
        logger.debug("Loaded config: %s", cfg)

    if args.command == "run":
        if not os.environ.get("OPENAI_API_KEY"):
            print("Error: OPENAI_API_KEY environment variable is not set.", file=sys.stderr)
            print("Set it with: export OPENAI_API_KEY='sk-...'", file=sys.stderr)
            return 1
        from .budget import BudgetLimits
        from .runner import BenchmarkRunner

        model = args.model or cfg.get("model") or "gpt-4o-mini"
        planner_model = args.planner_model or cfg.get("planner_model") or model
        judge_model = args.judge_model or cfg.get("judge_model") or model
        timeout = args.timeout if args.timeout is not None else cfg.get("timeout")
        max_retries = args.max_retries if args.max_retries is not None else cfg.get("max_retries")
        budget = BudgetLimits.from_dict(
            {
                "max_output_tokens_planner": args.max_output_tokens_planner
                or cfg.get("max_output_tokens_planner"),
                "max_output_tokens_agent": args.max_output_tokens_agent
                or cfg.get("max_output_tokens_agent"),
                "max_output_tokens_judge": args.max_output_tokens_judge
                or cfg.get("max_output_tokens_judge"),
                "max_logical_requests": args.max_logical_requests
                or cfg.get("max_logical_requests"),
                "max_http_attempts": args.max_http_attempts or cfg.get("max_http_attempts"),
                "max_total_input_tokens": args.max_total_input_tokens
                or cfg.get("max_total_input_tokens"),
                "max_total_output_tokens": args.max_total_output_tokens
                or cfg.get("max_total_output_tokens"),
            }
        )

        runner = BenchmarkRunner(
            agent_a_path=args.agent_a,
            agent_b_path=args.agent_b,
            output_dir=args.output_dir,
            model=model,
            planner_model=planner_model,
            judge_model=judge_model,
            plan_path=args.plan,
            overwrite=args.overwrite,
            timeout=timeout,
            max_retries=max_retries,
            budget=budget,
            resume_from=args.resume,
            num_judges=args.judges,
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
