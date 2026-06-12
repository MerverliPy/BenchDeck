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
