"""Tests for benchmark runner resume functionality.

Uses deterministic fake gateways to verify that an interrupted run
can be resumed, skipping already-judged cases and completing the rest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conftest import make_single_plan
from fakes import FakeGateway, json_response, text_response

from benchdeck.models import (
    BenchmarkPlan,
    CaseJudgment,
    CaseRunResult,
    GateCheck,
    GateStatus,
    Rating,
    ResponseCapture,
    Rubric,
    RubricDimension,
    RunStatus,
)
from benchdeck.runner import BenchmarkRunner

# ── helpers ──────────────────────────────────────────────────────────────


def _make_judgment(case_id: int, agent_label: str = "agent_a") -> CaseJudgment:
    return CaseJudgment(
        case_id=case_id,
        agent_label=agent_label,
        case_verdict="Good",
        gate_check=GateCheck(status=GateStatus.PASS, reason="All checks passed"),
        rubric=Rubric(
            dimensions=[
                RubricDimension(dimension=d, rating=Rating.STRONG, evidence="ok")
                for d in [
                    "mission_fidelity",
                    "task_success",
                    "priority_adherence",
                    "ambiguity_handling",
                    "process_discipline",
                    "tool_discipline",
                    "robustness",
                    "regression_safety",
                ]
            ]
        ),
        overall_rating=Rating.STRONG,
        why="Good work.",
    )


def _make_result(case_id: int, agent_label: str = "agent_a") -> CaseRunResult:
    return CaseRunResult(
        case_id=case_id,
        agent_label=agent_label,
        final_output=f"Output for case {case_id}",
        agent_capture=ResponseCapture(text=f"Output for case {case_id}"),
    )


def _setup_partial_run_dir(run_dir: Path, plan: BenchmarkPlan, judged_count: int) -> None:
    """Set up a run directory as if a run was interrupted after judging `judged_count` cases."""
    plan_path = run_dir / "benchmark_plan.json"
    plan_path.write_text(plan.model_dump_json())

    judgments = [_make_judgment(case_id=i + 1) for i in range(judged_count)]
    (run_dir / "case_judgments.json").write_text(
        json.dumps([j.model_dump(mode="json") for j in judgments], ensure_ascii=False) + "\n"
    )

    results = [_make_result(case_id=i + 1).model_dump(mode="json") for i in range(judged_count)]
    (run_dir / "run_results.json").write_text(
        json.dumps({"agent_a": results}, ensure_ascii=False) + "\n"
    )

    (run_dir / "run_metadata.json").write_text(
        json.dumps({"run_id": run_dir.name, "status": "running"}, ensure_ascii=False) + "\n"
    )


# ── tests ────────────────────────────────────────────────────────────────


def test_resume_skips_judged_cases(tmp_path: Path) -> None:
    """Resume should skip the 4 already-judged cases and judge only the remaining 4."""
    plan = make_single_plan()
    run_dir = tmp_path / "20260101T000000.000000Z"
    run_dir.mkdir()
    _setup_partial_run_dir(run_dir, plan, judged_count=4)

    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# Test agent\n")

    agent_scripts = [text_response("OK") for _ in range(4)]
    judge_scripts = [json_response(_valid_judgment_json()) for _ in range(4)]

    runner = BenchmarkRunner(
        agent_a_path=agent_path,
        agent_b_path=None,
        output_dir=tmp_path / "unused",
        model="gpt-4o-mini",
        judge_model="gpt-4o-mini",
        agent_gateway=FakeGateway(agent_scripts),
        judge_gateway=FakeGateway(judge_scripts),
        resume_from=run_dir,
    )
    status = runner.run()
    assert status == RunStatus.COMPLETED

    judgments_raw = json.loads((run_dir / "case_judgments.json").read_text())
    assert len(judgments_raw) == 8


def test_resume_no_existing_judgments(tmp_path: Path) -> None:
    """Resume with 0 existing judgments should run all cases."""
    plan = make_single_plan()
    run_dir = tmp_path / "20260101T000000.000000Z"
    run_dir.mkdir()
    _setup_partial_run_dir(run_dir, plan, judged_count=0)

    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# Test agent\n")

    agent_scripts = [text_response("OK") for _ in range(8)]
    judge_scripts = [json_response(_valid_judgment_json()) for _ in range(8)]

    runner = BenchmarkRunner(
        agent_a_path=agent_path,
        agent_b_path=None,
        output_dir=tmp_path / "unused",
        model="gpt-4o-mini",
        judge_model="gpt-4o-mini",
        agent_gateway=FakeGateway(agent_scripts),
        judge_gateway=FakeGateway(judge_scripts),
        resume_from=run_dir,
    )
    status = runner.run()
    assert status == RunStatus.COMPLETED

    judgments_raw = json.loads((run_dir / "case_judgments.json").read_text())
    assert len(judgments_raw) == 8


def test_resume_all_already_judged(tmp_path: Path) -> None:
    """Resume with all cases already judged should complete without new agent calls."""
    plan = make_single_plan()
    run_dir = tmp_path / "20260101T000000.000000Z"
    run_dir.mkdir()
    _setup_partial_run_dir(run_dir, plan, judged_count=8)

    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# Test agent\n")

    runner = BenchmarkRunner(
        agent_a_path=agent_path,
        agent_b_path=None,
        output_dir=tmp_path / "unused",
        model="gpt-4o-mini",
        judge_model="gpt-4o-mini",
        agent_gateway=FakeGateway([]),
        judge_gateway=FakeGateway([]),
        resume_from=run_dir,
    )
    status = runner.run()
    assert status == RunStatus.COMPLETED

    judgments_raw = json.loads((run_dir / "case_judgments.json").read_text())
    assert len(judgments_raw) == 8


def test_resume_missing_plan_raises(tmp_path: Path) -> None:
    """Resume without a benchmark_plan.json should return INFRASTRUCTURE_FAILED."""
    run_dir = tmp_path / "20260101T000000.000000Z"
    run_dir.mkdir()
    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# Test agent\n")

    runner = BenchmarkRunner(
        agent_a_path=agent_path,
        agent_b_path=None,
        output_dir=tmp_path / "unused",
        model="gpt-4o-mini",
        judge_model="gpt-4o-mini",
        agent_gateway=FakeGateway([]),
        judge_gateway=FakeGateway([]),
        resume_from=run_dir,
    )
    status = runner.run()
    assert status == RunStatus.INFRASTRUCTURE_FAILED


def test_resume_preserves_existing_blocks(tmp_path: Path) -> None:
    """Resume should preserve existing policy blocks from the prior run."""
    plan = make_single_plan()
    run_dir = tmp_path / "20260101T000000.000000Z"
    run_dir.mkdir()

    plan_path = run_dir / "benchmark_plan.json"
    plan_path.write_text(plan.model_dump_json())

    judgments = [_make_judgment(case_id=1)]
    (run_dir / "case_judgments.json").write_text(
        json.dumps([j.model_dump(mode="json") for j in judgments], ensure_ascii=False) + "\n"
    )

    results = [_make_result(case_id=1).model_dump(mode="json")]
    (run_dir / "run_results.json").write_text(
        json.dumps({"agent_a": results}, ensure_ascii=False) + "\n"
    )

    block = {
        "case_id": 1,
        "case_title": "Case 1",
        "agent_label": "agent_a",
        "stage": "agent",
        "operation": "case 1",
        "message": "blocked",
    }
    (run_dir / "policy_blocks.json").write_text(json.dumps([block], ensure_ascii=False) + "\n")

    infra = {
        "case_id": 2,
        "agent_label": "agent_a",
        "stage": "agent",
        "message": "timeout",
    }
    (run_dir / "infrastructure_errors.json").write_text(
        json.dumps([infra], ensure_ascii=False) + "\n"
    )

    (run_dir / "run_metadata.json").write_text(
        json.dumps({"run_id": run_dir.name, "status": "running"}, ensure_ascii=False) + "\n"
    )

    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# Test agent\n")

    agent_scripts = [text_response("OK") for _ in range(7)]
    judge_scripts = [json_response(_valid_judgment_json()) for _ in range(7)]

    runner = BenchmarkRunner(
        agent_a_path=agent_path,
        agent_b_path=None,
        output_dir=tmp_path / "unused",
        model="gpt-4o-mini",
        judge_model="gpt-4o-mini",
        agent_gateway=FakeGateway(agent_scripts),
        judge_gateway=FakeGateway(judge_scripts),
        resume_from=run_dir,
    )
    status = runner.run()
    assert status in (RunStatus.COMPLETED, RunStatus.INCONCLUSIVE)

    blocks_raw = json.loads((run_dir / "policy_blocks.json").read_text())
    assert len(blocks_raw) >= 1

    infra_raw = json.loads((run_dir / "infrastructure_errors.json").read_text())
    assert len(infra_raw) >= 1


def test_resume_with_comparison_plan(tmp_path: Path) -> None:
    """Resume should work with two-agent comparison plans."""
    plan = make_single_plan()
    plan.mode = "comparison"
    run_dir = tmp_path / "20260101T000000.000000Z"
    run_dir.mkdir()
    _setup_partial_run_dir(run_dir, plan, judged_count=2)

    agent_a_path = tmp_path / "agent_a.md"
    agent_a_path.write_text("# Agent A\n")
    agent_b_path = tmp_path / "agent_b.md"
    agent_b_path.write_text("# Agent B\n")

    agent_scripts = [text_response("OK") for _ in range(14)]
    judge_scripts = [json_response(_valid_judgment_json()) for _ in range(14)]

    runner = BenchmarkRunner(
        agent_a_path=agent_a_path,
        agent_b_path=agent_b_path,
        output_dir=tmp_path / "unused",
        model="gpt-4o-mini",
        judge_model="gpt-4o-mini",
        agent_gateway=FakeGateway(agent_scripts),
        judge_gateway=FakeGateway(judge_scripts),
        resume_from=run_dir,
    )
    status = runner.run()
    assert status == RunStatus.COMPLETED

    judgments_raw = json.loads((run_dir / "case_judgments.json").read_text())
    assert len(judgments_raw) == 16


def _valid_judgment_json() -> dict[str, Any]:
    return {
        "case_verdict": "Good",
        "gate_check": {"status": "Pass", "reason": "ok"},
        "rubric_dimensions": [
            {"dimension": d, "rating": "Strong", "evidence": "", "strengths": [], "weaknesses": []}
            for d in [
                "mission_fidelity",
                "task_success",
                "priority_adherence",
                "ambiguity_handling",
                "process_discipline",
                "tool_discipline",
                "robustness",
                "regression_safety",
            ]
        ],
        "overall_rating": "Strong",
        "why": "Good work.",
        "regression_notes": [],
    }
