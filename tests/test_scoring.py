"""Phase 1 tests for scoring with agent-attributed tallies."""

from benchdeck.models import (
    BenchmarkCase,
    CaseJudgment,
    ExecutionKey,
)
from benchdeck.scoring import build_tally, validate_execution_coverage


def _case(case_id: int, family: str) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        title=f"Case {case_id}",
        family=family,
        purpose="x",
        test_prompt=f"Prompt {case_id}",
        hard_fail_conditions=["f"],
    )


def _judgment(case_id: int, rating: str, agent_label: str = "agent_a") -> CaseJudgment:
    return CaseJudgment.model_validate(
        {
            "case_id": case_id,
            "agent_label": agent_label,
            "case_verdict": "ok",
            "gate_check": {"status": "Pass", "reason": "ok"},
            "rubric": {"task_success": rating},
            "overall_rating": rating,
            "why": "ok",
        }
    )


def test_documented_zero_to_four_scale() -> None:
    tally = build_tally(
        [_case(1, "happy-path"), _case(2, "happy-path"), _case(3, "happy-path")],
        [_judgment(1, "Excellent"), _judgment(2, "Excellent"), _judgment(3, "Strong")],
        agent_label="agent_a",
    )
    assert tally.score_scale["Excellent"] == 4
    assert tally.family_scores["happy_path"] == 3.67


def test_per_agent_tally_filters_by_label() -> None:
    cases = [_case(1, "happy_path"), _case(2, "happy_path")]
    judgments = [
        _judgment(1, "Excellent", agent_label="agent_a"),
        _judgment(2, "Weak", agent_label="agent_a"),
        _judgment(1, "Fail", agent_label="agent_b"),
        _judgment(2, "Strong", agent_label="agent_b"),
    ]
    tally_a = build_tally(cases, judgments, agent_label="agent_a")
    tally_b = build_tally(cases, judgments, agent_label="agent_b")

    assert tally_a.cases_judged == 2
    assert tally_b.cases_judged == 2
    assert tally_a.rating_counts.get("Excellent", 0) == 1
    assert tally_a.rating_counts.get("Fail", 0) == 0
    assert tally_b.rating_counts.get("Fail", 0) == 1


def test_tally_counts_gate_failures() -> None:
    cases = [_case(1, "happy_path")]
    j = CaseJudgment.model_validate(
        {
            "case_id": 1,
            "agent_label": "agent_a",
            "case_verdict": "bad",
            "gate_check": {"status": "Fail", "reason": "hard-fail"},
            "rubric": {"task_success": "Weak"},
            "overall_rating": "Fail",
            "why": "failed gate",
        }
    )
    tally = build_tally(cases, [j], agent_label="agent_a")
    assert tally.gate_failures == 1


def test_coverage_validation_diagnostics() -> None:
    expected = {
        ExecutionKey(agent_label="agent_a", case_id=1),
        ExecutionKey(agent_label="agent_a", case_id=2),
    }
    terminal = {
        ExecutionKey(agent_label="agent_a", case_id=1),
        ExecutionKey(agent_label="agent_b", case_id=2),
    }
    coverage = validate_execution_coverage(expected, terminal)
    assert not coverage.is_complete
    assert len(coverage.missing_keys) == 1  # agent_a, case 2
    assert len(coverage.extra_keys) == 1  # agent_b, case 2
    assert len(coverage.diagnostics) == 2


def test_coverage_complete_when_exact_match() -> None:
    expected = {
        ExecutionKey(agent_label="agent_a", case_id=1),
        ExecutionKey(agent_label="agent_b", case_id=1),
    }
    terminal = set(expected)
    coverage = validate_execution_coverage(expected, terminal)
    assert coverage.is_complete
    assert not coverage.diagnostics
    assert not coverage.missing_keys
    assert not coverage.extra_keys
