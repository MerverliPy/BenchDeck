"""Generate TUI screenshots from synthetic or real benchmark data.

Usage:
  python scripts/generate_demo_screens.py                        # synthetic demo data
  python scripts/generate_demo_screens.py --run-dir benchmark_out # real benchmark
  python scripts/generate_demo_screens.py --run-zip fixtures/original_run.zip
  python scripts/generate_demo_screens.py --format webp --theme light
  python scripts/generate_demo_screens.py --widths 40,60,80 --dual
  python scripts/generate_demo_screens.py --show
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchdeck.loader import Snapshot, load_snapshot  # noqa: E402
from benchdeck.tui import BenchDeckTUI  # noqa: E402

# ── version / metadata helpers ──────────────────────────────────────────────


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(PROJECT_ROOT),
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _benchdeck_version() -> str:
    try:
        cfg = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'version\s*=\s*"([^"]+)"', cfg)
        return m.group(1) if m else "0.0.0"
    except (OSError, AttributeError):
        return "0.0.0"


# ── colour themes ───────────────────────────────────────────────────────────

THEMES: dict[str, dict[str, tuple[int, int, int]]] = {
    "dark": {
        "BG": (24, 24, 32),
        "FG": (212, 212, 212),
        "FG_DIM": (128, 128, 128),
        "FG_BRIGHT": (255, 255, 255),
        "YELLOW": (220, 200, 100),
        "GREEN": (120, 210, 120),
        "RED": (220, 100, 100),
        "BLUE": (100, 180, 230),
        "CYAN": (80, 200, 200),
        "ORANGE": (230, 170, 100),
        "HEADER_BG": (36, 36, 50),
        "TAB_ACTIVE": (60, 60, 110),
        "TAB_INACTIVE": (32, 32, 44),
        "ROW_HOVER": (44, 44, 60),
        "LABEL": (100, 100, 120),
    },
    "light": {
        "BG": (248, 248, 252),
        "FG": (40, 40, 48),
        "FG_DIM": (140, 140, 148),
        "FG_BRIGHT": (16, 16, 24),
        "YELLOW": (180, 150, 20),
        "GREEN": (40, 140, 60),
        "RED": (200, 60, 60),
        "BLUE": (40, 100, 180),
        "CYAN": (30, 140, 150),
        "ORANGE": (180, 120, 40),
        "HEADER_BG": (232, 232, 240),
        "TAB_ACTIVE": (200, 210, 240),
        "TAB_INACTIVE": (220, 220, 228),
        "ROW_HOVER": (210, 210, 220),
        "LABEL": (130, 130, 145),
    },
    "github": {
        "BG": (13, 17, 23),
        "FG": (230, 237, 243),
        "FG_DIM": (125, 133, 144),
        "FG_BRIGHT": (255, 255, 255),
        "YELLOW": (210, 168, 0),
        "GREEN": (63, 185, 80),
        "RED": (248, 81, 73),
        "BLUE": (88, 166, 255),
        "CYAN": (57, 197, 207),
        "ORANGE": (219, 109, 40),
        "HEADER_BG": (22, 27, 34),
        "TAB_ACTIVE": (31, 111, 235),
        "TAB_INACTIVE": (33, 38, 45),
        "ROW_HOVER": (40, 46, 55),
        "LABEL": (110, 118, 129),
    },
}


def _resolve_theme(
    theme_name: str, theme_file: str | None = None
) -> dict[str, tuple[int, int, int]]:
    if theme_file:
        try:
            data = json.loads(Path(theme_file).read_text(encoding="utf-8"))
            return {k: tuple(v) for k, v in data.items()}
        except (OSError, json.JSONDecodeError, TypeError):
            print(
                f"Warning: could not load theme file '{theme_file}', falling back.", file=sys.stderr
            )
    return THEMES.get(theme_name, THEMES["dark"])


# ── font discovery ──────────────────────────────────────────────────────────

_MONO_PATTERNS = [
    "Mono",
    "mono",
    "Mono",
    "Consol",
    "consol",
    "Courier",
    "courier",
    "monaco",
    "Monaco",
    "Hack",
    "SourceCode",
    "FiraCode",
    "Fira Mono",
    "Ubuntu Mono",
    "NotoMono",
    "DejaVuSansMono",
]


def _find_font(font_path_override: str | None = None) -> str | None:
    if font_path_override and Path(font_path_override).exists():
        return font_path_override

    font_dirs = [
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        os.path.expanduser("~/.fonts"),
        os.path.expanduser("~/.local/share/fonts"),
        "/Library/Fonts",
        "/System/Library/Fonts",
    ]
    if sys.platform == "darwin":
        font_dirs.insert(0, os.path.expanduser("~/Library/Fonts"))

    best_score = -1
    best_path: str | None = None

    for font_dir in font_dirs:
        font_path = Path(font_dir)
        if not font_path.is_dir():
            continue
        for candidate in font_path.rglob("*.ttf"):
            name = candidate.name
            score = 0
            for i, pat in enumerate(_MONO_PATTERNS):
                if pat in name:
                    score = len(_MONO_PATTERNS) - i
                    break
            if "Bold" in name:
                score -= 0.5
            if score > best_score:
                best_score = score
                best_path = str(candidate)

    if best_path:
        return best_path

    # fallback: try hardcoded Debian/Ubuntu paths
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    ]:
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
    return ImageFont.load_default()


# ── synthetic demo data ─────────────────────────────────────────────────────


def _build_demo_snapshot() -> Snapshot:
    return Snapshot(
        metadata={
            "status": "completed",
            "cases_in_plan": 12,
            "executions_judged": 10,
            "policy_blocks": 2,
            "infrastructure_failures": 1,
            "token_usage": {"requests": 48, "total_tokens": 184_320},
        },
        tally={
            "repository-integrity-agent": {
                "score_scale": {"Excellent": 4, "Strong": 3, "Acceptable": 2, "Weak": 1, "Fail": 0},
                "rating_counts": {
                    "Excellent": 3,
                    "Strong": 4,
                    "Acceptable": 2,
                    "Weak": 1,
                    "Fail": 2,
                },
                "family_scores": {
                    "happy_path": 92.0,
                    "regression_protection": 85.5,
                    "edge_case_logic": 70.0,
                    "policy_compliance": 95.0,
                    "output_hygiene": 88.0,
                },
                "gate_failures": 1,
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
                "why": "Detected the version mismatch and provided a root-cause analysis.",
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
                "why": "Found the CI config but missed one matrix exclusion edge case.",
                "gate_check": {"status": "PASS", "reason": "CI analysis mostly complete"},
            },
            {
                "case_id": 5,
                "overall_rating": "Strong",
                "agent_label": "repository-integrity-agent",
                "why": "Identified 3 conflicts between pyproject.toml and .flake8.",
                "gate_check": {"status": "PASS", "reason": "Conflicts correctly identified"},
            },
            {
                "case_id": 6,
                "overall_rating": "Strong",
                "agent_label": "repository-integrity-agent",
                "why": "Recommended types-boto3 and types-requests, explained the trade-offs.",
                "gate_check": {"status": "PASS", "reason": "Good type-stub analysis"},
            },
            {
                "case_id": 7,
                "overall_rating": "Strong",
                "agent_label": "repository-integrity-agent",
                "why": "Audited 42 transitive deps, flagged one GPL-3.0 dependency.",
                "gate_check": {"status": "PASS", "reason": "Complete license audit"},
            },
            {
                "case_id": 8,
                "overall_rating": "Acceptable",
                "agent_label": "repository-integrity-agent",
                "why": "Identified the circular import but suggested a workaround rather than a structural fix.",
                "gate_check": {"status": "PASS", "reason": "Issue identified"},
            },
            {
                "case_id": 9,
                "overall_rating": "Acceptable",
                "agent_label": "repository-integrity-agent",
                "why": "Verified the base image is current but didn't suggest digest pinning.",
                "gate_check": {"status": "PASS", "reason": "Base check performed"},
            },
            {
                "case_id": 10,
                "overall_rating": "Weak",
                "agent_label": "repository-integrity-agent",
                "why": "Response mentioned env vars but didn't validate them. Incomplete analysis.",
                "gate_check": {"status": "PASS", "reason": "Partial analysis"},
            },
            {
                "case_id": 11,
                "overall_rating": "Fail",
                "agent_label": "repository-integrity-agent",
                "why": "Incorrectly claimed logging is configurable when it's hardcoded. Misleading.",
                "gate_check": {
                    "status": "FAIL",
                    "reason": "Factually incorrect assessment",
                },
            },
        ],
        policy_blocks=[
            {"case_id": 12, "message": "Content policy triggered on security-related prompt"},
            {"case_id": 3, "message": "Content policy triggered on CVE-related prompt"},
        ],
        infrastructure_errors=[
            {
                "case_id": 12,
                "agent_label": "repository-integrity-agent",
                "stage": "agent",
                "error_type": "policy_block",
                "message": "Model refused to respond: content policy triggered",
                "response_id": None,
                "attempts": 3,
            },
        ],
        results={
            "repository-integrity-agent": [
                {
                    "case_id": 1,
                    "final_output": (
                        "The project imports 'click' in src/cli.py:3 but does not declare it in "
                        "requirements.txt or pyproject.toml. Add 'click>=8.0' to the dependencies "
                        "list."
                    ),
                },
                {
                    "case_id": 2,
                    "final_output": (
                        "requirements.txt pins requests==2.28.0, but pip freeze shows requests==2.31.0. "
                        "Recommendation: (1) pin to 2.31.0 after testing, or (2) add a constraints.txt "
                        "and enforce it in CI with pip check."
                    ),
                },
                {
                    "case_id": 3,
                    "final_output": (
                        "CVE scan results:\n"
                        "- urllib3<2.0: CVE-2023-45803 (medium)\n"
                        "- certifi<2023.7.22: CVE-2023-37920 (medium)\n"
                        "Both are transitive through requests."
                    ),
                },
                {
                    "case_id": 4,
                    "final_output": (
                        "The CI matrix tests Python 3.11, 3.12, and 3.13. "
                        "pyproject.toml declares support for 3.11+. "
                        "No gap found."
                    ),
                },
                {
                    "case_id": 5,
                    "final_output": (
                        "Conflicts found:\n"
                        "1. pyproject.toml sets line-length=88, .flake8 sets max-line-length=79\n"
                        "2. pyproject.toml selects=['E','F','I'], .flake8 ignore=E203,W503\n"
                        "Recommend: remove .flake8, consolidate in pyproject.toml."
                    ),
                },
                {
                    "case_id": 6,
                    "final_output": (
                        "boto3 lacks inline type annotations. Install types-boto3 for mypy support.\n"
                        "Also consider types-requests if strict mypy is used."
                    ),
                },
                {
                    "case_id": 7,
                    "final_output": (
                        "Dependency license audit (42 packages):\n"
                        "- 38 packages: MIT, BSD, Apache-2.0\n"
                        "- 2 packages: LGPL-2.1\n"
                        "- 1 package: GPL-3.0 (libfoo==1.2.0)\n"
                        "Action: replace libfoo with an MIT-licensed alternative."
                    ),
                },
                {
                    "case_id": 8,
                    "final_output": (
                        "Circular import detected: src/models.py imports from src/validators.py, "
                        "which imports from src/models.py. Refactor to break the cycle."
                    ),
                },
                {
                    "case_id": 9,
                    "final_output": (
                        "Dockerfile uses python:3.11-slim. Current digest maps to 3.11.9. "
                        "Latest is 3.11.10. Recommended: update and consider digest pinning."
                    ),
                },
            ],
        },
        planner_capture={
            "value": {"mode": "single"},
            "attempts": [
                {"usage": {"input_tokens": 1200, "output_tokens": 350}},
                {"usage": {"input_tokens": 1200, "output_tokens": 340}},
            ],
            "total_http_attempts": 2,
        },
    )


def _build_dual_agent_demo_snapshot() -> Snapshot:
    snapshot = _build_demo_snapshot()
    tally: dict[str, Any] = dict(snapshot.tally)
    tally["repository-integrity-agent"] = {
        "score_scale": {"Excellent": 4, "Strong": 3, "Acceptable": 2, "Weak": 1, "Fail": 0},
        "rating_counts": {"Excellent": 3, "Strong": 4, "Acceptable": 2, "Weak": 1, "Fail": 0},
        "family_scores": {
            "happy_path": 92.0,
            "regression_protection": 85.5,
            "edge_case_logic": 70.0,
            "policy_compliance": 95.0,
            "output_hygiene": 88.0,
        },
        "gate_failures": 1,
    }
    tally["security-auditor-agent"] = {
        "score_scale": {"Excellent": 4, "Strong": 3, "Acceptable": 2, "Weak": 1, "Fail": 0},
        "rating_counts": {"Excellent": 2, "Strong": 5, "Acceptable": 1, "Weak": 1, "Fail": 1},
        "family_scores": {
            "happy_path": 78.0,
            "regression_protection": 70.0,
            "edge_case_logic": 65.0,
            "policy_compliance": 98.0,
            "output_hygiene": 72.0,
        },
        "gate_failures": 2,
    }
    snapshot.tally = tally

    plan = dict(snapshot.plan)
    plan["mode"] = "compare"
    plan["profile"] = {
        "agent_name_a": "repository-integrity-agent",
        "agent_name_b": "security-auditor-agent",
        "inferred_mission": "Compare repository integrity vs security audit approaches",
    }
    snapshot.plan = plan

    existing_judgments = list(snapshot.judgments)
    extra_judgments = [
        {
            "case_id": 1,
            "overall_rating": "Strong",
            "agent_label": "security-auditor-agent",
            "why": "Identified the missing dependency but didn't check for known vulnerabilities in the suggested version.",
            "gate_check": {"status": "PASS", "reason": "Dependency found"},
        },
        {
            "case_id": 2,
            "overall_rating": "Excellent",
            "agent_label": "security-auditor-agent",
            "why": "Detected version drift and flagged the security implications of the outdated pin.",
            "gate_check": {"status": "PASS", "reason": "Version drift + security analysis"},
        },
        {
            "case_id": 3,
            "overall_rating": "Excellent",
            "agent_label": "security-auditor-agent",
            "why": "Complete CVE scan with CVSS scores and exploit availability assessment. Added OWASP dependency-check recommendation.",
            "gate_check": {"status": "PASS", "reason": "Thorough CVE analysis"},
        },
        {
            "case_id": 4,
            "overall_rating": "Acceptable",
            "agent_label": "security-auditor-agent",
            "why": "Found CI config but didn't evaluate CI pipeline security (secrets handling, workflow permissions).",
            "gate_check": {"status": "PASS", "reason": "CI found"},
        },
        {
            "case_id": 5,
            "overall_rating": "Strong",
            "agent_label": "security-auditor-agent",
            "why": "Identified linter conflicts and additionally flagged that neither config enforces bandit or safety checks.",
            "gate_check": {"status": "PASS", "reason": "Linter conflicts + security gap"},
        },
        {
            "case_id": 6,
            "overall_rating": "Weak",
            "agent_label": "security-auditor-agent",
            "why": "Suggested types-boto3 but gave no security rationale. Missed opportunity to discuss typed security boundaries.",
            "gate_check": {"status": "PASS", "reason": "Basic type suggestion"},
        },
        {
            "case_id": 7,
            "overall_rating": "Strong",
            "agent_label": "security-auditor-agent",
            "why": "Audited licenses and cross-referenced against known license compatibility issues. Cited SPDX identifiers.",
            "gate_check": {"status": "PASS", "reason": "License audit with SPDX"},
        },
        {
            "case_id": 8,
            "overall_rating": "Strong",
            "agent_label": "security-auditor-agent",
            "why": "Found the circular import and noted it can mask security-relevant import order attacks.",
            "gate_check": {"status": "PASS", "reason": "Circular import + security note"},
        },
        {
            "case_id": 9,
            "overall_rating": "Strong",
            "agent_label": "security-auditor-agent",
            "why": "Verified base image freshness AND checked for known vulnerabilities in python:3.11-slim via Docker Scout.",
            "gate_check": {"status": "PASS", "reason": "Base image + vuln check"},
        },
        {
            "case_id": 10,
            "overall_rating": "Fail",
            "agent_label": "security-auditor-agent",
            "why": "Response was empty after 3 retries. Gate check failure.",
            "gate_check": {
                "status": "FAIL",
                "reason": "No output produced after maximum retries",
            },
        },
    ]
    snapshot.judgments = existing_judgments + extra_judgments

    results = dict(snapshot.results)
    results["security-auditor-agent"] = [
        {
            "case_id": 1,
            "final_output": (
                "Missing dependency: click. Recommendation: add 'click>=8.1' to pyproject.toml. "
                "Note: click versions before 8.1 had CVE-2021-29510 — ensure minimum version."
            ),
        },
        {
            "case_id": 2,
            "final_output": (
                "Version drift: requests 2.28.0 -> 2.31.0. Security impact: 2.28.0 has known "
                "CVE-2023-32681. Upgrade is necessary, not optional. Pin to >=2.31.0."
            ),
        },
        {
            "case_id": 3,
            "final_output": (
                "CVE Scan Results:\n"
                "CRITICAL: none    HIGH: 0    MEDIUM: 2    LOW: 1\n"
                "CVE-2023-45803 (urllib3, CVSS 6.5) — proxy-authorization header leak\n"
                "CVE-2023-37920 (certifi, CVSS 5.3) — root certificate removal\n"
                "Recommend: add OWASP Dependency-Check to CI pipeline."
            ),
        },
    ]
    snapshot.results = results

    extra_policy_blocks = list(snapshot.policy_blocks)
    extra_policy_blocks.append(
        {"case_id": 1, "message": "Content policy triggered on CVE-2021-29510 details"}
    )
    snapshot.policy_blocks = extra_policy_blocks

    return snapshot


# ── colourisation ────────────────────────────────────────────────────────────

_RATING_COLOUR_MAP = {
    "Excellent": "GREEN",
    "Strong": "BLUE",
    "Acceptable": "YELLOW",
    "Weak": "ORANGE",
    "Fail": "RED",
}


def _colourise_line(
    line: str, theme: dict[str, tuple[int, int, int]]
) -> list[tuple[str, tuple[int, int, int]]]:
    """Regex-based colourisation for progress bars, ratings, status keywords."""
    FG = theme["FG"]
    FG_DIM = theme["FG_DIM"]
    GREEN = theme["GREEN"]
    BLUE = theme["BLUE"]
    YELLOW = theme["YELLOW"]
    ORANGE = theme["ORANGE"]
    RED = theme["RED"]

    rating_colours = {
        "Excellent": GREEN,
        "Strong": BLUE,
        "Acceptable": YELLOW,
        "Weak": ORANGE,
        "Fail": RED,
    }

    # Progress bar: [####---]
    m = re.match(r"(Progress\s+\[)(#+)(-*)(\].*)", line)
    if m:
        parts: list[tuple[str, tuple[int, int, int]]] = []
        parts.append((m.group(1), FG))
        parts.append((m.group(2), GREEN))
        parts.append((m.group(3), FG_DIM))
        parts.append((m.group(4), FG))
        return parts

    # BLOCKED keyword
    if "BLOCKED" in line and not _inside_quotes(line, "BLOCKED"):
        idx = line.index("BLOCKED")
        return [
            (line[:idx], FG),
            ("BLOCKED", RED),
            (line[idx + 7 :], FG),
        ]

    # PENDING keyword
    if "PENDING" in line and not _inside_quotes(line, "PENDING"):
        idx = line.index("PENDING")
        return [
            (line[:idx], FG),
            ("PENDING", FG_DIM),
            (line[idx + 7 :], FG),
        ]

    # Rating keywords
    for rating, colour in rating_colours.items():
        if rating in line and not _inside_quotes(line, rating):
            idx = line.index(rating)
            return [
                (line[:idx], FG),
                (rating, colour),
                (line[idx + len(rating) :], FG),
            ]

    return [(line, FG)]


def _inside_quotes(line: str, keyword: str) -> bool:
    idx = line.index(keyword)
    before = line[:idx]
    return before.count('"') % 2 == 1 or before.count("'") % 2 == 1


# ── rendering ───────────────────────────────────────────────────────────────


def _render_tab_bar(
    draw: Any,
    bold_font: Any,
    img_w: int,
    tab_bar_h: int,
    char_h: int,
    active_idx: int,
    theme: dict[str, tuple[int, int, int]],
    tab_names: list[str] | None = None,
) -> None:
    if tab_names is None:
        tab_names = ["1:Overview", "2:Cases", "3:Detail", "4:Help", "5:Compare"]
    TAB_ACTIVE = theme["TAB_ACTIVE"]
    TAB_INACTIVE = theme["TAB_INACTIVE"]
    FG_BRIGHT = theme["FG_BRIGHT"]
    FG_DIM = theme["FG_DIM"]
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
    draw: Any,
    font: Any,
    img_w: int,
    footer_y: int,
    footer_h: int,
    char_h: int,
    theme: dict[str, tuple[int, int, int]],
) -> None:
    HEADER_BG = theme["HEADER_BG"]
    FG_DIM = theme["FG_DIM"]
    draw.rectangle([(0, footer_y), (img_w, footer_y + footer_h)], fill=HEADER_BG)
    footer_text = "h/l tabs  j/k move  Enter detail  e export  r reload  q quit"
    fw = draw.textlength(footer_text, font=font)
    draw.text(
        ((img_w - fw) / 2, footer_y + (footer_h - char_h) / 2),
        footer_text,
        fill=FG_DIM,
        font=font,
    )


def _render_label(
    draw: Any,
    font: Any,
    img_w: int,
    label_y: int,
    label: str,
    theme: dict[str, tuple[int, int, int]],
) -> None:
    LABEL = theme["LABEL"]
    draw.text((16, label_y), label, fill=LABEL, font=font)


def _add_watermark(img: Any, text: str, theme: dict[str, tuple[int, int, int]]) -> None:
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    try:
        wm_font = _load_font(_find_font(), max(9, int(img.height * 0.012)))
    except Exception:
        return
    tw = draw.textlength(text, font=wm_font) if hasattr(draw, "textlength") else len(text) * 6
    x = img.width - tw - 12
    y = img.height - 28
    draw.text((x, y), text, fill=theme["FG_DIM"], font=wm_font)


def _embed_metadata(
    img: Any, width_cols: int, font_size: int, theme_name: str, snapshot_source: str
) -> None:
    meta = {
        "generator": f"BenchDeck/{_benchdeck_version()}",
        "git_sha": _git_sha(),
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "width_cols": width_cols,
        "font_size": font_size,
        "theme": theme_name,
        "snapshot_source": snapshot_source,
    }
    img.info["benchdeck"] = json.dumps(meta)


def _render_to_png(
    lines: list[str],
    out_dir: Path,
    spec: dict[str, Any],
    font: Any,
    bold_font: Any,
    font_size: int,
    width_cols: int,
    theme: dict[str, tuple[int, int, int]],
    theme_name: str = "dark",
    snapshot_source: str = "synthetic",
    watermark_text: str | None = None,
) -> Path:
    from PIL import Image, ImageDraw

    BG = theme["BG"]

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

    tab_names = spec.get("tab_names")
    _render_tab_bar(draw, bold_font, img_w, tab_bar_h, char_h, spec["tab"], theme, tab_names)

    label_y = tab_bar_h + int(font_size * 0.5)
    _render_label(draw, font, img_w, label_y, spec["label"], theme)

    y = label_y + char_h + py
    for line in lines:
        parts = _colourise_line(line, theme)
        cx = px_x
        for text, colour in parts:
            draw.text((cx, y), text, fill=colour, font=font)
            tw = draw.textlength(text, font=font)
            cx += tw
        y += char_h

    _render_footer(draw, font, img_w, y, footer_h, char_h, theme)

    _embed_metadata(img, width_cols, font_size, theme_name, snapshot_source)

    if watermark_text:
        _add_watermark(img, watermark_text, theme)

    png_path = out_dir / f"{spec['name']}.png"
    img.save(png_path, "PNG")
    return png_path


def _render_to_webp(
    lines: list[str],
    out_dir: Path,
    spec: dict[str, Any],
    font: Any,
    bold_font: Any,
    font_size: int,
    width_cols: int,
    theme: dict[str, tuple[int, int, int]],
    theme_name: str = "dark",
    snapshot_source: str = "synthetic",
    watermark_text: str | None = None,
    quality: int = 85,
) -> Path:
    from PIL import Image, ImageDraw

    BG = theme["BG"]
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

    tab_names = spec.get("tab_names")
    _render_tab_bar(draw, bold_font, img_w, tab_bar_h, char_h, spec["tab"], theme, tab_names)

    label_y = tab_bar_h + int(font_size * 0.5)
    _render_label(draw, font, img_w, label_y, spec["label"], theme)

    y = label_y + char_h + py
    for line in lines:
        parts = _colourise_line(line, theme)
        cx = px_x
        for text, colour in parts:
            draw.text((cx, y), text, fill=colour, font=font)
            tw = draw.textlength(text, font=font)
            cx += tw
        y += char_h

    _render_footer(draw, font, img_w, y, footer_h, char_h, theme)
    _embed_metadata(img, width_cols, font_size, theme_name, snapshot_source)

    if watermark_text:
        _add_watermark(img, watermark_text, theme)

    webp_path = out_dir / f"{spec['name']}.webp"
    img.save(webp_path, "WEBP", quality=quality)
    return webp_path


def _render_to_svg(
    lines: list[str],
    out_dir: Path,
    spec: dict[str, Any],
    font_family: str,
    font_size: int,
    width_cols: int,
    theme: dict[str, tuple[int, int, int]],
    theme_name: str = "dark",
    snapshot_source: str = "synthetic",
) -> Path:
    char_w = int(font_size * 0.6)
    char_h = int(font_size * 1.35)
    px_x = int(font_size * 0.9)
    py = int(font_size * 0.7)
    tab_bar_h = char_h + int(font_size * 0.8)
    footer_h = char_h + int(font_size * 0.6)
    label_y = tab_bar_h + int(font_size * 0.5)

    img_w = width_cols * char_w + px_x * 2
    content_h = len(lines) * char_h
    img_h = content_h + py * 2 + tab_bar_h + footer_h

    def _rgb(rgb_tuple: tuple[int, int, int]) -> str:
        return f"rgb({rgb_tuple[0]},{rgb_tuple[1]},{rgb_tuple[2]})"

    def _escape_xml(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{img_w}" height="{img_h}" '
        f'viewBox="0 0 {img_w} {img_h}">',
        "<style>",
        f"  text {{ font-family: '{font_family}', monospace; font-size: {font_size}px; }}",
        "</style>",
        f'<rect width="{img_w}" height="{img_h}" fill="{_rgb(theme["BG"])}"/>',
    ]

    # tab bar
    tab_names = spec.get("tab_names") or ["Overview", "Cases", "Detail", "Help"]
    tab_w = img_w / len(tab_names)
    for i, tname in enumerate(tab_names):
        x0 = int(i * tab_w)
        fill_col = theme["TAB_ACTIVE"] if i == spec["tab"] else theme["TAB_INACTIVE"]
        text_col = theme["FG_BRIGHT"] if i == spec["tab"] else theme["FG_DIM"]
        svg_lines.append(
            f'<rect x="{x0}" y="0" width="{int(tab_w)}" height="{tab_bar_h}" '
            f'fill="{_rgb(fill_col)}"/>'
        )
        svg_lines.append(
            f'<text x="{x0 + tab_w / 2}" y="{(tab_bar_h + char_h) / 2 - 3}" '
            f'text-anchor="middle" fill="{_rgb(text_col)}">{_escape_xml(tname)}</text>'
        )

    # label
    svg_lines.append(
        f'<text x="16" y="{label_y + font_size}" '
        f'fill="{_rgb(theme["LABEL"])}">{_escape_xml(spec["label"])}</text>'
    )

    # content
    y = label_y + char_h + py + font_size
    for line in lines:
        parts = _colourise_line(line, theme)
        cx = px_x
        for text, colour in parts:
            esc_text = _escape_xml(text)
            svg_lines.append(f'<text x="{cx}" y="{y}" fill="{_rgb(colour)}">{esc_text}</text>')
            cx += len(text) * char_w
        y += char_h

    # footer
    foot_y = y
    svg_lines.append(
        f'<rect x="0" y="{foot_y}" width="{img_w}" height="{footer_h}" '
        f'fill="{_rgb(theme["HEADER_BG"])}"/>'
    )
    footer_text = "h/l tabs  j/k move  Enter detail  e export  r reload  q quit"
    svg_lines.append(
        f'<text x="{img_w / 2}" y="{foot_y + (footer_h + char_h) / 2 - 3}" '
        f'text-anchor="middle" fill="{_rgb(theme["FG_DIM"])}">{_escape_xml(footer_text)}</text>'
    )

    # metadata comment
    svg_lines.append(
        f"<!-- generator: BenchDeck/{_benchdeck_version()} git: {_git_sha()} "
        f"timestamp: {datetime.datetime.now(datetime.UTC).isoformat()} "
        f"width: {width_cols} theme: {theme_name} source: {snapshot_source} -->"
    )

    svg_lines.append("</svg>")

    svg_path = out_dir / f"{spec['name']}.svg"
    svg_path.write_text("\n".join(svg_lines) + "\n", encoding="utf-8")
    return svg_path


# ── screen specs ─────────────────────────────────────────────────────────────

SCREEN_SPECS: list[dict[str, Any]] = [
    {
        "tab": 0,
        "name": "overview",
        "label": "Overview - progress bar, rating distribution, per-family scores, policy blocks, usage stats",
        "selected": 0,
    },
    {
        "tab": 1,
        "name": "cases",
        "label": "Case list - all cases with per-agent ratings, blocked cases, pending items",
        "selected": 0,
    },
    {
        "tab": 2,
        "name": "detail",
        "label": "Case detail - purpose, judgment (rating, why, gate check), agent output for case 1",
        "selected": 0,
    },
    {
        "tab": 3,
        "name": "help",
        "label": "Help - keyboard controls for phone-friendly SSH navigation",
        "selected": 0,
    },
]

DUAL_AGENT_SCREEN_SPECS: list[dict[str, Any]] = [
    {
        "tab": 0,
        "name": "overview",
        "label": "Overview - dual-agent progress bar, per-agent rating distribution, per-family scores, policy blocks",
        "selected": 0,
    },
    {
        "tab": 1,
        "name": "cases",
        "label": "Case list - all cases with per-agent ratings (A/B inline), blocked cases, pending items",
        "selected": 0,
    },
    {
        "tab": 2,
        "name": "detail",
        "label": "Case detail - purpose, dual-agent judgments, gate checks, agent outputs for case 1",
        "selected": 0,
    },
    {
        "tab": 3,
        "name": "help",
        "label": "Help - keyboard controls for phone-friendly SSH navigation",
        "selected": 0,
    },
    {
        "tab": 4,
        "name": "compare",
        "label": "Agent comparison - side-by-side ratings heatmap, per-family score delta, gate failure counts",
        "selected": 0,
        "tab_names": ["1:Overview", "2:Cases", "3:Detail", "4:Help", "5:Compare"],
    },
]


def _add_compare_tab(tui: BenchDeckTUI, width: int) -> list[str]:
    tally = tui.snapshot.tally
    agents = sorted(tally.keys()) if isinstance(tally, dict) and tally else []
    if len(agents) < 2:
        return ["Compare tab requires at least two agents in tally data."]

    lines = ["Agent Comparison (dual-agent view)"]
    lines.append("")
    lines.append(f"{'Family':<24} {'A':>6} {'B':>6} {'Delta':>7}")
    lines.append("-" * 47)

    a_label = agents[0]
    b_label = agents[1] if len(agents) > 1 else agents[0]
    a_data = tally.get(a_label, {})
    b_data = tally.get(b_label, {})

    all_families: set[str] = set()
    for agent_data in (a_data, b_data):
        fs = agent_data.get("family_scores") or {}
        all_families.update(fs.keys())

    for family in sorted(all_families):
        a_score = (a_data.get("family_scores") or {}).get(family)
        b_score = (b_data.get("family_scores") or {}).get(family)
        a_str = f"{a_score:.1f}" if isinstance(a_score, (int, float)) else "N/A"
        b_str = f"{b_score:.1f}" if isinstance(b_score, (int, float)) else "N/A"
        if isinstance(a_score, (int, float)) and isinstance(b_score, (int, float)):
            delta = a_score - b_score
            delta_str = f"{delta:+.1f}"
        else:
            delta_str = "N/A"
        lines.append(f"  {family:<22} {a_str:>6} {b_str:>6} {delta_str:>7}")

    lines.append("")
    lines.append(f"{'Rating':<12} {'A':>6} {'B':>6}")
    lines.append("-" * 28)
    for rating in ("Excellent", "Strong", "Acceptable", "Weak", "Fail"):
        a_count = (a_data.get("rating_counts") or {}).get(rating, 0)
        b_count = (b_data.get("rating_counts") or {}).get(rating, 0)
        lines.append(f"  {rating:<10} {a_count:>6} {b_count:>6}")

    lines.append("")
    gate_a = a_data.get("gate_failures", 0)
    gate_b = b_data.get("gate_failures", 0)
    lines.append(f"Gate failures:  A: {gate_a}  B: {gate_b}")

    return lines


# ── interactive mode ────────────────────────────────────────────────────────


def _interactive_mode(
    tui: BenchDeckTUI,
    args: argparse.Namespace,
    font: Any,
    bold_font: Any,
    theme: dict[str, tuple[int, int, int]],
    theme_name: str,
    snapshot_source: str,
) -> None:
    print("Interactive screenshot mode")
    print("  Commands: 1-5 tabs, j/k select, Enter screenshot, q quit")
    print()

    specs = DUAL_AGENT_SCREEN_SPECS if args.dual else SCREEN_SPECS
    tab_count = len(specs)
    width = args.w

    while True:
        tui.tab = min(tui.tab, tab_count - 1)
        if tui.tab == 4 and not args.dual:
            tui.tab = 0

        lines = _add_compare_tab(tui, width) if tui.tab == 4 else tui._render(width)

        spec = specs[tui.tab]
        print(f"\n--- Tab {tui.tab + 1}: {spec['name']} (selected={tui.selected}) ---")
        for ln in lines[:12]:
            print(f"  {ln}")
        if len(lines) > 12:
            print(f"  ... ({len(lines) - 12} more lines)")

        cmd = input("\n> ").strip().lower()

        if cmd in ("q", "quit", "exit"):
            break
        if cmd in ("1", "2", "3", "4", "5"):
            tab_idx = int(cmd) - 1
            if tab_idx < tab_count:
                tui.tab = tab_idx
        elif cmd in ("j", "down"):
            tui.selected = min(tui.selected + 1, len(tui._cases()) - 1)
        elif cmd in ("k", "up"):
            tui.selected = max(0, tui.selected - 1)
        elif cmd in ("", "enter", "s"):
            lines = _add_compare_tab(tui, width) if tui.tab == 4 else tui._render(width)
            out_dir = Path(args.o)
            out_dir.mkdir(parents=True, exist_ok=True)
            s = specs[tui.tab]
            fmt = args.format
            if fmt == "svg":
                _render_to_svg(
                    lines,
                    out_dir,
                    s,
                    "monospace",
                    args.font_size,
                    width,
                    theme,
                    theme_name,
                    snapshot_source,
                )
            elif fmt == "webp":
                _render_to_webp(
                    lines,
                    out_dir,
                    s,
                    font,
                    bold_font,
                    args.font_size,
                    width,
                    theme,
                    theme_name,
                    snapshot_source,
                )
            else:
                _render_to_png(
                    lines,
                    out_dir,
                    s,
                    font,
                    bold_font,
                    args.font_size,
                    width,
                    theme,
                    theme_name,
                    snapshot_source,
                )
            print(f"  -> saved {s['name']}.{fmt}")
        elif cmd == "h":
            print("  1-5: tab  j/k: select  Enter: screenshot  q: quit  h: help")


# ── main ────────────────────────────────────────────────────────────────────


def generate_screenshots(
    snapshot: Snapshot,
    out_dir: Path,
    specs: list[dict[str, Any]] | None = None,
    width_cols: int = 80,
    widths: list[int] | None = None,
    font_size: int = 15,
    font_path: str | None = None,
    fmt: str = "png",
    theme_name: str = "dark",
    theme: dict[str, tuple[int, int, int]] | None = None,
    snapshot_source: str = "synthetic",
    watermark: bool = False,
    dual: bool = False,
) -> list[Path]:
    """Programmatic API for generating TUI screenshots.

    Returns a list of Path objects for all generated files.
    """
    if theme is None:
        theme = _resolve_theme(theme_name)

    resolved_font_path = _find_font(font_path)
    font = _load_font(resolved_font_path, font_size)
    bold_font = _load_font(resolved_font_path, font_size)

    tui = BenchDeckTUI(Path("/tmp/benchdeck-screenshots"))
    tui.snapshot = snapshot

    out_dir.mkdir(parents=True, exist_ok=True)

    if specs is None:
        specs = DUAL_AGENT_SCREEN_SPECS if dual else SCREEN_SPECS

    wm_text = (
        f"BenchDeck v{_benchdeck_version()}  {snapshot_source}  {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d')}"
        if watermark
        else None
    )

    actual_widths = widths if widths else [width_cols]
    saved: list[Path] = []

    for w in actual_widths:
        for spec in specs:
            tui.tab = spec["tab"]
            tui.selected = spec.get("selected", 0)

            lines = _add_compare_tab(tui, w) if spec["tab"] == 4 and dual else tui._render(w)

            w_suffix = f"-w{w}" if len(actual_widths) > 1 else ""
            name = spec["name"]

            if fmt == "svg":
                path = _render_to_svg(
                    lines,
                    out_dir,
                    spec,
                    "monospace",
                    font_size,
                    w,
                    theme,
                    theme_name,
                    snapshot_source,
                )
                if w_suffix:
                    new_path = out_dir / f"{name}{w_suffix}.svg"
                    path.rename(new_path)
                    path = new_path
            elif fmt == "webp":
                path = _render_to_webp(
                    lines,
                    out_dir,
                    spec,
                    font,
                    bold_font,
                    font_size,
                    w,
                    theme,
                    theme_name,
                    snapshot_source,
                    wm_text,
                )
                if w_suffix:
                    new_path = out_dir / f"{name}{w_suffix}.webp"
                    path.rename(new_path)
                    path = new_path
            elif fmt == "all":
                path_png = _render_to_png(
                    lines,
                    out_dir,
                    spec,
                    font,
                    bold_font,
                    font_size,
                    w,
                    theme,
                    theme_name,
                    snapshot_source,
                    wm_text,
                )
                if w_suffix:
                    new_path = out_dir / f"{name}{w_suffix}.png"
                    path_png.rename(new_path)
                    path_png = new_path
                path_webp = _render_to_webp(
                    lines,
                    out_dir,
                    spec,
                    font,
                    bold_font,
                    font_size,
                    w,
                    theme,
                    theme_name,
                    snapshot_source,
                    wm_text,
                )
                if w_suffix:
                    new_path = out_dir / f"{name}{w_suffix}.webp"
                    path_webp.rename(new_path)
                    path_webp = new_path
                path_svg = _render_to_svg(
                    lines,
                    out_dir,
                    spec,
                    "monospace",
                    font_size,
                    w,
                    theme,
                    theme_name,
                    snapshot_source,
                )
                if w_suffix:
                    new_path = out_dir / f"{name}{w_suffix}.svg"
                    path_svg.rename(new_path)
                    path_svg = new_path
                saved.extend([path_png, path_webp])
                path = path_svg
            else:
                path = _render_to_png(
                    lines,
                    out_dir,
                    spec,
                    font,
                    bold_font,
                    font_size,
                    w,
                    theme,
                    theme_name,
                    snapshot_source,
                    wm_text,
                )
                if w_suffix:
                    new_path = out_dir / f"{name}{w_suffix}.png"
                    path.rename(new_path)
                    path = new_path

            saved.append(path)
            print(f"  {path.name}")

    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TUI screenshots for BenchDeck")
    parser.add_argument(
        "-o", type=Path, default=Path("assets/screenshots"), help="Output directory"
    )
    parser.add_argument("-w", type=int, default=80, help="Terminal width (columns)")
    parser.add_argument(
        "--widths",
        type=str,
        default=None,
        help="Comma-separated widths for multi-resolution export (e.g. 40,60,80)",
    )
    parser.add_argument("--font-size", type=int, default=15, help="Font size in points")
    parser.add_argument("--font-path", type=str, default=None, help="Path to monospace TTF font")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Path to a real benchmark run directory for live-data screenshots",
    )
    parser.add_argument(
        "--run-zip",
        type=Path,
        default=None,
        help="Path to a benchmark run ZIP file for live-data screenshots",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="png",
        choices=["png", "webp", "svg", "all"],
        help="Output format (default: png)",
    )
    parser.add_argument(
        "--theme",
        type=str,
        default="dark",
        choices=["dark", "light", "github"],
        help="Colour theme (default: dark)",
    )
    parser.add_argument(
        "--theme-file",
        type=str,
        default=None,
        help="Path to a custom JSON theme file",
    )
    parser.add_argument(
        "--dual",
        action="store_true",
        default=False,
        help="Generate dual-agent comparison screenshots (with compare tab)",
    )
    parser.add_argument(
        "--watermark",
        action="store_true",
        default=False,
        help="Add version/source watermark to images",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        default=False,
        help="Open generated images in system viewer",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        default=False,
        help="Launch interactive screenshot selector",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=85,
        help="WebP quality (1-100, default: 85)",
    )
    args = parser.parse_args()

    # ensure Pillow is installed
    try:
        import PIL.Image  # noqa: F401
    except ImportError:
        print(
            "Pillow is required for screenshot generation. Install it with:\n"
            "  pip install Pillow>=9.0.0\n"
            "or:\n"
            "  pip install -e '.[screenshots]'",
            file=sys.stderr,
        )
        sys.exit(1)

    font_path = _find_font(args.font_path)
    font = _load_font(font_path, args.font_size)
    bold_font = _load_font(font_path, args.font_size)

    theme = _resolve_theme(args.theme, args.theme_file)

    # load snapshot
    if args.run_dir:
        snapshot_source = f"run-dir:{args.run_dir.name}"
        snapshot = load_snapshot(args.run_dir)
    elif args.run_zip:
        snapshot_source = f"run-zip:{args.run_zip.name}"
        snapshot = load_snapshot(args.run_zip)
    elif args.dual:
        snapshot_source = "synthetic-dual-agent"
        snapshot = _build_dual_agent_demo_snapshot()
    else:
        snapshot_source = "synthetic"
        snapshot = _build_demo_snapshot()

    tui = BenchDeckTUI(Path("/tmp/benchdeck-screenshots"))
    tui.snapshot = snapshot

    out_dir: Path = args.o
    out_dir.mkdir(parents=True, exist_ok=True)

    # interactive mode
    if args.interactive:
        _interactive_mode(tui, args, font, bold_font, theme, args.theme, snapshot_source)
        return

    # parse widths
    if args.widths:
        widths: list[int] | None = [int(w.strip()) for w in args.widths.split(",") if w.strip()]
    else:
        widths = None

    specs = DUAL_AGENT_SCREEN_SPECS if args.dual else SCREEN_SPECS

    saved = generate_screenshots(
        snapshot=snapshot,
        out_dir=out_dir,
        specs=specs,
        width_cols=args.w,
        widths=widths,
        font_size=args.font_size,
        font_path=args.font_path,
        fmt=args.format,
        theme_name=args.theme,
        theme=theme,
        snapshot_source=snapshot_source,
        watermark=args.watermark,
        dual=args.dual,
    )

    # show
    if args.show and saved:
        _show_images(saved)


def _show_images(paths: list[Path]) -> None:
    for p in paths:
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            elif sys.platform == "win32":
                os.startfile(str(p))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except OSError:
            print(f"Could not open {p.name}")


if __name__ == "__main__":
    main()
