from pathlib import Path

from benchdeck.inspect import inspect_run
from benchdeck.loader import Snapshot

FIXTURE = Path(__file__).parents[1] / "fixtures" / "original_run.zip"


def test_original_run_defects_are_detected() -> None:
    report = inspect_run(FIXTURE)
    assert report["status"] == "completed"
    assert report["planned_cases"] == 8
    assert report["judged_cases"] == 8
    assert report["policy_blocks"] == 0
    assert len(report["warnings"]) == 0, f"Expected zero warnings, got: {report['warnings']}"


def test_inspect_reports_infrastructure_errors(monkeypatch) -> None:
    snapshot = Snapshot(
        metadata={},
        infrastructure_errors=[
            {
                "case_id": 2,
                "agent_label": "agent_a",
                "case_title": "Case 2",
                "stage": "agent",
                "error_type": "RuntimeError",
                "message": "Connection timed out",
            }
        ],
    )
    monkeypatch.setattr("benchdeck.inspect.load_snapshot", lambda _: snapshot)
    report = inspect_run(Path("/tmp/fake"))
    infra_warnings = [w for w in report["warnings"] if "Infrastructure error" in w]
    assert len(infra_warnings) == 1
    assert "RuntimeError" in infra_warnings[0]
    assert "Connection timed out" in infra_warnings[0]


def test_inspect_planner_terminal_error_warning(monkeypatch) -> None:
    snapshot = Snapshot(
        metadata={},
        planner_capture={
            "terminal_error": {
                "message": "API rate limit exceeded",
                "category": "auth_error",
            },
        },
    )
    monkeypatch.setattr("benchdeck.inspect.load_snapshot", lambda _: snapshot)
    report = inspect_run(Path("/tmp/fake"))
    assert report["planner_error"] is True
    planner_warnings = [w for w in report["warnings"] if "Planner terminal error" in w]
    assert len(planner_warnings) == 1
    assert "API rate limit exceeded" in planner_warnings[0]
    assert "auth_error" in planner_warnings[0]


def test_inspect_planner_parse_error_warning(monkeypatch) -> None:
    snapshot = Snapshot(
        metadata={},
        planner_capture={
            "parse_error": "Invalid JSON in planner response",
        },
    )
    monkeypatch.setattr("benchdeck.inspect.load_snapshot", lambda _: snapshot)
    report = inspect_run(Path("/tmp/fake"))
    assert report["planner_error"] is True
    planner_warnings = [w for w in report["warnings"] if "Planner parse error" in w]
    assert len(planner_warnings) == 1
    assert "Invalid JSON in planner response" in planner_warnings[0]


def test_inspect_planner_mode_mismatch_warning(monkeypatch) -> None:
    snapshot = Snapshot(
        metadata={},
        plan={"mode": "single"},
        tally={},
        planner_capture={"value": {"mode": "comparison"}},
    )
    monkeypatch.setattr("benchdeck.inspect.load_snapshot", lambda _: snapshot)
    report = inspect_run(Path("/tmp/fake"))
    assert report["planner_mode"] == "comparison"
    mismatch_warnings = [w for w in report["warnings"] if "mode mismatch" in w]
    assert len(mismatch_warnings) == 1


def test_inspect_planner_no_error_when_empty(monkeypatch) -> None:
    snapshot = Snapshot(metadata={}, planner_capture={})
    monkeypatch.setattr("benchdeck.inspect.load_snapshot", lambda _: snapshot)
    report = inspect_run(Path("/tmp/fake"))
    assert report["planner_error"] is False
    planner_warnings = [w for w in report["warnings"] if "Planner" in w]
    assert len(planner_warnings) == 0


def test_load_schema_returns_non_none() -> None:
    from benchdeck.inspect import _load_schema

    schema = _load_schema("summary_tally.schema.json")
    assert isinstance(schema, dict)
    assert "properties" in schema
