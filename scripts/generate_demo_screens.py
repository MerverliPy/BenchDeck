"""Generate demo-quality TUI screenshots with realistic synthetic data."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchdeck.tui import BenchDeckTUI, Snapshot  # noqa: E402


def _ensure_pillow() -> None:
    try:
        import PIL.Image  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow>=9"])


# ── terminal colour palette ───────────────────────────────────────────────
BG = (24, 24, 32)
FG = (212, 212, 212)
FG_DIM = (128, 128, 128)
FG_BRIGHT = (255, 255, 255)
YELLOW = (220, 200, 100)
GREEN = (120, 210, 120)
RED = (220, 100, 100)
BLUE = (100, 180, 230)
CYAN = (80, 200, 200)
ORANGE = (230, 170, 100)
HEADER_BG = (36, 36, 50)
TAB_ACTIVE = (60, 60, 110)
TAB_INACTIVE = (32, 32, 44)
ROW_HOVER = (44, 44, 60)

# ── font helpers ──────────────────────────────────────────────────────────


def _find_font() -> str | None:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/noto/NotoMono-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    return None


def _load_font(path: str | None, size: int) -> Any:
    from PIL import ImageFont

    if path and Path(path).exists():
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    for candidate in _find_font_candidates():
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _find_font_candidates() -> list[str]:
    return [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]


# ── synthetic demo data ──────────────────────────────────────────────────


def _build_demo_snapshot() -> Snapshot:
    return Snapshot(
        metadata={
            "status": "completed",
            "cases_in_plan": 12,
            "executions_judged": 10,
            "policy_blocks": 1,
            "infrastructure_failures": 1,
            "token_usage": {"requests": 48, "total_tokens": 184_320},
        },
        tally={
            "cases_planned": 12,
            "cases_judged": 10,
            "policy_blocks": 1,
            "infrastructure_failures": 1,
            "rating_counts": {
                "Excellent": 3,
                "Strong": 4,
                "Acceptable": 2,
                "Weak": 0,
                "Fail": 1,
            },
            "family_scores": {
                "happy_path": 92.0,
                "regression_protection": 85.5,
                "edge_case_logic": 70.0,
                "policy_compliance": 95.0,
                "output_hygiene": 88.0,
            },
        },
        plan={
            "mode": "single",
            "profile": {
                "agent_name_a": "repository-integrity-agent",
                "inferred_mission": "Verify repository integrity through test-driven analysis",
            },
            "cases": [
                {
                    "id": 1,
                    "title": "Detect missing dependency declaration",
                    "family": "happy_path",
                    "purpose": "Agent should identify that a package is imported but not declared in requirements.",
                    "test_prompt": "Review the following project. Does it have any undeclared runtime dependencies?",
                },
                {
                    "id": 2,
                    "title": "Flag pinned version drift",
                    "family": "regression_protection",
                    "purpose": "Agent should detect when a pinned version in requirements.txt differs from the installed package.",
                    "test_prompt": "The project pins requests==2.28.0 but the installed version is 2.31.0. What should be done?",
                },
                {
                    "id": 3,
                    "title": "Security advisory check",
                    "family": "policy_compliance",
                    "purpose": "Agent should cross-reference dependencies against known CVEs.",
                    "test_prompt": "Check all dependencies against the OSS vulnerability database. Report any findings.",
                },
                {
                    "id": 4,
                    "title": "CI config completeness",
                    "family": "happy_path",
                    "purpose": "Agent should verify GitHub Actions workflow covers all supported Python versions.",
                    "test_prompt": "Review the CI configuration. Are all declared Python versions tested?",
                },
                {
                    "id": 5,
                    "title": "Linter config conflict",
                    "family": "regression_protection",
                    "purpose": "Agent should detect conflicting linter rules between pyproject.toml and .flake8.",
                    "test_prompt": "The project has both pyproject.toml and .flake8 with overlapping rules. Find conflicts.",
                },
                {
                    "id": 6,
                    "title": "Missing type stub package",
                    "family": "edge_case_logic",
                    "purpose": "Agent should suggest adding types-* packages for libraries that lack inline types.",
                    "test_prompt": "This project uses boto3 without type stubs. What is the recommended approach?",
                },
                {
                    "id": 7,
                    "title": "License compatibility audit",
                    "family": "policy_compliance",
                    "purpose": "Agent should verify that all transitive dependencies have compatible licenses.",
                    "test_prompt": "The project is Apache-2.0. Audit transitive dependency licenses for compatibility.",
                },
                {
                    "id": 8,
                    "title": "Circular import detection",
                    "family": "edge_case_logic",
                    "purpose": "Agent should find circular imports that cause ImportError at runtime.",
                    "test_prompt": "The module structure contains potential circular imports. Identify and suggest a fix.",
                },
                {
                    "id": 9,
                    "title": "Dockerfile base image freshness",
                    "family": "happy_path",
                    "purpose": "Agent should recommend updating the Docker base image to the latest patch.",
                    "test_prompt": "The Dockerfile uses python:3.11-slim. Is this base image current?",
                },
                {
                    "id": 10,
                    "title": "Environment variable validation",
                    "family": "output_hygiene",
                    "purpose": "Agent should check that all required env vars are documented and validated.",
                    "test_prompt": "This service reads 6 environment variables at startup. Are they all validated and documented?",
                },
                {
                    "id": 11,
                    "title": "Logging level configuration",
                    "family": "output_hygiene",
                    "purpose": "Agent should ensure log levels are configurable and not hardcoded.",
                    "test_prompt": "Review the logging setup. Is the log level configurable via environment or config file?",
                },
                {
                    "id": 12,
                    "title": "Policy-blocked content check",
                    "family": "policy_compliance",
                    "purpose": "Agent should identify when a case triggers a model policy block.",
                    "test_prompt": "This case contains a benign security question: explain how SSL pinning works.",
                },
            ],
        },
        judgments=[
            {
                "case_id": 1,
                "overall_rating": "Excellent",
                "agent_label": "repository-integrity-agent",
                "why": "Correctly identified the undeclared dependency, cited the import line and the missing requirements entry, and suggested a specific fix with version pinning.",
                "gate_check": {"status": "PASS", "reason": "All required elements present"},
            },
            {
                "case_id": 2,
                "overall_rating": "Excellent",
                "agent_label": "repository-integrity-agent",
                "why": "Detected the version mismatch and provided a root-cause analysis. Suggested both immediate fix and process improvement.",
                "gate_check": {"status": "PASS", "reason": "Version drift identified correctly"},
            },
            {
                "case_id": 3,
                "overall_rating": "Excellent",
                "agent_label": "repository-integrity-agent",
                "why": "Cross-referenced all dependencies against the CVE database, reported two medium-severity findings with remediation steps.",
                "gate_check": {"status": "PASS", "reason": "Complete CVE analysis provided"},
            },
            {
                "case_id": 4,
                "overall_rating": "Strong",
                "agent_label": "repository-integrity-agent",
                "why": "Found the CI config but missed one matrix exclusion edge case. Overall analysis was thorough and actionable.",
                "gate_check": {"status": "PASS", "reason": "CI analysis mostly complete"},
            },
            {
                "case_id": 5,
                "overall_rating": "Strong",
                "agent_label": "repository-integrity-agent",
                "why": "Identified 3 conflicts between pyproject.toml and .flake8. Response was clear and well-structured.",
                "gate_check": {"status": "PASS", "reason": "Conflicts correctly identified"},
            },
            {
                "case_id": 6,
                "overall_rating": "Strong",
                "agent_label": "repository-integrity-agent",
                "why": "Recommended types-boto3 and types-requests, explained the trade-offs. Could have mentioned stub-only packages.",
                "gate_check": {"status": "PASS", "reason": "Good type-stub analysis"},
            },
            {
                "case_id": 7,
                "overall_rating": "Strong",
                "agent_label": "repository-integrity-agent",
                "why": "Audited 42 transitive deps, flagged one GPL-3.0 dependency that may conflict with Apache-2.0. Thorough and well-reasoned.",
                "gate_check": {"status": "PASS", "reason": "Complete license audit"},
            },
            {
                "case_id": 8,
                "overall_rating": "Acceptable",
                "agent_label": "repository-integrity-agent",
                "why": "Identified the circular import but suggested a workaround rather than a structural fix. Correct but incomplete.",
                "gate_check": {"status": "PASS", "reason": "Issue identified"},
            },
            {
                "case_id": 9,
                "overall_rating": "Acceptable",
                "agent_label": "repository-integrity-agent",
                "why": "Verified the base image is current but didn't suggest digest pinning for reproducibility.",
                "gate_check": {"status": "PASS", "reason": "Base check performed"},
            },
            {
                "case_id": 10,
                "overall_rating": "Fail",
                "agent_label": "repository-integrity-agent",
                "why": "Response was empty after 3 retries. Infrastructure failure recorded separately.",
                "gate_check": {
                    "status": "FAIL",
                    "reason": "No output produced after maximum retries",
                },
            },
        ],
        policy_blocks=[
            {"case_id": 12, "message": "Content policy triggered on security-related prompt"},
        ],
        results={
            "repository-integrity-agent": [
                {
                    "case_id": 1,
                    "final_output": (
                        "The project imports 'click' in src/cli.py:3 but does not declare it in "
                        "requirements.txt or pyproject.toml. Add 'click>=8.0' to the dependencies "
                        "list. The import is reached in the CLI entry point, making this a runtime "
                        "dependency, not a dev dependency."
                    ),
                },
                {
                    "case_id": 2,
                    "final_output": (
                        "requirements.txt pins requests==2.28.0, but pip freeze shows requests==2.31.0. "
                        "This indicates an unpinned install or a transitive dependency upgrade. "
                        "Recommendation: (1) pin to 2.31.0 after testing, or (2) add a constraints.txt "
                        "and enforce it in CI with pip check."
                    ),
                },
                {
                    "case_id": 3,
                    "final_output": (
                        "CVE scan results:\n"
                        "- urllib3<2.0: CVE-2023-45803 (medium) — recommended upgrade to 2.0.7+\n"
                        "- certifi<2023.7.22: CVE-2023-37920 (medium) — recommended upgrade to 2024.2.2+\n"
                        "Both are transitive through requests. Pinning requests>=2.31.0 resolves both."
                    ),
                },
                {
                    "case_id": 4,
                    "final_output": (
                        "The CI matrix tests Python 3.11, 3.12, and 3.13. "
                        "pyproject.toml declares support for 3.11+. "
                        "No gap found — all declared versions are covered. "
                        "Minor improvement: add a pre-commit hook running on all three versions."
                    ),
                },
                {
                    "case_id": 5,
                    "final_output": (
                        "Conflicts found:\n"
                        "1. pyproject.toml sets line-length=88, .flake8 sets max-line-length=79 → conflict\n"
                        "2. pyproject.toml selects=['E','F','I'], .flake8 ignore=E203,W503 → redundant\n"
                        "3. pyproject.toml target-version=py311, .flake8 has no version pin → drift risk\n"
                        "Recommend: remove .flake8, consolidate in pyproject.toml."
                    ),
                },
                {
                    "case_id": 6,
                    "final_output": (
                        "boto3 lacks inline type annotations. Install types-boto3 for mypy support.\n"
                        "Also consider types-requests if strict mypy is used.\n"
                        "Alternative: boto3-stubs provides more granular types per service."
                    ),
                },
                {
                    "case_id": 7,
                    "final_output": (
                        "Dependency license audit (42 packages):\n"
                        "- 38 packages: MIT, BSD, Apache-2.0 → compatible\n"
                        "- 2 packages: LGPL-2.1 → dynamically linked, ok\n"
                        "- 1 package: GPL-3.0 (libfoo==1.2.0) → incompatible with Apache-2.0\n"
                        "- 1 package: unlicensed → investigate\n"
                        "Action: replace libfoo with an MIT-licensed alternative."
                    ),
                },
                {
                    "case_id": 8,
                    "final_output": (
                        "Circular import detected: src/models.py imports from src/validators.py, "
                        "which imports from src/models.py → cycle. "
                        "Workaround: move shared types to src/_types.py. "
                        "Better fix: refactor validators to accept dependencies via constructor injection."
                    ),
                },
                {
                    "case_id": 9,
                    "final_output": (
                        "Dockerfile uses python:3.11-slim. Current digest maps to 3.11.9. "
                        "Latest is 3.11.10 (patch release with security fixes). "
                        "Recommended: update to python:3.11.10-slim and consider digest pinning "
                        "for reproducible builds."
                    ),
                },
            ],
        },
    )


SCREEN_SPECS: list[dict[str, Any]] = [
    {
        "tab": 0,
        "name": "overview",
        "label": "Overview screen — progress bar, rating distribution, per-family scores, policy blocks, and usage stats",
        "selected": 0,
    },
    {
        "tab": 1,
        "name": "cases",
        "label": "Case list — all 12 cases with per-agent ratings, blocked cases, and pending items",
        "selected": 0,
    },
    {
        "tab": 2,
        "name": "detail",
        "label": "Case detail — purpose, judgment (rating, why, gate check), and agent output for case 1",
        "selected": 0,
    },
    {
        "tab": 3,
        "name": "help",
        "label": "Help — keyboard controls for phone-friendly SSH navigation",
        "selected": 0,
    },
]


# ── rendering ────────────────────────────────────────────────────────────


def _render_tab_bar(
    draw: Any, bold_font: Any, img_w: int, tab_bar_h: int, char_h: int, active_idx: int
) -> None:
    tab_names = ["1:Overview", "2:Cases", "3:Detail", "4:Help"]
    tab_w = img_w / len(tab_names)
    for i, tname in enumerate(tab_names):
        x0, x1 = int(i * tab_w), int((i + 1) * tab_w)
        fill = TAB_ACTIVE if i == active_idx else TAB_INACTIVE
        draw.rectangle([(x0, 0), (x1, tab_bar_h)], fill=fill)
        tw = draw.textlength(tname, font=bold_font)
        draw.text(
            (x0 + (tab_w - tw) / 2, (tab_bar_h - char_h) / 2),
            tname,
            fill=FG_BRIGHT if i == active_idx else FG_DIM,
            font=bold_font,
        )


def _render_footer(
    draw: Any, font: Any, img_w: int, footer_y: int, footer_h: int, char_h: int
) -> None:
    draw.rectangle([(0, footer_y), (img_w, footer_y + footer_h)], fill=HEADER_BG)
    footer_text = "h/l tabs  j/k move  Enter detail  e export  r reload  q quit"
    fw = draw.textlength(footer_text, font=font)
    draw.text(
        ((img_w - fw) / 2, footer_y + (footer_h - char_h) / 2),
        footer_text,
        fill=FG_DIM,
        font=font,
    )


def _render_label(draw: Any, font: Any, img_w: int, label_y: int, label: str) -> None:
    draw.text((16, label_y), label, fill=(100, 100, 120), font=font)


def _colourise_line(line: str) -> list[tuple[str, tuple[int, int, int]]]:
    """Very simple colourisation: progress bar, rating keywords, etc."""
    parts: list[tuple[str, tuple[int, int, int]]] = []
    l = line

    # leading progress bar chunk "[#####---]"
    if l.startswith("Progress ["):
        end_br = l.find("]")
        if end_br != -1:
            bar_text = l[: end_br + 1]
            # colour hashes green
            hash_end = bar_text.find("-") if "-" in bar_text else len(bar_text) - 1
            if hash_end > 10:
                parts.append((bar_text[:hash_end], GREEN))
            if hash_end < len(bar_text) - 1:
                parts.append((bar_text[hash_end:], FG_DIM))
            l = l[end_br + 1 :]
            parts.append((l, FG))
            return parts

    if "BLOCKED" in l:
        idx = l.index("BLOCKED")
        parts.append((l[:idx], FG))
        parts.append(("BLOCKED", RED))
        parts.append((l[idx + 7 :], FG))
        return parts
    if "PENDING" in l:
        idx = l.index("PENDING")
        parts.append((l[:idx], FG))
        parts.append(("PENDING", FG_DIM))
        parts.append((l[idx + 7 :], FG))
        return parts

    # colour ratings inline
    for rating, colour in [
        ("Excellent", GREEN),
        ("Strong", BLUE),
        ("Acceptable", YELLOW),
        ("Weak", ORANGE),
        ("Fail", RED),
    ]:
        if rating in l:
            idx = l.index(rating)
            before = l[:idx]
            after = l[idx + len(rating) :]
            parts.append((before, FG))
            parts.append((rating, colour))
            parts.append((after, FG))
            return parts

    parts.append((l, FG))
    return parts


def _render_to_png(
    lines: list[str],
    out_dir: Path,
    spec: dict[str, Any],
    font: Any,
    bold_font: Any,
    font_size: int,
    width_cols: int,
) -> Path:
    from PIL import Image, ImageDraw

    char_w = int(font_size * 0.6)
    char_h = int(font_size * 1.35)
    px_x = int(font_size * 0.9)
    py = int(font_size * 0.7)
    tab_bar_h = char_h + int(font_size * 0.8)
    footer_h = char_h + int(font_size * 0.6)

    img_w = width_cols * char_w + px_x * 2
    content_h = len(lines) * char_h
    img_h = content_h + py * 2 + tab_bar_h + footer_h

    img = Image.new("RGB", (img_w, img_h), BG)
    draw = ImageDraw.Draw(img)

    # tab bar
    _render_tab_bar(draw, bold_font, img_w, tab_bar_h, char_h, spec["tab"])

    # label beneath tab bar
    label_y = tab_bar_h + int(font_size * 0.5)
    _render_label(draw, font, img_w, label_y, spec["label"])

    # content
    y = label_y + char_h + py
    for line in lines:
        parts = _colourise_line(line)
        cx = px_x
        for text, colour in parts:
            draw.text((cx, y), text, fill=colour, font=font)
            tw = draw.textlength(text, font=font)
            cx += tw
        y += char_h

    # footer
    _render_footer(draw, font, img_w, y, footer_h, char_h)

    png_path = out_dir / f"{spec['name']}.png"
    img.save(png_path, "PNG")
    return png_path


# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate demo TUI screenshots")
    parser.add_argument(
        "-o", type=Path, default=Path("assets/screenshots"), help="Output directory"
    )
    parser.add_argument("-w", type=int, default=80, help="Terminal width")
    parser.add_argument("--font-size", type=int, default=15, help="Font size")
    args = parser.parse_args()

    _ensure_pillow()

    font_path = _find_font()
    font = _load_font(font_path, args.font_size)
    bold_font = _load_font(font_path, args.font_size)  # same for simplicity

    snapshot = _build_demo_snapshot()
    tui = BenchDeckTUI(Path("/tmp/demo-benchmark"))
    tui.snapshot = snapshot

    out_dir: Path = args.o
    out_dir.mkdir(parents=True, exist_ok=True)

    saved: list[Path] = []
    for spec in SCREEN_SPECS:
        tui.tab = spec["tab"]
        tui.selected = spec["selected"]
        lines = tui._render(args.w)
        path = _render_to_png(lines, out_dir, spec, font, bold_font, args.font_size, args.w)
        saved.append(path)
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
