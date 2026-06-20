"""Tests for the disagreement analysis module."""

from __future__ import annotations

from benchdeck.disagreement import analyze_disagreement
from benchdeck.models import (
    REQUIRED_RUBRIC_DIMENSIONS,
    CaseJudgment,
    GateCheck,
    GateStatus,
    Rating,
    Rubric,
    RubricDimension,
)


def _make_judgment(
    case_id: int,
    *,
    agent_label: str = "agent_a",
    judge_index: int = 0,
    rating: str = "Strong",
    gate_status: str = "Pass",
    why: str = "ok",
    rubric_overrides: dict[str, str] | None = None,
) -> CaseJudgment:
    dim_ratings: dict[str, str] = {d: rating for d in REQUIRED_RUBRIC_DIMENSIONS}
    if rubric_overrides:
        dim_ratings.update(rubric_overrides)

    rubric = Rubric(
        dimensions=[
            RubricDimension(dimension=d, rating=Rating(r), evidence=f"Evidence for {d}")
            for d, r in sorted(dim_ratings.items())
        ]
    )

    gate = GateCheck(
        status=GateStatus(gate_status),
        reason="OK" if gate_status == "Pass" else "Hard-fail triggered",
    )

    return CaseJudgment(
        case_id=case_id,
        agent_label=agent_label,
        judge_index=judge_index,
        case_verdict="Acceptable" if rating != "Fail" else "Unacceptable",
        gate_check=gate,
        rubric=rubric,
        overall_rating=Rating(rating),
        why=why,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Empty and single-judgment inputs
# ═══════════════════════════════════════════════════════════════════════════


def test_empty_list_returns_all_zeroes() -> None:
    result = analyze_disagreement([])
    assert result["multi_judged_cases"] == 0
    assert result["high_disagreement_cases"] == []
    assert result["overall_agreement"] == {
        "total_multi_judged": 0,
        "agreed": 0,
        "disagreed": 0,
    }
    assert result["total_judgments"] == 0


def test_single_judgment_no_multi_judged() -> None:
    j = _make_judgment(case_id=1)
    result = analyze_disagreement([j])
    assert result["multi_judged_cases"] == 0
    assert result["high_disagreement_cases"] == []
    assert result["overall_agreement"]["total_multi_judged"] == 0
    assert result["total_judgments"] == 1


def test_single_judge_multiple_cases_no_multi_judged() -> None:
    j1 = _make_judgment(case_id=1)
    j2 = _make_judgment(case_id=2)
    j3 = _make_judgment(case_id=3)
    result = analyze_disagreement([j1, j2, j3])
    assert result["multi_judged_cases"] == 0
    assert result["high_disagreement_cases"] == []
    assert result["total_judgments"] == 3
    assert result["overall_agreement"] == {
        "total_multi_judged": 0,
        "agreed": 0,
        "disagreed": 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Agreement / disagreement for two judges
# ═══════════════════════════════════════════════════════════════════════════


def test_two_judgments_same_rating_agreed() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Strong")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Strong", judge_index=1)
    result = analyze_disagreement([j1, j2])

    assert result["multi_judged_cases"] == 1
    assert result["high_disagreement_cases"] == []
    assert result["overall_agreement"] == {
        "total_multi_judged": 1,
        "agreed": 1,
        "disagreed": 0,
    }
    assert result["total_judgments"] == 2


def test_two_judgments_different_rating_disagreed() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Excellent")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Weak", judge_index=1)
    result = analyze_disagreement([j1, j2])

    assert result["multi_judged_cases"] == 1
    assert result["overall_agreement"] == {
        "total_multi_judged": 1,
        "agreed": 0,
        "disagreed": 1,
    }

    assert len(result["high_disagreement_cases"]) == 1
    hd = result["high_disagreement_cases"][0]
    assert hd["agent"] == "a"
    assert hd["case_id"] == 1
    assert set(hd["ratings"]) == {"Excellent", "Weak"}
    assert hd["judge_count"] == 2


def test_three_judgments_two_same_one_different_disagreed() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Strong")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Strong", judge_index=1)
    j3 = _make_judgment(case_id=1, agent_label="a", rating="Acceptable", judge_index=2)
    result = analyze_disagreement([j1, j2, j3])

    assert result["multi_judged_cases"] == 1
    assert result["overall_agreement"]["agreed"] == 0
    assert result["overall_agreement"]["disagreed"] == 1

    assert len(result["high_disagreement_cases"]) == 1
    hd = result["high_disagreement_cases"][0]
    assert set(hd["ratings"]) == {"Acceptable", "Strong"}
    assert hd["judge_count"] == 3


def test_three_judgments_all_agree() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Excellent")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Excellent", judge_index=1)
    j3 = _make_judgment(case_id=1, agent_label="a", rating="Excellent", judge_index=2)
    result = analyze_disagreement([j1, j2, j3])

    assert result["multi_judged_cases"] == 1
    assert result["overall_agreement"]["agreed"] == 1
    assert result["overall_agreement"]["disagreed"] == 0
    assert result["high_disagreement_cases"] == []


def test_three_judgments_all_different() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Excellent")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Strong", judge_index=1)
    j3 = _make_judgment(case_id=1, agent_label="a", rating="Acceptable", judge_index=2)
    result = analyze_disagreement([j1, j2, j3])

    assert result["overall_agreement"]["disagreed"] == 1
    hd = result["high_disagreement_cases"][0]
    assert set(hd["ratings"]) == {"Acceptable", "Excellent", "Strong"}
    assert hd["judge_count"] == 3


# ═══════════════════════════════════════════════════════════════════════════
# High disagreement case detection
# ═══════════════════════════════════════════════════════════════════════════


def test_high_disagreement_when_ratings_set_has_multiple_values() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Excellent")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Fail", judge_index=1)
    result = analyze_disagreement([j1, j2])

    assert len(result["high_disagreement_cases"]) == 1
    hd = result["high_disagreement_cases"][0]
    assert hd["agent"] == "a"
    assert hd["case_id"] == 1
    assert set(hd["ratings"]) == {"Excellent", "Fail"}
    assert hd["judge_count"] == 2


def test_no_high_disagreement_when_single_rating_in_group() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Acceptable")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Acceptable", judge_index=1)
    result = analyze_disagreement([j1, j2])

    assert result["multi_judged_cases"] == 1
    assert result["high_disagreement_cases"] == []
    assert result["overall_agreement"]["agreed"] == 1


def test_high_disagreement_ratings_are_sorted() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Weak")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Excellent", judge_index=1)
    result = analyze_disagreement([j1, j2])

    hd = result["high_disagreement_cases"][0]
    assert hd["ratings"] == sorted(hd["ratings"])


# ═══════════════════════════════════════════════════════════════════════════
# Dimension variance
# ═══════════════════════════════════════════════════════════════════════════


def test_dimension_variance_zero_when_all_judges_same_score() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Excellent")
    j2 = _make_judgment(
        case_id=1,
        agent_label="a",
        rating="Weak",
        judge_index=1,
        rubric_overrides={d: "Excellent" for d in REQUIRED_RUBRIC_DIMENSIONS},
    )
    result = analyze_disagreement([j1, j2])

    hd = result["high_disagreement_cases"][0]
    dim_vars = hd["dimension_variances"]
    for dim in REQUIRED_RUBRIC_DIMENSIONS:
        assert dim in dim_vars
        assert dim_vars[dim] == 0.0


def test_dimension_variance_positive_when_scores_differ() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Strong")
    j2 = _make_judgment(
        case_id=1,
        agent_label="a",
        rating="Weak",
        judge_index=1,
        rubric_overrides={"mission_fidelity": "Excellent"},
    )
    result = analyze_disagreement([j1, j2])

    hd = result["high_disagreement_cases"][0]
    dim_vars = hd["dimension_variances"]

    # mission_fidelity: scores [3, 4], mean=3.5, pop var = ((3-3.5)^2 + (4-3.5)^2)/2 = 0.25
    assert dim_vars["mission_fidelity"] == 0.25

    # All other dimensions: both judges give their overall rating scores
    # Judge 0: Strong=3 on all dims; Judge 1: Weak=1 on all dims (except mission_fidelity)
    # So for all other dims: scores [3, 1], mean=2, pop var = ((3-2)^2+(1-2)^2)/2 = 1.0
    for dim in REQUIRED_RUBRIC_DIMENSIONS:
        if dim == "mission_fidelity":
            continue
        assert dim_vars[dim] == 1.0


def test_dimension_variance_three_judges_mixed() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Excellent")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Strong", judge_index=1)
    j3 = _make_judgment(case_id=1, agent_label="a", rating="Strong", judge_index=2)
    result = analyze_disagreement([j1, j2, j3])

    hd = result["high_disagreement_cases"][0]
    dim_vars = hd["dimension_variances"]

    # Scores: [4, 3, 3], mean = 10/3, variance = ((4-10/3)^2 + 2*(3-10/3)^2)/3
    # = ((2/3)^2 + 2*(-1/3)^2)/3 = (4/9 + 2/9)/3 = (6/9)/3 = 2/9 ≈ 0.222
    for dim in REQUIRED_RUBRIC_DIMENSIONS:
        assert dim_vars[dim] == 0.222


def test_dimension_variance_absent_when_single_judge() -> None:
    j = _make_judgment(case_id=1, agent_label="a", rating="Strong")
    result = analyze_disagreement([j])
    assert result["high_disagreement_cases"] == []


# ═══════════════════════════════════════════════════════════════════════════
# Multiple agents and cases
# ═══════════════════════════════════════════════════════════════════════════


def test_multiple_agents_with_own_cases() -> None:
    # Agent A: case 1 with 2 judgments (agreed), case 2 with 1 judgment
    # Agent B: case 1 with 2 judgments (disagreed)
    j_a1 = _make_judgment(case_id=1, agent_label="agent_a", rating="Strong")
    j_a2 = _make_judgment(case_id=1, agent_label="agent_a", rating="Strong", judge_index=1)
    j_a3 = _make_judgment(case_id=2, agent_label="agent_a", rating="Excellent")
    j_b1 = _make_judgment(case_id=1, agent_label="agent_b", rating="Excellent")
    j_b2 = _make_judgment(case_id=1, agent_label="agent_b", rating="Fail", judge_index=1)

    result = analyze_disagreement([j_a1, j_a2, j_a3, j_b1, j_b2])

    assert result["multi_judged_cases"] == 2
    assert result["total_judgments"] == 5
    assert result["overall_agreement"] == {
        "total_multi_judged": 2,
        "agreed": 1,
        "disagreed": 1,
    }
    assert len(result["high_disagreement_cases"]) == 1
    hd = result["high_disagreement_cases"][0]
    assert hd["agent"] == "agent_b"
    assert hd["case_id"] == 1


def test_mixed_agents_agent_a_agreed_agent_b_disagreed() -> None:
    j_a1 = _make_judgment(case_id=1, agent_label="agent_a", rating="Acceptable")
    j_a2 = _make_judgment(case_id=1, agent_label="agent_a", rating="Acceptable", judge_index=1)
    j_b1 = _make_judgment(case_id=1, agent_label="agent_b", rating="Excellent")
    j_b2 = _make_judgment(case_id=1, agent_label="agent_b", rating="Weak", judge_index=1)

    result = analyze_disagreement([j_a1, j_a2, j_b1, j_b2])

    assert result["multi_judged_cases"] == 2
    assert result["overall_agreement"] == {
        "total_multi_judged": 2,
        "agreed": 1,
        "disagreed": 1,
    }
    assert len(result["high_disagreement_cases"]) == 1
    hd = result["high_disagreement_cases"][0]
    assert hd["agent"] == "agent_b"


def test_all_agents_agree_across_multiple_cases() -> None:
    j_a1_0 = _make_judgment(case_id=1, agent_label="agent_a", rating="Strong")
    j_a1_1 = _make_judgment(case_id=1, agent_label="agent_a", rating="Strong", judge_index=1)
    j_a2_0 = _make_judgment(case_id=2, agent_label="agent_a", rating="Excellent")
    j_a2_1 = _make_judgment(case_id=2, agent_label="agent_a", rating="Excellent", judge_index=1)

    result = analyze_disagreement([j_a1_0, j_a1_1, j_a2_0, j_a2_1])

    assert result["multi_judged_cases"] == 2
    assert result["overall_agreement"] == {
        "total_multi_judged": 2,
        "agreed": 2,
        "disagreed": 0,
    }
    assert result["high_disagreement_cases"] == []


# ═══════════════════════════════════════════════════════════════════════════
# overall_agreement summary
# ═══════════════════════════════════════════════════════════════════════════


def test_overall_agreement_summary_counts() -> None:
    j_a1_0 = _make_judgment(case_id=1, agent_label="a", rating="Excellent")
    j_a1_1 = _make_judgment(case_id=1, agent_label="a", rating="Excellent", judge_index=1)
    j_a2_0 = _make_judgment(case_id=2, agent_label="a", rating="Strong")
    j_a2_1 = _make_judgment(case_id=2, agent_label="a", rating="Weak", judge_index=1)
    j_a3_0 = _make_judgment(case_id=3, agent_label="a", rating="Fail")

    result = analyze_disagreement([j_a1_0, j_a1_1, j_a2_0, j_a2_1, j_a3_0])

    assert result["overall_agreement"] == {
        "total_multi_judged": 2,
        "agreed": 1,
        "disagreed": 1,
    }
    assert result["multi_judged_cases"] == 2


def test_overall_agreement_all_single_judge_gives_zeroes() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Strong")
    j2 = _make_judgment(case_id=2, agent_label="a", rating="Weak")
    result = analyze_disagreement([j1, j2])

    assert result["overall_agreement"] == {
        "total_multi_judged": 0,
        "agreed": 0,
        "disagreed": 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
# total_judgments field
# ═══════════════════════════════════════════════════════════════════════════


def test_total_judgments_equals_input_length() -> None:
    items: list[CaseJudgment] = []
    for i in range(5):
        items.append(_make_judgment(case_id=i + 1, agent_label="a"))
    result = analyze_disagreement(items)
    assert result["total_judgments"] == 5


def test_total_judgments_zero_for_empty() -> None:
    assert analyze_disagreement([])["total_judgments"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# rating_distributions
# ═══════════════════════════════════════════════════════════════════════════


def test_rating_distributions_single_judge_multiple_cases() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Excellent")
    j2 = _make_judgment(case_id=2, agent_label="a", rating="Strong")
    j3 = _make_judgment(case_id=3, agent_label="a", rating="Strong")

    result = analyze_disagreement([j1, j2, j3])
    rd = result.get("rating_distributions", {})

    assert rd.get("a:1", {}).get("Excellent") == 1
    assert rd.get("a:2", {}).get("Strong") == 1
    assert rd.get("a:3", {}).get("Strong") == 1


def test_rating_distributions_multi_judge_same_case() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Excellent")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Weak", judge_index=1)

    result = analyze_disagreement([j1, j2])
    rd = result.get("rating_distributions", {})

    assert rd.get("a:1", {}).get("Excellent") == 1
    assert rd.get("a:1", {}).get("Weak") == 1


def test_rating_distributions_mixed_agents() -> None:
    j_a = _make_judgment(case_id=1, agent_label="agent_a", rating="Strong")
    j_b = _make_judgment(case_id=1, agent_label="agent_b", rating="Fail")

    result = analyze_disagreement([j_a, j_b])
    rd = result.get("rating_distributions", {})

    assert rd.get("agent_a:1", {}).get("Strong") == 1
    assert rd.get("agent_b:1", {}).get("Fail") == 1
    assert rd.get("agent_a:1", {}).get("Fail", 0) == 0


def test_rating_distributions_empty_input() -> None:
    result = analyze_disagreement([])
    rd = result.get("rating_distributions", {})
    assert rd == {}


# ═══════════════════════════════════════════════════════════════════════════
# Rating values across all enum members
# ═══════════════════════════════════════════════════════════════════════════


def test_all_rating_enum_values_handled() -> None:
    judgments = [
        _make_judgment(case_id=1, agent_label="a", rating="Excellent"),
        _make_judgment(case_id=2, agent_label="a", rating="Strong"),
        _make_judgment(case_id=3, agent_label="a", rating="Acceptable"),
        _make_judgment(case_id=4, agent_label="a", rating="Weak"),
        _make_judgment(case_id=5, agent_label="a", rating="Fail"),
    ]
    result = analyze_disagreement(judgments)
    assert result["total_judgments"] == 5

    rd = result.get("rating_distributions", {})
    assert rd.get("a:1", {}).get("Excellent") == 1
    assert rd.get("a:2", {}).get("Strong") == 1
    assert rd.get("a:3", {}).get("Acceptable") == 1
    assert rd.get("a:4", {}).get("Weak") == 1
    assert rd.get("a:5", {}).get("Fail") == 1


def test_disagreement_across_all_rating_values() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Excellent")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Fail", judge_index=1)
    result = analyze_disagreement([j1, j2])

    assert result["overall_agreement"]["disagreed"] == 1
    hd = result["high_disagreement_cases"][0]
    assert set(hd["ratings"]) == {"Excellent", "Fail"}


def test_weak_and_acceptable_disagreement() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Weak")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Acceptable", judge_index=1)
    result = analyze_disagreement([j1, j2])

    assert result["overall_agreement"]["disagreed"] == 1
    hd = result["high_disagreement_cases"][0]
    assert set(hd["ratings"]) == {"Acceptable", "Weak"}


def test_strong_and_fail_disagreement() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Strong")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Fail", judge_index=1)
    result = analyze_disagreement([j1, j2])

    assert result["overall_agreement"]["disagreed"] == 1
    hd = result["high_disagreement_cases"][0]
    assert set(hd["ratings"]) == {"Fail", "Strong"}


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases and regression
# ═══════════════════════════════════════════════════════════════════════════


def test_multiple_judges_same_case_same_agent_grouped_correctly() -> None:
    j1 = _make_judgment(case_id=1, agent_label="x", rating="Excellent", judge_index=0)
    j2 = _make_judgment(case_id=1, agent_label="x", rating="Strong", judge_index=1)
    j3 = _make_judgment(case_id=2, agent_label="x", rating="Weak", judge_index=0)
    j4 = _make_judgment(case_id=2, agent_label="x", rating="Weak", judge_index=1)

    result = analyze_disagreement([j1, j2, j3, j4])

    assert result["multi_judged_cases"] == 2
    assert result["overall_agreement"]["agreed"] == 1
    assert result["overall_agreement"]["disagreed"] == 1
    assert len(result["high_disagreement_cases"]) == 1
    assert result["high_disagreement_cases"][0]["case_id"] == 1


def test_same_case_id_different_agents_not_grouped_together() -> None:
    j_a = _make_judgment(case_id=1, agent_label="agent_a", rating="Excellent")
    j_b = _make_judgment(case_id=1, agent_label="agent_b", rating="Fail")

    result = analyze_disagreement([j_a, j_b])

    assert result["multi_judged_cases"] == 0
    assert result["high_disagreement_cases"] == []
    assert result["overall_agreement"]["total_multi_judged"] == 0


def test_gate_fail_judgment_overall_rating_forced_to_fail() -> None:
    j = _make_judgment(case_id=1, agent_label="a", rating="Strong", gate_status="Fail")

    assert j.overall_rating == Rating.FAIL
    assert j.gate_check.status == GateStatus.FAIL


def test_high_disagreement_includes_dimension_variances_key() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Excellent")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Weak", judge_index=1)
    result = analyze_disagreement([j1, j2])

    hd = result["high_disagreement_cases"][0]
    assert "dimension_variances" in hd
    assert len(hd["dimension_variances"]) == len(REQUIRED_RUBRIC_DIMENSIONS)


def test_dimension_variances_rounded_to_three_decimals() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Excellent")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Strong", judge_index=1)
    result = analyze_disagreement([j1, j2])

    hd = result["high_disagreement_cases"][0]
    for val in hd["dimension_variances"].values():
        assert val == round(val, 3)


def test_total_judgments_includes_all_inputs() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Excellent")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Excellent", judge_index=1)
    j3 = _make_judgment(case_id=2, agent_label="b", rating="Fail")
    j4 = _make_judgment(case_id=2, agent_label="b", rating="Fail", judge_index=1)
    j5 = _make_judgment(case_id=3, agent_label="a", rating="Weak")

    result = analyze_disagreement([j1, j2, j3, j4, j5])
    assert result["total_judgments"] == 5
    assert result["multi_judged_cases"] == 2


def test_multi_judged_cases_equals_total_multi_judged() -> None:
    j1 = _make_judgment(case_id=1, agent_label="a", rating="Strong")
    j2 = _make_judgment(case_id=1, agent_label="a", rating="Strong", judge_index=1)
    j3 = _make_judgment(case_id=2, agent_label="a", rating="Weak")
    j4 = _make_judgment(case_id=2, agent_label="a", rating="Fail", judge_index=1)
    j5 = _make_judgment(case_id=3, agent_label="b", rating="Excellent")
    j6 = _make_judgment(case_id=3, agent_label="b", rating="Excellent", judge_index=1)
    j7 = _make_judgment(case_id=4, agent_label="c", rating="Acceptable")

    result = analyze_disagreement([j1, j2, j3, j4, j5, j6, j7])

    assert result["multi_judged_cases"] == result["overall_agreement"]["total_multi_judged"]
    assert result["multi_judged_cases"] == 3
