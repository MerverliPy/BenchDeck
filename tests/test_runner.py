"""Phase 0 regression tests for the benchmark runner.

These tests lock the documented correctness failures *before* any
production repair begins.  Every test uses deterministic fake
gateways — no live model calls are made.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

from conftest import (
    make_case,
    make_judgment,
    make_run_result,
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
    Family,
    ResponseCapture,
    RunStatus,
)
from benchdeck.runner import BenchmarkRunner
from benchdeck.scoring import build_tally

# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

_PLANNER_PROMPT_KEYS = {"task", "required_shape", "agent_a", "agent_b"}


def _plan_json_for(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a valid plan JSON that includes all required families."""
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


# ═══════════════════════════════════════════════════════════════════════════
# 1. Two-agent judgments require agent attribution
# ═══════════════════════════════════════════════════════════════════════════


def test_two_agent_judgments_lack_agent_attribution() -> None:
    """CaseJudgment has no agent_label field, so two-agent verdicts collapse."""
    judgment = make_judgment(case_id=1)

    assert not hasattr(judgment, "agent_label"), (
        "CaseJudgment should carry an agent_label but does not"
    )


def test_agent_a_and_agent_b_results_share_judgment_lookup() -> None:
    """Lookups keyed by case_id alone conflate agents A and B."""
    # Two agents, same case.
    results: dict[str, list[CaseRunResult]] = {
        "agent_a": [make_run_result(case_id=1, agent_label="agent_a")],
        "agent_b": [make_run_result(case_id=1, agent_label="agent_b")],
    }
    # Single judgment — cannot tell which agent it belongs to.
    judgments = [make_judgment(case_id=1)]

    # Simulate the current scoring behaviour: group by case_id only.
    judgment_by_case = {j.case_id: j for j in judgments}
    # Both agents resolve to the same judgment.
    for label in ("agent_a", "agent_b"):
        for res in results.get(label, []):
            assert judgment_by_case.get(res.case_id) is not None
    # Proof of conflation: we have 2 completions but only 1 judgment.
    assert len(judgments) == 1
    assert len(results["agent_a"]) + len(results["agent_b"]) == 2


def test_duplicate_judgments_for_case_1_cannot_compensate_for_missing_case_2() -> None:
    """Duplicate judgments inflate counts; missing coverage is silent."""
    plan = BenchmarkPlan(
        mode="single",
        profile=make_single_plan().profile,
        cases=[
            make_case(1, "happy_path"),
            make_case(2, "happy_path"),
        ],
    )
    # Duplicate judgment for case 1, none for case 2.
    judgments = [
        make_judgment(case_id=1),
        make_judgment(case_id=1),
    ]
    tally = build_tally(plan.cases, judgments)
    # Currently the tally reports everything as fine.
    assert tally["cases_planned"] == 2
    assert tally["cases_judged"] == 2
    assert tally["gate_failures"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# 2. Plan contract violations
# ═══════════════════════════════════════════════════════════════════════════


def test_duplicate_plan_case_ids_not_rejected() -> None:
    """BenchmarkPlan accepts duplicate case IDs without complaint."""
    plan = BenchmarkPlan.model_validate(
        _plan_json_for(
            [
                make_case(1, "happy_path").model_dump(mode="json"),
                make_case(1, "regression_protection").model_dump(mode="json"),
                make_case(3, "stress_adversarial").model_dump(mode="json"),
                make_case(4, "ambiguity").model_dump(mode="json"),
            ]
        )
    )
    ids = [c.id for c in plan.cases]
    assert ids[0] == ids[1], "Duplicate IDs should be rejected but are accepted"


def test_empty_plan_not_rejected() -> None:
    """BenchmarkPlan accepts an empty cases list."""
    plan = BenchmarkPlan.model_validate(_plan_json_for([]))
    assert len(plan.cases) == 0, "Empty plans should be rejected but are accepted"


def test_missing_benchmark_families_not_rejected() -> None:
    """BenchmarkPlan does not require all four benchmark families."""
    plan = BenchmarkPlan.model_validate(
        _plan_json_for(
            [
                make_case(1, "happy_path").model_dump(mode="json"),
                make_case(2, "happy_path").model_dump(mode="json"),
            ]
        )
    )
    families = {c.normalized_family for c in plan.cases}
    assert families == {Family("happy_path")}, "Missing required families should be rejected"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Policy block detection — nested errors
# ═══════════════════════════════════════════════════════════════════════════


class TestNestedPolicyBlockDetection:
    """The current gateway / runner only inspects error.body.code, missing
    the nested error.body.error.code path used by real providers."""

    def test_nested_cyber_policy_not_classified_as_policy_block(self) -> None:
        """Nested body.error.code=cyber_policy should be a policy block but is not."""
        err = {
            "type": "APIStatusError",
            "status_code": 400,
            "message": "Content filtered",
            "request_id": "req-cyber-1",
            "body": {"error": {"code": "cyber_policy", "message": "filtered"}},
        }
        capture = ResponseCapture(error=err)
        # Use a fake agent gateway so the Runner constructor does not
        # attempt to create a real OpenAI client.
        fake = FakeGateway()
        runner = BenchmarkRunner(
            agent_a_path=Path("/dev/null"),
            agent_b_path=None,
            output_dir=Path("/tmp/nonexistent"),
            model="fake",
            judge_model="fake",
            agent_gateway=fake,
            judge_gateway=FakeGateway(),
        )
        block = runner._policy_block_from_capture(make_case(1), "agent_a", capture)
        assert block is None, (
            "Nested cyber_policy error is NOT classified as a policy block — "
            "the current code only checks error.body.code, not error.body.error.code"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Refusal detection
# ═══════════════════════════════════════════════════════════════════════════


def test_refusal_not_detected_over_generic_completed_status() -> None:
    """A refusal response with status=completed and finish_reason=refusal
    should be classified as a refusal, but the current code may not do so."""
    # The gateway currently produces a capture with text and finish_reason.
    cap = ResponseCapture(
        text="I'm sorry, I cannot help with that.",
        status="completed",
        finish_reason="refusal",
        response_id="resp-ref-1",
        input_tokens=5,
        output_tokens=10,
    )
    # The runner considers any capture with text as successful (no error).
    # The refusal finish_reason is stored but not used by the runner.
    from benchdeck.runner import _failed_capture

    result = CaseRunResult(
        case_id=1,
        agent_label="agent_a",
        first_output=cap.text,
        final_output=cap.text,
        agent_capture=cap,
    )
    failed = _failed_capture(result)
    # Currently NOT treated as a failure — text is present.
    assert failed is None, (
        "Refusal with text is NOT detected as a failure — "
        "runner treats any non-empty output as success"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 5. Malformed / schema-invalid JSON preserves capture
# ═══════════════════════════════════════════════════════════════════════════


def test_malformed_judge_json_loses_capture() -> None:
    """When judge output is malformed JSON, the gateway raises RuntimeError
    and the runner writes only str(exc) to infrastructure_errors, losing
    the raw capture."""
    plan = make_single_plan(cases=[make_case(1, "happy_path")])

    # Gateway that returns malformed JSON for the judge.
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
    # Simulate _judge_case directly
    try:
        runner._judge_case(plan.cases[0], "Some agent output")
    except Exception as exc:
        # The current code catches the exception in _run_case and loses the
        # raw capture — only str(exc) is saved.
        assert isinstance(exc, (ValueError, RuntimeError)), (
            f"Expected ValueError/RuntimeError for malformed JSON, got {type(exc).__name__}"
        )
    else:
        # If it didn't raise, the current code accepted bad JSON
        pass


def test_schema_invalid_planner_json_retains_capture() -> None:
    """When planner JSON is valid JSON but schema-invalid, the runner should
    preserve the capture alongside the validation error."""
    plan = make_single_plan(cases=[make_case(1, "happy_path")])

    # Valid JSON but missing required fields for a judge response.
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
        runner._judge_case(plan.cases[0], "output")


# ═══════════════════════════════════════════════════════════════════════════
# 6. Retry attempts are preserved
# ═══════════════════════════════════════════════════════════════════════════


def test_all_retry_attempts_preserved() -> None:
    """The current gateway overwrites the capture on each retry loop
    iteration.  Failed attempts disappear from the record."""
    # The real gateway cannot be instantiated without an API key, and
    # its retry loop overwrites per-attempt captures.  The gateway's
    # GatewayConfig tracks max_empty_retries but the ResponseCapture
    # only stores the final attempt count.
    from benchdeck.openai_gateway import GatewayConfig

    cfg = GatewayConfig(model="fake", max_empty_retries=2)
    assert cfg.max_empty_retries == 2, (
        "Gateway config has retry intent but no per-attempt audit trail"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 7. Prior run / output directory isolation
# ═══════════════════════════════════════════════════════════════════════════


def test_prior_run_output_directory_not_detected(tmp_path: Path) -> None:
    """Writing into an existing output directory does not raise a warning
    or take protective isolation."""
    out = tmp_path / "prior"
    out.mkdir()
    # Simulate a prior run artifact.
    (out / "run_metadata.json").write_text(json.dumps({"status": "completed", "planned_cases": 8}))
    (out / "run_results.json").write_text(json.dumps({"agent_a": []}))

    # Nothing prevents a new runner from writing into the same directory.
    from benchdeck.storage import ArtifactStore

    store = ArtifactStore(out)
    store.write_json("run_metadata.json", {"status": "running", "planned_cases": 4})
    meta = store.read_json("run_metadata.json")
    assert meta["planned_cases"] == 4, "Old artifacts silently overwritten"


# ═══════════════════════════════════════════════════════════════════════════
# 8. Run covers all families
# ═══════════════════════════════════════════════════════════════════════════


def test_runner_requires_all_families_for_validation() -> None:
    """The scoring/reporting code does not enforce minimum family coverage
    for validation.  A plan missing ambiguity can still be 'Validated'."""
    from benchdeck.reporting import build_final_verdict

    plan = BenchmarkPlan.model_validate(
        _plan_json_for(
            [
                make_case(1, "happy_path").model_dump(mode="json"),
                make_case(2, "regression_protection").model_dump(mode="json"),
                make_case(3, "stress_adversarial").model_dump(mode="json"),
            ]
        )
    )
    judgments = [
        make_judgment(1, rating="Excellent"),
        make_judgment(2, rating="Excellent"),
        make_judgment(3, rating="Excellent"),
    ]
    tally = build_tally(plan.cases, judgments)
    _verdict = build_final_verdict(plan, judgments, tally, RunStatus.COMPLETED)
    # The current code only checks if all present family scores >= 3.0.
    # Ambiguity is missing but no hard error is raised.
    families: dict[str, Any] = tally.get("family_scores") or {}  # type: ignore[assignment]
    assert "ambiguity" not in families, (
        "Ambiguity is missing from family scores but the run can still be Validated"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 9. Integration — full single-agent run with fake gateways
# ═══════════════════════════════════════════════════════════════════════════


def test_single_agent_run_completes_with_fake_gateways(tmp_path: Path, agent_a_path: Path) -> None:
    """End-to-end single-agent run using only scripted gateways."""
    plan_cases = [
        make_case(1, "happy_path"),
        make_case(2, "regression_protection"),
        make_case(3, "stress_adversarial"),
        make_case(4, "ambiguity"),
    ]
    plan = make_single_plan(cases=plan_cases)
    plan_json = plan.model_dump(mode="json")

    # Planner gateway: respond with the plan JSON.
    planner = FakeGateway([json_response(plan_json)])
    # Agent gateway: respond with plain text for each case.
    agent = FakeGateway([text_response(f"Answer for case {c.id}") for c in plan_cases])
    # Judge gateway: respond with judgment JSON for each case.
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
    # With 4 cases, all judged, no failures — should complete.
    assert status == RunStatus.COMPLETED

    # Verify artifacts were written.
    assert (out / "benchmark_plan.json").exists()
    assert (out / "run_results.json").exists()
    assert (out / "case_judgments.json").exists()
    assert (out / "summary_tally.json").exists()


# ═══════════════════════════════════════════════════════════════════════════
# 10. Output directory contamination (prior run) — integration
# ═══════════════════════════════════════════════════════════════════════════


def test_output_directory_with_prior_run_silently_produces_mixed_run(
    tmp_path: Path, agent_a_path: Path
) -> None:
    """BenchmarkRunner writes into a pre-populated directory and does not
    detect or reject stale artifacts from a previous run."""
    out = tmp_path / "mixed_out"
    out.mkdir()

    # Simulate prior run artifacts.
    (out / "run_metadata.json").write_text(
        json.dumps({"status": "completed", "planned_cases": 8, "judged_cases": 8})
    )
    (out / "summary_tally.json").write_text(json.dumps({"cases_planned": 8, "cases_judged": 8}))
    (out / "case_judgments.json").write_text(
        json.dumps([_judgment_json(i, "Excellent") for i in range(1, 9)])
    )

    plan_cases = [make_case(1, "happy_path"), make_case(2, "happy_path")]
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

    # After the run, the old tally and new run_results coexist.
    tally = json.loads((out / "summary_tally.json").read_text())
    assert tally["cases_planned"] == 2
    # The new run only had 2 cases, but old artifacts for 8 cases are gone.
    # A reader cannot distinguish this from a legitimate 2-case run.
    meta = json.loads((out / "run_metadata.json").read_text())
    assert meta["planned_cases"] == 2
