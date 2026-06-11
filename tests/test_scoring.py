from benchdeck.models import BenchmarkCase, CaseJudgment
from benchdeck.scoring import build_tally


def case(case_id: int, family: str) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        title="x",
        family=family,
        purpose="x",
        test_prompt="x",
    )


def judgment(case_id: int, rating: str) -> CaseJudgment:
    return CaseJudgment.model_validate(
        {
            "case_id": case_id,
            "case_verdict": "ok",
            "gate_check": {"status": "Pass", "reason": "ok"},
            "rubric": {"task_success": rating},
            "overall_rating": rating,
            "why": "ok",
        }
    )


def test_documented_zero_to_four_scale() -> None:
    tally = build_tally(
        [case(1, "happy-path"), case(2, "happy-path"), case(3, "happy-path")],
        [judgment(1, "Excellent"), judgment(2, "Excellent"), judgment(3, "Strong")],
    )
    assert tally["score_scale"]["Excellent"] == 4
    assert tally["family_scores"]["happy_path"] == 3.67
