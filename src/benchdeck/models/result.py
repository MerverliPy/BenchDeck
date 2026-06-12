from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .execution import ExecutionKey
from .infra import RunStatus


class CoverageReport(BaseModel):
    expected_keys: set[ExecutionKey] = Field(default_factory=set)
    terminal_keys: set[ExecutionKey] = Field(default_factory=set)
    missing_keys: set[ExecutionKey] = Field(default_factory=set)
    extra_keys: set[ExecutionKey] = Field(default_factory=set)

    @property
    def is_complete(self) -> bool:
        return not self.missing_keys and not self.extra_keys

    @property
    def diagnostics(self) -> list[str]:
        diags: list[str] = []
        if self.missing_keys:
            diags.append(f"Missing: {_fmt_keys(self.missing_keys)}")
        if self.extra_keys:
            diags.append(f"Extra/unknown: {_fmt_keys(self.extra_keys)}")
        return diags


def _fmt_keys(keys: set[ExecutionKey]) -> str:
    return ", ".join(
        f"({k.agent_label}, {k.case_id})"
        for k in sorted(keys, key=lambda x: (x.agent_label, x.case_id))
    )


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


class AgentBenchmarkVerdict(BaseModel):
    agent_label: str
    coverage: CoverageReport
    tally: AgentTally
    verdict: Literal["validated", "not_validated", "inconclusive"]
    reasons: list[str] = Field(default_factory=list)


class ComparisonVerdict(BaseModel):
    agent_a_label: str
    agent_b_label: str
    wins_by_agent: dict[str, int] = Field(default_factory=dict)
    losses_by_agent: dict[str, int] = Field(default_factory=dict)
    ties: int = 0
    family_wins: dict[str, dict[str, int]] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    valid: bool = True


class BenchmarkRunVerdict(BaseModel):
    status: RunStatus
    agents: dict[str, AgentBenchmarkVerdict] = Field(default_factory=dict)
    comparison: ComparisonVerdict | None = None
