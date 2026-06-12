"""Capture real benchmark screenshots for the specified 4 tabs.

Usage:
    python scripts/_capture_screens.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from benchdeck.loader import load_snapshot  # noqa: E402
from benchdeck.tui import BenchDeckTUI  # noqa: E402

# Import render helpers from the generate_demo_screens module
from scripts.generate_demo_screens import (  # noqa: E402
    _find_font,
    _load_font,
    _render_to_png,
    _resolve_theme,
)

OUT_DIR = PROJECT_ROOT / "assets" / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RUN_DIR = PROJECT_ROOT / "benchmark_out" / "20260612T172324.803315Z"

WIDTH = 80
FONT_SIZE = 15
THEME = "dark"

# Custom specs matching the user's navigation request
SPECS = [
    {
        "tab": 0,
        "name": "overview_real",
        "label": (
            "Overview - progress bar, rating distribution, per-family scores, "
            "policy blocks, usage stats"
        ),
        "selected": 0,
    },
    {
        "tab": 1,
        "name": "cases_real",
        "label": "Case list - all cases with per-agent ratings, blocked cases, pending items",
        "selected": 0,
    },
    {
        "tab": 2,
        "name": "detail_real",
        "label": (
            "Case detail - purpose, judgment (rating, why, gate check), agent output for case 2"
        ),
        "selected": 1,  # case 2 (0-indexed)
    },
    {
        "tab": 3,
        "name": "help_real",
        "label": "Help - keyboard controls for phone-friendly SSH navigation",
        "selected": 0,
    },
]


def main() -> None:
    print(f"Loading snapshot from {RUN_DIR}")
    snapshot = load_snapshot(RUN_DIR)

    print(f"  status: {snapshot.metadata.get('status')}")
    print(f"  cases: {snapshot.metadata.get('cases_in_plan')}")
    print(f"  agents: {snapshot.metadata.get('agents_in_run')}")
    print(f"  judged: {snapshot.metadata.get('executions_judged')}")

    theme = _resolve_theme(THEME)
    font_path = _find_font()
    print(f"Font: {font_path}")

    font = _load_font(font_path, FONT_SIZE)
    bold_font = _load_font(font_path, FONT_SIZE)  # same font, Pillow doesn't do bold natively

    tui = BenchDeckTUI(Path("/tmp/benchdeck-screenshots"))
    tui.snapshot = snapshot

    saved_paths = []

    for spec in SPECS:
        tui.tab = spec["tab"]
        tui.selected = spec.get("selected", 0)

        lines = tui._render(WIDTH)
        print(f"\nRendering tab {spec['tab'] + 1}: {spec['name']} (selected={tui.selected})")
        print(f"  lines: {len(lines)}")

        png_path = _render_to_png(
            lines=lines,
            out_dir=OUT_DIR,
            spec=spec,
            font=font,
            bold_font=bold_font,
            font_size=FONT_SIZE,
            width_cols=WIDTH,
            theme=theme,
            theme_name=THEME,
            snapshot_source="real",
        )
        saved_paths.append(png_path)
        print(f"  saved -> {png_path}")

    print("\n--- All screenshots saved ---")
    for p in saved_paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()
