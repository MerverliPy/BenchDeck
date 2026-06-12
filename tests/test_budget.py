"""Tests for budget tracking and preflight checks."""

from __future__ import annotations

from benchdeck.budget import (
    BudgetLimits,
    BudgetTracker,
    _int_or_none,
    estimate_executions,
    estimate_logical_calls,
    preflight_check,
)


class TestBudgetLimits:
    def test_from_dict_all_none(self) -> None:
        limits = BudgetLimits.from_dict({})
        assert limits.max_logical_requests is None
        assert limits.max_http_attempts is None
        assert limits.max_total_input_tokens is None
        assert limits.max_total_output_tokens is None

    def test_from_dict_with_values(self) -> None:
        limits = BudgetLimits.from_dict(
            {
                "max_logical_requests": 50,
                "max_http_attempts": 100,
                "max_total_input_tokens": 50000,
                "max_total_output_tokens": 25000,
                "max_output_tokens_planner": 4000,
            }
        )
        assert limits.max_logical_requests == 50
        assert limits.max_http_attempts == 100
        assert limits.max_total_input_tokens == 50000
        assert limits.max_total_output_tokens == 25000
        assert limits.max_output_tokens_planner == 4000

    def test_from_dict_converts_strings(self) -> None:
        limits = BudgetLimits.from_dict({"max_logical_requests": "42"})
        assert limits.max_logical_requests == 42

    def test_from_dict_converts_floats(self) -> None:
        limits = BudgetLimits.from_dict({"max_logical_requests": 99.0})
        assert limits.max_logical_requests == 99

    def test_from_dict_ignores_invalid_values(self) -> None:
        limits = BudgetLimits.from_dict({"max_logical_requests": "not_a_number"})
        assert limits.max_logical_requests is None

    def test_from_dict_ignores_unknown_keys(self) -> None:
        limits = BudgetLimits.from_dict({"unknown_field": 123})
        assert limits.max_logical_requests is None


class TestBudgetTracker:
    def test_record_call_increments_counters(self) -> None:
        tracker = BudgetTracker(limits=BudgetLimits())
        tracker.record_call(stage="agent", input_tokens=100, output_tokens=50, http_attempts=2)
        assert tracker.logical_calls == 1
        assert tracker.http_attempts == 2
        assert tracker.total_input_tokens == 100
        assert tracker.total_output_tokens == 50

    def test_record_call_tracks_per_stage(self) -> None:
        tracker = BudgetTracker(limits=BudgetLimits())
        tracker.record_call(stage="planner", input_tokens=10, output_tokens=20)
        tracker.record_call(stage="agent", input_tokens=30, output_tokens=40)
        tracker.record_call(stage="judge", input_tokens=50, output_tokens=60)

        assert tracker.input_tokens_planner == 10
        assert tracker.output_tokens_planner == 20
        assert tracker.input_tokens_agent == 30
        assert tracker.output_tokens_agent == 40
        assert tracker.input_tokens_judge == 50
        assert tracker.output_tokens_judge == 60

    def test_limits_not_exhausted_by_default(self) -> None:
        tracker = BudgetTracker(limits=BudgetLimits())
        tracker.record_call(stage="agent", input_tokens=1000, output_tokens=500)
        assert not tracker.exhausted
        assert tracker.exhausted_reason == ""

    def test_exhausted_on_logical_requests(self) -> None:
        limits = BudgetLimits(max_logical_requests=3)
        tracker = BudgetTracker(limits=limits)
        for _ in range(3):
            tracker.record_call(stage="agent", input_tokens=1, output_tokens=1)
        assert not tracker.exhausted
        tracker.record_call(stage="agent", input_tokens=1, output_tokens=1)
        assert tracker.exhausted
        assert "logical requests" in tracker.exhausted_reason

    def test_exhausted_on_http_attempts(self) -> None:
        limits = BudgetLimits(max_http_attempts=5)
        tracker = BudgetTracker(limits=limits)
        for _ in range(5):
            tracker.record_call(stage="agent", input_tokens=1, output_tokens=1)
        assert not tracker.exhausted
        tracker.record_call(stage="agent", input_tokens=1, output_tokens=1)
        assert tracker.exhausted
        assert "HTTP attempts" in tracker.exhausted_reason

    def test_exhausted_on_input_tokens(self) -> None:
        limits = BudgetLimits(max_total_input_tokens=100)
        tracker = BudgetTracker(limits=limits)
        tracker.record_call(stage="agent", input_tokens=100, output_tokens=1)
        assert not tracker.exhausted
        tracker.record_call(stage="agent", input_tokens=1, output_tokens=1)
        assert tracker.exhausted
        assert "input tokens" in tracker.exhausted_reason

    def test_exhausted_on_output_tokens(self) -> None:
        limits = BudgetLimits(max_total_output_tokens=50)
        tracker = BudgetTracker(limits=limits)
        tracker.record_call(stage="agent", input_tokens=1, output_tokens=50)
        assert not tracker.exhausted
        tracker.record_call(stage="agent", input_tokens=1, output_tokens=1)
        assert tracker.exhausted
        assert "output tokens" in tracker.exhausted_reason

    def test_multiple_limit_violations(self) -> None:
        limits = BudgetLimits(max_logical_requests=1, max_total_input_tokens=50)
        tracker = BudgetTracker(limits=limits)
        tracker.record_call(stage="agent", input_tokens=100, output_tokens=100)
        assert tracker.exhausted
        assert "Budget exhausted" in tracker.exhausted_reason

    def test_exhausted_stays_exhausted(self) -> None:
        limits = BudgetLimits(max_logical_requests=1)
        tracker = BudgetTracker(limits=limits)
        tracker.record_call(stage="agent", input_tokens=10, output_tokens=10)
        tracker.record_call(stage="agent", input_tokens=10, output_tokens=10)
        assert tracker.exhausted
        reason = tracker.exhausted_reason
        tracker.record_call(stage="agent", input_tokens=10, output_tokens=10)
        assert tracker.exhausted
        assert tracker.exhausted_reason == reason

    def test_usage_report(self) -> None:
        tracker = BudgetTracker(limits=BudgetLimits())
        tracker.record_call(stage="planner", input_tokens=10, output_tokens=20, http_attempts=2)
        tracker.record_call(stage="agent", input_tokens=30, output_tokens=40, http_attempts=3)
        report = tracker.usage_report
        assert report.prompt_tokens == 40
        assert report.completion_tokens == 60
        assert report.total_tokens == 100
        assert report.requests == 5

    def test_no_limits_never_exhausts(self) -> None:
        tracker = BudgetTracker(limits=BudgetLimits())
        for _ in range(1000):
            tracker.record_call(stage="agent", input_tokens=10000, output_tokens=10000)
        assert not tracker.exhausted


class TestEstimates:
    def test_estimate_executions(self) -> None:
        assert estimate_executions(10, 1) == 10
        assert estimate_executions(10, 2) == 20
        assert estimate_executions(0, 5) == 0

    def test_estimate_logical_calls_no_plan(self) -> None:
        calls = estimate_logical_calls(10, 1, plan_generated=False, clarification_rate=0.0)
        assert calls == 20  # 10 agent + 10 judge

    def test_estimate_logical_calls_with_plan(self) -> None:
        calls = estimate_logical_calls(10, 1, plan_generated=True, clarification_rate=0.0)
        assert calls == 21  # 1 planner + 10 agent + 10 judge

    def test_estimate_logical_calls_with_clarifications(self) -> None:
        calls = estimate_logical_calls(10, 1, plan_generated=False, clarification_rate=0.2)
        assert calls == 22  # 10 agent + 2 clarification + 10 judge

    def test_estimate_logical_calls_two_agents(self) -> None:
        calls = estimate_logical_calls(10, 2, plan_generated=False, clarification_rate=0.0)
        assert calls == 40  # 20 agent + 20 judge


class TestPreflight:
    def test_preflight_no_limits(self) -> None:
        warnings = preflight_check(BudgetLimits(), 10, 1)
        assert warnings == []

    def test_preflight_under_limit(self) -> None:
        limits = BudgetLimits(max_logical_requests=100)
        warnings = preflight_check(limits, 10, 1)
        assert warnings == []

    def test_preflight_over_limit(self) -> None:
        limits = BudgetLimits(max_logical_requests=10)
        warnings = preflight_check(limits, 20, 2)
        assert len(warnings) == 1
        assert "budget" in warnings[0].lower()

    def test_preflight_only_checks_logical_requests(self) -> None:
        limits = BudgetLimits(max_http_attempts=1)
        warnings = preflight_check(limits, 100, 10)
        assert warnings == []


class TestIntOrNone:
    def test_none(self) -> None:
        assert _int_or_none(None) is None

    def test_int(self) -> None:
        assert _int_or_none(42) == 42

    def test_str_valid(self) -> None:
        assert _int_or_none("42") == 42

    def test_str_invalid(self) -> None:
        assert _int_or_none("abc") is None

    def test_float(self) -> None:
        assert _int_or_none(42.0) == 42

    def test_float_truncation(self) -> None:
        assert _int_or_none(42.9) == 42

    def test_other_type(self) -> None:
        assert _int_or_none([]) is None
