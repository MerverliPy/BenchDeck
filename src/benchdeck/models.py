from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    @classmethod
    def required_families(cls) -> set[Family]:
        return {cls.HAPPY_PATH, cls.REGRESSION, cls.STRESS, cls.AMBIGUITY}


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


class BenchmarkMode(StrEnum):
    SINGLE = "single"
    COMPARISON = "comparison"


class ClarificationExpectation(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    UNDESIRABLE = "undesirable"


class Stage(StrEnum):
    PLANNER = "planner"
    AGENT = "agent"
    JUDGE = "judge"


# ── canonical execution identity ──────────────────────────────────────────


class ExecutionKey(BaseModel):
    """Immutable compound key that uniquely identifies one agent × case pair."""

    agent_label: str
    case_id: int

    def __hash__(self) -> int:
        return hash((self.agent_label, self.case_id))


# ── agent profile ─────────────────────────────────────────────────────────


class AgentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


# ── benchmark case ────────────────────────────────────────────────────────


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
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


# ── benchmark plan ────────────────────────────────────────────────────────

_CASE_COUNT_MIN = 8
_CASE_COUNT_MAX = 12


class BenchmarkPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "single"
    profile: AgentProfile
    validation_standard: list[str] = Field(default_factory=list)
    cases: list[BenchmarkCase]

    @model_validator(mode="after")
    def _validate_plan(self) -> BenchmarkPlan:
        # ── cases non-empty ──
        if not self.cases:
            raise ValueError("Benchmark plan must contain at least one case")

        # ── unique positive IDs ──
        seen: set[int] = set()
        for case in self.cases:
            if case.id <= 0:
                raise ValueError(f"Case IDs must be positive integers, got {case.id}")
            if case.id in seen:
                raise ValueError(f"Duplicate case ID {case.id} in plan")
            seen.add(case.id)

        # ── 8–12 cases for generated plans ──
        if len(self.cases) < _CASE_COUNT_MIN or len(self.cases) > _CASE_COUNT_MAX:
            raise ValueError(
                f"Plan must contain {_CASE_COUNT_MIN}–{_CASE_COUNT_MAX} cases, "
                f"got {len(self.cases)}"
            )

        # ── required families all present ──
        families = {case.normalized_family for case in self.cases}
        missing = Family.required_families() - families
        if missing:
            raise ValueError(
                f"Plan is missing required families: {', '.join(m.value for m in sorted(missing))}"
            )

        # ── mode must be valid ──
        if self.mode not in {"single", "comparison"}:
            raise ValueError(f"Unknown benchmark mode: {self.mode!r}")

        # ── non-empty prompts and titles ──
        for case in self.cases:
            if not case.test_prompt.strip():
                raise ValueError(f"Case {case.id} has an empty test_prompt")
            if not case.title.strip():
                raise ValueError(f"Case {case.id} has an empty title")

        # ── at least one hard-fail condition across all cases ──
        if not any(case.hard_fail_conditions for case in self.cases):
            raise ValueError("Plan must have at least one hard-fail condition across all cases")

        return self

    @property
    def agent_labels(self) -> list[str]:
        if self.mode == "comparison" and self.profile.agent_name_b:
            return [self.profile.agent_name_a, self.profile.agent_name_b]
        return [self.profile.agent_name_a]

    def all_execution_keys(self, agent_labels: list[str] | None = None) -> set[ExecutionKey]:
        labels = agent_labels or self.agent_labels
        return {
            ExecutionKey(agent_label=label, case_id=c.id) for label in labels for c in self.cases
        }


# ── response capture ──────────────────────────────────────────────────────


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


# ── case run result ───────────────────────────────────────────────────────


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

    @property
    def execution_key(self) -> ExecutionKey:
        return ExecutionKey(agent_label=self.agent_label, case_id=self.case_id)


# ── gate check & case judgment ────────────────────────────────────────────


class GateCheck(BaseModel):
    status: GateStatus
    reason: str


class CaseJudgment(BaseModel):
    case_id: int
    agent_label: str
    case_verdict: str
    gate_check: GateCheck
    rubric: dict[str, Rating]
    overall_rating: Rating
    why: str
    regression_notes: list[str] = Field(default_factory=list)
    judge_capture: ResponseCapture | None = None

    @property
    def execution_key(self) -> ExecutionKey:
        return ExecutionKey(agent_label=self.agent_label, case_id=self.case_id)


# ── policy block ──────────────────────────────────────────────────────────


class PolicyBlock(BaseModel):
    status: str = "policy_blocked"
    case_id: int
    case_title: str
    agent_label: str
    stage: str
    excluded_from_score: bool = True
    operation: str
    http_status: int | None = None
    error_type: str | None = None
    error_code: str | None = None
    message: str
    request_id: str | None = None
    retryable: bool = False

    @property
    def execution_key(self) -> ExecutionKey:
        return ExecutionKey(agent_label=self.agent_label, case_id=self.case_id)


# ── infrastructure error record ───────────────────────────────────────────


class InfrastructureError(BaseModel):
    case_id: int
    agent_label: str
    case_title: str = ""
    stage: str
    error_type: str = ""
    message: str = ""
    response_id: str | None = None
    request_id: str | None = None
    status: str | None = None
    finish_reason: str | None = None
    attempts: int = 0
    error: dict[str, Any] | None = None
    raw_response: dict[str, Any] | None = None

    @property
    def execution_key(self) -> ExecutionKey:
        return ExecutionKey(agent_label=self.agent_label, case_id=self.case_id)


# ── token usage ───────────────────────────────────────────────────────────


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0


# ── run metadata ──────────────────────────────────────────────────────────


class RunMetadata(BaseModel):
    schema_version: str = "2.0"
    run_id: str = Field(default_factory=lambda: _new_run_id())
    started_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    status: RunStatus = RunStatus.RUNNING
    stop_reason: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    cases_in_plan: int = 0
    agents_in_run: int = 0
    executions_planned: int = 0
    executions_attempted: int = 0
    executions_model_completed: int = 0
    executions_judged: int = 0
    policy_blocks: int = 0
    infrastructure_failures: int = 0


# ── coverage report ───────────────────────────────────────────────────────


class CoverageReport(BaseModel):
    expected_keys: set[ExecutionKey] = Field(default_factory=set)
    terminal_keys: set[ExecutionKey] = Field(default_factory=set)
    missing_keys: set[ExecutionKey] = Field(default_factory=set)
    extra_keys: set[ExecutionKey] = Field(default_factory=set)
    duplicate_keys: list[ExecutionKey] = Field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return not self.missing_keys and not self.extra_keys and not self.duplicate_keys

    @property
    def diagnostics(self) -> list[str]:
        diags: list[str] = []
        if self.missing_keys:
            diags.append(f"Missing: {_fmt_keys(self.missing_keys)}")
        if self.extra_keys:
            diags.append(f"Extra/unknown: {_fmt_keys(self.extra_keys)}")
        if self.duplicate_keys:
            diags.append(f"Duplicate: {_fmt_keys(self.duplicate_keys)}")
        return diags


def _fmt_keys(keys: set[ExecutionKey] | list[ExecutionKey]) -> str:
    return ", ".join(
        f"({k.agent_label}, {k.case_id})"
        for k in sorted(keys, key=lambda x: (x.agent_label, x.case_id))
    )


# ── agent tally ───────────────────────────────────────────────────────────


class AgentTally(BaseModel):
    agent_label: str
    score_scale: dict[str, int] = Field(default_factory=dict)
    cases_planned: int = 0
    cases_judged: int = 0
    rating_counts: dict[str, int] = Field(default_factory=dict)
    gate_failures: int = 0
    family_scores: dict[str, float] = Field(default_factory=dict)
    policy_blocks: int = 0
    infrastructure_failures: int = 0


# ── agent verdict ─────────────────────────────────────────────────────────


class AgentBenchmarkVerdict(BaseModel):
    agent_label: str
    coverage: CoverageReport
    tally: AgentTally
    verdict: Literal["validated", "not_validated", "inconclusive"]
    reasons: list[str] = Field(default_factory=list)


# ── comparison verdict ────────────────────────────────────────────────────


class ComparisonVerdict(BaseModel):
    agent_a_label: str
    agent_b_label: str
    wins_by_agent: dict[str, int] = Field(default_factory=dict)
    losses_by_agent: dict[str, int] = Field(default_factory=dict)
    ties: int = 0
    family_wins: dict[str, dict[str, int]] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    valid: bool = True


# ── run-level verdict ─────────────────────────────────────────────────────


class BenchmarkRunVerdict(BaseModel):
    status: RunStatus
    agents: dict[str, AgentBenchmarkVerdict] = Field(default_factory=dict)
    comparison: ComparisonVerdict | None = None


# ── helpers ───────────────────────────────────────────────────────────────


def _new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
