"""Phase 1 tests for scoring and reporting.

Tests verify per-agent tally building, verdict construction,
and comparison scoring with proper agent isolation.
"""

from __future__ import annotations

from conftest import (
    make_comparison_plan,
    make_judgment,
    make_single_plan,
)

from benchdeck.models import RunStatus
from benchdeck.reporting import build_per_agent_verdict, build_run_verdict, run_verdict_markdown
from benchdeck.scoring import build_tally, validate_execution_coverage

# ═══════════════════════════════════════════════════════════════════════════
# Per-agent scoring isolation
# ═══════════════════════════════════════════════════════════════════════════


def test_per_agent_tally_separates_agents() -> None:
    """build_tally with agent_label filters judgments by agent."""
    plan = make_comparison_plan()
    judgments = [
        make_judgment(c.id, agent_label="agent_a", rating="Excellent") for c in plan.cases
    ] + [make_judgment(c.id, agent_label="agent_b", rating="Fail") for c in plan.cases]
    tally_a = build_tally(plan.cases, judgments, agent_label="agent_a")
    tally_b = build_tally(plan.cases, judgments, agent_label="agent_b")

    assert tally_a.rating_counts["Excellent"] == 8
    assert tally_a.rating_counts.get("Fail", 0) == 0
    assert tally_b.rating_counts["Fail"] == 8
    assert tally_b.rating_counts.get("Excellent", 0) == 0


def test_comparison_mode_family_scores_are_per_agent() -> None:
    """Family scores are per-agent, not averaged across both."""
    plan = make_comparison_plan()
    judgments = []
    for case in plan.cases:
        judgments.append(make_judgment(case.id, agent_label="agent_a", rating="Excellent"))
        judgments.append(make_judgment(case.id, agent_label="agent_b", rating="Weak"))
    tally_a = build_tally(plan.cases, judgments, agent_label="agent_a")
    tally_b = build_tally(plan.cases, judgments, agent_label="agent_b")

    assert tally_a.agent_label == "agent_a"
    assert tally_b.agent_label == "agent_b"
    # Family scores for agent_a should be 4.0, agent_b should be 1.0
    assert tally_a.family_scores.get("happy_path") == 4.0
    assert tally_b.family_scores.get("happy_path") == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Verdict construction
# ═══════════════════════════════════════════════════════════════════════════


def test_per_agent_verdict_validated() -> None:
    plan = make_single_plan()
    judgments = [make_judgment(c.id, agent_label="agent_a", rating="Excellent") for c in plan.cases]
    tally = build_tally(plan.cases, judgments, agent_label="agent_a")
    expected = plan.all_execution_keys(["agent_a"])
    terminal = {j.execution_key for j in judgments}
    coverage = validate_execution_coverage(expected, terminal)
    verdict = build_per_agent_verdict(
        "agent_a", plan, judgments, tally, coverage, RunStatus.COMPLETED
    )
    assert verdict.verdict == "validated"
    assert verdict.agent_label == "agent_a"


def test_per_agent_verdict_not_validated_with_gate_failure() -> None:
    plan = make_single_plan()
    judgments = [
        make_judgment(c.id, agent_label="agent_a", rating="Excellent", gate_status="Pass")
        for c in plan.cases
    ]
    judgments[0] = make_judgment(1, agent_label="agent_a", rating="Fail", gate_status="Fail")
    tally = build_tally(plan.cases, judgments, agent_label="agent_a")
    expected = plan.all_execution_keys(["agent_a"])
    terminal = {j.execution_key for j in judgments}
    coverage = validate_execution_coverage(expected, terminal)
    verdict = build_per_agent_verdict(
        "agent_a", plan, judgments, tally, coverage, RunStatus.COMPLETED
    )
    assert verdict.verdict == "not_validated"


def test_per_agent_verdict_inconclusive_with_incomplete_coverage() -> None:
    plan = make_single_plan()
    judgments = [
        make_judgment(c.id, agent_label="agent_a", rating="Excellent") for c in plan.cases[:4]
    ]
    tally = build_tally(plan.cases, judgments, agent_label="agent_a")
    expected = plan.all_execution_keys(["agent_a"])
    terminal = {j.execution_key for j in judgments}
    coverage = validate_execution_coverage(expected, terminal)
    assert not coverage.is_complete
    verdict = build_per_agent_verdict(
        "agent_a", plan, judgments, tally, coverage, RunStatus.INCONCLUSIVE
    )
    assert verdict.verdict == "inconclusive"


# ═══════════════════════════════════════════════════════════════════════════
# Comparison verdict
# ═══════════════════════════════════════════════════════════════════════════


def test_comparison_shows_wins_by_case() -> None:
    plan = make_comparison_plan()
    judgments = []
    for case in plan.cases:
        # agent_a gets Excellent (score 4), agent_b gets Acceptable (score 2)
        judgments.append(make_judgment(case.id, agent_label="agent_a", rating="Excellent"))
        judgments.append(make_judgment(case.id, agent_label="agent_b", rating="Acceptable"))

    tally_a = build_tally(plan.cases, judgments, agent_label="agent_a")
    tally_b = build_tally(plan.cases, judgments, agent_label="agent_b")
    expected = plan.all_execution_keys(["agent_a", "agent_b"])
    terminal = {j.execution_key for j in judgments}
    cov_a = validate_execution_coverage(
        {k for k in expected if k.agent_label == "agent_a"},
        {k for k in terminal if k.agent_label == "agent_a"},
    )
    cov_b = validate_execution_coverage(
        {k for k in expected if k.agent_label == "agent_b"},
        {k for k in terminal if k.agent_label == "agent_b"},
    )

    verdict_a = build_per_agent_verdict(
        "agent_a", plan, judgments, tally_a, cov_a, RunStatus.COMPLETED
    )
    verdict_b = build_per_agent_verdict(
        "agent_b", plan, judgments, tally_b, cov_b, RunStatus.COMPLETED
    )
    run_verdict = build_run_verdict(
        RunStatus.COMPLETED,
        {"agent_a": verdict_a, "agent_b": verdict_b},
        plan,
        judgments,
    )
    assert run_verdict.comparison is not None
    assert run_verdict.comparison.valid is True
    assert run_verdict.comparison.wins_by_agent["agent_a"] == 8
    assert run_verdict.comparison.wins_by_agent["agent_b"] == 0


def test_comparison_invalid_with_incomplete_coverage() -> None:
    plan = make_comparison_plan()
    judgments = [make_judgment(c.id, agent_label="agent_a", rating="Excellent") for c in plan.cases]
    expected = plan.all_execution_keys(["agent_a", "agent_b"])
    terminal = {j.execution_key for j in judgments}

    cov_a = validate_execution_coverage(
        {k for k in expected if k.agent_label == "agent_a"},
        {k for k in terminal if k.agent_label == "agent_a"},
    )
    cov_b = validate_execution_coverage(
        {k for k in expected if k.agent_label == "agent_b"},
        {k for k in terminal if k.agent_label == "agent_b"},
    )

    tally_a = build_tally(plan.cases, judgments, agent_label="agent_a")
    tally_b = build_tally(plan.cases, [], agent_label="agent_b")

    verdict_a = build_per_agent_verdict(
        "agent_a", plan, judgments, tally_a, cov_a, RunStatus.INCONCLUSIVE
    )
    verdict_b = build_per_agent_verdict("agent_b", plan, [], tally_b, cov_b, RunStatus.INCONCLUSIVE)
    run_verdict = build_run_verdict(
        RunStatus.INCONCLUSIVE,
        {"agent_a": verdict_a, "agent_b": verdict_b},
        plan,
        judgments,
    )
    assert run_verdict.comparison is not None
    assert run_verdict.comparison.valid is False


# ═══════════════════════════════════════════════════════════════════════════
# Typed markdown verdict
# ═══════════════════════════════════════════════════════════════════════════


def test_run_verdict_markdown_includes_per_agent_sections() -> None:
    plan = make_single_plan()
    judgments = [make_judgment(c.id, agent_label="agent_a", rating="Excellent") for c in plan.cases]
    tally = build_tally(plan.cases, judgments, agent_label="agent_a")
    cov = validate_execution_coverage(
        plan.all_execution_keys(["agent_a"]),
        {j.execution_key for j in judgments},
    )
    agent_verdict = build_per_agent_verdict(
        "agent_a", plan, judgments, tally, cov, RunStatus.COMPLETED
    )
    run_verdict = build_run_verdict(
        RunStatus.COMPLETED, {"agent_a": agent_verdict}, plan, judgments
    )
    md = run_verdict_markdown(run_verdict, plan)
    assert "Agent: agent_a" in md
    assert "**Verdict:** validated" in md
    assert "Excellent" in md


def test_coverage_planned_versus_judged() -> None:
    plan = make_single_plan()
    half = len(plan.cases) // 2
    judgments = [
        make_judgment(c.id, agent_label="agent_a", rating="Strong") for c in plan.cases[:half]
    ]
    tally = build_tally(plan.cases, judgments, agent_label="agent_a")
    assert tally.cases_planned == 8
    assert tally.cases_judged == half
