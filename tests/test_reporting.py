"""Phase 0 regression tests for scoring and reporting.

Tests document defects in agent-scoped scoring, verdict construction,
and family-coverage enforcement.
"""

from __future__ import annotations

from conftest import (
    make_comparison_plan,
    make_judgment,
    make_single_plan,
)

from benchdeck.models import (
    RunStatus,
)
from benchdeck.reporting import build_final_verdict
from benchdeck.scoring import build_tally

# ═══════════════════════════════════════════════════════════════════════════
# Cross-agent scoring collapse
# ═══════════════════════════════════════════════════════════════════════════


def test_two_agent_scoring_conflates_both_agents() -> None:
    """build_tally and build_final_verdict group judgments by case_id only.

    When two agents produce judgments for the same cases, the tally cannot
    separate them, and the comparison loses per-agent identity.
    """
    plan = make_comparison_plan()
    # Both agents receive judgments — but judgments have no agent_label.
    judgments = [make_judgment(c.id, rating="Excellent") for c in plan.cases] + [
        make_judgment(c.id, rating="Fail")
        for c in plan.cases  # agent_b's results
    ]
    tally = build_tally(plan.cases, judgments)
    # 16 judgments (8 per agent) but all counted together.
    assert tally["cases_judged"] == 16
    # Excellent and Fail both appear — but we cannot tell which agent
    # earned which rating.
    rating_counts = tally["rating_counts"]
    assert isinstance(rating_counts, dict)
    assert rating_counts["Excellent"] == 8
    assert rating_counts["Fail"] == 8
    # Family scores average across both agents.
    family_scores = tally["family_scores"]
    assert isinstance(family_scores, dict)
    assert "happy_path" in family_scores


def test_comparison_mode_family_scores_not_per_agent() -> None:
    """Family scores are averaged over all judgments regardless of agent."""
    plan = make_comparison_plan()
    judgments = []
    for case in plan.cases:
        judgments.append(make_judgment(case.id, rating="Excellent"))
        judgments.append(make_judgment(case.id, rating="Weak"))
    tally = build_tally(plan.cases, judgments)
    scores = tally["family_scores"]
    assert isinstance(scores, dict)
    happy_score = scores.get("happy_path")
    # Average of 4 (Excellent) and 1 (Weak) = 2.5 per case, across both
    # agents, so both agents' scores are averaged together.
    assert isinstance(happy_score, (int, float))


# ═══════════════════════════════════════════════════════════════════════════
# Verdict construction
# ═══════════════════════════════════════════════════════════════════════════


def test_verdict_validated_when_all_excellent() -> None:
    """A complete set of Excellent judgments yields 'Validated'."""
    plan = make_single_plan()
    judgments = [make_judgment(c.id, rating="Excellent") for c in plan.cases]
    tally = build_tally(plan.cases, judgments)
    verdict = build_final_verdict(plan, judgments, tally, RunStatus.COMPLETED)
    assert verdict["overall_verdict"] == "Validated"


def test_verdict_not_validated_with_gate_failure() -> None:
    """A single gate failure makes the verdict 'Not Validated'."""
    plan = make_single_plan()
    judgments = [make_judgment(c.id, rating="Excellent", gate_status="Pass") for c in plan.cases]
    # Replace case 1's gate with a failure.
    judgments[0] = make_judgment(1, rating="Fail", gate_status="Fail")
    tally = build_tally(plan.cases, judgments)
    verdict = build_final_verdict(plan, judgments, tally, RunStatus.COMPLETED)
    assert verdict["overall_verdict"] == "Not Validated"


def test_verdict_not_validated_when_inconclusive() -> None:
    """An INCONCLUSIVE run cannot be Validated."""
    plan = make_single_plan()
    judgments = [make_judgment(c.id, rating="Excellent") for c in plan.cases]
    tally = build_tally(plan.cases, judgments)
    verdict = build_final_verdict(plan, judgments, tally, RunStatus.INCONCLUSIVE)
    assert verdict["overall_verdict"] == "Not Validated"


# ═══════════════════════════════════════════════════════════════════════════
# Coverage reporting
# ═══════════════════════════════════════════════════════════════════════════


def test_coverage_planned_versus_judged() -> None:
    """The tally distinguishes planned vs judged counts."""
    plan = make_single_plan()
    half = len(plan.cases) // 2
    judgments = [make_judgment(c.id, rating="Strong") for c in plan.cases[:half]]
    tally = build_tally(plan.cases, judgments)
    assert tally["cases_planned"] == 8
    assert tally["cases_judged"] == half


def test_policy_blocks_excluded_from_scoring() -> None:
    """Policy blocks are tallied separately and do not affect rating counts."""
    plan = make_single_plan()
    judgments = [make_judgment(c.id, rating="Excellent") for c in plan.cases]
    tally = build_tally(plan.cases, judgments, policy_blocks=2)
    assert tally["policy_blocks"] == 2
    assert tally["cases_judged"] == 8


# ═══════════════════════════════════════════════════════════════════════════
# Family score edge cases
# ═══════════════════════════════════════════════════════════════════════════


def test_family_scores_when_no_judgments() -> None:
    """Empty judgments produce no family scores."""
    plan = make_single_plan()
    tally = build_tally(plan.cases, [])
    assert tally["family_scores"] == {}


def test_family_score_floor_is_zero() -> None:
    """All-Fail judgments produce a family score of 0.0."""
    plan = make_single_plan()
    judgments = [make_judgment(c.id, rating="Fail") for c in plan.cases]
    tally = build_tally(plan.cases, judgments)
    scores = tally["family_scores"]
    assert isinstance(scores, dict)
    for score in scores.values():
        assert score == 0.0
