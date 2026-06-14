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
