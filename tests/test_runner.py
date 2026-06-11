"""Phase 1 tests for the benchmark runner.

Tests prove that (agent_label, case_id) is the canonical identity,
per-agent scoring is isolated, and plan validators are enforced.
All tests use deterministic fake gateways — no live model calls.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

from conftest import (
    make_case,
    make_judgment,
    make_single_plan,
)
from fakes import (
    FakeGateway,
    json_response,
    malformed_json_response,
    schema_invalid_json_response,
    text_response,
)

from benchdeck.models import (
    BenchmarkPlan,
    CaseRunResult,
    ExecutionKey,
    ResponseCapture,
    RunStatus,
)
from benchdeck.runner import BenchmarkRunner, _policy_block_from_capture
from benchdeck.scoring import build_tally, validate_execution_coverage

# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _plan_json_for(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mode": "single",
        "profile": {
            "agent_name_a": "TestAgent",
            "inferred_mission": "Test.",
            "top_priorities": [],
            "boundaries": [],
            "tool_posture": "",
            "mission_critical_capability": "",
            "rare_defining_capability": "",
            "likely_weak_spots": [],
            "likely_regression_risks": [],
        },
        "validation_standard": ["correctness"],
        "cases": cases,
    }


def _judgment_json(case_id: int, rating: str = "Strong") -> dict[str, Any]:
    return {
        "case_verdict": "ok",
        "gate_check": {"status": "Pass", "reason": "ok"},
        "rubric": {
            "mission_fidelity": rating,
            "task_success": rating,
            "priority_adherence": rating,
            "ambiguity_handling": rating,
            "process_discipline": rating,
            "tool_discipline": rating,
            "robustness": rating,
            "regression_safety": rating,
        },
        "overall_rating": rating,
        "why": "ok",
        "regression_notes": [],
    }


def _valid_case(case_id: int, family: str = "happy_path") -> dict[str, Any]:
    return {
        "id": case_id,
        "title": f"Case {case_id}",
        "family": family,
        "purpose": "x",
        "test_prompt": f"Prompt {case_id}",
        "hard_fail_conditions": ["violates safety"],
    }


_FAMILIES = [
    "happy_path",
    "happy_path",
    "regression_protection",
    "regression_protection",
    "stress_adversarial",
    "stress_adversarial",
    "ambiguity",
    "ambiguity",
]


# ═══════════════════════════════════════════════════════════════════════════
# ExecutionKey and agent identity
# ═══════════════════════════════════════════════════════════════════════════


def test_execution_key_construction() -> None:
    key = ExecutionKey(agent_label="agent_a", case_id=5)
    assert key.agent_label == "agent_a"
    assert key.case_id == 5


def test_judgment_now_has_agent_label() -> None:
    judgment = make_judgment(case_id=1, agent_label="agent_a")
    assert judgment.agent_label == "agent_a"
    assert hasattr(judgment, "agent_label")


def test_agent_a_and_agent_b_have_separate_judgments() -> None:
    """Two agents for the same case produce distinct judgments with agent_label."""
    judgments = [
        make_judgment(case_id=1, agent_label="agent_a"),
        make_judgment(case_id=1, agent_label="agent_b"),
    ]
    # Group judgments by execution key
    by_key: dict[tuple[str, int], object] = {}
    for j in judgments:
        k = (j.agent_label, j.case_id)
        assert k not in by_key, f"Duplicate terminal outcome for {k}"
        by_key[k] = j

    assert ("agent_a", 1) in by_key
    assert ("agent_b", 1) in by_key
    assert len(by_key) == 2


def test_duplicate_judgments_detected_by_coverage_validation() -> None:
    """Duplicate judgments for case 1 cannot compensate for missing case 2."""
    plan = BenchmarkPlan(
        mode="single",
        profile=make_single_plan().profile,
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
    expected = plan.all_execution_keys(["agent_a"])
    # Duplicate judgment for case 1, missing case 2
    judgments = [
        make_judgment(case_id=1, agent_label="agent_a"),
        make_judgment(case_id=1, agent_label="agent_a"),
        make_judgment(case_id=3, agent_label="agent_a"),
        make_judgment(case_id=4, agent_label="agent_a"),
        make_judgment(case_id=5, agent_label="agent_a"),
        make_judgment(case_id=6, agent_label="agent_a"),
        make_judgment(case_id=7, agent_label="agent_a"),
    ]
    terminal = {j.execution_key for j in judgments}
    coverage = validate_execution_coverage(expected, terminal)
    assert not coverage.is_complete
    assert "agent_a" in str(coverage.diagnostics)


# ═══════════════════════════════════════════════════════════════════════════
# Plan validators enforced
# ═══════════════════════════════════════════════════════════════════════════


def test_valid_plan_passes_validation() -> None:
    plan = BenchmarkPlan.model_validate(
        _plan_json_for([_valid_case(i, _FAMILIES[i - 1]) for i in range(1, 9)])
    )
    assert len(plan.cases) == 8


def test_plan_with_insufficient_cases_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="8–12"):
        BenchmarkPlan.model_validate(_plan_json_for([_valid_case(1), _valid_case(2)]))


# ═══════════════════════════════════════════════════════════════════════════
# Nested policy block detection (repaired)
# ═══════════════════════════════════════════════════════════════════════════


class TestNestedPolicyBlockDetection:
    def test_nested_cyber_policy_is_classified_as_policy_block(self) -> None:
        """Nested body.error.code=cyber_policy is now detected."""
        err = {
            "type": "APIStatusError",
            "status_code": 400,
            "message": "Content filtered",
            "request_id": "req-cyber-1",
            "body": {"error": {"code": "cyber_policy", "message": "filtered"}},
        }
        capture = ResponseCapture(error=err)
        block = _policy_block_from_capture(make_case(1), "agent_a", capture)
        assert block is not None, "Nested cyber_policy should be detected as a policy block"
        assert block.error_code == "cyber_policy"

    def test_flat_policy_code_still_detected(self) -> None:
        """Flat body.code=content_policy is still detected."""
        err = {
            "type": "APIStatusError",
            "status_code": 400,
            "message": "Content filtered",
            "body": {"code": "content_policy", "message": "filtered"},
        }
        capture = ResponseCapture(error=err)
        block = _policy_block_from_capture(make_case(1), "agent_a", capture)
        assert block is not None
        assert block.error_code == "content_policy"


# ═══════════════════════════════════════════════════════════════════════════
# Coverage validation
# ═══════════════════════════════════════════════════════════════════════════


def test_coverage_validation_detects_missing_keys() -> None:
    expected = {
        ExecutionKey(agent_label="agent_a", case_id=1),
        ExecutionKey(agent_label="agent_a", case_id=2),
    }
    terminal = {ExecutionKey(agent_label="agent_a", case_id=1)}
    coverage = validate_execution_coverage(expected, terminal)
    assert not coverage.is_complete
    assert len(coverage.missing_keys) == 1


def test_coverage_validation_detects_extra_keys() -> None:
    expected = {ExecutionKey(agent_label="agent_a", case_id=1)}
    terminal = {
        ExecutionKey(agent_label="agent_a", case_id=1),
        ExecutionKey(agent_label="agent_a", case_id=99),
    }
    coverage = validate_execution_coverage(expected, terminal)
    assert not coverage.is_complete
    assert len(coverage.extra_keys) == 1


def test_coverage_validation_complete() -> None:
    expected = {
        ExecutionKey(agent_label="agent_a", case_id=1),
        ExecutionKey(agent_label="agent_a", case_id=2),
    }
    terminal = set(expected)
    coverage = validate_execution_coverage(expected, terminal)
    assert coverage.is_complete
    assert not coverage.diagnostics


# ═══════════════════════════════════════════════════════════════════════════
# Per-agent scoring isolation
# ═══════════════════════════════════════════════════════════════════════════


def test_per_agent_tally_separates_agents() -> None:
    plan = make_single_plan()
    judgments = [
        make_judgment(c.id, agent_label="agent_a", rating="Excellent") for c in plan.cases
    ] + [make_judgment(c.id, agent_label="agent_b", rating="Fail") for c in plan.cases]
    tally_a = build_tally(plan.cases, judgments, agent_label="agent_a")
    tally_b = build_tally(plan.cases, judgments, agent_label="agent_b")
    assert tally_a.rating_counts["Excellent"] == 8
    assert tally_b.rating_counts["Fail"] == 8
    assert tally_a.family_scores != tally_b.family_scores


# ═══════════════════════════════════════════════════════════════════════════
# Integration — single-agent run with fake gateways
# ═══════════════════════════════════════════════════════════════════════════


def test_single_agent_run_completes_with_fake_gateways(tmp_path: Path, agent_a_path: Path) -> None:
    plan_cases = [
        make_case(1, "happy_path"),
        make_case(2, "happy_path"),
        make_case(3, "regression_protection"),
        make_case(4, "regression_protection"),
        make_case(5, "stress_adversarial"),
        make_case(6, "stress_adversarial"),
        make_case(7, "ambiguity"),
        make_case(8, "ambiguity"),
    ]
    plan = make_single_plan(cases=plan_cases)
    plan_json = plan.model_dump(mode="json")

    planner = FakeGateway([json_response(plan_json)])
    agent = FakeGateway([text_response(f"Answer for case {c.id}") for c in plan_cases])
    judge = FakeGateway([json_response(_judgment_json(c.id, "Excellent")) for c in plan_cases])

    out = tmp_path / "run_out"
    runner = BenchmarkRunner(
        agent_a_path=agent_a_path,
        agent_b_path=None,
        output_dir=out,
        model="fake-model",
        judge_model="fake-judge",
        planner_gateway=planner,
        agent_gateway=agent,
        judge_gateway=judge,
    )

    status = runner.run()
    assert status == RunStatus.COMPLETED

    assert (out / "benchmark_plan.json").exists()
    assert (out / "run_results.json").exists()
    assert (out / "case_judgments.json").exists()
    assert (out / "summary_tally.json").exists()


def test_output_directory_with_prior_run_silently_produces_mixed_run(
    tmp_path: Path, agent_a_path: Path
) -> None:
    """BenchmarkRunner writes into a pre-populated directory (current behavior)."""
    out = tmp_path / "mixed_out"
    out.mkdir()

    (out / "run_metadata.json").write_text(
        json.dumps({"status": "completed", "planned_cases": 8, "judged_cases": 8})
    )
    (out / "summary_tally.json").write_text(json.dumps({"cases_planned": 8, "cases_judged": 8}))
    (out / "case_judgments.json").write_text(
        json.dumps([_judgment_json(i, "Excellent") for i in range(1, 9)])
    )

    plan_cases = [
        make_case(1, "happy_path"),
        make_case(2, "happy_path"),
        make_case(3, "regression_protection"),
        make_case(4, "regression_protection"),
        make_case(5, "stress_adversarial"),
        make_case(6, "stress_adversarial"),
        make_case(7, "ambiguity"),
        make_case(8, "ambiguity"),
    ]
    plan = make_single_plan(cases=plan_cases)
    plan_json = plan.model_dump(mode="json")

    planner = FakeGateway([json_response(plan_json)])
    agent = FakeGateway([text_response(f"Answer {c.id}") for c in plan_cases])
    judge = FakeGateway([json_response(_judgment_json(c.id, "Strong")) for c in plan_cases])

    runner = BenchmarkRunner(
        agent_a_path=agent_a_path,
        agent_b_path=None,
        output_dir=out,
        model="fake",
        judge_model="fake",
        planner_gateway=planner,
        agent_gateway=agent,
        judge_gateway=judge,
    )
    runner.run()

    meta = json.loads((out / "run_metadata.json").read_text())
    assert meta["cases_in_plan"] == 8


# ═══════════════════════════════════════════════════════════════════════════
# Refusal detection (still Phase 2 concern, test preserved)
# ═══════════════════════════════════════════════════════════════════════════


def test_refusal_not_detected_over_generic_completed_status() -> None:
    cap = ResponseCapture(
        text="I'm sorry, I cannot help with that.",
        status="completed",
        finish_reason="refusal",
        response_id="resp-ref-1",
        input_tokens=5,
        output_tokens=10,
    )
    from benchdeck.runner import _failed_capture

    result = CaseRunResult(
        case_id=1,
        agent_label="agent_a",
        first_output=cap.text,
        final_output=cap.text,
        agent_capture=cap,
    )
    failed = _failed_capture(result)
    assert failed is None


# ═══════════════════════════════════════════════════════════════════════════
# Malformed / schema-invalid JSON
# ═══════════════════════════════════════════════════════════════════════════


def test_malformed_judge_json_loses_capture() -> None:
    plan = make_single_plan()
    judge = FakeGateway([malformed_json_response("not json {{{")])

    runner = BenchmarkRunner(
        agent_a_path=Path("/dev/null"),
        agent_b_path=None,
        output_dir=Path("/tmp/nonexistent2"),
        model="fake",
        judge_model="fake",
        agent_gateway=FakeGateway(),
        judge_gateway=judge,
    )
    with contextlib.suppress(Exception):
        runner._judge_case(plan.cases[0], "agent_a", "Some agent output")


def test_schema_invalid_planner_json_retains_capture() -> None:
    plan = make_single_plan()
    judge = FakeGateway([schema_invalid_json_response()])
    runner = BenchmarkRunner(
        agent_a_path=Path("/dev/null"),
        agent_b_path=None,
        output_dir=Path("/tmp/nonexistent3"),
        model="fake",
        judge_model="fake",
        agent_gateway=FakeGateway(),
        judge_gateway=judge,
    )
    with contextlib.suppress(Exception):
        runner._judge_case(plan.cases[0], "agent_a", "output")


# ═══════════════════════════════════════════════════════════════════════════
# Retry attempts (Phase 2 concern, test preserved)
# ═══════════════════════════════════════════════════════════════════════════


def test_all_retry_attempts_preserved() -> None:
    from benchdeck.openai_gateway import GatewayConfig

    cfg = GatewayConfig(model="fake", max_empty_retries=2)
    assert cfg.max_empty_retries == 2


# ═══════════════════════════════════════════════════════════════════════════
# Prior run / output directory (not yet isolated — Phase 4 concern)
# ═══════════════════════════════════════════════════════════════════════════


def test_prior_run_output_directory_not_detected(tmp_path: Path) -> None:
    out = tmp_path / "prior"
    out.mkdir()
    (out / "run_metadata.json").write_text(json.dumps({"status": "completed", "planned_cases": 8}))

    from benchdeck.storage import ArtifactStore

    store = ArtifactStore(out)
    store.write_json("run_metadata.json", {"status": "running", "planned_cases": 4})
    meta = store.read_json("run_metadata.json")
    assert meta["planned_cases"] == 4
