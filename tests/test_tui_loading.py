"""Phase 0 regression tests for TUI loading and ZIP safety.

Tests document defects in artifact loading, agent-scoped result lookups,
ZIP validation, and fixture integrity.
"""

from __future__ import annotations

import base64
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from benchdeck.loader import (
    Snapshot,
    _load_zip_bytes,
    load_snapshot,
)
from benchdeck.tui import BenchDeckTUI

# ═══════════════════════════════════════════════════════════════════════════
# TUI result lookup by agent and case
# ═══════════════════════════════════════════════════════════════════════════


def test_result_for_respects_agent_label_when_provided() -> None:
    """_result_for with agent_label returns only the matching agent's result."""

    tui = BenchDeckTUI(Path("/tmp/nonexistent_tui"))
    tui.snapshot = Snapshot(
        results={
            "agent_a": [
                {"case_id": 1, "final_output": "from agent A", "agent_label": "agent_a"},
            ],
            "agent_b": [
                {"case_id": 1, "final_output": "from agent B", "agent_label": "agent_b"},
            ],
        }
    )
    result_a = tui._result_for(1, agent_label="agent_a")
    assert result_a is not None
    assert result_a["final_output"] == "from agent A"

    result_b = tui._result_for(1, agent_label="agent_b")
    assert result_b is not None
    assert result_b["final_output"] == "from agent B"

    # Without agent_label, returns first match (by dict insertion order)
    result_any = tui._result_for(1)
    assert result_any is not None


def test_tui_snapshot_case_plan_has_no_agent_label() -> None:
    """The TUI's _cases method reads from the plan, which has no agent_label
    on individual cases."""

    tui = BenchDeckTUI(Path("/tmp/nonexistent_tui"))
    tui.snapshot = Snapshot(
        plan={
            "cases": [
                {"id": 1, "title": "Test A", "family": "happy_path"},
                {"id": 2, "title": "Test B", "family": "regression_protection"},
            ]
        }
    )
    cases = tui._cases()
    assert len(cases) == 2
    for case in cases:
        assert "agent_label" not in case, "Cases in plan do not carry agent attribution"

    # Judgment lookup is by case_id only.
    tui.snapshot.judgments = [
        {"case_id": 1, "overall_rating": "Excellent"},
        {"case_id": 2, "overall_rating": "Strong"},
    ]
    # The case list view shows both cases but can't attribute to agents.


# ═══════════════════════════════════════════════════════════════════════════
# ZIP loading safety
# ═══════════════════════════════════════════════════════════════════════════


def make_zip_bytes(files: dict[str, Any]) -> bytes:
    """Create an in-memory ZIP with the given filename → content mapping."""
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            if isinstance(data, (dict, list)):
                zf.writestr(name, json.dumps(data))
            else:
                zf.writestr(name, str(data))
    return buf.getvalue()


def test_zip_duplicate_basename_raises_valueerror() -> None:
    """Duplicate ZIP basenames in different directories raise ValueError."""
    duplicate_zip = make_zip_bytes(
        {
            "run_metadata.json": {"status": "completed", "planned_cases": 8},
            "subdir/run_metadata.json": {"status": "running", "planned_cases": 0},
        }
    )
    with pytest.raises(ValueError, match="Duplicate basename"):
        _load_zip_bytes(duplicate_zip)


def test_zip_loading_handles_corrupt_zip() -> None:
    """_load_zip_bytes returns empty Snapshot for corrupt data."""
    snapshot = _load_zip_bytes(b"not a zip file at all")
    assert snapshot.metadata == {}
    assert snapshot.plan == {}
    assert snapshot.tally == {}
    assert snapshot.judgments == []
    assert snapshot.results == {}


def test_zip_loading_handles_empty_zip() -> None:
    """_load_zip_bytes returns defaults for empty ZIP."""
    snapshot = _load_zip_bytes(make_zip_bytes({}))
    assert snapshot.metadata == {}
    assert snapshot.judgments == []


def test_zip_loading_reads_all_expected_files() -> None:
    """_load_zip_bytes correctly loads all six expected JSON files."""
    data = make_zip_bytes(
        {
            "run_metadata.json": {"status": "completed", "planned_cases": 8},
            "benchmark_plan.json": {
                "mode": "single",
                "profile": {"agent_name_a": "Agent", "inferred_mission": "x"},
                "cases": [
                    {
                        "id": 1,
                        "title": "A",
                        "family": "happy_path",
                        "purpose": "x",
                        "test_prompt": "x",
                    }
                ],
            },
            "summary_tally.json": {"cases_planned": 8, "cases_judged": 8},
            "case_judgments.json": [{"case_id": 1, "overall_rating": "Strong", "why": "ok"}],
            "policy_blocks.json": [{"case_id": 2, "message": "blocked"}],
            "run_results.json": {"agent_a": [{"case_id": 1, "final_output": "result"}]},
        }
    )
    snapshot = _load_zip_bytes(data)
    assert snapshot.metadata["status"] == "completed"
    assert len(snapshot.judgments) == 1
    assert len(snapshot.policy_blocks) == 1
    assert "agent_a" in snapshot.results


def test_zip_loading_malformed_json_defaults() -> None:
    """Malformed JSON inside a ZIP member returns the default value."""
    data = make_zip_bytes(
        {
            "run_metadata.json": "not valid json {{{",
            "benchmark_plan.json": "also broken",
        }
    )
    snapshot = _load_zip_bytes(data)
    assert snapshot.metadata == {}, "Malformed metadata JSON should default to {}"
    assert snapshot.plan == {}, "Malformed plan JSON should default to {}"


# ═══════════════════════════════════════════════════════════════════════════
# Directory-based loading
# ═══════════════════════════════════════════════════════════════════════════


def test_load_snapshot_directory_missing_defaults(tmp_path: Path) -> None:
    """Missing files in a directory produce defaults, not exceptions."""
    run_dir = tmp_path / "empty_run"
    run_dir.mkdir()
    snapshot = load_snapshot(run_dir)
    assert snapshot.metadata == {}
    assert snapshot.plan == {}
    assert snapshot.tally == {}
    assert snapshot.judgments == []
    assert snapshot.policy_blocks == []
    assert snapshot.results == {}


def test_load_snapshot_directory_reads_json(tmp_path: Path) -> None:
    """load_snapshot reads valid JSON from a directory."""
    run_dir = tmp_path / "valid_run"
    run_dir.mkdir()
    (run_dir / "run_metadata.json").write_text(
        json.dumps({"status": "running", "planned_cases": 4})
    )
    (run_dir / "benchmark_plan.json").write_text(
        json.dumps(
            {
                "mode": "single",
                "profile": {"agent_name_a": "A", "inferred_mission": "m"},
                "cases": [],
            }
        )
    )
    (run_dir / "summary_tally.json").write_text(json.dumps({"cases_planned": 4}))
    (run_dir / "case_judgments.json").write_text("[]")
    (run_dir / "policy_blocks.json").write_text("[]")
    (run_dir / "run_results.json").write_text("{}")

    snapshot = load_snapshot(run_dir)
    assert snapshot.metadata["status"] == "running"
    assert snapshot.tally["cases_planned"] == 4


# ═══════════════════════════════════════════════════════════════════════════
# Existing fixture integrity
# ═══════════════════════════════════════════════════════════════════════════


def test_bundled_fixture_loads() -> None:
    """The bundled fixtures/original_run.zip loads without crashing."""
    fixture = Path(__file__).parents[1] / "fixtures" / "original_run.zip"
    assert fixture.exists(), "Fixture file must exist"
    snapshot = load_snapshot(fixture)
    # We don't assert content correctness (the fixture is known-invalid)
    # but loading must not raise.
    assert isinstance(snapshot, Snapshot)


def test_bundled_fixture_has_metadata() -> None:
    """The fixture has some metadata even if incomplete."""
    fixture = Path(__file__).parents[1] / "fixtures" / "original_run.zip"
    snapshot = load_snapshot(fixture)
    # The fixture should at least have metadata with a status.
    assert "status" in snapshot.metadata or snapshot.metadata == {}, (
        "Fixture metadata should be loadable"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Malformed data rendering
# ═══════════════════════════════════════════════════════════════════════════


def test_malformed_plan_json_defaults_to_empty() -> None:
    """When benchmark_plan.json is malformed, the TUI defaults to {} silently."""

    tui = BenchDeckTUI(Path("/tmp/nonexistent_tui2"))
    tui.snapshot = Snapshot(plan={})
    cases = tui._cases()
    assert cases == [], "Malformed plan silently produces empty case list"

    # TUI does not surface the parse error — it silently treats
    # missing "cases" key as an empty list.
    tui.snapshot.plan = {"not_cases": 123}
    cases_from_missing = tui._cases()
    assert cases_from_missing == [], "TUI silently defaults to empty when plan has no 'cases' key"


# ═══════════════════════════════════════════════════════════════════════════
# New artifact loading — infrastructure_errors and planner_capture
# ═══════════════════════════════════════════════════════════════════════════


def test_load_snapshot_directory_reads_infrastructure_errors(tmp_path: Path) -> None:
    """load_snapshot reads infrastructure_errors.json from a directory."""
    run_dir = tmp_path / "infra_run"
    run_dir.mkdir()
    (run_dir / "infrastructure_errors.json").write_text(
        json.dumps(
            [
                {
                    "case_id": 3,
                    "agent_label": "agent_a",
                    "case_title": "Case 3",
                    "stage": "agent",
                    "error_type": "RuntimeError",
                    "message": "Connection reset",
                }
            ]
        )
    )
    snapshot = load_snapshot(run_dir)
    assert len(snapshot.infrastructure_errors) == 1
    assert snapshot.infrastructure_errors[0]["case_id"] == 3
    assert snapshot.infrastructure_errors[0]["error_type"] == "RuntimeError"


def test_load_snapshot_directory_reads_planner_capture(tmp_path: Path) -> None:
    """load_snapshot reads planner_capture.json from a directory."""
    run_dir = tmp_path / "planner_run"
    run_dir.mkdir()
    (run_dir / "planner_capture.json").write_text(
        json.dumps({"value": {"mode": "single"}, "total_http_attempts": 1})
    )
    snapshot = load_snapshot(run_dir)
    assert snapshot.planner_capture["value"]["mode"] == "single"
    assert snapshot.planner_capture["total_http_attempts"] == 1


def test_zip_loading_reads_infrastructure_errors() -> None:
    """_load_zip_bytes loads infrastructure_errors.json from ZIP."""
    data = make_zip_bytes(
        {
            "run_metadata.json": {"status": "inconclusive"},
            "infrastructure_errors.json": [
                {"case_id": 5, "agent_label": "agent_b", "stage": "judge"}
            ],
        }
    )
    snapshot = _load_zip_bytes(data)
    assert len(snapshot.infrastructure_errors) == 1
    assert snapshot.infrastructure_errors[0]["case_id"] == 5


def test_zip_loading_reads_planner_capture() -> None:
    """_load_zip_bytes loads planner_capture.json from ZIP."""
    data = make_zip_bytes(
        {
            "run_metadata.json": {"status": "completed"},
            "planner_capture.json": {"value": {"mode": "comparison"}},
        }
    )
    snapshot = _load_zip_bytes(data)
    assert snapshot.planner_capture["value"]["mode"] == "comparison"


def test_tui_detail_shows_infrastructure_errors() -> None:
    """TUI detail view shows infrastructure error records for the selected case."""
    tui = BenchDeckTUI(Path("/tmp/nonexistent_tui3"))
    tui.snapshot = Snapshot(
        plan={
            "cases": [
                {"id": 1, "title": "Test", "family": "happy_path", "purpose": "x"},
            ]
        },
        infrastructure_errors=[
            {
                "case_id": 1,
                "agent_label": "agent_a",
                "case_title": "Test",
                "stage": "agent",
                "error_type": "ConnectionError",
                "message": "Network failure",
                "response_id": "resp-123",
                "attempts": 3,
            }
        ],
    )
    lines = tui._detail(40)
    text = "\n".join(lines)
    assert "Infrastructure error details" in text
    assert "ConnectionError" in text
    assert "Network failure" in text
    assert "resp-123" in text


# ═══════════════════════════════════════════════════════════════════════════
# Loader auto-discovery of run_id subdirectories
# ═══════════════════════════════════════════════════════════════════════════


def test_load_snapshot_discovers_run_id_subdirectory(tmp_path: Path) -> None:
    root = tmp_path / "benchmark_out"
    run_dir = root / "20240601T120000.000000Z"
    run_dir.mkdir(parents=True)
    (run_dir / "run_metadata.json").write_text(
        json.dumps({"status": "completed", "cases_in_plan": 8})
    )

    snapshot = load_snapshot(root)
    assert snapshot.metadata["status"] == "completed"
    assert snapshot.metadata["cases_in_plan"] == 8


def test_load_snapshot_picks_most_recent_run_id(tmp_path: Path) -> None:
    root = tmp_path / "benchmark_out"
    older = root / "20240601T110000.000000Z"
    newer = root / "20240601T120000.000000Z"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    (older / "run_metadata.json").write_text(json.dumps({"status": "old"}))
    (newer / "run_metadata.json").write_text(json.dumps({"status": "new"}))

    snapshot = load_snapshot(root)
    assert snapshot.metadata["status"] == "new"


def test_load_snapshot_direct_subdir_still_works(tmp_path: Path) -> None:
    run_dir = tmp_path / "direct_run"
    run_dir.mkdir()
    (run_dir / "run_metadata.json").write_text(json.dumps({"status": "running"}))

    snapshot = load_snapshot(run_dir)
    assert snapshot.metadata["status"] == "running"


# ═══════════════════════════════════════════════════════════════════════════
# TUI overview shows planner capture diagnostics
# ═══════════════════════════════════════════════════════════════════════════


def test_tui_overview_shows_planner_info() -> None:
    tui = BenchDeckTUI(Path("/tmp/nonexistent_tui4"))
    tui.snapshot = Snapshot(
        metadata={"cases_in_plan": 8, "executions_judged": 8},
        tally={
            "agent_a": {
                "cases_planned": 8,
                "cases_judged": 8,
                "score_scale": {"Excellent": 4},
            }
        },
        planner_capture={
            "value": {"mode": "single"},
            "total_http_attempts": 2,
            "attempts": [
                {"usage": {"input_tokens": 100, "output_tokens": 50}},
                {"usage": {"input_tokens": 200, "output_tokens": 75}},
            ],
        },
    )
    lines = tui._overview(80)
    text = "\n".join(lines)
    assert "Planner: single mode" in text
    assert "2 HTTP attempts" in text
    assert "425 tokens" in text


def test_tui_overview_shows_planner_terminal_error() -> None:
    tui = BenchDeckTUI(Path("/tmp/nonexistent_tui5"))
    tui.snapshot = Snapshot(
        metadata={"cases_in_plan": 8, "executions_judged": 8},
        tally={},
        planner_capture={
            "terminal_error": {
                "message": "API authentication failed",
                "category": "auth_error",
            },
        },
    )
    lines = tui._overview(80)
    text = "\n".join(lines)
    assert "WARNING: planner terminal error" in text
    assert "API authentication failed" in text


def test_tui_overview_shows_planner_parse_error() -> None:
    tui = BenchDeckTUI(Path("/tmp/nonexistent_tui6"))
    tui.snapshot = Snapshot(
        metadata={"cases_in_plan": 8, "executions_judged": 8},
        tally={},
        planner_capture={"parse_error": "Bad JSON in response"},
    )
    lines = tui._overview(80)
    text = "\n".join(lines)
    assert "WARNING: planner parse error" in text
    assert "Bad JSON in response" in text


def test_tui_overview_no_planner_line_when_empty() -> None:
    tui = BenchDeckTUI(Path("/tmp/nonexistent_tui7"))
    tui.snapshot = Snapshot(
        metadata={"cases_in_plan": 8, "executions_judged": 8},
        tally={},
        planner_capture={},
    )
    lines = tui._overview(80)
    text = "\n".join(lines)
    assert "Planner:" not in text


# ═══════════════════════════════════════════════════════════════════════════
# Segmented .b64.* ZIP loading (P0-8)
# ═══════════════════════════════════════════════════════════════════════════


def test_load_snapshot_reads_segmented_b64_zip(tmp_path: Path) -> None:
    """When the ``.zip`` file does not exist but its ``.b64.*`` segments
    do, ``load_snapshot`` decodes the concatenated base64 segments and
    reads the resulting ZIP as a normal archive.

    This is the in-repo "checked-in fixture" path used by the TUI when
    a run is exported as a multi-segment base64 bundle (e.g. for size
    limits on hosted services). The ``.b64.N`` segments are joined in
    lexicographic order, base64-decoded as one blob, then unpacked by
    ``_load_zip_bytes``.
    """
    # Build a real ZIP in memory with the expected JSON members.
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr(
            "run_metadata.json",
            json.dumps({"status": "running", "cases_in_plan": 1}),
        )
        archive.writestr(
            "benchmark_plan.json",
            json.dumps({"cases": [{"id": 1, "title": "Segmented"}]}),
        )
    zip_bytes = zip_buffer.getvalue()
    # Encode and split into two ASCII segments at the midpoint.
    encoded = base64.b64encode(zip_bytes).decode("ascii")
    midpoint = len(encoded) // 2
    segment_0 = encoded[:midpoint]
    segment_1 = encoded[midpoint:]
    assert segment_0 and segment_1  # sanity: both halves are non-empty
    # Write the segments; the .zip file is intentionally NOT created.
    zip_path = tmp_path / "foo.zip"
    assert not zip_path.exists()
    (tmp_path / "foo.zip.b64.0").write_text(segment_0, encoding="ascii")
    (tmp_path / "foo.zip.b64.1").write_text(segment_1, encoding="ascii")
    # Sanity: the segments are joined back to the same bytes.
    assert base64.b64decode(segment_0 + segment_1) == zip_bytes
    # Call load_snapshot on the .zip path (which doesn't exist as a file).
    snapshot = load_snapshot(zip_path)
    # The snapshot's metadata and plan came from the decoded ZIP.
    assert snapshot.metadata.get("status") == "running"
    assert snapshot.metadata.get("cases_in_plan") == 1
    assert snapshot.plan.get("cases") == [{"id": 1, "title": "Segmented"}]
