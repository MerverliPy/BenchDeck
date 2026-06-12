"""Tests for the benchdeck CLI entry point (cli.py)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from benchdeck.cli import build_parser, main


def test_build_parser_run_subcommand() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["run", "--agent-a", "/tmp/agent.md", "--model", "gpt-4o", "--output-dir", "/tmp/out"]
    )
    assert args.command == "run"
    assert args.agent_a == Path("/tmp/agent.md")
    assert args.agent_b is None
    assert args.model == "gpt-4o"
    assert args.judge_model == "gpt-4o-mini"
    assert args.output_dir == Path("/tmp/out")
    assert args.plan is None


def test_build_parser_run_default_model() -> None:
    parser = build_parser()
    args = parser.parse_args(["run", "--agent-a", "/tmp/agent.md"])
    assert args.model == "gpt-4o-mini"
    assert args.judge_model == "gpt-4o-mini"


def test_build_parser_run_comparison() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "--agent-a",
            "/tmp/agent_a.md",
            "--agent-b",
            "/tmp/agent_b.md",
            "--plan",
            "/tmp/plan.json",
        ]
    )
    assert args.command == "run"
    assert args.agent_a == Path("/tmp/agent_a.md")
    assert args.agent_b == Path("/tmp/agent_b.md")
    assert args.plan == Path("/tmp/plan.json")


def test_build_parser_run_requires_agent_a() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["run"])


def test_build_parser_requires_subcommand() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_build_parser_tui_subcommand() -> None:
    parser = build_parser()
    args = parser.parse_args(["tui", "/tmp/run_dir"])
    assert args.command == "tui"
    assert args.run_dir == Path("/tmp/run_dir")
    assert args.refresh == 1.0


def test_build_parser_tui_custom_refresh() -> None:
    parser = build_parser()
    args = parser.parse_args(["tui", "/tmp/run_dir", "--refresh", "0.5"])
    assert args.command == "tui"
    assert args.refresh == 0.5


def test_build_parser_inspect_subcommand() -> None:
    parser = build_parser()
    args = parser.parse_args(["inspect", "/tmp/run_dir"])
    assert args.command == "inspect"
    assert args.run_dir == Path("/tmp/run_dir")
    assert args.json is False


def test_build_parser_inspect_json_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["inspect", "/tmp/run_dir", "--json"])
    assert args.command == "inspect"
    assert args.json is True


def test_main_run_missing_api_key() -> None:
    with patch.dict(os.environ, {}, clear=True):
        result = main(["run", "--agent-a", "/tmp/agent.md"])
        assert result == 1


def test_main_run_returns_2_on_planner_failure_with_invalid_key(tmp_path: Path) -> None:
    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# Agent\n")
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
        result = main(["run", "--agent-a", str(agent_path), "--output-dir", str(tmp_path / "out")])
        assert result == 2


def test_main_tui_exits_on_bad_run_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "nonexistent"
    with patch("benchdeck.cli.BenchDeckTUI") as mock_tui:
        mock_tui.return_value.run.return_value = None
        result = main(["tui", str(run_dir)])
    assert result == 0


def test_main_inspect_text_output(tmp_path: Path) -> None:
    run_dir = tmp_path / "inspect_dir"
    run_dir.mkdir()
    (run_dir / "run_metadata.json").write_text(
        json.dumps({"status": "completed", "cases_in_plan": 8, "executions_judged": 8})
    )
    (run_dir / "benchmark_plan.json").write_text("{}")
    (run_dir / "summary_tally.json").write_text(
        json.dumps(
            {"agent_a": {"cases_planned": 8, "cases_judged": 8, "score_scale": {"Excellent": 4}}}
        )
    )
    (run_dir / "case_judgments.json").write_text("[]")
    (run_dir / "policy_blocks.json").write_text("[]")
    (run_dir / "run_results.json").write_text("{}")

    result = main(["inspect", str(run_dir)])
    assert result in (0, 1)


def test_main_inspect_json_output(tmp_path: Path) -> None:
    run_dir = tmp_path / "inspect_dir"
    run_dir.mkdir()
    (run_dir / "run_metadata.json").write_text(
        json.dumps({"status": "completed", "cases_in_plan": 8, "executions_judged": 8})
    )
    (run_dir / "benchmark_plan.json").write_text("{}")
    (run_dir / "summary_tally.json").write_text(
        json.dumps(
            {"agent_a": {"cases_planned": 8, "cases_judged": 8, "score_scale": {"Excellent": 4}}}
        )
    )
    (run_dir / "case_judgments.json").write_text("[]")
    (run_dir / "policy_blocks.json").write_text("[]")
    (run_dir / "run_results.json").write_text("{}")

    result = main(["inspect", str(run_dir), "--json"])
    assert result in (0, 1)


def test_main_unknown_command() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["nonexistent"])
    assert exc_info.value.code == 2


def test_main_print_help() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
