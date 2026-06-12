from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .execution import ExecutionKey


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_FAILURES = "completed_with_failures"
    INCONCLUSIVE = "inconclusive"
    INFRASTRUCTURE_FAILED = "infrastructure_failed"
    ABORTED = "aborted"


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


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0


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


def _new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
