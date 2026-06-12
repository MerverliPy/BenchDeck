from __future__ import annotations

from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


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
