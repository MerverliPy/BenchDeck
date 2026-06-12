from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ExecutionKey(BaseModel):
    """Immutable compound key that uniquely identifies one agent × case pair."""

    agent_label: str
    case_id: int

    def __hash__(self) -> int:
        return hash((self.agent_label, self.case_id))


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

    @property
    def execution_key(self) -> ExecutionKey:
        return ExecutionKey(agent_label=self.agent_label, case_id=self.case_id)
