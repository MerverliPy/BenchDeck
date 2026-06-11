"""Reusable test fixtures and builders for Phase 1.

Every builder returns canonical Pydantic model instances.  No fixture
makes a live API call — everything is constructed in-process.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from benchdeck.models import (
    AgentProfile,
    BenchmarkCase,
    BenchmarkPlan,
    CaseJudgment,
    CaseRunResult,
    ExecutionKey,
    GateCheck,
    GateStatus,
    PolicyBlock,
    Rating,
    ResponseCapture,
    Rubric,
    RubricDimension,
    RunMetadata,
    RunStatus,
    TokenUsage,
)

# ═══════════════════════════════════════════════════════════════════════════
# Agent profiles
# ═══════════════════════════════════════════════════════════════════════════


def make_agent_profile(agent_name_a: str = "TestAgent") -> AgentProfile:
    return AgentProfile(
        agent_name_a=agent_name_a,
        inferred_mission="Complete software engineering tasks accurately.",
        top_priorities=["correctness", "safety"],
        boundaries=["no destructive operations"],
        tool_posture="file-editing allowed",
        mission_critical_capability="code generation",
        rare_defining_capability="architecture design",
        likely_weak_spots=["complex refactoring"],
        likely_regression_risks=["breaking existing tests"],
    )


def make_comparison_agent_profile() -> AgentProfile:
    return AgentProfile(
        agent_name_a="Agent A",
        agent_name_b="Agent B",
        inferred_mission="Compare two coding agents on shared tasks.",
        top_priorities=["accuracy"],
        boundaries=[],
    )


# ═══════════════════════════════════════════════════════════════════════════
# Benchmark cases
# ═══════════════════════════════════════════════════════════════════════════


def make_case(
    case_id: int,
    family: str = "happy_path",
    *,
    title: str = "",
    clarify: str = "optional",
    hard_fail_conditions: list[str] | None = None,
) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        title=title or f"Case {case_id}",
        family=family,
        purpose=f"Purpose of case {case_id}",
        test_prompt=f"Perform task {case_id}.",
        clarification_expectation=clarify,
        hard_fail_conditions=hard_fail_conditions or ["violates safety policy"],
    )


# ═══════════════════════════════════════════════════════════════════════════
# Plans
# ═══════════════════════════════════════════════════════════════════════════


def make_single_plan(
    cases: list[BenchmarkCase] | None = None,
    agent_name: str = "TestAgent",
) -> BenchmarkPlan:
    if cases is None:
        cases = _canonical_cases()
    return BenchmarkPlan(
        mode="single",
        profile=make_agent_profile(agent_name),
        validation_standard=["correctness", "safety"],
        cases=cases,
    )


def make_comparison_plan(
    cases: list[BenchmarkCase] | None = None,
) -> BenchmarkPlan:
    if cases is None:
        cases = _canonical_cases()
    return BenchmarkPlan(
        mode="comparison",
        profile=make_comparison_agent_profile(),
        validation_standard=["correctness", "safety"],
        cases=cases,
    )


def make_minimal_plan() -> BenchmarkPlan:
    """Smallest valid plan (one case per required family, 8 cases)."""
    return BenchmarkPlan(
        mode="single",
        profile=make_agent_profile(),
        cases=[
            make_case(1, "happy_path"),
            make_case(2, "happy_path"),
            make_case(3, "regression_protection"),
            make_case(4, "regression_protection"),
            make_case(5, "stress_adversarial"),
            make_case(6, "stress_adversarial"),
            make_case(7, "ambiguity"),
            make_case(8, "ambiguity"),
        ],
    )


def _canonical_cases() -> list[BenchmarkCase]:
    return [
        make_case(1, "happy_path"),
        make_case(2, "happy_path"),
        make_case(3, "regression_protection"),
        make_case(4, "regression_protection"),
        make_case(5, "stress_adversarial"),
        make_case(6, "stress_adversarial"),
        make_case(7, "ambiguity"),
        make_case(8, "ambiguity"),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Response captures
# ═══════════════════════════════════════════════════════════════════════════


def make_capture(
    text: str = "",
    *,
    response_id: str | None = None,
    request_id: str | None = None,
    error: dict[str, Any] | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    attempts: int = 1,
) -> ResponseCapture:
    return ResponseCapture(
        text=text,
        response_id=response_id,
        request_id=request_id,
        status="completed" if not error else None,
        finish_reason="stop" if not error else None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        error=error,
        attempts=attempts,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Run results
# ═══════════════════════════════════════════════════════════════════════════


def make_run_result(
    case_id: int,
    agent_label: str = "agent_a",
    *,
    final_output: str = "Test output.",
    clarification_used: bool = False,
    infrastructure_error: bool = False,
    agent_capture: ResponseCapture | None = None,
) -> CaseRunResult:
    return CaseRunResult(
        case_id=case_id,
        agent_label=agent_label,
        clarification_used=clarification_used,
        first_output=final_output,
        final_output=final_output,
        agent_capture=agent_capture or make_capture(text=final_output),
        infrastructure_error=infrastructure_error,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Judgments
# ═══════════════════════════════════════════════════════════════════════════


def make_judgment(
    case_id: int,
    *,
    agent_label: str = "agent_a",
    rating: str = "Strong",
    gate_status: str = "Pass",
    why: str = "Adequate response.",
    rubric_dimensions: dict[str, str] | None = None,
) -> CaseJudgment:
    if rubric_dimensions is None:
        rubric_dimensions = {
            "mission_fidelity": rating,
            "task_success": rating,
            "priority_adherence": rating,
            "ambiguity_handling": rating,
            "process_discipline": rating,
            "tool_discipline": rating,
            "robustness": rating,
            "regression_safety": rating,
        }
    rubric = Rubric(
        dimensions=[
            RubricDimension(
                dimension=dim,
                rating=Rating(rat),
                evidence=f"Evidence for {dim}",
            )
            for dim, rat in rubric_dimensions.items()
        ]
    )
    return CaseJudgment(
        case_id=case_id,
        agent_label=agent_label,
        case_verdict="Acceptable" if rating != "Fail" else "Unacceptable",
        gate_check=GateCheck(
            status=GateStatus.PASS if gate_status == "Pass" else GateStatus.FAIL,
            reason="OK" if gate_status == "Pass" else "Hard-fail triggered",
        ),
        rubric=rubric,
        overall_rating=Rating(rating),
        why=why,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Policy blocks
# ═══════════════════════════════════════════════════════════════════════════


def make_policy_block(
    case_id: int,
    *,
    agent_label: str = "agent_a",
    stage: str = "agent",
    message: str = "Content policy blocked",
) -> PolicyBlock:
    return PolicyBlock(
        case_id=case_id,
        case_title=f"Case {case_id}",
        stage=stage,
        agent_label=agent_label,
        operation=f"case {case_id} · {agent_label}",
        message=message,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Run metadata
# ═══════════════════════════════════════════════════════════════════════════


def make_metadata(
    *,
    cases_in_plan: int = 0,
    executions_judged: int = 0,
    status: RunStatus = RunStatus.RUNNING,
) -> RunMetadata:
    return RunMetadata(
        status=status,
        cases_in_plan=cases_in_plan,
        executions_planned=cases_in_plan,
        executions_judged=executions_judged,
        token_usage=TokenUsage(),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Execution ledgers (complete sets of results + judgments)
# ═══════════════════════════════════════════════════════════════════════════


def make_single_agent_ledger(
    plan: BenchmarkPlan,
    *,
    agent_label: str = "agent_a",
) -> tuple[dict[str, list[CaseRunResult]], list[CaseJudgment]]:
    results: dict[str, list[CaseRunResult]] = {agent_label: []}
    judgments: list[CaseJudgment] = []
    for case in plan.cases:
        results[agent_label].append(make_run_result(case.id, agent_label=agent_label))
        judgments.append(make_judgment(case.id, agent_label=agent_label))
    return results, judgments


def make_two_agent_ledger(
    plan: BenchmarkPlan,
) -> tuple[dict[str, list[CaseRunResult]], list[CaseJudgment]]:
    """Produce results and judgments for a two-agent plan.

    Each judgment is properly attributed to its agent.
    """
    results: dict[str, list[CaseRunResult]] = {"agent_a": [], "agent_b": []}
    judgments: list[CaseJudgment] = []
    for case in plan.cases:
        results["agent_a"].append(make_run_result(case.id, agent_label="agent_a"))
        results["agent_b"].append(make_run_result(case.id, agent_label="agent_b"))
        judgments.append(make_judgment(case.id, agent_label="agent_a"))
        judgments.append(make_judgment(case.id, agent_label="agent_b"))
    return results, judgments


# ═══════════════════════════════════════════════════════════════════════════
# Execution keys
# ═══════════════════════════════════════════════════════════════════════════


def make_key(case_id: int, agent_label: str = "agent_a") -> ExecutionKey:
    return ExecutionKey(agent_label=agent_label, case_id=case_id)


def make_expected_keys(
    plan: BenchmarkPlan,
    agent_labels: list[str] | None = None,
) -> set[ExecutionKey]:
    return plan.all_execution_keys(agent_labels or plan.agent_labels)


# ═══════════════════════════════════════════════════════════════════════════
# Temporary agent files
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def agent_a_path(tmp_path: Path) -> Path:
    path = tmp_path / "agent_a.md"
    path.write_text(
        "# Agent A\n\nYou are a helpful coding assistant.\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def agent_b_path(tmp_path: Path) -> Path:
    path = tmp_path / "agent_b.md"
    path.write_text(
        "# Agent B\n\nYou are a meticulous code reviewer.\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    d = tmp_path / "benchmark_out"
    d.mkdir()
    return d
