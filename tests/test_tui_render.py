"""Tests for TUI rendering output without curses.

All render methods are pure Snapshot -> list[str] transforms.
No terminal required.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from benchdeck.loader import Snapshot
from benchdeck.tui import BenchDeckTUI


def _make_tui(**kwargs: object) -> BenchDeckTUI:
    tui = BenchDeckTUI(Path("/tmp/fake_run"))
    for key, value in kwargs.items():
        setattr(tui, key, value)
    return tui


@contextmanager
def _mock_popen() -> Generator[MagicMock, None, None]:
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.poll.return_value = None
    with patch("benchdeck.tui._sp.Popen", return_value=mock_proc) as mock_popen:
        yield mock_popen


def _snapshot_with_data(
    *,
    metadata: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
    tally: dict[str, Any] | None = None,
    judgments: list[dict[str, Any]] | None = None,
    results: dict[str, Any] | None = None,
) -> Snapshot:
    return Snapshot(
        metadata=metadata or {},
        plan=plan or {},
        tally=tally or {},
        judgments=judgments or [],
        results=results or {},
    )


# ── overview ────────────────────────────────────────────────────────────────


def test_overview_shows_run_dir() -> None:
    tui = _make_tui(
        run_dir=Path("/tmp/fake_run"),
        snapshot=Snapshot(
            metadata={
                "cases_in_plan": 8,
                "executions_judged": 4,
                "token_usage": {"requests": 10, "total_tokens": 5000},
            },
            tally={},
        ),
    )
    lines = tui._overview(80)
    assert any("fake_run" in line for line in lines)
    assert any("4/8" in line for line in lines)


def test_overview_progress_bar() -> None:
    tui = _make_tui(
        snapshot=Snapshot(
            metadata={
                "cases_in_plan": 8,
                "executions_judged": 4,
                "token_usage": {"requests": 1, "total_tokens": 100},
            },
            tally={},
        ),
    )
    lines = tui._overview(80)
    bar_line = next(line for line in lines if "]" in line and "[" in line and "#" in line)
    assert "#" in bar_line
    assert "-" in bar_line


def test_overview_shows_policy_blocks_and_infra() -> None:
    tui = _make_tui(
        snapshot=Snapshot(
            metadata={
                "cases_in_plan": 8,
                "executions_judged": 8,
                "policy_blocks": 2,
                "infrastructure_failures": 1,
                "token_usage": {},
            },
            tally={},
        ),
    )
    lines = tui._overview(80)
    joined = "\n".join(lines)
    assert "2" in joined  # policy blocks
    assert "1" in joined  # infra failures


def test_overview_shows_tally_data() -> None:
    tui = _make_tui(
        snapshot=Snapshot(
            metadata={
                "cases_in_plan": 8,
                "executions_judged": 8,
                "token_usage": {"requests": 1, "total_tokens": 200},
            },
            tally={
                "agent_a": {
                    "score_scale": {"Excellent": 4},
                    "rating_counts": {"Excellent": 5, "Strong": 3},
                    "family_scores": {"happy_path": 4.0},
                    "gate_failures": 0,
                }
            },
        ),
    )
    lines = tui._overview(80)
    assert any("Excellent" in line for line in lines)


def test_overview_no_tally_data() -> None:
    tui = _make_tui(
        snapshot=Snapshot(
            metadata={"cases_in_plan": 8, "executions_judged": 0, "token_usage": {}},
            tally={},
        ),
    )
    lines = tui._overview(80)
    assert any("No tally data" in line for line in lines)


def test_overview_shows_planner_errors() -> None:
    tui = _make_tui(
        snapshot=Snapshot(
            metadata={"cases_in_plan": 8, "executions_judged": 0, "token_usage": {}},
            tally={},
            planner_capture={"terminal_error": {"message": "test error"}, "total_http_attempts": 3},
        ),
    )
    lines = tui._overview(80)
    joined = "\n".join(lines)
    assert "test error" in joined


# ── help ────────────────────────────────────────────────────────────────────


def test_help_contains_controls() -> None:
    tui = _make_tui()
    lines = tui._help(40)
    joined = "\n".join(lines)
    assert "1-4" in joined
    assert "h / l" in joined
    assert "j / k" in joined
    assert "Enter" in joined


# ── detail ──────────────────────────────────────────────────────────────────


def test_detail_no_cases() -> None:
    tui = _make_tui(snapshot=Snapshot(plan={}))
    lines = tui._detail(80)
    assert any("No benchmark plan" in line for line in lines)


def test_detail_with_judgment() -> None:
    tui = _make_tui(
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {
                        "id": 1,
                        "title": "Case One",
                        "family": "happy_path",
                        "purpose": "Test purpose",
                        "test_prompt": "Do it",
                    },
                ]
            },
            judgments=[
                {
                    "case_id": 1,
                    "agent_label": "agent_a",
                    "overall_rating": "Strong",
                    "why": "good",
                    "gate_check": {"status": "Pass", "reason": "ok"},
                }
            ],
            results={},
        ),
    )
    lines = tui._detail(80)
    joined = "\n".join(lines)
    assert "Case 1" in joined
    assert "Case One" in joined
    assert "Strong" in joined


# ── case list ────────────────────────────────────────────────────────────────


def test_case_list_with_judgments() -> None:
    tui = _make_tui(
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {"id": 1, "title": "First Case"},
                    {"id": 2, "title": "Second Case"},
                ]
            },
            judgments=[
                {"case_id": 1, "agent_label": "agent_a", "overall_rating": "Excellent"},
                {"case_id": 2, "agent_label": "agent_a", "overall_rating": "Weak"},
            ],
        ),
    )
    lines = tui._case_list(80)
    assert any("Excellent" in line for line in lines)
    assert any("Weak" in line for line in lines)


def test_case_list_shows_pending() -> None:
    tui = _make_tui(
        selected=0,
        snapshot=Snapshot(
            plan={"cases": [{"id": 1, "title": "Pending Case"}]},
            judgments=[],
        ),
    )
    lines = tui._case_list(80)
    assert any("PENDING" in line for line in lines)


def test_case_list_shows_blocked() -> None:
    tui = _make_tui(
        selected=0,
        snapshot=Snapshot(
            plan={"cases": [{"id": 1, "title": "Blocked Case"}]},
            judgments=[],
            policy_blocks=[{"case_id": 1, "agent_label": "agent_a"}],
        ),
    )
    lines = tui._case_list(80)
    assert any("BLOCKED" in line for line in lines)


# ── export ──────────────────────────────────────────────────────────────────


def test_export_case_uses_absolute_path(tmp_path: Path) -> None:
    tui = BenchDeckTUI(tmp_path)
    tui.snapshot = Snapshot(
        plan={
            "cases": [
                {
                    "id": 1,
                    "title": "Exported Case",
                    "family": "happy_path",
                    "purpose": "test",
                    "test_prompt": "do",
                }
            ]
        },
        judgments=[],
        results={},
    )
    tui.selected = 0
    tui._export_case()
    assert tui._status_msg != ""
    assert "Exported" in tui._status_msg
    exported = list(tmp_path.glob("case_*.md"))
    assert len(exported) == 1
    content = exported[0].read_text(encoding="utf-8")
    assert "Exported Case" in content


def test_export_case_no_cases_does_nothing() -> None:
    tui = BenchDeckTUI(Path("/tmp/fake"))
    tui.snapshot = Snapshot(plan={})
    tui._export_case()
    assert tui._status_msg == ""


# ── scroll clamping ─────────────────────────────────────────────────────────


def test_clamp_scroll_bounds_check() -> None:
    lines = ["line 1", "line 2", "line 3"]
    assert BenchDeckTUI._clamp_scroll(lines, 2, 999, 0, 0) == 1
    assert BenchDeckTUI._clamp_scroll(lines, 3, 5, 0, 0) == 0
    assert BenchDeckTUI._clamp_scroll(lines, 1, 0, 0, 0) == 0


def test_clamp_scroll_keeps_selected_visible_on_case_list() -> None:
    lines = [f"case {i}" for i in range(20)]
    scroll = BenchDeckTUI._clamp_scroll(lines, 5, 0, 1, 18)
    assert scroll > 0
    assert scroll <= 18 - 5 + 2


def test_clamp_scroll_non_case_list_ignores_selection() -> None:
    lines = [f"row {i}" for i in range(50)]
    scroll = BenchDeckTUI._clamp_scroll(lines, 10, 0, 0, 40)
    assert scroll == 0


# ── subprocess launch ───────────────────────────────────────────────────────


def test_launch_run_rejects_missing_agent_file(tmp_path: Path) -> None:
    tui = BenchDeckTUI(tmp_path, agent_a_path=Path("/nonexistent/agent.md"))
    tui._launch_run()
    assert "not found" in tui._status_msg


def test_launch_run_uses_snapshot_metadata_fallback(tmp_path: Path) -> None:
    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# test agent")
    tui = BenchDeckTUI(tmp_path)
    tui.snapshot = Snapshot(metadata={"config": {"agent_a": str(agent_path), "model": "gpt-4o"}})
    with _mock_popen():
        tui._launch_run()
        assert tui._status_msg.startswith("Launched PID")
        assert tui._proc is not None
        tui._cancel_run()


def test_launch_run_prefers_explicit_args(tmp_path: Path) -> None:
    agent_a = tmp_path / "explicit_agent.md"
    agent_a.write_text("# test")
    tui = BenchDeckTUI(tmp_path, agent_a_path=agent_a, model="gpt-4o-mini")
    tui.snapshot = Snapshot(metadata={"config": {"agent_a": "/other/agent.md", "model": "gpt-4o"}})
    with _mock_popen():
        tui._launch_run()
        assert tui._status_msg.startswith("Launched PID")


# ── case list at narrow width ───────────────────────────────────────────────


def test_case_list_renders_at_minimum_width() -> None:
    tui = _make_tui(
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {"id": 1, "title": "A" * 50},
                    {"id": 2, "title": "BBBB"},
                ]
            },
            judgments=[
                {"case_id": 1, "agent_label": "agent_a", "overall_rating": "Excellent"},
            ],
        ),
    )
    lines = tui._case_list(32)
    assert len(lines) >= 2
    assert any("Excellent" in line for line in lines)


# ── plan warning ────────────────────────────────────────────────────────────


def test_detail_shows_orphan_infra_errors() -> None:
    tui = _make_tui(
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {"id": 1, "title": "Case", "family": "happy_path", "purpose": "x"},
                ]
            },
            infrastructure_errors=[
                {
                    "case_id": None,
                    "agent_label": "agent_a",
                    "stage": "planner",
                    "error_type": "ConfigError",
                    "message": "Bad config",
                },
                {
                    "case_id": 1,
                    "agent_label": "agent_a",
                    "stage": "agent",
                    "error_type": "Timeout",
                    "message": "timed out",
                },
            ],
        ),
    )
    lines = tui._detail(80)
    text = "\n".join(lines)
    assert "Pre-execution infrastructure errors" in text
    assert "ConfigError" in text
    assert "Bad config" in text
    assert "Timeout" in text


# ── cancel confirmation ────────────────────────────────────────────────────


def test_cancel_requires_double_press(tmp_path: Path) -> None:
    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# test")
    tui = BenchDeckTUI(tmp_path, agent_a_path=agent_path, model="gpt-4o")
    with _mock_popen():
        tui._launch_run()
        assert tui._proc is not None
    tui._handle_cancel_key()
    assert tui._proc is not None
    assert "again" in tui._status_msg.lower()
    assert tui._cancel_requested_at is not None


def test_cancel_double_press_terminates(tmp_path: Path) -> None:
    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# test")
    tui = BenchDeckTUI(tmp_path, agent_a_path=agent_path, model="gpt-4o")
    with _mock_popen():
        tui._launch_run()
    tui._handle_cancel_key()
    tui._handle_cancel_key()
    assert tui._proc is None
    assert "Cancelled" in tui._status_msg


def test_cancel_cleared_by_any_other_key(tmp_path: Path) -> None:
    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# test")
    tui = BenchDeckTUI(tmp_path, agent_a_path=agent_path, model="gpt-4o")
    with _mock_popen():
        tui._launch_run()
    tui._handle_cancel_key()
    assert tui._cancel_requested_at is not None
    tui._handle_key(ord("j"))
    assert tui._cancel_requested_at is None
    assert tui._proc is not None


def test_cancel_timeout_clears_request(tmp_path: Path) -> None:
    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# test")
    tui = BenchDeckTUI(tmp_path, agent_a_path=agent_path, model="gpt-4o")
    with _mock_popen():
        tui._launch_run()
    tui._handle_cancel_key()
    assert tui._cancel_requested_at is not None
    tui._cancel_requested_at = tui._cancel_requested_at - 10.0
    tui._handle_key(ord(" "))
    assert tui._cancel_requested_at is None
