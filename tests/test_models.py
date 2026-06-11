"""Phase 0 regression tests for the data models.

These tests lock defects in BenchmarkPlan validation, identity
contracts, and data integrity before production repairs begin.
"""

from __future__ import annotations

import pytest
from conftest import (
    make_judgment,
    make_run_result,
)

from benchdeck.models import (
    BenchmarkCase,
    BenchmarkPlan,
    CaseJudgment,
    Family,
    ResponseCapture,
)


def _case_dict(case_id: int, title: str, family: str) -> dict[str, object]:
    return {
        "id": case_id,
        "title": title,
        "family": family,
        "purpose": "x",
        "test_prompt": "x",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Plan identity and contract
# ═══════════════════════════════════════════════════════════════════════════


class TestPlanValidation:
    def test_duplicate_case_ids_accepted(self) -> None:
        """BenchmarkPlan currently accepts duplicate case IDs."""
        plan = BenchmarkPlan.model_validate(
            {
                "mode": "single",
                "profile": {
                    "agent_name_a": "Test",
                    "inferred_mission": "x",
                },
                "cases": [
                    _case_dict(1, "A", "happy_path"),
                    _case_dict(1, "B", "regression_protection"),
                    _case_dict(3, "C", "stress_adversarial"),
                    _case_dict(4, "D", "ambiguity"),
                ],
            }
        )
        ids = [c.id for c in plan.cases]
        assert ids[0] == ids[1], "Duplicate case IDs not rejected"

    def test_empty_plan_accepted(self) -> None:
        """BenchmarkPlan currently accepts an empty cases list."""
        plan = BenchmarkPlan.model_validate(
            {
                "mode": "single",
                "profile": {"agent_name_a": "Test", "inferred_mission": "x"},
                "cases": [],
            }
        )
        assert len(plan.cases) == 0, "Empty plan not rejected"

    def test_missing_families_accepted(self) -> None:
        """Plans with fewer than 4 families are accepted."""
        plan = BenchmarkPlan.model_validate(
            {
                "mode": "single",
                "profile": {"agent_name_a": "Test", "inferred_mission": "x"},
                "cases": [
                    {
                        "id": 1,
                        "title": "A",
                        "family": "happy_path",
                        "purpose": "x",
                        "test_prompt": "x",
                    },
                    {
                        "id": 2,
                        "title": "B",
                        "family": "happy_path",
                        "purpose": "x",
                        "test_prompt": "x",
                    },
                ],
            }
        )
        families = {c.normalized_family for c in plan.cases}
        assert len(families) < 4, (
            f"Only {families} present but all four required families not enforced"
        )

    def test_negative_case_id_accepted(self) -> None:
        """BenchmarkCase accepts negative IDs."""
        case = BenchmarkCase.model_validate(
            {
                "id": -1,
                "title": "x",
                "family": "happy_path",
                "purpose": "x",
                "test_prompt": "x",
            }
        )
        assert case.id == -1, "Negative IDs not rejected"

    def test_zero_case_id_accepted(self) -> None:
        """BenchmarkCase accepts zero as an ID."""
        case = BenchmarkCase.model_validate(
            {
                "id": 0,
                "title": "x",
                "family": "happy_path",
                "purpose": "x",
                "test_prompt": "x",
            }
        )
        assert case.id == 0, "Zero ID not rejected"

    def test_extra_fields_silently_accepted(self) -> None:
        """BenchmarkPlan accepts unknown fields due to extra='allow'."""
        plan = BenchmarkPlan.model_validate(
            {
                "mode": "single",
                "profile": {"agent_name_a": "Test", "inferred_mission": "x"},
                "cases": [
                    {
                        "id": 1,
                        "title": "A",
                        "family": "happy_path",
                        "purpose": "x",
                        "test_prompt": "x",
                        "extraneous_field": "should be rejected",
                    },
                ],
                "bogus_top_level": 123,
            }
        )
        assert getattr(plan, "bogus_top_level", None) == 123, (
            "Extra top-level fields silently accepted"
        )


# ═══════════════════════════════════════════════════════════════════════════
# CaseJudgment identity
# ═══════════════════════════════════════════════════════════════════════════


class TestJudgmentIdentity:
    def test_case_judgment_lacks_agent_label_field(self) -> None:
        """CaseJudgment has no agent_label — judgments cannot be attributed
        to a specific agent in comparison mode."""
        j = make_judgment(case_id=1)
        assert not hasattr(j, "agent_label"), "CaseJudgment must carry agent_label for attribution"

    def test_judgment_model_silently_ignores_agent_label(self) -> None:
        """CaseJudgment silently ignores agent_label because it has no
        extra='allow' configuration — Pydantic v2 drops unknown fields."""
        j = CaseJudgment.model_validate(
            {
                "case_id": 1,
                "case_verdict": "ok",
                "agent_label": "agent_a",  # silently dropped
                "gate_check": {"status": "Pass", "reason": "ok"},
                "rubric": {"task_success": "Strong"},
                "overall_rating": "Strong",
                "why": "ok",
            }
        )
        assert getattr(j, "agent_label", None) is None, (
            "CaseJudgment silently drops agent_label — extra fields are ignored"
        )

    def test_case_run_result_has_agent_label(self) -> None:
        """CaseRunResult correctly carries agent_label (current good behaviour)."""
        r = make_run_result(case_id=1, agent_label="agent_a")
        assert r.agent_label == "agent_a"


# ═══════════════════════════════════════════════════════════════════════════
# ResponseCapture integrity
# ═══════════════════════════════════════════════════════════════════════════


class TestResponseCapture:
    def test_error_body_preserved(self) -> None:
        """ResponseCapture preserves the full error dict."""
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
        """finish_reason is a first-class field."""
        cap = ResponseCapture(
            text="ok",
            finish_reason="stop",
            status="completed",
        )
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
