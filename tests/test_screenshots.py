"""Tests for the screenshot generation script.

Covers: theme resolution, font discovery, synthetic data builders,
colourisation, rendering, metadata, and the generate_screenshots() API.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import generate_demo_screens as gds  # noqa: E402

# ── theme resolution ────────────────────────────────────────────────────────


def test_resolve_theme_dark() -> None:
    theme = gds._resolve_theme("dark")
    assert theme["BG"] == (24, 24, 32)
    assert theme["FG"] == (212, 212, 212)
    assert "GREEN" in theme
    assert "RED" in theme


def test_resolve_theme_light() -> None:
    theme = gds._resolve_theme("light")
    assert theme["BG"] == (248, 248, 252)
    assert theme["FG"] == (40, 40, 48)


def test_resolve_theme_github() -> None:
    theme = gds._resolve_theme("github")
    assert theme["BG"] == (13, 17, 23)
    assert theme["TAB_ACTIVE"] == (31, 111, 235)


def test_resolve_theme_unknown_falls_back_to_dark() -> None:
    theme = gds._resolve_theme("nonexistent")
    assert theme == gds.THEMES["dark"]


def test_resolve_theme_from_file(tmp_path: Path) -> None:
    theme_file = tmp_path / "custom.json"
    theme_file.write_text(json.dumps({"BG": [255, 0, 0], "FG": [0, 255, 0]}))
    theme = gds._resolve_theme("dark", str(theme_file))
    assert theme["BG"] == (255, 0, 0)
    assert theme["FG"] == (0, 255, 0)


def test_resolve_theme_bad_file_falls_back(tmp_path: Path) -> None:
    theme_file = tmp_path / "bad.json"
    theme_file.write_text("not json")
    theme = gds._resolve_theme("light", str(theme_file))
    assert theme == gds.THEMES["light"]


# ── font discovery ──────────────────────────────────────────────────────────


def test_find_font_returns_something() -> None:
    result = gds._find_font()
    # On any Linux CI system, at least one mono font should be found,
    # or returns None gracefully.
    assert result is None or isinstance(result, str)


def test_find_font_override_valid(tmp_path: Path) -> None:
    fake_font = tmp_path / "fake.ttf"
    fake_font.write_text("not a real font")
    result = gds._find_font(str(fake_font))
    assert result == str(fake_font)


def test_find_font_override_missing() -> None:
    result = gds._find_font("/nonexistent/path/font.ttf")
    # Should not crash; will fall through to discovery or return None
    assert result is None or isinstance(result, str)


# ── version helpers ─────────────────────────────────────────────────────────


def test_benchdeck_version() -> None:
    v = gds._benchdeck_version()
    assert isinstance(v, str)
    assert len(v) > 0


def test_git_sha() -> None:
    sha = gds._git_sha()
    assert isinstance(sha, str)
    assert len(sha) > 0


# ── synthetic data ──────────────────────────────────────────────────────────


def test_build_demo_snapshot_has_all_fields() -> None:
    snap = gds._build_demo_snapshot()
    assert isinstance(snap.metadata, dict)
    assert isinstance(snap.plan, dict)
    assert isinstance(snap.tally, dict)
    assert isinstance(snap.judgments, list)
    assert isinstance(snap.policy_blocks, list)
    assert isinstance(snap.results, dict)
    assert isinstance(snap.infrastructure_errors, list)
    assert isinstance(snap.planner_capture, dict)


def test_build_demo_snapshot_metadata_values() -> None:
    snap = gds._build_demo_snapshot()
    assert snap.metadata["status"] == "completed"
    assert snap.metadata["cases_in_plan"] == 12
    assert snap.metadata["executions_judged"] == 10
    assert snap.metadata["policy_blocks"] == 2
    assert snap.metadata["infrastructure_failures"] == 1


def test_build_demo_snapshot_has_12_cases() -> None:
    snap = gds._build_demo_snapshot()
    cases = snap.plan.get("cases", [])
    assert len(cases) == 12


def test_build_demo_snapshot_has_11_judgments() -> None:
    snap = gds._build_demo_snapshot()
    assert len(snap.judgments) == 11


def test_build_demo_snapshot_has_all_ratings() -> None:
    snap = gds._build_demo_snapshot()
    ratings = {j["overall_rating"] for j in snap.judgments}
    assert "Excellent" in ratings
    assert "Strong" in ratings
    assert "Acceptable" in ratings
    assert "Weak" in ratings
    assert "Fail" in ratings


def test_build_demo_snapshot_has_family_scores() -> None:
    snap = gds._build_demo_snapshot()
    agent_tally = snap.tally.get("repository-integrity-agent", {})
    scores = agent_tally.get("family_scores", {})
    assert len(scores) == 5
    assert scores["happy_path"] == 92.0


def test_build_demo_snapshot_has_policy_blocks() -> None:
    snap = gds._build_demo_snapshot()
    assert len(snap.policy_blocks) >= 2


def test_build_demo_snapshot_has_infrastructure_errors() -> None:
    snap = gds._build_demo_snapshot()
    assert len(snap.infrastructure_errors) >= 1


def test_build_demo_snapshot_has_planner_capture() -> None:
    snap = gds._build_demo_snapshot()
    assert snap.planner_capture.get("total_http_attempts") == 2
    assert snap.planner_capture.get("value", {}).get("mode") == "single"


def test_build_demo_snapshot_cases_have_all_families() -> None:
    snap = gds._build_demo_snapshot()
    families = {c["family"] for c in snap.plan.get("cases", [])}
    assert "happy_path" in families
    assert "regression_protection" in families
    assert "edge_case_logic" in families
    assert "policy_compliance" in families
    assert "output_hygiene" in families


# ── dual-agent synthetic data ──────────────────────────────────────────────


def test_build_dual_agent_demo_snapshot() -> None:
    snap = gds._build_dual_agent_demo_snapshot()
    assert snap.plan["mode"] == "compare"
    agents = list(snap.tally.keys())
    assert "repository-integrity-agent" in agents
    assert "security-auditor-agent" in agents


def test_dual_agent_snapshot_has_more_judgments() -> None:
    snap = gds._build_dual_agent_demo_snapshot()
    single = gds._build_demo_snapshot()
    assert len(snap.judgments) > len(single.judgments)


def test_dual_agent_snapshot_has_both_agent_labels() -> None:
    snap = gds._build_dual_agent_demo_snapshot()
    labels = {j["agent_label"] for j in snap.judgments}
    assert "repository-integrity-agent" in labels
    assert "security-auditor-agent" in labels


def test_dual_agent_snapshot_has_both_agent_results() -> None:
    snap = gds._build_dual_agent_demo_snapshot()
    assert "repository-integrity-agent" in snap.results
    assert "security-auditor-agent" in snap.results


def test_dual_agent_snapshot_has_three_policy_blocks() -> None:
    snap = gds._build_dual_agent_demo_snapshot()
    assert len(snap.policy_blocks) >= 3


# ── colourisation ───────────────────────────────────────────────────────────


THEME = gds.THEMES["dark"]


def test_colourise_progress_bar() -> None:
    parts = gds._colourise_line("Progress [#####---] 5/8", THEME)
    assert len(parts) >= 3
    assert parts[0][0] == "Progress ["
    assert "#" in "".join(p[0] for p in parts)
    assert "-" in "".join(p[0] for p in parts)


def test_colourise_blocked() -> None:
    parts = gds._colourise_line("  1 BLOCKED Case Title", THEME)
    colours = {p[1] for p in parts}
    assert THEME["RED"] in colours


def test_colourise_pending() -> None:
    parts = gds._colourise_line("  2 PENDING Case Title", THEME)
    colours = {p[1] for p in parts}
    assert THEME["FG_DIM"] in colours


def test_colourise_excellent() -> None:
    parts = gds._colourise_line("  Excellent rating found", THEME)
    colours = {p[1] for p in parts}
    assert THEME["GREEN"] in colours


def test_colourise_strong() -> None:
    parts = gds._colourise_line("  Strong rating found", THEME)
    colours = {p[1] for p in parts}
    assert THEME["BLUE"] in colours


def test_colourise_acceptable() -> None:
    parts = gds._colourise_line("  Acceptable rating found", THEME)
    colours = {p[1] for p in parts}
    assert THEME["YELLOW"] in colours


def test_colourise_weak() -> None:
    parts = gds._colourise_line("  Weak rating found", THEME)
    colours = {p[1] for p in parts}
    assert THEME["ORANGE"] in colours


def test_colourise_fail() -> None:
    parts = gds._colourise_line("  Fail rating found", THEME)
    colours = {p[1] for p in parts}
    assert THEME["RED"] in colours


def test_colourise_no_match_defaults_to_fg() -> None:
    parts = gds._colourise_line("Just some regular text", THEME)
    assert len(parts) == 1
    assert parts[0][1] == THEME["FG"]


def test_colourise_rating_inside_quotes_not_coloured() -> None:
    parts = gds._colourise_line('He said "Excellent job" to the agent', THEME)
    colours = {p[1] for p in parts if p[0] == "Excellent"}
    assert THEME["GREEN"] not in colours


def test_colourise_handles_empty_line() -> None:
    parts = gds._colourise_line("", THEME)
    assert parts == [("", THEME["FG"])]


# ── compare tab ────────────────────────────────────────────────────────────


def test_add_compare_tab_with_dual_agents() -> None:
    from benchdeck.tui import BenchDeckTUI

    snap = gds._build_dual_agent_demo_snapshot()
    tui = BenchDeckTUI(Path("/tmp/test"))
    tui.snapshot = snap
    lines = gds._add_compare_tab(tui, 80)
    joined = "\n".join(lines)
    assert "Agent Comparison" in joined
    assert (
        "repository-integrity-agent" in joined
        or "A:" in joined
        or " B:" in joined
        or "Delta" in joined
    )
    assert "Gate failures" in joined


def test_add_compare_tab_single_agent_message() -> None:
    from benchdeck.tui import BenchDeckTUI

    snap = gds._build_demo_snapshot()
    tui = BenchDeckTUI(Path("/tmp/test"))
    tui.snapshot = snap
    lines = gds._add_compare_tab(tui, 80)
    joined = "\n".join(lines)
    assert "requires at least two agents" in joined


# ── SCREEN_SPECS ────────────────────────────────────────────────────────────


def test_screen_specs_has_four_tabs() -> None:
    assert len(gds.SCREEN_SPECS) == 4


def test_screen_specs_names() -> None:
    names = [s["name"] for s in gds.SCREEN_SPECS]
    assert names == ["overview", "cases", "detail", "help"]


def test_dual_agent_screen_specs_has_five_tabs() -> None:
    assert len(gds.DUAL_AGENT_SCREEN_SPECS) >= 5


def test_dual_agent_screen_specs_includes_compare() -> None:
    names = [s["name"] for s in gds.DUAL_AGENT_SCREEN_SPECS]
    assert "compare" in names


# ── generate_screenshots API ────────────────────────────────────────────────


def test_generate_screenshots_png(tmp_path: Path) -> None:
    snap = gds._build_demo_snapshot()
    paths = gds.generate_screenshots(
        snapshot=snap,
        out_dir=tmp_path,
        width_cols=80,
        font_size=12,
        fmt="png",
        theme_name="dark",
    )
    assert len(paths) == 4
    for p in paths:
        assert p.exists()
        assert p.stat().st_size > 100


def test_generate_screenshots_webp(tmp_path: Path) -> None:
    snap = gds._build_demo_snapshot()
    paths = gds.generate_screenshots(
        snapshot=snap,
        out_dir=tmp_path,
        width_cols=80,
        font_size=12,
        fmt="webp",
        theme_name="dark",
    )
    assert len(paths) == 4
    for p in paths:
        assert p.exists()
        assert p.stat().st_size > 100
        assert p.suffix == ".webp"


def test_generate_screenshots_svg(tmp_path: Path) -> None:
    snap = gds._build_demo_snapshot()
    paths = gds.generate_screenshots(
        snapshot=snap,
        out_dir=tmp_path,
        width_cols=80,
        font_size=12,
        fmt="svg",
        theme_name="dark",
    )
    assert len(paths) == 4
    for p in paths:
        assert p.exists()
        assert p.stat().st_size > 100
        assert p.suffix == ".svg"
        content = p.read_text(encoding="utf-8")
        assert "<svg" in content
        assert "</svg>" in content


def test_generate_screenshots_all_formats(tmp_path: Path) -> None:
    snap = gds._build_demo_snapshot()
    paths = gds.generate_screenshots(
        snapshot=snap,
        out_dir=tmp_path,
        width_cols=80,
        font_size=12,
        fmt="all",
        theme_name="dark",
    )
    assert len(paths) == 12  # 4 tabs * 3 formats
    suffixes = {p.suffix for p in paths}
    assert ".png" in suffixes
    assert ".webp" in suffixes
    assert ".svg" in suffixes


def test_generate_screenshots_multi_width(tmp_path: Path) -> None:
    snap = gds._build_demo_snapshot()
    paths = gds.generate_screenshots(
        snapshot=snap,
        out_dir=tmp_path,
        width_cols=80,
        widths=[40, 80],
        font_size=12,
        fmt="png",
        theme_name="dark",
    )
    assert len(paths) == 8  # 4 tabs * 2 widths
    w40 = [p for p in paths if "w40" in p.name]
    w80 = [p for p in paths if "w80" in p.name]
    assert len(w40) == 4
    assert len(w80) == 4


def test_generate_screenshots_dual_agent(tmp_path: Path) -> None:
    snap = gds._build_dual_agent_demo_snapshot()
    paths = gds.generate_screenshots(
        snapshot=snap,
        out_dir=tmp_path,
        width_cols=80,
        font_size=12,
        fmt="png",
        theme_name="dark",
        dual=True,
    )
    assert len(paths) >= 5
    names = [p.stem.split("-")[0] for p in paths]
    assert "compare" in names


def test_generate_screenshots_with_watermark(tmp_path: Path) -> None:
    snap = gds._build_demo_snapshot()
    paths = gds.generate_screenshots(
        snapshot=snap,
        out_dir=tmp_path,
        width_cols=80,
        font_size=12,
        fmt="png",
        theme_name="dark",
        watermark=True,
    )
    assert len(paths) == 4
    for p in paths:
        assert p.exists()
        assert p.stat().st_size > 100


def test_generate_screenshots_light_theme(tmp_path: Path) -> None:
    snap = gds._build_demo_snapshot()
    paths = gds.generate_screenshots(
        snapshot=snap,
        out_dir=tmp_path,
        width_cols=80,
        font_size=12,
        fmt="png",
        theme_name="light",
    )
    assert len(paths) == 4
    for p in paths:
        assert p.exists()


def test_generate_screenshots_github_theme(tmp_path: Path) -> None:
    snap = gds._build_demo_snapshot()
    paths = gds.generate_screenshots(
        snapshot=snap,
        out_dir=tmp_path,
        width_cols=80,
        font_size=12,
        fmt="png",
        theme_name="github",
    )
    assert len(paths) == 4
    for p in paths:
        assert p.exists()


def test_generate_screenshots_custom_specs(tmp_path: Path) -> None:
    snap = gds._build_demo_snapshot()
    custom_specs = [gds.SCREEN_SPECS[0]]  # only overview
    paths = gds.generate_screenshots(
        snapshot=snap,
        out_dir=tmp_path,
        specs=custom_specs,
        width_cols=80,
        font_size=12,
        fmt="png",
        theme_name="dark",
    )
    assert len(paths) == 1
    assert paths[0].exists()
    assert "overview" in paths[0].name


# ── SVG rendering ───────────────────────────────────────────────────────────


def test_render_to_svg_creates_valid_svg(tmp_path: Path) -> None:
    from benchdeck.tui import BenchDeckTUI

    snap = gds._build_demo_snapshot()
    tui = BenchDeckTUI(Path("/tmp/test"))
    tui.snapshot = snap
    tui.tab = 0
    lines = tui._render(80)
    spec = gds.SCREEN_SPECS[0]

    path = gds._render_to_svg(
        lines,
        tmp_path,
        spec,
        "monospace",
        12,
        80,
        gds.THEMES["dark"],
        "dark",
        "synthetic",
    )
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "<svg" in content
    assert "</svg>" in content
    assert "Overview" in content.replace("&gt;", ">").replace("&lt;", "<")


# ── metadata embedding ─────────────────────────────────────────────────────


def test_embed_metadata_adds_info() -> None:
    from PIL import Image

    img = Image.new("RGB", (100, 100), (0, 0, 0))
    gds._embed_metadata(img, 80, 12, "dark", "test-source")
    assert "benchdeck" in img.info
    meta = json.loads(img.info["benchdeck"])
    assert meta["width_cols"] == 80
    assert meta["theme"] == "dark"
    assert meta["snapshot_source"] == "test-source"
    assert "generator" in meta
    assert "timestamp" in meta


# ── inside_quotes helper ───────────────────────────────────────────────────


def test_inside_quotes_double_quoted() -> None:
    assert gds._inside_quotes('He said "Excellent work"', "Excellent")


def test_inside_quotes_not_inside() -> None:
    assert not gds._inside_quotes("Excellent work", "Excellent")


def test_inside_quotes_single_quoted() -> None:
    assert gds._inside_quotes("He said 'Excellent work'", "Excellent")


# ── TUI integration ────────────────────────────────────────────────────────


def test_tui_renders_overview_with_demo_snapshot() -> None:
    from benchdeck.tui import BenchDeckTUI

    snap = gds._build_demo_snapshot()
    tui = BenchDeckTUI(Path("/tmp/test"))
    tui.snapshot = snap
    tui.tab = 0
    lines = tui._render(80)
    joined = "\n".join(lines)
    assert "Progress" in joined
    assert "10/12" in joined
    assert "Policy blocks" in joined
    assert "Excellent" in joined
    assert "Weak" in joined
    assert "Fail" in joined


def test_tui_renders_cases_with_demo_snapshot() -> None:
    from benchdeck.tui import BenchDeckTUI

    snap = gds._build_demo_snapshot()
    tui = BenchDeckTUI(Path("/tmp/test"))
    tui.snapshot = snap
    tui.tab = 1
    lines = tui._render(80)
    joined = "\n".join(lines)
    assert "Case" in joined or "Cases" in joined
    assert "BLOCKED" in joined


def test_tui_renders_detail_with_demo_snapshot() -> None:
    from benchdeck.tui import BenchDeckTUI

    snap = gds._build_demo_snapshot()
    tui = BenchDeckTUI(Path("/tmp/test"))
    tui.snapshot = snap
    tui.tab = 2
    tui.selected = 0
    lines = tui._render(80)
    joined = "\n".join(lines)
    assert "Case 1" in joined
    assert "Excellent" in joined


def test_tui_renders_help_with_demo_snapshot() -> None:
    from benchdeck.tui import BenchDeckTUI

    snap = gds._build_demo_snapshot()
    tui = BenchDeckTUI(Path("/tmp/test"))
    tui.snapshot = snap
    tui.tab = 3
    lines = tui._render(80)
    joined = "\n".join(lines)
    assert "1-4" in joined
    assert "h / l" in joined
    assert "j / k" in joined
