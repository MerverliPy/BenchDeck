"""Phase 1 tests for the data models.

Tests enforce the new identity contracts, plan validators, and
agent-attributed judgments.
"""

from __future__ import annotations

import pytest
from conftest import (
    make_case,
    make_comparison_plan,
    make_judgment,
    make_run_result,
    make_single_plan,
)

from benchdeck.models import (
    BenchmarkPlan,
    CaseJudgment,
    ExecutionKey,
    Family,
    ResponseCapture,
    RunMetadata,
)


def _cases(*families: str) -> list[dict[str, object]]:
    return [
        {
            "id": i,
            "title": f"Case {i}",
            "family": fam,
            "purpose": "x",
            "test_prompt": f"Prompt {i}",
            "hard_fail_conditions": ["f"],
        }
        for i, fam in enumerate(families, 1)
    ]


def _plan(**kw: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "mode": "single",
        "profile": {"agent_name_a": "Test", "inferred_mission": "x"},
        "cases": _cases(
            "happy_path",
            "happy_path",
            "regression_protection",
            "regression_protection",
            "stress_adversarial",
            "stress_adversarial",
            "ambiguity",
            "ambiguity",
        ),
    }
    defaults.update(kw)
    return defaults


# ═══════════════════════════════════════════════════════════════════════════
# Plan validation — positive
# ═══════════════════════════════════════════════════════════════════════════


class TestPlanValidation:
    def test_valid_eight_case_plan_accepted(self) -> None:
        plan = make_single_plan()
        assert len(plan.cases) == 8

    def test_plan_rejects_duplicate_case_ids(self) -> None:
        with pytest.raises(ValueError, match="Duplicate case ID"):
            BenchmarkPlan.model_validate(
                _plan(
                    cases=[
                        {
                            "id": 1,
                            "title": "A",
                            "family": "happy_path",
                            "purpose": "x",
                            "test_prompt": "x",
                            "hard_fail_conditions": ["f"],
                        },
                        {
                            "id": 1,
                            "title": "B",
                            "family": "regression_protection",
                            "purpose": "x",
                            "test_prompt": "x",
                            "hard_fail_conditions": ["f"],
                        },
                        *_cases(
                            "stress_adversarial",
                            "ambiguity",
                            "happy_path",
                            "happy_path",
                            "regression_protection",
                            "ambiguity",
                        ),
                    ]
                )
            )

    def test_plan_rejects_empty_cases(self) -> None:
        with pytest.raises(ValueError, match="at least one case"):
            BenchmarkPlan.model_validate(_plan(cases=[]))

    def test_plan_rejects_too_few_cases(self) -> None:
        with pytest.raises(ValueError, match="8–12"):
            BenchmarkPlan.model_validate(
                _plan(
                    cases=_cases(
                        "happy_path", "regression_protection", "stress_adversarial", "ambiguity"
                    )
                )
            )

    def test_plan_rejects_missing_families(self) -> None:
        with pytest.raises(ValueError, match="missing required families"):
            BenchmarkPlan.model_validate(_plan(cases=_cases(*(["happy_path"] * 8))))

    def test_plan_rejects_negative_case_id(self) -> None:
        with pytest.raises(ValueError):
            BenchmarkPlan.model_validate(
                _plan(
                    cases=[
                        {
                            "id": -1,
                            "title": "x",
                            "family": "happy_path",
                            "purpose": "x",
                            "test_prompt": "x",
                            "hard_fail_conditions": ["f"],
                        },
                        *_cases(
                            "happy_path",
                            "regression_protection",
                            "regression_protection",
                            "stress_adversarial",
                            "stress_adversarial",
                            "ambiguity",
                            "ambiguity",
                        ),
                    ]
                )
            )

    def test_plan_rejects_zero_case_id(self) -> None:
        with pytest.raises(ValueError):
            BenchmarkPlan.model_validate(
                _plan(
                    cases=[
                        {
                            "id": 0,
                            "title": "x",
                            "family": "happy_path",
                            "purpose": "x",
                            "test_prompt": "x",
                            "hard_fail_conditions": ["f"],
                        },
                        *_cases(
                            "happy_path",
                            "regression_protection",
                            "regression_protection",
                            "stress_adversarial",
                            "stress_adversarial",
                            "ambiguity",
                            "ambiguity",
                        ),
                    ]
                )
            )

    def test_plan_rejects_empty_prompt(self) -> None:
        with pytest.raises(ValueError, match="empty test_prompt"):
            fams = [
                "happy_path",
                "happy_path",
                "regression_protection",
                "regression_protection",
                "stress_adversarial",
                "stress_adversarial",
                "ambiguity",
                "ambiguity",
            ]
            bad_case = {
                "id": 1,
                "title": "Bad",
                "family": "happy_path",
                "purpose": "x",
                "test_prompt": "",
                "hard_fail_conditions": ["f"],
            }
            ok_cases = [
                {
                    "id": i,
                    "title": f"Case {i}",
                    "family": fams[i - 1],
                    "purpose": "x",
                    "test_prompt": f"Prompt {i}",
                    "hard_fail_conditions": ["f"],
                }
                for i in range(2, 9)
            ]
            BenchmarkPlan.model_validate(_plan(cases=[bad_case] + ok_cases))

    def test_plan_rejects_empty_title(self) -> None:
        with pytest.raises(ValueError, match="empty title"):
            fams = [
                "happy_path",
                "happy_path",
                "regression_protection",
                "regression_protection",
                "stress_adversarial",
                "stress_adversarial",
                "ambiguity",
                "ambiguity",
            ]
            bad_case = {
                "id": 1,
                "title": "",
                "family": "happy_path",
                "purpose": "x",
                "test_prompt": "x",
                "hard_fail_conditions": ["f"],
            }
            ok_cases = [
                {
                    "id": i,
                    "title": f"Case {i}",
                    "family": fams[i - 1],
                    "purpose": "x",
                    "test_prompt": f"Prompt {i}",
                    "hard_fail_conditions": ["f"],
                }
                for i in range(2, 9)
            ]
            BenchmarkPlan.model_validate(_plan(cases=[bad_case] + ok_cases))

    def test_plan_rejects_unknown_mode(self) -> None:
        with pytest.raises(ValueError, match="Unknown benchmark mode"):
            BenchmarkPlan.model_validate(_plan(mode="triple"))

    def test_plan_rejects_extra_fields(self) -> None:
        with pytest.raises(ValueError):
            fams = [
                "happy_path",
                "happy_path",
                "regression_protection",
                "regression_protection",
                "stress_adversarial",
                "stress_adversarial",
                "ambiguity",
                "ambiguity",
            ]
            bad_case = {
                "id": 1,
                "title": "Bad",
                "family": "happy_path",
                "purpose": "x",
                "test_prompt": "x",
                "extraneous_field": "bad",
                "hard_fail_conditions": ["f"],
            }
            ok_cases = [
                {
                    "id": i,
                    "title": f"Case {i}",
                    "family": fams[i - 1],
                    "purpose": "x",
                    "test_prompt": f"Prompt {i}",
                    "hard_fail_conditions": ["f"],
                }
                for i in range(2, 9)
            ]
            BenchmarkPlan.model_validate(_plan(cases=[bad_case] + ok_cases))

    def test_plan_rejects_no_hard_fail_conditions(self) -> None:
        with pytest.raises(ValueError, match="hard-fail condition"):
            families = [
                "happy_path",
                "happy_path",
                "regression_protection",
                "regression_protection",
                "stress_adversarial",
                "stress_adversarial",
                "ambiguity",
                "ambiguity",
            ]
            BenchmarkPlan.model_validate(
                _plan(
                    cases=[
                        {
                            "id": i,
                            "title": f"C{i}",
                            "family": families[i - 1],
                            "purpose": "x",
                            "test_prompt": f"p{i}",
                            "hard_fail_conditions": [],
                        }
                        for i in range(1, 9)
                    ]
                )
            )

    def test_plan_too_many_cases_rejected(self) -> None:
        with pytest.raises(ValueError, match="8–12"):
            BenchmarkPlan(
                mode="single",
                profile=make_single_plan().profile,
                cases=[make_case(i, "happy_path") for i in range(1, 14)],
            )


# ═══════════════════════════════════════════════════════════════════════════
# ExecutionKey
# ═══════════════════════════════════════════════════════════════════════════


class TestExecutionKey:
    def test_key_equality(self) -> None:
        k1 = ExecutionKey(agent_label="agent_a", case_id=1)
        k2 = ExecutionKey(agent_label="agent_a", case_id=1)
        k3 = ExecutionKey(agent_label="agent_b", case_id=1)
        assert k1 == k2
        assert k1 != k3
        assert hash(k1) == hash(k2)

    def test_key_in_set(self) -> None:
        keys = {ExecutionKey(agent_label="agent_a", case_id=1)}
        assert ExecutionKey(agent_label="agent_a", case_id=1) in keys
        assert ExecutionKey(agent_label="agent_b", case_id=1) not in keys

    def test_all_execution_keys_single_agent(self) -> None:
        plan = make_single_plan()
        keys = plan.all_execution_keys(["agent_a"])
        assert len(keys) == len(plan.cases)
        for case in plan.cases:
            assert ExecutionKey(agent_label="agent_a", case_id=case.id) in keys

    def test_all_execution_keys_two_agents(self) -> None:
        plan = make_comparison_plan()
        keys = plan.all_execution_keys(["agent_a", "agent_b"])
        assert len(keys) == len(plan.cases) * 2


# ═══════════════════════════════════════════════════════════════════════════
# CaseJudgment identity (now has agent_label)
# ═══════════════════════════════════════════════════════════════════════════


class TestJudgmentIdentity:
    def test_case_judgment_has_agent_label(self) -> None:
        j = make_judgment(case_id=1, agent_label="agent_a")
        assert j.agent_label == "agent_a"

    def test_case_judgment_execution_key(self) -> None:
        j = make_judgment(case_id=1, agent_label="agent_b")
        key = j.execution_key
        assert key.agent_label == "agent_b"
        assert key.case_id == 1

    def test_judgment_model_accepts_agent_label(self) -> None:
        j = CaseJudgment.model_validate(
            {
                "case_id": 1,
                "agent_label": "agent_a",
                "case_verdict": "ok",
                "gate_check": {"status": "Pass", "reason": "ok"},
                "rubric": {
                    "dimensions": [
                        {"dimension": d, "rating": "Strong"}
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
                },
                "overall_rating": "Strong",
                "why": "ok",
            }
        )
        assert j.agent_label == "agent_a"

    def test_case_run_result_has_agent_label(self) -> None:
        r = make_run_result(case_id=1, agent_label="agent_a")
        assert r.agent_label == "agent_a"
        assert r.execution_key == ExecutionKey(agent_label="agent_a", case_id=1)


# ═══════════════════════════════════════════════════════════════════════════
# ResponseCapture integrity
# ═══════════════════════════════════════════════════════════════════════════


class TestResponseCapture:
    def test_error_body_preserved(self) -> None:
        cap = ResponseCapture(
            error={
                "type": "APIStatusError",
                "status_code": 429,
                "message": "Rate limited",
                "request_id": "req-rl-1",
                "body": {"error": {"code": "rate_limit_exceeded"}},
            }
        )
        assert cap.error is not None
        assert cap.error["body"]["error"]["code"] == "rate_limit_exceeded"

    def test_finish_reason_preserved(self) -> None:
        cap = ResponseCapture(text="ok", finish_reason="stop", status="completed")
        assert cap.finish_reason == "stop"


# ═══════════════════════════════════════════════════════════════════════════
# Family normalisation
# ═══════════════════════════════════════════════════════════════════════════


class TestFamilyNormalization:
    def test_all_four_families_normalise(self) -> None:
        aliases = {
            "happy-path": Family.HAPPY_PATH,
            "happy_path": Family.HAPPY_PATH,
            "regression": Family.REGRESSION,
            "regression_protection": Family.REGRESSION,
            "stress": Family.STRESS,
            "stress-adversarial": Family.STRESS,
            "stress_adversarial": Family.STRESS,
            "ambiguity": Family.AMBIGUITY,
        }
        for raw, expected in aliases.items():
            assert Family.normalize(raw) == expected, f"{raw!r} → {expected}"

    def test_unknown_family_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported case family"):
            Family.normalize("bogus_family")


# ═══════════════════════════════════════════════════════════════════════════
# RunMetadata counters
# ═══════════════════════════════════════════════════════════════════════════


class TestRunMetadata:
    def test_new_counter_names(self) -> None:
        meta = RunMetadata(
            cases_in_plan=8,
            agents_in_run=1,
            executions_planned=8,
            executions_attempted=8,
            executions_model_completed=8,
            executions_judged=8,
            policy_blocks=0,
            infrastructure_failures=0,
        )
        assert meta.cases_in_plan == 8
        assert meta.executions_planned == 8

    def test_metadata_has_schema_version_and_run_id(self) -> None:
        meta = RunMetadata()
        assert meta.schema_version == "2.0"
        assert meta.run_id != ""


_FROZEN_FAMILIES = ["happy_path", "regression_protection", "stress_adversarial", "ambiguity"]


def _case_dict(case_id: int, family: str) -> dict[str, object]:
    return {
        "id": case_id,
        "title": f"Case {case_id}",
        "family": family,
        "purpose": "Test purpose",
        "test_prompt": f"Test prompt {case_id}",
        "hard_fail_conditions": ["condition"],
    }


def test_frozen_plan_allows_custom_case_count() -> None:
    """Frozen plans from --plan should not enforce the 8-12 case count."""
    plan = BenchmarkPlan.model_validate(
        {
            "mode": "single",
            "profile": {"agent_name_a": "Test", "inferred_mission": "x"},
            "provenance": {
                "source": "frozen",
                "plan_sha256": "abc123",
                "generated_at": "2025-01-01T00:00:00Z",
            },
            "cases": [_case_dict(i, _FROZEN_FAMILIES[(i - 1) % 4]) for i in range(1, 6)],
        }
    )
    assert len(plan.cases) == 5


def test_frozen_plan_allows_large_case_count() -> None:
    """Frozen plans from --plan should not reject >12 cases."""
    plan = BenchmarkPlan.model_validate(
        {
            "mode": "single",
            "profile": {"agent_name_a": "Test", "inferred_mission": "x"},
            "provenance": {
                "source": "frozen",
                "plan_sha256": "abc123",
                "generated_at": "2025-01-01T00:00:00Z",
            },
            "cases": [_case_dict(i, _FROZEN_FAMILIES[(i - 1) % 4]) for i in range(1, 16)],
        }
    )
    assert len(plan.cases) == 15


def test_generated_plan_still_rejects_too_few_cases() -> None:
    """Generated plans (no frozen provenance) still enforce 8-12 count."""
    import pytest

    with pytest.raises(ValueError, match="8–12"):
        BenchmarkPlan.model_validate(
            {
                "mode": "single",
                "profile": {"agent_name_a": "Test", "inferred_mission": "x"},
                "cases": [_case_dict(i, _FROZEN_FAMILIES[(i - 1) % 4]) for i in range(1, 5)],
            }
        )
