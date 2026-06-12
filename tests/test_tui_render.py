"""Tests for TUI rendering output without curses.

All render methods are pure Snapshot -> list[str] transforms.
No terminal required.
"""

from __future__ import annotations

from pathlib import Path

from benchdeck.loader import Snapshot
from benchdeck.tui import BenchDeckTUI


def _make_tui(**kwargs: object) -> BenchDeckTUI:
    tui = BenchDeckTUI(Path("/tmp/fake_run"))
    for key, value in kwargs.items():
        setattr(tui, key, value)
    return tui


def _snapshot_with_data(
    *,
    metadata: dict | None = None,
    plan: dict | None = None,
    tally: dict | None = None,
    judgments: list | None = None,
    results: dict | None = None,
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
