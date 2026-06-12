from __future__ import annotations

import logging
from dataclasses import dataclass

from .models import TokenUsage

logger = logging.getLogger("benchdeck.budget")


@dataclass
class BudgetLimits:
    max_output_tokens_planner: int | None = None
    max_output_tokens_agent: int | None = None
    max_output_tokens_judge: int | None = None
    max_logical_requests: int | None = None
    max_http_attempts: int | None = None
    max_total_input_tokens: int | None = None
    max_total_output_tokens: int | None = None

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> BudgetLimits:
        return cls(
            max_output_tokens_planner=_int_or_none(d.get("max_output_tokens_planner")),
            max_output_tokens_agent=_int_or_none(d.get("max_output_tokens_agent")),
            max_output_tokens_judge=_int_or_none(d.get("max_output_tokens_judge")),
            max_logical_requests=_int_or_none(d.get("max_logical_requests")),
            max_http_attempts=_int_or_none(d.get("max_http_attempts")),
            max_total_input_tokens=_int_or_none(d.get("max_total_input_tokens")),
            max_total_output_tokens=_int_or_none(d.get("max_total_output_tokens")),
        )


@dataclass
class BudgetTracker:
    limits: BudgetLimits

    logical_calls: int = 0
    http_attempts: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    input_tokens_planner: int = 0
    output_tokens_planner: int = 0
    input_tokens_agent: int = 0
    output_tokens_agent: int = 0
    input_tokens_judge: int = 0
    output_tokens_judge: int = 0

    exhausted: bool = False
    exhausted_reason: str = ""

    def record_call(
        self,
        *,
        stage: str,
        input_tokens: int,
        output_tokens: int,
        http_attempts: int = 1,
    ) -> None:
        self.logical_calls += 1
        self.http_attempts += http_attempts
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        if stage == "planner":
            self.input_tokens_planner += input_tokens
            self.output_tokens_planner += output_tokens
        elif stage == "agent":
            self.input_tokens_agent += input_tokens
            self.output_tokens_agent += output_tokens
        elif stage == "judge":
            self.input_tokens_judge += input_tokens
            self.output_tokens_judge += output_tokens

        self._check_limits(stage)

    def _check_limits(self, stage: str) -> None:
        if self.exhausted:
            return
        reasons: list[str] = []
        if (
            self.limits.max_logical_requests is not None
            and self.logical_calls > self.limits.max_logical_requests
        ):
            reasons.append(
                f"logical requests ({self.logical_calls} > {self.limits.max_logical_requests})"
            )
        if (
            self.limits.max_http_attempts is not None
            and self.http_attempts > self.limits.max_http_attempts
        ):
            reasons.append(
                f"HTTP attempts ({self.http_attempts} > {self.limits.max_http_attempts})"
            )
        if (
            self.limits.max_total_input_tokens is not None
            and self.total_input_tokens > self.limits.max_total_input_tokens
        ):
            reasons.append(
                f"input tokens ({self.total_input_tokens} > {self.limits.max_total_input_tokens})"
            )
        if (
            self.limits.max_total_output_tokens is not None
            and self.total_output_tokens > self.limits.max_total_output_tokens
        ):
            max_out = self.limits.max_total_output_tokens
            reasons.append(f"output tokens ({self.total_output_tokens} > {max_out})")
        if reasons:
            self.exhausted = True
            self.exhausted_reason = "Budget exhausted: " + "; ".join(reasons)
            logger.warning("Budget exhausted: %s", self.exhausted_reason)

    @property
    def usage_report(self) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=self.total_input_tokens,
            completion_tokens=self.total_output_tokens,
            total_tokens=self.total_input_tokens + self.total_output_tokens,
            requests=self.http_attempts,
        )


def estimate_executions(
    cases_in_plan: int,
    agents: int,
) -> int:
    return cases_in_plan * agents


def estimate_logical_calls(
    cases_in_plan: int,
    agents: int,
    *,
    plan_generated: bool = True,
    clarification_rate: float = 0.2,
) -> int:
    calls = 1 if plan_generated else 0
    calls += cases_in_plan * agents
    calls += int(cases_in_plan * agents * clarification_rate)
    calls += cases_in_plan * agents
    return calls


def preflight_check(limits: BudgetLimits, cases: int, agents: int) -> list[str]:
    warnings: list[str] = []
    estimated_calls = estimate_logical_calls(cases, agents)
    if limits.max_logical_requests and estimated_calls > limits.max_logical_requests:
        warnings.append(
            f"Estimated {estimated_calls} logical calls but limit is "
            f"{limits.max_logical_requests} — run may exhaust budget"
        )
    return warnings


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, (str, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None
