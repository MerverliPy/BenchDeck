from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .execution import ExecutionKey


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


from .execution import ResponseCapture  # noqa: E402, F811
