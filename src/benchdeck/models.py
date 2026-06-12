from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T")


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


class ClarificationExpectation(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    UNDESIRABLE = "undesirable"


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
    schema_version: str = "2.0"
    prompt_version: str = "2"
    provenance: PlanProvenance | None = None

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
        if self.provenance and self.provenance.source == "frozen":
            pass  # skip case-count constraint for frozen plans
        elif len(self.cases) < _CASE_COUNT_MIN or len(self.cases) > _CASE_COUNT_MAX:
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

        # ── required-clarification cases must have an answer key ──
        for case in self.cases:
            if (
                case.clarification_expectation == ClarificationExpectation.REQUIRED.value
                and not case.clarification_answer_key
            ):
                raise ValueError(
                    f"Case {case.id} requires clarification but has no clarification_answer_key"
                )

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


# ── Phase 2 gateway models ────────────────────────────────────────────────


class ErrorCategory(StrEnum):
    POLICY = "policy"
    REFUSAL = "refusal"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    TRANSPORT = "transport"
    PROVIDER = "provider"
    PARSE = "parse"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class UsageDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0
    provider_extensions: dict[str, Any] = Field(default_factory=dict)


class ErrorRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ErrorCategory
    message: str
    http_status: int | None = None
    provider_type: str | None = None
    provider_code: str | None = None
    request_id: str | None = None
    retryable: bool = False
    raw_error: dict[str, Any] | None = None

    @classmethod
    def from_provider_error(
        cls,
        *,
        exc_type: str,
        status_code: int | None,
        message: str,
        body: dict[str, Any] | None,
        request_id: str | None = None,
    ) -> ErrorRecord:
        category = cls._classify(status_code, body)
        provider_code = cls._extract_code(body)
        provider_type = body.get("type") if isinstance(body, dict) else None
        retryable_cats = {
            ErrorCategory.TIMEOUT,
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.TRANSPORT,
            ErrorCategory.PROVIDER,
        }
        retryable = category in retryable_cats
        return cls(
            category=category,
            message=message,
            http_status=status_code,
            provider_type=provider_type,
            provider_code=provider_code,
            request_id=request_id,
            retryable=retryable,
            raw_error={
                "type": exc_type,
                "status_code": status_code,
                "message": message,
                "request_id": request_id,
                "body": body,
            },
        )

    @classmethod
    def _classify(cls, status_code: int | None, body: dict[str, Any] | None) -> ErrorCategory:
        if status_code == 408 or status_code == 504:
            return ErrorCategory.TIMEOUT
        if status_code == 429:
            return ErrorCategory.RATE_LIMIT
        code = cls._extract_code(body)
        if code in {"cyber_policy", "content_policy", "policy_violation"}:
            return ErrorCategory.POLICY
        if status_code is not None and 500 <= status_code < 600:
            return ErrorCategory.PROVIDER
        if status_code is not None and 400 <= status_code < 500:
            return ErrorCategory.PROVIDER
        return ErrorCategory.UNKNOWN

    @staticmethod
    def _extract_code(body: dict[str, Any] | None) -> str | None:
        if not isinstance(body, dict):
            return None
        code = body.get("code")
        if code is not None:
            return str(code)
        nested = body.get("error")
        if isinstance(nested, dict):
            return ErrorRecord._extract_code(nested)
        return None


class ResponseAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_number: int
    started_at: str = ""
    completed_at: str = ""
    response_id: str | None = None
    request_id: str | None = None
    provider_status: str | None = None
    finish_reason: str | None = None
    output_text: str = ""
    refusal: str | None = None
    usage: UsageDetails = Field(default_factory=UsageDetails)
    error: ErrorRecord | None = None
    raw_response: dict[str, Any] | None = None


class GenerationResult(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    value: T | None = None
    attempts: list[ResponseAttempt] = Field(default_factory=list)
    terminal_error: ErrorRecord | None = None
    parse_error: str | None = None
    validation_error: str | None = None
    logical_calls: int = 1
    total_http_attempts: int = 0

    @property
    def succeeded(self) -> bool:
        return self.value is not None and self.terminal_error is None

    @property
    def last_attempt(self) -> ResponseAttempt | None:
        return self.attempts[-1] if self.attempts else None

    @property
    def total_input_tokens(self) -> int:
        return sum(a.usage.input_tokens for a in self.attempts)

    @property
    def total_output_tokens(self) -> int:
        return sum(a.usage.output_tokens for a in self.attempts)

    @property
    def has_refusal(self) -> bool:
        return any(
            att.refusal is not None or att.finish_reason == "refusal" for att in self.attempts
        )


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


# ── typed rubric ───────────────────────────────────────────────────────────

REQUIRED_RUBRIC_DIMENSIONS = (
    "mission_fidelity",
    "task_success",
    "priority_adherence",
    "ambiguity_handling",
    "process_discipline",
    "tool_discipline",
    "robustness",
    "regression_safety",
)


class RubricDimension(BaseModel):
    """One scored dimension with evidence/reasons, not just a rating."""

    model_config = ConfigDict(extra="forbid")

    dimension: str
    rating: Rating
    evidence: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class Rubric(BaseModel):
    """Typed rubric containing all required dimensions."""

    model_config = ConfigDict(extra="forbid")

    dimensions: list[RubricDimension] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_required_dimensions(self) -> Rubric:
        present = {d.dimension for d in self.dimensions}
        missing = set(REQUIRED_RUBRIC_DIMENSIONS) - present
        if missing:
            raise ValueError(f"Rubric missing required dimensions: {', '.join(sorted(missing))}")
        unknown = present - set(REQUIRED_RUBRIC_DIMENSIONS)
        if unknown:
            raise ValueError(f"Rubric contains unknown dimensions: {', '.join(sorted(unknown))}")
        return self

    def overall_rating(self) -> Rating:
        """Deterministic Python-level rating from dimensions.

        Policy (version 1): minimum dimension rating, with gate-fail override
        applied by the caller.
        """
        if not self.dimensions:
            return Rating.FAIL
        scores = [d.rating.score for d in self.dimensions]
        min_score = min(scores)
        avg_score = sum(scores) / len(scores)
        if min_score <= 1:
            return Rating.FAIL
        if avg_score >= 3.5 and min_score >= 3:
            return Rating.EXCELLENT
        if avg_score >= 2.5 and min_score >= 2:
            return Rating.STRONG
        if avg_score >= 1.5:
            return Rating.ACCEPTABLE
        return Rating.WEAK

    def as_dict(self) -> dict[str, Rating]:
        return {d.dimension: d.rating for d in self.dimensions}


# ── plan provenance ────────────────────────────────────────────────────────


class PlanProvenance(BaseModel):
    """Records how a plan was produced and its content integrity."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["generated", "frozen"] = "generated"
    source_file: str | None = None
    source_sha256: str | None = None
    planner_model: str | None = None
    prompt_version: str = "2"
    schema_version: str = "1"
    plan_sha256: str = ""
    generated_at: str = ""


# ── gate check & case judgment ────────────────────────────────────────────


class GateCheck(BaseModel):
    status: GateStatus
    reason: str


class CaseJudgment(BaseModel):
    case_id: int
    agent_label: str
    judge_index: int = 0
    case_verdict: str
    gate_check: GateCheck
    rubric: Rubric
    overall_rating: Rating
    why: str
    regression_notes: list[str] = Field(default_factory=list)
    judge_capture: ResponseCapture | None = None

    @model_validator(mode="after")
    def _gate_fail_forces_fail(self) -> CaseJudgment:
        if self.gate_check.status == GateStatus.FAIL and self.overall_rating != Rating.FAIL:
            self.overall_rating = Rating.FAIL
        return self

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
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
