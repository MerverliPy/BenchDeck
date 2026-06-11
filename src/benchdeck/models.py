from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Family(StrEnum):
    HAPPY_PATH = "happy_path"
    REGRESSION = "regression_protection"
    STRESS = "stress_adversarial"
    AMBIGUITY = "ambiguity"

    @classmethod
    def normalize(cls, value: str) -> Family:
        aliases = {
            "happy-path": cls.HAPPY_PATH,
            "happy_path": cls.HAPPY_PATH,
            "regression": cls.REGRESSION,
            "regression_protection": cls.REGRESSION,
            "stress": cls.STRESS,
            "stress-adversarial": cls.STRESS,
            "stress_adversarial": cls.STRESS,
            "ambiguity": cls.AMBIGUITY,
        }
        try:
            return aliases[value.strip().lower()]
        except KeyError as exc:
            raise ValueError(f"Unsupported case family: {value!r}") from exc


class Rating(StrEnum):
    EXCELLENT = "Excellent"
    STRONG = "Strong"
    ACCEPTABLE = "Acceptable"
    WEAK = "Weak"
    FAIL = "Fail"

    @property
    def score(self) -> int:
        return {
            Rating.EXCELLENT: 4,
            Rating.STRONG: 3,
            Rating.ACCEPTABLE: 2,
            Rating.WEAK: 1,
            Rating.FAIL: 0,
        }[self]


class GateStatus(StrEnum):
    PASS = "Pass"
    FAIL = "Fail"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_FAILURES = "completed_with_failures"
    INCONCLUSIVE = "inconclusive"
    INFRASTRUCTURE_FAILED = "infrastructure_failed"
    ABORTED = "aborted"


class AgentProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    agent_name_a: str
    agent_name_b: str | None = None
    inferred_mission: str
    top_priorities: list[str] = Field(default_factory=list)
    boundaries: list[str] = Field(default_factory=list)
    tool_posture: str = ""
    mission_critical_capability: str = ""
    rare_defining_capability: str = ""
    likely_weak_spots: list[str] = Field(default_factory=list)
    likely_regression_risks: list[str] = Field(default_factory=list)


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    title: str
    family: str
    purpose: str
    clarification_expectation: str = "optional"
    tool_expectation: str = "n/a"
    test_prompt: str
    clarification_answer_key: str | None = None
    strong_behavior: list[str] = Field(default_factory=list)
    weak_behavior: list[str] = Field(default_factory=list)
    hard_fail_conditions: list[str] = Field(default_factory=list)

    @property
    def normalized_family(self) -> Family:
        return Family.normalize(self.family)


class BenchmarkPlan(BaseModel):
    model_config = ConfigDict(extra="allow")

    mode: str = "single"
    profile: AgentProfile
    validation_standard: list[str] = Field(default_factory=list)
    cases: list[BenchmarkCase]


class ResponseCapture(BaseModel):
    text: str = ""
    response_id: str | None = None
    request_id: str | None = None
    status: str | None = None
    finish_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    raw_response: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    attempts: int = 1


class CaseRunResult(BaseModel):
    case_id: int
    agent_label: str
    clarification_used: bool = False
    clarification_question: str | None = None
    first_output: str = ""
    final_output: str = ""
    agent_capture: ResponseCapture
    clarification_capture: ResponseCapture | None = None
    infrastructure_error: bool = False


class GateCheck(BaseModel):
    status: GateStatus
    reason: str


class CaseJudgment(BaseModel):
    case_id: int
    case_verdict: str
    gate_check: GateCheck
    rubric: dict[str, Rating]
    overall_rating: Rating
    why: str
    regression_notes: list[str] = Field(default_factory=list)
    judge_capture: ResponseCapture | None = None


class PolicyBlock(BaseModel):
    status: str = "policy_blocked"
    case_id: int
    case_title: str
    stage: str
    agent: str
    excluded_from_score: bool = True
    operation: str
    http_status: int | None = None
    error_type: str | None = None
    error_code: str | None = None
    message: str
    request_id: str | None = None
    retryable: bool = False


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0


class RunMetadata(BaseModel):
    started_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    status: RunStatus = RunStatus.RUNNING
    stop_reason: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    attempted_cases: int = 0
    model_completed_cases: int = 0
    judged_cases: int = 0
    planned_cases: int = 0
    policy_blocks: int = 0
    infrastructure_failures: int = 0
