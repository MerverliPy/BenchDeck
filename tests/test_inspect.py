from pathlib import Path

from benchdeck.inspect import inspect_run


FIXTURE = Path(__file__).parents[1] / "fixtures" / "original_run.zip"


def test_original_run_defects_are_detected() -> None:
    report = inspect_run(FIXTURE)
    warnings = "\n".join(report["warnings"])
    assert "Only 9 of 10" in warnings
    assert "case 10 has an empty final output" in warnings
    assert "candidate output as judge_transcript" in warnings
    assert "marked completed" in warnings
