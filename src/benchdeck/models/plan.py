from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .execution import ExecutionKey


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


class ClarificationExpectation(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    UNDESIRABLE = "undesirable"


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
        if not self.cases:
            raise ValueError("Benchmark plan must contain at least one case")

        seen: set[int] = set()
        for case in self.cases:
            if case.id <= 0:
                raise ValueError(f"Case IDs must be positive integers, got {case.id}")
            if case.id in seen:
                raise ValueError(f"Duplicate case ID {case.id} in plan")
            seen.add(case.id)

        if self.provenance and self.provenance.source == "frozen":
            pass
        elif len(self.cases) < _CASE_COUNT_MIN or len(self.cases) > _CASE_COUNT_MAX:
            raise ValueError(
                f"Plan must contain {_CASE_COUNT_MIN}–{_CASE_COUNT_MAX} cases, "
                f"got {len(self.cases)}"
            )

        families = {case.normalized_family for case in self.cases}
        missing = Family.required_families() - families
        if missing:
            raise ValueError(
                f"Plan is missing required families: {', '.join(m.value for m in sorted(missing))}"
            )

        if self.mode not in {"single", "comparison"}:
            raise ValueError(f"Unknown benchmark mode: {self.mode!r}")

        for case in self.cases:
            if not case.test_prompt.strip():
                raise ValueError(f"Case {case.id} has an empty test_prompt")
            if not case.title.strip():
                raise ValueError(f"Case {case.id} has an empty title")

        if not any(case.hard_fail_conditions for case in self.cases):
            raise ValueError("Plan must have at least one hard-fail condition across all cases")

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
