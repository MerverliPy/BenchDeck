"""Tests for TUI rendering output without curses.

All render methods are pure Snapshot -> list[str] transforms.
No terminal required.
"""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from benchdeck.loader import Snapshot
from benchdeck.manifest import Manifest
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


# ── overview heartbeat (P2-3) ──────────────────────────────────────────────


def test_overview_shows_last_refresh_age() -> None:
    """With `enable_heartbeat=True` and `last_load > 0`, `_overview`
    emits a `Last refresh: Ns ago` line in the header. This is the
    default-off heartbeat: a separate test (the default-off contract
    check) confirms the line is absent when the flag is False."""
    tui = _make_tui(
        enable_heartbeat=True,
        snapshot=Snapshot(metadata={"status": "running", "token_usage": {}}),
        last_load=time.monotonic() - 5,
    )
    lines = tui._overview(80)
    joined = "\n".join(lines)
    assert "Last refresh:" in joined
    assert "s ago" in joined
    # The line carries a non-negative integer-second count.
    refresh_line = next(line for line in lines if line.startswith("Last refresh:"))
    # The format is `Last refresh: Ns ago` where N >= 0.
    assert refresh_line.endswith("s ago")
    suffix = refresh_line.removeprefix("Last refresh: ").removesuffix("s ago")
    assert suffix.isdigit()
    assert int(suffix) >= 0


def test_overview_shows_subprocess_elapsed_when_running() -> None:
    """With `enable_heartbeat=True` and a live subprocess (i.e.
    `self._proc is not None` and `self._proc_started_at > 0`),
    `_overview` emits a `Run alive: yes · Ns elapsed` line in the
    header. The line is absent when the subprocess has not been
    launched (the default state)."""
    tui = _make_tui(
        enable_heartbeat=True,
        snapshot=Snapshot(metadata={"status": "running", "token_usage": {}}),
    )
    # Simulate a launched-and-alive subprocess.
    tui._proc = MagicMock()
    tui._proc.pid = 12345
    tui._proc_started_at = time.monotonic() - 7
    lines = tui._overview(80)
    joined = "\n".join(lines)
    assert "Run alive: yes" in joined
    assert "s elapsed" in joined
    # The elapsed count is a non-negative integer.
    run_line = next(line for line in lines if line.startswith("Run alive:"))
    assert run_line.endswith("s elapsed")
    suffix = run_line.removeprefix("Run alive: yes · ").removesuffix("s elapsed")
    assert suffix.isdigit()
    assert int(suffix) >= 0


def test_overview_omits_heartbeat_when_flag_disabled() -> None:
    """Default-off contract: when `enable_heartbeat=False` (the
    default), neither the `Last refresh` nor the `Run alive` line
    appears in `_overview`, even if `last_load > 0` and a subprocess
    is alive. This guards the Phase 2 default-off feature flag."""
    tui = _make_tui(
        # enable_heartbeat defaults to False; not passed explicitly.
        snapshot=Snapshot(metadata={"status": "running", "token_usage": {}}),
        last_load=time.monotonic() - 5,
    )
    tui._proc = MagicMock()
    tui._proc.pid = 12345
    tui._proc_started_at = time.monotonic() - 7
    lines = tui._overview(80)
    joined = "\n".join(lines)
    assert "Last refresh" not in joined
    assert "Run alive" not in joined


# ── overview infra-error pointer (P2-6) ─────────────────────────────────────


def test_overview_infra_error_pointer_when_present() -> None:
    """With `enable_infra_pointer=True` and `infrastructure_failures > 0`,
    `_overview` emits a 1-line `Infra failures: N (see Detail tab)`
    pointer in the header. The pointer supplements (does not replace)
    the always-on `Infra failures: N` summary in the base header."""
    tui = _make_tui(
        enable_infra_pointer=True,
        snapshot=Snapshot(
            metadata={
                "cases_in_plan": 8,
                "executions_judged": 0,
                "infrastructure_failures": 2,
                "token_usage": {},
            },
            tally={},
        ),
    )
    lines = tui._overview(80)
    joined = "\n".join(lines)
    # The pointer line must appear with the live count.
    pointer_line = next(
        line for line in lines if line.startswith("Infra failures:") and "see Detail" in line
    )
    assert pointer_line == "Infra failures: 2 (see Detail tab)"
    # Sanity: the existing always-on summary in the base header is
    # also still present (it lives on the `Policy blocks: N   Infra
    # failures: N` line; the count "2" still appears in joined text).
    assert "Infra failures: 2" in joined


def test_overview_omits_pointer_when_zero() -> None:
    """With `enable_infra_pointer=True` but `infrastructure_failures == 0`,
    `_overview` does NOT emit the pointer line (nothing to point at).
    The always-on `Infra failures: 0` summary in the base header is
    still present and unchanged."""
    tui = _make_tui(
        enable_infra_pointer=True,
        snapshot=Snapshot(
            metadata={
                "cases_in_plan": 8,
                "executions_judged": 0,
                "infrastructure_failures": 0,
                "token_usage": {},
            },
            tally={},
        ),
    )
    lines = tui._overview(80)
    joined = "\n".join(lines)
    # The pointer line must NOT appear.
    assert "see Detail" not in joined
    assert not any(
        line.startswith("Infra failures:") and "see Detail" in line for line in lines
    )
    # The always-on summary in the base header is still present and
    # unchanged (it shows the count "0" because infra == 0).
    assert "Infra failures: 0" in joined


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


# ── _draw boundary tests (P0-1) ─────────────────────────────────────────────


def test_draw_too_small_height(make_fake_stdscr: Any) -> None:
    """height < 10 emits the single-line 'Terminal too small' message and
    then returns without further output."""
    tui = _make_tui(snapshot=Snapshot(metadata={"status": "running"}))
    stdscr = make_fake_stdscr(9, 80)
    tui._draw(stdscr)
    assert len(stdscr.calls) == 1
    row, col, text, _n, _attr = stdscr.calls[0]
    assert row == 0
    assert col == 0
    assert text.startswith("Terminal too small")
    assert "(min 32x10)" in text
    # The early return path must not invoke `refresh` (it does, but no
    # further `addnstr` is allowed); assert no row 1+ content was drawn.
    rows_used = {r for (r, _c, _t, _n, _a) in stdscr.calls}
    assert rows_used == {0}


def test_draw_too_small_width(make_fake_stdscr: Any) -> None:
    """width < 32 emits the same single-line 'Terminal too small' message."""
    tui = _make_tui(snapshot=Snapshot(metadata={"status": "running"}))
    stdscr = make_fake_stdscr(24, 31)
    tui._draw(stdscr)
    assert len(stdscr.calls) == 1
    _row, _col, text, _n, _attr = stdscr.calls[0]
    assert text.startswith("Terminal too small")
    assert "(min 32x10)" in text


def test_draw_short_tab_names_at_width_39(make_fake_stdscr: Any) -> None:
    """At width=39 the tab row uses the short form `[1:Ov] 2:Ca 3:De 4:He`
    and does NOT include the long form `Overview` / `Cases`."""
    tui = _make_tui(
        tab=0,
        snapshot=Snapshot(
            metadata={"status": "running"},
            plan={
                "cases": [
                    {
                        "id": 1,
                        "title": "Sample",
                        "family": "happy_path",
                        "purpose": "p",
                    }
                ]
            },
        ),
    )
    stdscr = make_fake_stdscr(24, 39)
    tui._draw(stdscr)
    tab_calls = [c for c in stdscr.calls if c[0] == 1]
    assert len(tab_calls) == 1
    _r, _c, tab_text, _n, _a = tab_calls[0]
    assert "[1:Ov]" in tab_text
    assert "2:Ca" in tab_text
    assert "3:De" in tab_text
    assert "4:He" in tab_text
    # The long form must not appear in the tab row.
    assert "Overview" not in tab_text
    assert "Cases" not in tab_text
    assert "Detail" not in tab_text
    assert "Help" not in tab_text


def test_render_dispatches_all_four_tabs(make_fake_stdscr: Any) -> None:
    """`_render(width)` returns a non-empty list whose first line is
    tab-appropriate for every one of the four TABS."""
    tui = _make_tui(
        tab=0,
        snapshot=Snapshot(
            metadata={"status": "running"},
            plan={
                "cases": [
                    {
                        "id": 1,
                        "title": "Sample",
                        "family": "happy_path",
                        "purpose": "p",
                        "test_prompt": "do the thing",
                    }
                ]
            },
            judgments=[
                {
                    "case_id": 1,
                    "agent_label": "agent_a",
                    "overall_rating": "Strong",
                    "why": "ok",
                    "gate_check": {"status": "Pass", "reason": "ok"},
                }
            ],
            results={
                "agent_a": [
                    {
                        "case_id": 1,
                        "final_output": "Done.",
                    }
                ]
            },
        ),
    )
    expected_first_line: dict[int, str] = {
        0: "Run:",
        1: "Cases",
        2: "Case 1:",
        3: "Mobile SSH controls",
    }
    for tab_idx, expected_prefix in expected_first_line.items():
        tui.tab = tab_idx
        tui.selected = 0
        tui.scroll = 0
        lines = tui._render(80)
        assert lines, f"tab {tab_idx} produced no lines"
        assert lines[0].startswith(expected_prefix), (
            f"tab {tab_idx}: expected first line to start with {expected_prefix!r},"
            f" got {lines[0]!r}"
        )


# ── multi-judge disagreement in _detail (P0-2) ──────────────────────────────


def test_detail_shows_judge_disagreement_when_ratings_diverge() -> None:
    """When 3 judgments on the same case have 3 distinct ratings, the
    detail view emits the 'Judge disagreement detected:' block with
    one line per rating (sorted) showing the per-rating count."""
    tui = _make_tui(
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {
                        "id": 1,
                        "title": "Diverging case",
                        "family": "happy_path",
                        "purpose": "p",
                    }
                ]
            },
            judgments=[
                {
                    "case_id": 1,
                    "agent_label": "agent_a",
                    "overall_rating": "Excellent",
                    "why": "good",
                    "gate_check": {"status": "Pass", "reason": "ok"},
                },
                {
                    "case_id": 1,
                    "agent_label": "agent_b",
                    "overall_rating": "Strong",
                    "why": "ok",
                    "gate_check": {"status": "Pass", "reason": "ok"},
                },
                {
                    "case_id": 1,
                    "agent_label": "agent_c",
                    "overall_rating": "Weak",
                    "why": "lacking",
                    "gate_check": {"status": "Fail", "reason": "no"},
                },
            ],
        ),
    )
    lines = tui._detail(80)
    text = "\n".join(lines)
    assert "Judge disagreement detected:" in text
    # Per-rating counts, sorted alphabetically: Excellent, Strong, Weak.
    assert "  Excellent: 1 judge(s)" in text
    assert "  Strong: 1 judge(s)" in text
    assert "  Weak: 1 judge(s)" in text
    # The disagreement block is preceded by a blank line and is the last
    # block before any infrastructure-error section (none in this snapshot).
    assert text.rstrip().endswith("  Weak: 1 judge(s)")


def test_detail_no_disagreement_block_when_ratings_agree() -> None:
    """When 2+ judgments on the same case all share one rating, the
    'Judge disagreement detected:' block is NOT emitted."""
    tui = _make_tui(
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {
                        "id": 1,
                        "title": "Agreeing case",
                        "family": "happy_path",
                        "purpose": "p",
                    }
                ]
            },
            judgments=[
                {
                    "case_id": 1,
                    "agent_label": "agent_a",
                    "overall_rating": "Strong",
                    "why": "ok",
                    "gate_check": {"status": "Pass", "reason": "ok"},
                },
                {
                    "case_id": 1,
                    "agent_label": "agent_b",
                    "overall_rating": "Strong",
                    "why": "agree",
                    "gate_check": {"status": "Pass", "reason": "ok"},
                },
            ],
        ),
    )
    lines = tui._detail(80)
    text = "\n".join(lines)
    assert "Judge disagreement detected:" not in text
    # Sanity: the per-judgment sections are still present.
    assert "Agent: agent_a" in text
    assert "Agent: agent_b" in text
    # The `_section` helper puts the title on one line and the value on the
    # next, so "Strong" appears as a standalone line per judgment (>= 2).
    assert text.count("\nStrong\n") >= 2


def test_detail_disagreement_counts_duplicate_ratings() -> None:
    """When ratings include duplicates (e.g. 4 judges, ratings split 2-1-1),
    the per-rating count reflects the duplicate."""
    tui = _make_tui(
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {
                        "id": 1,
                        "title": "Split case",
                        "family": "happy_path",
                        "purpose": "p",
                    }
                ]
            },
            judgments=[
                {
                    "case_id": 1,
                    "agent_label": "agent_a",
                    "overall_rating": "Excellent",
                    "why": "ok",
                    "gate_check": {"status": "Pass", "reason": "ok"},
                },
                {
                    "case_id": 1,
                    "agent_label": "agent_b",
                    "overall_rating": "Excellent",
                    "why": "ok",
                    "gate_check": {"status": "Pass", "reason": "ok"},
                },
                {
                    "case_id": 1,
                    "agent_label": "agent_c",
                    "overall_rating": "Strong",
                    "why": "ok",
                    "gate_check": {"status": "Pass", "reason": "ok"},
                },
                {
                    "case_id": 1,
                    "agent_label": "agent_d",
                    "overall_rating": "Weak",
                    "why": "ok",
                    "gate_check": {"status": "Fail", "reason": "no"},
                },
            ],
        ),
    )
    lines = tui._detail(80)
    text = "\n".join(lines)
    assert "Judge disagreement detected:" in text
    # Sorted: Excellent, Strong, Weak with counts 2, 1, 1.
    assert "  Excellent: 2 judge(s)" in text
    assert "  Strong: 1 judge(s)" in text
    assert "  Weak: 1 judge(s)" in text


# ── manifest integrity in _overview (P0-3) ──────────────────────────────────


def test_overview_manifest_warning_when_verify_fails(tmp_path: Path) -> None:
    """When the on-disk manifest declares a file that has since been
    tampered with, `_overview` emits a `Manifest gen N: WARNING — N
    integrity issue(s)` line and does NOT show `valid`."""
    # Record a real entry so the manifest is well-formed and the file
    # exists; then tamper with the file's contents so the recorded sha
    # no longer matches the bytes on disk.
    Manifest(tmp_path).record("artifact.json", "original content")
    (tmp_path / "artifact.json").write_text("tampered content", encoding="utf-8")
    tui = _make_tui(
        run_dir=tmp_path,
        snapshot=Snapshot(metadata={}),
    )
    lines = tui._overview(80)
    text = "\n".join(lines)
    assert "Manifest gen 1: WARNING" in text
    assert "1 integrity issue" in text
    # The TUI shows only the count, not the underlying verify() details.
    assert "Manifest gen 1: valid" not in text
    # Sanity: the regular overview content is also emitted.
    assert "Progress" in text
    assert "Policy blocks" in text


def test_overview_manifest_not_present_when_gen_zero(tmp_path: Path) -> None:
    """When the run_dir has no manifest.json, `_overview` emits the
    `Manifest: not yet present` line and does NOT show `WARNING`."""
    # tmp_path exists but has no manifest.json.
    assert not (tmp_path / "manifest.json").exists()
    tui = _make_tui(
        run_dir=tmp_path,
        snapshot=Snapshot(metadata={}),
    )
    lines = tui._overview(80)
    text = "\n".join(lines)
    assert "Manifest: not yet present" in text
    assert "WARNING" not in text
    assert "Manifest gen" not in text


# ── scroll indicators in _draw (P0-4) ──────────────────────────────────────


_INDICATOR_TEXTS = (" ↑", " ↓")


def _indicator_calls(stdscr: Any) -> list[tuple[int, int, str, int, int]]:
    """Return the recorded `addnstr` calls whose text starts with ` ↑` or ` ↓`."""
    return [c for c in stdscr.calls if c[2].startswith(_INDICATOR_TEXTS)]


def test_draw_scroll_indicator_at_top(make_fake_stdscr: Any) -> None:
    """At scroll=0 (top), only the down-arrow indicator is emitted; the
    up-arrow is suppressed because there is no content above the viewport."""
    tui = _make_tui(
        tab=1,  # Cases tab
        scroll=0,
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {"id": i, "title": f"Case {i}"} for i in range(1, 51)
                ]
            },
        ),
    )
    stdscr = make_fake_stdscr(24, 80)
    tui._draw(stdscr)
    # Sanity: clamp kept us at the top.
    assert tui.scroll == 0
    indicators = _indicator_calls(stdscr)
    assert len(indicators) == 1
    row, col, text, _n, _a = indicators[0]
    # The down-arrow is shown at the bottom of the viewport.
    assert text.startswith(" ↓")
    assert col == 80 - 2
    # view_height = 24 - 4 = 20, so the indicator is at row 2 + 20 - 1 = 21.
    assert row == 2 + (24 - 4) - 1


def test_draw_scroll_indicator_at_bottom(make_fake_stdscr: Any) -> None:
    """At scroll=max_scroll (bottom), only the up-arrow indicator is
    emitted; the down-arrow is suppressed because there is no content
    below the viewport."""
    tui = _make_tui(
        tab=1,  # Cases tab
        # Setting selected=49 forces `_clamp_scroll` to push the scroll
        # to the maximum position (49 - 20 + 2 = 31 = max_scroll).
        selected=49,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {"id": i, "title": f"Case {i}"} for i in range(1, 51)
                ]
            },
        ),
    )
    stdscr = make_fake_stdscr(24, 80)
    tui._draw(stdscr)
    # Sanity: clamp pushed scroll to max_scroll = 51 - 20 = 31.
    assert tui.scroll == 51 - 20
    indicators = _indicator_calls(stdscr)
    assert len(indicators) == 1
    row, col, text, _n, _a = indicators[0]
    # The up-arrow is shown at the top of the viewport (row 2).
    assert text.startswith(" ↑")
    assert col == 80 - 2
    assert row == 2


def test_draw_no_indicator_when_fits(make_fake_stdscr: Any) -> None:
    """When the rendered content fits inside the viewport, neither
    scroll indicator is emitted."""
    tui = _make_tui(
        tab=1,  # Cases tab
        snapshot=Snapshot(
            plan={"cases": [{"id": 1, "title": "Only case"}]},
        ),
    )
    stdscr = make_fake_stdscr(24, 80)
    tui._draw(stdscr)
    # `_case_list` produces 2 lines (header + 1 case); view_height=20, so
    # the content fits and no scroll is needed.
    indicators = _indicator_calls(stdscr)
    assert indicators == []


# ── _line_attr colorization (P0-5) ─────────────────────────────────────────


def test_line_attr_quoted_rating_not_colored() -> None:
    """A rating token in double-quotes is NOT colored (current behavior).

    This is a regression guard for the boundary check in `_line_attr`.
    The double-quote character is not in the boundary set
    ``(" ", "[", ":", "]", ",", "(")``, so the rating substring is
    treated as a non-word match and the function returns 0. The
    exemption is *incidental*, not intentional: it would silently break
    if the boundary set were ever extended to include ``"``.

    The plan named this test ``test_line_attr_quoted_rating_still_colored``;
    the actual current behavior is "not colored", so the test name and
    assertion are aligned with the function, not the plan's wording.
    """
    attr = BenchDeckTUI._line_attr('Judge said "Excellent" in the report')
    assert attr == 0


def test_line_attr_gate_pass_colored() -> None:
    """A line containing both 'Pass' and 'Gate' is colored (green pair)."""
    # Patch `curses.color_pair` to return a deterministic per-pair value
    # so we can both confirm the gate branch was hit and that the
    # resulting attribute is non-zero (i.e., the line is colored).
    def _fake_color_pair(n: int) -> int:
        return 0x100 * n

    with patch("benchdeck.tui.curses.color_pair", side_effect=_fake_color_pair):
        attr = BenchDeckTUI._line_attr("Pass: Gate ok")
    # The Gate-Pass branch returns curses.color_pair(2).
    assert attr == 0x200


def test_line_attr_gate_fail_colored() -> None:
    """A line containing both 'Fail' and 'Gate' is colored (red pair).

    Note: this particular line is matched by the *rating* check
    ('Fail' with whole-word boundary) first, not the gate check. The
    rating-Fail branch and the gate-Fail branch both return the same
    red pair, so the test asserts only that the result is colored and
    matches pair 1.
    """

    def _fake_color_pair(n: int) -> int:
        return 0x100 * n

    with patch("benchdeck.tui.curses.color_pair", side_effect=_fake_color_pair):
        attr = BenchDeckTUI._line_attr("Fail: Gate broken")
    # The rating-Fail branch returns curses.color_pair(1).
    assert attr == 0x100


# ── _poll_subprocess (P0-6) ─────────────────────────────────────────────────


def test_poll_subprocess_nonzero_reports_log(tmp_path: Path) -> None:
    """When the subprocess has exited with a non-zero code, the status
    message includes both the `exit=N` tag and the stderr log file name,
    and all subprocess tracking state is cleared."""
    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# test")
    tui = BenchDeckTUI(tmp_path, agent_a_path=agent_path, model="gpt-4o")
    with _mock_popen():
        tui._launch_run()
    assert tui._proc is not None
    # Capture the log path the launch recorded (real file on disk).
    assert tui._stderr_log is not None
    log_name = tui._stderr_log.name
    # Override poll() to report a non-zero exit.
    tui._proc.poll.return_value = 1

    tui._poll_subprocess()

    assert tui._status_msg is not None
    assert "exit=1" in tui._status_msg
    assert "log:" in tui._status_msg
    assert log_name in tui._status_msg
    # All subprocess tracking state is cleared.
    assert tui._proc is None
    assert tui._proc_run_dir is None
    assert tui._stderr_log is None
    assert tui._stderr_handle is None


def test_poll_subprocess_zero_clears_proc(tmp_path: Path) -> None:
    """When the subprocess has exited with code 0, the status message
    contains the `ok` tag and the log file name is NOT mentioned (the
    footer line is short). All tracking state is cleared."""
    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# test")
    tui = BenchDeckTUI(tmp_path, agent_a_path=agent_path, model="gpt-4o")
    with _mock_popen():
        tui._launch_run()
    assert tui._proc is not None
    # Override poll() to report a clean exit.
    tui._proc.poll.return_value = 0

    tui._poll_subprocess()

    assert tui._status_msg is not None
    assert "ok" in tui._status_msg
    # The log file name is NOT appended on the rc==0 path.
    assert "log:" not in tui._status_msg
    # State is cleared.
    assert tui._proc is None
    assert tui._proc_run_dir is None
    assert tui._stderr_log is None
    assert tui._stderr_handle is None


def test_poll_subprocess_noop_when_proc_is_none(tmp_path: Path) -> None:
    """When no subprocess is running, `_poll_subprocess` is a no-op
    (no status message change, no exceptions)."""
    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# test")
    tui = BenchDeckTUI(tmp_path, agent_a_path=agent_path, model="gpt-4o")
    assert tui._proc is None
    # Set a status message to verify it's not clobbered.
    tui._status_msg = "prior status"

    tui._poll_subprocess()

    # No-op: status message unchanged.
    assert tui._status_msg == "prior status"


# ── _launch_run with agent_b (P0-7) ─────────────────────────────────────────


def test_launch_run_includes_agent_b_when_present(tmp_path: Path) -> None:
    """When both `_agent_a_path` and `_agent_b_path` are set and both
    files exist, the launched command list includes `--agent-b` followed
    by the agent_b path (in addition to `--agent-a`)."""
    agent_a = tmp_path / "agent_a.md"
    agent_a.write_text("# Agent A")
    agent_b = tmp_path / "agent_b.md"
    agent_b.write_text("# Agent B")
    tui = BenchDeckTUI(
        tmp_path,
        agent_a_path=agent_a,
        agent_b_path=agent_b,
        model="gpt-4o",
    )
    with _mock_popen() as mock_popen:
        tui._launch_run()
    # Sanity: the subprocess was spawned.
    assert tui._proc is not None
    # The mock was called with the command list as the first positional arg.
    assert mock_popen.called
    cmd = mock_popen.call_args[0][0]
    # The single-agent flags must be present (regression guard for the
    # existing path).
    assert "--agent-a" in cmd
    assert str(agent_a) in cmd
    # The two-agent flag must be appended because both files exist.
    assert "--agent-b" in cmd
    idx = cmd.index("--agent-b")
    assert cmd[idx + 1] == str(agent_b)


def test_launch_run_omits_agent_b_when_file_missing(tmp_path: Path) -> None:
    """When `_agent_b_path` is set but the file does NOT exist, the
    launched command does NOT include `--agent-b` (the guard in
    `_launch_run` skips the flag if the file is missing)."""
    agent_a = tmp_path / "agent_a.md"
    agent_a.write_text("# Agent A")
    agent_b = tmp_path / "agent_b.md"  # file is NOT created
    tui = BenchDeckTUI(
        tmp_path,
        agent_a_path=agent_a,
        agent_b_path=agent_b,
        model="gpt-4o",
    )
    with _mock_popen() as mock_popen:
        tui._launch_run()
    assert tui._proc is not None
    cmd = mock_popen.call_args[0][0]
    assert "--agent-b" not in cmd


# ── footer hint width-based selection (P1-6) ───────────────────────────────


def test_footer_hint_short_form_at_narrow_width(make_fake_stdscr: Any) -> None:
    """At width < 56, the footer (row height-1) uses the short hint
    `1-4 tabs · j/k move · q quit` so it fits within the 32-56 column
    band. The full-form tokens must NOT appear."""
    tui = _make_tui(snapshot=Snapshot(metadata={"status": "running"}))
    stdscr = make_fake_stdscr(24, 40)
    tui._draw(stdscr)
    footer_calls = [c for c in stdscr.calls if c[0] == 23]
    assert len(footer_calls) == 1
    _r, _c, text, _n, _a = footer_calls[0]
    assert "1-4 tabs" in text
    assert "j/k move" in text
    assert "q quit" in text
    # Full-form tokens must be absent.
    assert "Enter detail" not in text
    assert "e export" not in text
    assert "h/l tabs" not in text


def test_footer_hint_full_form_at_wide_width(make_fake_stdscr: Any) -> None:
    """At width >= 56 with tab=0 (Overview), the footer uses the
    per-tab hint map joined with ' | '. This is the wide-form contract
    that P1-1 introduced; the pre-P1-1 two-space-separated full list
    has been replaced."""
    tui = _make_tui(
        tab=0,
        snapshot=Snapshot(metadata={"status": "running"}),
    )
    stdscr = make_fake_stdscr(24, 80)
    tui._draw(stdscr)
    footer_calls = [c for c in stdscr.calls if c[0] == 23]
    assert len(footer_calls) == 1
    _r, _c, text, _n, _a = footer_calls[0]
    # The Overview tab's contextual hint tokens.
    assert "h/l tabs" in text
    assert "j/k move" in text
    assert "n run" in text
    assert "r reload" in text
    assert "q quit" in text
    # The P1-1 joiner is in effect.
    assert " | " in text
    # Tokens that belong to other tabs (Cases / Detail) must not leak in.
    assert "Enter open" not in text
    assert "e export" not in text
    assert "j/k scroll" not in text


# ── contextual footer hint per tab (P1-1) ───────────────────────────────────


def test_footer_hint_context_for_cases_tab(make_fake_stdscr: Any) -> None:
    """At width=80 with tab=1 (Cases), the footer leads with
    `Enter open · e export` (the most salient keys for the Cases tab)
    rather than the Overview-default `h/l tabs · j/k move · n run`."""
    tui = _make_tui(
        tab=1,
        snapshot=Snapshot(metadata={"status": "running"}),
    )
    stdscr = make_fake_stdscr(24, 80)
    tui._draw(stdscr)
    footer_calls = [c for c in stdscr.calls if c[0] == 23]
    assert len(footer_calls) == 1
    _r, _c, text, _n, _a = footer_calls[0]
    # Cases-specific keys must be present.
    assert "Enter open" in text
    assert "e export" in text
    # The Cases hint uses the contextual map, not the default
    # two-space-separated string from P1-6.
    assert " | " in text


def test_footer_hint_truncates_at_narrow_width(make_fake_stdscr: Any) -> None:
    """At narrow widths (width < 56), the short-form hint is used and
    the recorded footer line is at most `width` characters long."""
    tui = _make_tui(
        tab=0,
        snapshot=Snapshot(metadata={"status": "running"}),
    )
    stdscr = make_fake_stdscr(24, 40)
    tui._draw(stdscr)
    footer_calls = [c for c in stdscr.calls if c[0] == 23]
    assert len(footer_calls) == 1
    _r, _c, text, _n, _a = footer_calls[0]
    # At width < 56 the P1-6 short form is used (28 chars), so the
    # recorded (untruncated) text is bounded by `width`.
    assert len(text) <= 40
    # The contextual map is NOT applied at narrow widths.
    assert " | " not in text


# ── Cases tab header summary (P1-3) ─────────────────────────────────────────


def test_case_list_header_includes_counts(make_fake_stdscr: Any) -> None:
    """At width=80, the Cases tab header (row 2) is a one-line summary
    that includes the total / judged / blocked counts."""
    tui = _make_tui(
        tab=1,
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {"id": 1, "title": "Case 1"},
                    {"id": 2, "title": "Case 2"},
                    {"id": 3, "title": "Case 3"},
                ]
            },
            judgments=[
                {
                    "case_id": 1,
                    "agent_label": "agent_a",
                    "overall_rating": "Strong",
                },
            ],
            policy_blocks=[{"case_id": 2, "message": "policy"}],
        ),
    )
    stdscr = make_fake_stdscr(24, 80)
    tui._draw(stdscr)
    # The first content row (row 2) is the header.
    header_calls = [c for c in stdscr.calls if c[0] == 2]
    assert len(header_calls) == 1
    _r, _c, text, _n, _a = header_calls[0]
    assert "Cases:" in text
    assert "3 total" in text
    assert "1 judged" in text
    assert "1 blocked" in text


def test_case_list_header_truncates_at_minimum_width(make_fake_stdscr: Any) -> None:
    """At width=32 (the hard minimum), the Cases header fits within
    the available columns (the full format is truncated to width chars)."""
    tui = _make_tui(
        tab=1,
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {"id": 1, "title": "Case 1"},
                    {"id": 2, "title": "Case 2"},
                ]
            },
            judgments=[
                {
                    "case_id": 1,
                    "agent_label": "agent_a",
                    "overall_rating": "Strong",
                },
            ],
        ),
    )
    stdscr = make_fake_stdscr(24, 32)
    tui._draw(stdscr)
    header_calls = [c for c in stdscr.calls if c[0] == 2]
    assert len(header_calls) == 1
    _r, _c, text, _n, _a = header_calls[0]
    # The header fits in the available columns.
    assert len(text) <= 32
    # The leading text is preserved.
    assert text.startswith("Cases")


# ── status marks in _case_list (P1-5) ───────────────────────────────────────


def test_case_list_includes_status_marks_for_ratings() -> None:
    """Each case-list row with a rating carries the worst-case status
    mark before the state segment:
        Excellent/Strong → [✓]
        Acceptable/Weak  → [!]
        Fail             → [X]"""
    tui = _make_tui(
        tab=1,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {"id": 1, "title": "Excellent case"},
                    {"id": 2, "title": "Acceptable case"},
                    {"id": 3, "title": "Failing case"},
                ]
            },
            judgments=[
                {
                    "case_id": 1,
                    "agent_label": "agent_a",
                    "overall_rating": "Excellent",
                },
                {
                    "case_id": 2,
                    "agent_label": "agent_a",
                    "overall_rating": "Acceptable",
                },
                {
                    "case_id": 3,
                    "agent_label": "agent_a",
                    "overall_rating": "Fail",
                },
            ],
        ),
    )
    lines = tui._case_list(80)
    text = "\n".join(lines)
    # All three mark glyphs are present.
    assert "[✓]" in text
    assert "[!]" in text
    assert "[X]" in text
    # The underlying rating words are still present (marks are added,
    # not replacements).
    assert "Excellent" in text
    assert "Acceptable" in text
    assert "Fail" in text
    # Each mark precedes its rating on the same row.
    excellent_line = next(line for line in lines if "Excellent" in line)
    assert excellent_line.index("[✓]") < excellent_line.index("Excellent")
    fail_line = next(line for line in lines if "Fail" in line)
    assert fail_line.index("[X]") < fail_line.index("Fail")


def test_case_list_includes_status_marks_for_blocked() -> None:
    """A case with a policy block is prefixed with [X] before the
    BLOCKED state segment on the same row."""
    tui = _make_tui(
        tab=1,
        snapshot=Snapshot(
            plan={"cases": [{"id": 1, "title": "Blocked case"}]},
            policy_blocks=[{"case_id": 1, "message": "policy"}],
        ),
    )
    lines = tui._case_list(80)
    text = "\n".join(lines)
    assert "[X]" in text
    assert "BLOCKED" in text
    # The mark is on the same line as BLOCKED and precedes it.
    blocked_line = next(line for line in lines if "BLOCKED" in line)
    assert "[X]" in blocked_line
    assert blocked_line.index("[X]") < blocked_line.index("BLOCKED")


# ── title age suffix (P1-2) ─────────────────────────────────────────────────


def test_draw_title_shows_last_loaded_age(make_fake_stdscr: Any) -> None:
    """At width >= 48 with `self.last_load > 0`, the title row
    includes a `· Ns ago` suffix showing the seconds since the
    last snapshot load."""
    # Set last_load to a fixed value 10s in the past to avoid timing
    # flakiness; the test computes the expected elapsed dynamically
    # so the assertion is robust to small jitter.
    tui = _make_tui(
        snapshot=Snapshot(metadata={"status": "running"}),
        last_load=time.monotonic() - 10,
    )
    stdscr = make_fake_stdscr(24, 80)
    tui._draw(stdscr)
    title_calls = [c for c in stdscr.calls if c[0] == 0]
    assert len(title_calls) == 1
    _r, _c, text, _n, _a = title_calls[0]
    expected_elapsed = int(time.monotonic() - tui.last_load)
    expected_suffix = f" · {expected_elapsed}s ago"
    assert text.endswith(expected_suffix)
    # The age segment is preceded by the title text.
    assert "BENCHDECK" in text


def test_draw_title_omits_age_when_narrow(make_fake_stdscr: Any) -> None:
    """At width < 48, the title does NOT include the age suffix,
    preserving the full 32-47 column band for the title text."""
    tui = _make_tui(
        snapshot=Snapshot(metadata={"status": "running"}),
        last_load=time.monotonic() - 10,
    )
    stdscr = make_fake_stdscr(24, 40)
    tui._draw(stdscr)
    title_calls = [c for c in stdscr.calls if c[0] == 0]
    assert len(title_calls) == 1
    _r, _c, text, _n, _a = title_calls[0]
    # The age suffix must not appear at narrow widths.
    assert "s ago" not in text
    assert "·" not in text
    # The base title is preserved.
    assert "BENCHDECK" in text
    assert "running" in text


def test_draw_title_omits_age_before_first_load(make_fake_stdscr: Any) -> None:
    """Before the first `load_snapshot` call, `self.last_load` is 0
    and the age suffix is NOT shown (avoids showing '-1s ago' on the
    very first draw)."""
    tui = _make_tui(
        snapshot=Snapshot(metadata={"status": "running"}),
        last_load=0.0,  # default value before any load
    )
    stdscr = make_fake_stdscr(24, 80)
    tui._draw(stdscr)
    title_calls = [c for c in stdscr.calls if c[0] == 0]
    assert len(title_calls) == 1
    _r, _c, text, _n, _a = title_calls[0]
    assert "s ago" not in text


# ── block markers in _detail (P1-4) ──────────────────────────────────────────


def test_detail_marks_test_prompt_block() -> None:
    """The Test Prompt section in `_detail` has its wrapped lines
    prefixed with the `│ ` glyph (Unicode box-drawing light vertical
    + space). The title line `Test Prompt` is NOT prefixed."""
    tui = _make_tui(
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {
                        "id": 1,
                        "title": "Sample",
                        "family": "happy_path",
                        "purpose": "p",
                        "test_prompt": "Do the first thing.\nThen verify the second.",
                    }
                ]
            },
        ),
    )
    lines = tui._detail(80)
    text = "\n".join(lines)
    # The Test Prompt section title is present (un-prefixed).
    assert "Test Prompt" in text
    # The block marker is present on the wrapped body lines.
    assert "│ " in text
    # The first body line is a wrapped-prefixed version of the prompt.
    assert "│ Do the first thing." in text


def test_detail_marks_agent_output_block() -> None:
    """The Agent output section in `_detail` has its wrapped lines
    prefixed with the `│ ` glyph. The title line `Agent output` is
    NOT prefixed."""
    tui = _make_tui(
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {
                        "id": 1,
                        "title": "Sample",
                        "family": "happy_path",
                        "purpose": "p",
                        "test_prompt": "Do the thing.",
                    }
                ]
            },
            judgments=[
                {
                    "case_id": 1,
                    "agent_label": "agent_a",
                    "overall_rating": "Strong",
                    "why": "ok",
                    "gate_check": {"status": "Pass", "reason": "ok"},
                }
            ],
            results={
                "agent_a": [
                    {
                        "case_id": 1,
                        "final_output": "Done.\nNext step here.",
                    }
                ]
            },
        ),
    )
    lines = tui._detail(80)
    text = "\n".join(lines)
    # The Agent output title is present.
    assert "Agent output" in text
    # The block marker is present on the wrapped body lines.
    assert "│ " in text
    # At least one wrapped line is prefixed.
    assert "│ Done." in text
    # The title line itself is NOT prefixed.
    title_line = next(line for line in lines if line == "Agent output")
    assert "│ " not in title_line


# ── case list filter & sort (P2-1) ──────────────────────────────────────────


def test_case_list_filter_by_family() -> None:
    """With `enable_case_filter=True` and `self._filter = "family:edge_case_logic"`,
    `_case_list` only shows cases whose `family` field matches. The
    header reflects the filtered count and the total."""
    tui = _make_tui(
        enable_case_filter=True,
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {"id": 1, "title": "Edge 1", "family": "edge_case_logic"},
                    {"id": 2, "title": "Happy 1", "family": "happy_path"},
                    {"id": 3, "title": "Edge 2", "family": "edge_case_logic"},
                ]
            },
            judgments=[],
        ),
    )
    tui._filter = "family:edge_case_logic"
    lines = tui._case_list(80)
    joined = "\n".join(lines)
    # The two edge cases appear; the happy case does not.
    assert "Edge 1" in joined
    assert "Edge 2" in joined
    assert "Happy 1" not in joined
    # Header reflects filtered count out of total.
    assert "2 of 3 total" in lines[0]
    # Sort is "id" (the default), so no `sort:…` suffix.
    assert "sort:" not in lines[0]


def test_case_list_filter_by_state_blocked() -> None:
    """With `self._filter = "state:BLOCKED"`, only blocked cases are
    visible. The other states (judged, pending) are filtered out."""
    tui = _make_tui(
        enable_case_filter=True,
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {"id": 1, "title": "Judged Case"},
                    {"id": 2, "title": "Blocked Case"},
                    {"id": 3, "title": "Pending Case"},
                ]
            },
            judgments=[
                {
                    "case_id": 1,
                    "agent_label": "agent_a",
                    "overall_rating": "Excellent",
                }
            ],
            policy_blocks=[{"case_id": 2, "agent_label": "agent_a"}],
        ),
    )
    tui._filter = "state:BLOCKED"
    lines = tui._case_list(80)
    joined = "\n".join(lines)
    # Only the blocked case is visible.
    assert "Blocked Case" in joined
    assert "Judged Case" not in joined
    assert "Pending Case" not in joined
    # Header counts: 1 of 3 total, 0 judged, 1 blocked.
    assert "1 of 3 total" in lines[0]
    assert "0 judged" in lines[0]
    assert "1 blocked" in lines[0]


def test_case_list_sort_by_family() -> None:
    """With `self._sort = "family"`, cases are ordered by family
    (alphabetical, case-insensitive) then by case id. The header
    carries a `sort:family` suffix."""
    tui = _make_tui(
        enable_case_filter=True,
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {"id": 1, "title": "Z case", "family": "zebra"},
                    {"id": 2, "title": "A case", "family": "alpha"},
                    {"id": 3, "title": "M case", "family": "mango"},
                ]
            },
            judgments=[],
        ),
    )
    tui._sort = "family"
    lines = tui._case_list(80)
    joined = "\n".join(lines)
    # Family order: alpha < mango < zebra → case 2, case 3, case 1.
    pos_a = joined.find("A case")
    pos_m = joined.find("M case")
    pos_z = joined.find("Z case")
    assert pos_a != -1 and pos_m != -1 and pos_z != -1
    assert pos_a < pos_m < pos_z
    # Header carries sort:family.
    assert "sort:family" in lines[0]


def test_case_list_filter_clears_status_on_escape() -> None:
    """When the filter prompt is open, pressing Esc restores the
    prior filter (the draft is discarded), closes the prompt, and
    sets a status message indicating the prompt was cancelled. The
    case list is unchanged from its prior filtered state."""
    tui = _make_tui(
        enable_case_filter=True,
        tab=1,
        snapshot=Snapshot(
            plan={"cases": [{"id": 1, "title": "Only Case"}]}
        ),
    )
    tui._filter = ""  # start with no filter
    # Open the filter prompt.
    tui._handle_key(ord("f"))
    assert tui._filter_mode is True
    # Type some text into the draft.
    tui._handle_key(ord("a"))
    tui._handle_key(ord("b"))
    assert tui._filter_draft == "ab"
    # Press Esc.
    tui._handle_key(27)
    # The prompt is closed; the prior filter is restored.
    assert tui._filter_mode is False
    assert tui._filter == ""
    assert tui._filter_draft == ""
    # A status message indicates the prompt was cancelled.
    assert "cancel" in tui._status_msg.lower()


def test_case_list_selected_clamps_after_filter() -> None:
    """After applying a filter that reduces the visible list below
    `self.selected`, `_case_list` re-clamps `self.selected` to the
    new length so the `>` marker remains on a valid (visible) row."""
    tui = _make_tui(
        enable_case_filter=True,
        selected=5,  # far past the end of the unfiltered list
        snapshot=Snapshot(
            plan={
                "cases": [
                    {"id": 1, "title": "Edge 1", "family": "edge_case_logic"},
                    {"id": 2, "title": "Happy 1", "family": "happy_path"},
                    {"id": 3, "title": "Edge 2", "family": "edge_case_logic"},
                ]
            },
            judgments=[],
        ),
    )
    tui._filter = "family:edge_case_logic"  # reduces to 2 cases
    lines = tui._case_list(80)
    # After clamping, self.selected points at the last visible case.
    assert tui.selected == 1
    # The `>` marker is on the last case row (the clamped selected).
    assert any(line.startswith(">") for line in lines[1:])
    assert lines[-1].startswith(">")
    # Only the 2 filtered cases are visible (no Happy 1).
    joined = "\n".join(lines)
    assert "Happy 1" not in joined


def test_case_list_default_off_omits_filter_and_sort() -> None:
    """Default-off contract: when `enable_case_filter=False` (the
    default), `self._filter` and `self._sort` are ignored by
    `_case_list` and the `f` / `s` keys are no-ops in `_handle_key`.
    This locks down the Phase 2 default-off guarantee for the
    case-list feature."""
    tui = _make_tui(
        # enable_case_filter defaults to False; not passed.
        selected=0,
        snapshot=Snapshot(
            plan={
                "cases": [
                    {"id": 1, "title": "Edge", "family": "edge_case_logic"},
                    {"id": 2, "title": "Happy", "family": "happy_path"},
                ]
            },
            judgments=[],
        ),
    )
    # If the flag were on, the filter would restrict to "Edge" and
    # the sort would reorder. With the flag off, both are ignored.
    tui._filter = "family:edge_case_logic"
    tui._sort = "family"
    lines = tui._case_list(80)
    joined = "\n".join(lines)
    # Both cases are visible (no filter applied).
    assert "Edge" in joined
    assert "Happy" in joined
    # Header is the original unfiltered form.
    assert " of " not in lines[0]
    assert lines[0] == "Cases: 2 total · 0 judged · 0 blocked"
    # The `f` and `s` keys are no-ops when the flag is off. The
    # filter prompt does not open, and the sort is not cycled
    # (whatever value the caller set is preserved).
    tui.tab = 1
    tui._handle_key(ord("f"))
    assert tui._filter_mode is False
    tui._handle_key(ord("s"))
    # The sort is unchanged from what the caller set — the `s`
    # keypress was ignored because the flag is off.
    assert tui._sort == "family"


# ── overview live log tail (P2-2) ──────────────────────────────────────────


def test_overview_includes_subprocess_log_tail_when_running(
    tmp_path: Path,
) -> None:
    """With `enable_log_tail=True` and a live subprocess, `_overview`
    appends a `Subprocess log (last N of M lines, X bytes):` section
    showing the tail of the captured stderr log file. Only the last
    8 lines are shown even when the log has more."""
    log_path = tmp_path / "benchdeck_20260615T120000Z.log"
    log_lines = [f"line {i:02d}: some output" for i in range(1, 21)]  # 20 lines
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    tui = _make_tui(
        enable_log_tail=True,
        snapshot=Snapshot(metadata={"status": "running", "token_usage": {}}),
    )
    # Simulate a launched-and-alive subprocess with a stderr log file.
    tui._proc = MagicMock()
    tui._proc.pid = 12345
    tui._stderr_log = log_path
    lines = tui._overview(80)
    joined = "\n".join(lines)
    # The section header is present with the captured line count
    # and the file size.
    assert "Subprocess log" in joined
    assert "20 lines" in joined  # total captured line count
    assert "last 8 of" in joined
    # The tail shows lines 13-20 (the last 8 of 20).
    assert "line 13: some output" in joined
    assert "line 20: some output" in joined
    # Earlier lines are NOT shown.
    assert "line 01: some output" not in joined
    assert "line 12: some output" not in joined


def test_overview_omits_log_tail_when_idle() -> None:
    """With `enable_log_tail=True` but no live subprocess (i.e.
    `self._proc is None`), `_overview` does NOT include the log
    tail section. The section is suppressed because there is no
    active run to tail, even if a stale `_stderr_log` path is set."""
    tui = _make_tui(
        enable_log_tail=True,
        snapshot=Snapshot(metadata={"status": "running", "token_usage": {}}),
    )
    # Idle state: no proc, no stderr log.
    assert tui._proc is None
    assert tui._stderr_log is None
    lines = tui._overview(80)
    joined = "\n".join(lines)
    # The section is absent.
    assert "Subprocess log" not in joined


def test_overview_default_off_omits_log_tail(tmp_path: Path) -> None:
    """Default-off contract: when `enable_log_tail=False` (the
    default), the `Subprocess log` section does NOT appear in
    `_overview`, even if a subprocess is alive and a stderr log
    file exists with content. This locks down the Phase 2
    default-off guarantee."""
    log_path = tmp_path / "should_not_be_read.log"
    log_path.write_text("line 1\nline 2\n", encoding="utf-8")
    tui = _make_tui(
        # enable_log_tail defaults to False; not passed.
        snapshot=Snapshot(metadata={"status": "running", "token_usage": {}}),
    )
    tui._proc = MagicMock()
    tui._proc.pid = 12345
    tui._stderr_log = log_path
    lines = tui._overview(80)
    joined = "\n".join(lines)
    # The section is absent even though the proc is alive and the
    # log file has content.
    assert "Subprocess log" not in joined
    # The log file was not read or modified.
    assert log_path.read_text(encoding="utf-8") == "line 1\nline 2\n"
