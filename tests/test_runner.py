"""Phase 2 tests for the benchmark runner — gateway integration and refusal/error handling.

Tests prove that the runner correctly consumes GenerationResult,
detects refusals before generic completion, classifies errors, and
preserves evidence across all gateway outcomes.
All tests use deterministic fake gateways — no live model calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import (
    make_case,
    make_comparison_plan,
    make_judgment,
    make_single_plan,
)
from fakes import (
    FakeGateway,
    error_attempt,
    error_response,
    json_response,
    malformed_json_response,
    policy_error,
    refusal_response,
    retry_sequence,
    schema_invalid_json_response,
    text_response,
)

from benchdeck.models import (
    BenchmarkPlan,
    CaseRunResult,
    ErrorCategory,
    ExecutionKey,
    ResponseCapture,
    RunStatus,
)
from benchdeck.openai_gateway import GatewayConfig
from benchdeck.runner import (
    BenchmarkRunner,
    _failed_capture,
    _policy_block_from_capture,
    _result_to_capture,
)
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
        "rubric_dimensions": [
            {"dimension": "mission_fidelity", "rating": rating, "evidence": "ok"},
            {"dimension": "task_success", "rating": rating, "evidence": "ok"},
            {"dimension": "priority_adherence", "rating": rating, "evidence": "ok"},
            {"dimension": "ambiguity_handling", "rating": rating, "evidence": "ok"},
            {"dimension": "process_discipline", "rating": rating, "evidence": "ok"},
            {"dimension": "tool_discipline", "rating": rating, "evidence": "ok"},
            {"dimension": "robustness", "rating": rating, "evidence": "ok"},
            {"dimension": "regression_safety", "rating": rating, "evidence": "ok"},
        ],
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
# ExecutionKey and agent identity (unchanged from Phase 1)
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
    judgments = [
        make_judgment(case_id=1, agent_label="agent_a"),
        make_judgment(case_id=1, agent_label="agent_b"),
    ]
    by_key: dict[tuple[str, int], object] = {}
    for j in judgments:
        k = (j.agent_label, j.case_id)
        assert k not in by_key, f"Duplicate terminal outcome for {k}"
        by_key[k] = j
    assert ("agent_a", 1) in by_key
    assert ("agent_b", 1) in by_key
    assert len(by_key) == 2


def test_duplicate_judgments_detected_by_coverage_validation() -> None:
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
# Plan validators enforced (unchanged from Phase 1)
# ═══════════════════════════════════════════════════════════════════════════


def test_valid_plan_passes_validation() -> None:
    plan = BenchmarkPlan.model_validate(
        _plan_json_for([_valid_case(i, _FAMILIES[i - 1]) for i in range(1, 9)])
    )
    assert len(plan.cases) == 8


def test_plan_with_insufficient_cases_rejected() -> None:
    with pytest.raises(ValueError, match="8–12"):
        BenchmarkPlan.model_validate(_plan_json_for([_valid_case(1), _valid_case(2)]))


# ═══════════════════════════════════════════════════════════════════════════
# Nested policy block detection (repaired in Phase 1)
# ═══════════════════════════════════════════════════════════════════════════


class TestNestedPolicyBlockDetection:
    def test_nested_cyber_policy_is_classified_as_policy_block(self) -> None:
        err = {
            "type": "APIStatusError",
            "status_code": 400,
            "message": "Content filtered",
            "request_id": "req-cyber-1",
            "body": {"error": {"code": "cyber_policy", "message": "filtered"}},
        }
        capture = ResponseCapture(error=err)
        block = _policy_block_from_capture(make_case(1), "agent_a", capture)
        assert block is not None
        assert block.error_code == "cyber_policy"

    def test_flat_policy_code_still_detected(self) -> None:
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
# Coverage validation (unchanged)
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
# Per-agent scoring isolation (unchanged)
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
        model="fake",
        judge_model="fake",
        planner_gateway=planner,
        agent_gateway=agent,
        judge_gateway=judge,
        overwrite=True,
    )

    status = runner.run()
    assert status == RunStatus.COMPLETED

    actual_out = runner.output_dir
    assert (actual_out / "benchmark_plan.json").exists()
    assert (actual_out / "run_results.json").exists()
    assert (actual_out / "case_judgments.json").exists()
    assert (actual_out / "summary_tally.json").exists()


def test_output_directory_with_prior_run_silently_produces_mixed_run(
    tmp_path: Path, agent_a_path: Path
) -> None:
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
        overwrite=True,
    )
    runner.run()

    actual_out = runner.output_dir
    meta = json.loads((actual_out / "run_metadata.json").read_text())
    assert meta["cases_in_plan"] == 8

    assert (out / "run_metadata.json").read_text().startswith('{"status": "completed"'), (
        "Prior run files must not be overwritten"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Refusal detection — refusal now detected before generic completion
# ═══════════════════════════════════════════════════════════════════════════


def test_refusal_is_now_detected_as_terminal_error() -> None:
    """After Phase 2, GenerationResult.has_refusal is True for refusals,
    and the terminal_error has ErrorCategory.REFUSAL."""
    gw = FakeGateway([refusal_response("I cannot help with that.")])
    result = gw.generate(instructions="x", input_text="y")
    assert result.has_refusal is True
    assert result.terminal_error is not None
    assert result.terminal_error.category == ErrorCategory.REFUSAL
    assert result.value is None


def test_runner_refusal_produces_infrastructure_flag_false() -> None:
    """A refusal is not an infrastructure error — it's a semantic refusal."""
    capture = ResponseCapture(
        text="I refuse to answer.",
        status="completed",
        finish_reason="refusal",
        response_id="resp-r1",
        input_tokens=5,
        output_tokens=10,
    )
    result = CaseRunResult(
        case_id=1,
        agent_label="agent_a",
        first_output=capture.text,
        final_output=capture.text,
        agent_capture=capture,
    )
    failed = _failed_capture(result)
    assert failed is None  # no infrastructure error


# ═══════════════════════════════════════════════════════════════════════════
# Malformed / schema-invalid JSON — evidence preserved (repaired)
# ═══════════════════════════════════════════════════════════════════════════


def test_malformed_judge_json_preserves_parse_error_evidence() -> None:
    """generate_json with malformed text returns parse_error, attempt record."""
    gw = FakeGateway([malformed_json_response("not json {{{")])
    result = gw.generate_json(instructions="j", input_text="i")
    assert result.value is None
    assert result.parse_error is not None
    assert len(result.attempts) == 1  # attempt evidence preserved
    assert result.attempts[0].output_text == "not json {{{"


def test_schema_invalid_planner_json_preserves_raw_data() -> None:
    """Valid JSON with wrong schema still returns the dict — validation at model level."""
    gw = FakeGateway([schema_invalid_json_response({"unknown_field": 42})])
    result = gw.generate_json(instructions="p", input_text="i")
    assert result.value == {"unknown_field": 42}
    assert result.parse_error is None
    assert len(result.attempts) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Retry ownership — deterministic, observable
# ═══════════════════════════════════════════════════════════════════════════


def test_gateway_config_explicit_max_retries() -> None:
    cfg = GatewayConfig(model="fake", max_retries=2, timeout_s=30.0)
    assert cfg.max_retries == 2
    assert cfg.timeout_s == 30.0


def test_retry_errors_preserve_attempt_telemetry() -> None:
    """Each retry attempt is individually recorded and not overwritten."""
    gw = FakeGateway(
        [
            retry_sequence(
                error_attempt(
                    ErrorCategory.TIMEOUT,
                    "timeout 1",
                    http_status=408,
                    retryable=True,
                ),
                error_attempt(
                    ErrorCategory.RATE_LIMIT,
                    "rate limited",
                    http_status=429,
                    retryable=True,
                ),
            )
        ]
    )
    result = gw.generate(instructions="x", input_text="y")
    assert result.terminal_error is not None
    # Last error wins (the RATE_LIMIT after TIMEOUT retry)
    assert result.terminal_error.category == ErrorCategory.RATE_LIMIT
    assert result.total_http_attempts == 2
    assert len(result.attempts) == 2
    assert result.attempts[0].error is not None
    assert result.attempts[0].error.category == ErrorCategory.TIMEOUT
    assert result.attempts[1].error is not None
    assert result.attempts[1].error.category == ErrorCategory.RATE_LIMIT


def test_policy_error_never_retryable_in_gateway() -> None:
    gw = FakeGateway(
        [
            policy_error(
                code="cyber_policy",
                message="Blocked",
                http_status=400,
                request_id="req-pol-1",
            )
        ]
    )
    result = gw.generate(instructions="x", input_text="y")
    assert result.terminal_error is not None
    assert result.terminal_error.category == ErrorCategory.POLICY
    assert result.terminal_error.retryable is False
    assert result.total_http_attempts == 1  # only one attempt, no retry


# ═══════════════════════════════════════════════════════════════════════════
# Result-to-capture conversion preserves evidence
# ═══════════════════════════════════════════════════════════════════════════


def test_result_to_capture_preserves_text_and_ids() -> None:
    gw = FakeGateway(
        [
            text_response(
                "Hello world",
                response_id="resp-abc",
                request_id="req-xyz",
                input_tokens=10,
                output_tokens=20,
            )
        ]
    )
    result = gw.generate(instructions="x", input_text="y")
    capture = _result_to_capture(result)
    assert capture.text == "Hello world"
    assert capture.response_id == "resp-abc"
    assert capture.request_id == "req-xyz"
    assert capture.input_tokens == 10
    assert capture.output_tokens == 20
    assert capture.attempts == 1
    assert capture.error is None


def test_result_to_capture_preserves_error() -> None:
    gw = FakeGateway([error_response(ErrorCategory.TIMEOUT, "too slow", http_status=408)])
    result = gw.generate(instructions="x", input_text="y")
    capture = _result_to_capture(result)
    assert capture.error is not None
    assert capture.error.get("status_code") == 408
    assert capture.attempts == 1


def test_result_to_capture_preserves_refusal() -> None:
    gw = FakeGateway([refusal_response("I cannot do that.")])
    result = gw.generate(instructions="x", input_text="y")
    capture = _result_to_capture(result)
    assert capture.text == "I cannot do that."
    assert capture.finish_reason == "refusal"
    assert capture.error is not None
    assert capture.error["type"] == "Refusal"


# ═══════════════════════════════════════════════════════════════════════════
# Run integration with error scenarios
# ═══════════════════════════════════════════════════════════════════════════


def test_runner_handles_agent_refusal(tmp_path: Path, agent_a_path: Path) -> None:
    """When the agent returns a refusal, the run should record it as a
    terminal outcome but not crash."""
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
    # All agent calls return refusal
    agent = FakeGateway([refusal_response("I refuse.") for _ in plan_cases])
    judge = FakeGateway([json_response(_judgment_json(c.id, "Fail")) for c in plan_cases])

    out = tmp_path / "refusal_out"
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

    status = runner.run()
    # With all refusals, coverage is incomplete → INCONCLUSIVE or COMPLETED_WITH_FAILURES
    assert status in {RunStatus.INCONCLUSIVE, RunStatus.COMPLETED_WITH_FAILURES}


def test_runner_records_policy_block(tmp_path: Path, agent_a_path: Path) -> None:
    """When the agent hits a policy block, it should be recorded as a PolicyBlock."""
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
    agent = FakeGateway([policy_error("cyber_policy", "Blocked") for _ in plan_cases])
    judge = FakeGateway([])

    out = tmp_path / "policy_out"
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

    status = runner.run()
    assert status == RunStatus.INCONCLUSIVE
    actual_out = runner.output_dir
    assert (actual_out / "policy_blocks.json").exists()
    blocks_data = json.loads((actual_out / "policy_blocks.json").read_text())
    assert len(blocks_data) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Prior run / output directory (Phase 4 concern, test preserved)
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


# ═══════════════════════════════════════════════════════════════════════════
# Integration — comparison mode with fake gateways
# ═══════════════════════════════════════════════════════════════════════════


def test_comparison_run_completes_with_fake_gateways(tmp_path: Path) -> None:
    agent_a = tmp_path / "agent_a.md"
    agent_a.write_text("# Agent A\n\nYou are a coding assistant.\n", encoding="utf-8")
    agent_b = tmp_path / "agent_b.md"
    agent_b.write_text("# Agent B\n\nYou are a code reviewer.\n", encoding="utf-8")

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
    plan = BenchmarkPlan(
        mode="comparison",
        profile=make_comparison_plan().profile,
        cases=plan_cases,
    )
    plan_json = plan.model_dump(mode="json")

    planner = FakeGateway([json_response(plan_json)])
    agent = FakeGateway(
        [text_response(f"Answer A for case {c.id}") for c in plan_cases]
        + [text_response(f"Answer B for case {c.id}") for c in plan_cases]
    )
    judge = FakeGateway(
        [json_response(_judgment_json(c.id, "Strong")) for c in plan_cases]
        + [json_response(_judgment_json(c.id, "Excellent")) for c in plan_cases]
    )

    out = tmp_path / "comparison_out"
    runner = BenchmarkRunner(
        agent_a_path=agent_a,
        agent_b_path=agent_b,
        output_dir=out,
        model="fake-model",
        judge_model="fake-judge",
        planner_gateway=planner,
        agent_gateway=agent,
        judge_gateway=judge,
    )

    status = runner.run()
    assert status == RunStatus.COMPLETED

    actual_out = runner.output_dir
    assert (actual_out / "summary_tally.json").exists()
    tally = json.loads((actual_out / "summary_tally.json").read_text())
    assert "agent_a" in tally
    assert "agent_b" in tally

    assert (actual_out / "final_verdict.json").exists()
    verdict = json.loads((actual_out / "final_verdict.json").read_text())
    comparison = verdict.get("comparison")
    assert comparison is not None, "final_verdict.json must have a comparison block"
    assert comparison.get("valid") is True, "comparison verdict must be valid"


# ═══════════════════════════════════════════════════════════════════════════
# Output directory isolation (Phase 4 / AUD-P2-005)
# ═══════════════════════════════════════════════════════════════════════════


def test_run_writes_to_run_id_subdirectory(tmp_path: Path, agent_a_path: Path) -> None:
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

    out = tmp_path / "root_out"
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

    assert runner.output_dir != out
    assert runner.output_dir.parent == out
    assert (runner.output_dir / "run_metadata.json").exists()
    assert runner.metadata.run_id in str(runner.output_dir)


def test_direct_dir_with_artifacts_rejected_without_overwrite(
    tmp_path: Path, agent_a_path: Path
) -> None:
    direct_dir = tmp_path / "old_run"
    direct_dir.mkdir()
    (direct_dir / "run_metadata.json").write_text(json.dumps({"status": "completed"}))

    with pytest.raises(RuntimeError, match="already contains run artifacts"):
        BenchmarkRunner(
            agent_a_path=agent_a_path,
            agent_b_path=None,
            output_dir=direct_dir,
            model="fake",
            judge_model="fake",
            planner_gateway=FakeGateway([]),
            agent_gateway=FakeGateway([]),
            judge_gateway=FakeGateway([]),
        )


def test_overwrite_allows_existing_nonempty_dir(tmp_path: Path, agent_a_path: Path) -> None:
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

    out = tmp_path / "overwrite_out"
    out.mkdir()

    runner1 = BenchmarkRunner(
        agent_a_path=agent_a_path,
        agent_b_path=None,
        output_dir=out,
        model="fake",
        judge_model="fake",
        planner_gateway=planner,
        agent_gateway=FakeGateway([text_response(f"First run {c.id}") for c in plan_cases]),
        judge_gateway=FakeGateway(
            [json_response(_judgment_json(c.id, "Excellent")) for c in plan_cases]
        ),
    )
    runner1.run()
    run1_dir = runner1.output_dir
    assert run1_dir.exists()

    runner2 = BenchmarkRunner(
        agent_a_path=agent_a_path,
        agent_b_path=None,
        output_dir=out,
        model="fake",
        judge_model="fake",
        planner_gateway=planner,
        agent_gateway=agent,
        judge_gateway=judge,
        overwrite=True,
    )
    runner2.run()
    run2_dir = runner2.output_dir
    assert run2_dir.exists()
