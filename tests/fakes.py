"""Deterministic fake gateway classes for Phase 2 evidence-preservation testing.

No network calls. Every response is scripted. Returns `GenerationResult`
with full per-attempt telemetry, enabling tests to assert on retry
ownership, refusal classification, error normalisation, and evidence
preservation.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from benchdeck.models import (
    ErrorCategory,
    ErrorRecord,
    GenerationResult,
    ResponseAttempt,
    UsageDetails,
)

# ── attempt-level script ──────────────────────────────────────────────────


@dataclass
class AttemptScript:
    """One HTTP attempt within a logical call."""

    # -- response shape ------------------------------------------------
    output_text: str = ""
    finish_reason: str | None = "stop"
    refusal: str | None = None
    response_id: str | None = None
    request_id: str | None = None
    provider_status: str | None = "completed"

    # -- usage ---------------------------------------------------------
    input_tokens: int = 10
    output_tokens: int = 20
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0

    # -- error ---------------------------------------------------------
    error_category: ErrorCategory | None = None
    error_message: str = ""
    error_http_status: int | None = None
    error_provider_code: str | None = None
    error_body: dict[str, Any] | None = None
    error_retryable: bool = False

    # -- structured output control -------------------------------------
    json_result: dict[str, Any] | None = None  # for generate_json

    # -- raw capture ---------------------------------------------------
    raw_response: dict[str, Any] | None = None

    @property
    def is_error(self) -> bool:
        return self.error_category is not None

    @property
    def is_refusal(self) -> bool:
        return self.refusal is not None or self.finish_reason == "refusal"


# ── call-level script ─────────────────────────────────────────────────────


@dataclass
class CallScript:
    """A complete logical call consisting of one or more HTTP attempts."""

    attempts: list[AttemptScript] = field(default_factory=list)

    @property
    def total_http_attempts(self) -> int:
        return len(self.attempts)


def single_attempt(a: AttemptScript) -> CallScript:
    return CallScript(attempts=[a])


def retry_sequence(*attempts: AttemptScript) -> CallScript:
    return CallScript(attempts=list(attempts))


# ── fake gateway ──────────────────────────────────────────────────────────


class FakeGateway:
    """Deterministic fake that replaces `OpenAIGateway` in tests.

    Per logical call the gateway consumes one `CallScript` from the
    supplied list.  Each `AttemptScript` inside that `CallScript` is
    recorded as a separate `ResponseAttempt` in the returned
    `GenerationResult`.

    Audit trails record every call for later assertion.
    """

    def __init__(self, scripts: list[CallScript] | None = None) -> None:
        self._scripts: list[CallScript] = list(scripts) if scripts else []
        self._next_idx: int = 0

        self.generate_calls: list[dict[str, str]] = []
        self.json_calls: list[dict[str, str]] = []

    # ── public API (mirrors OpenAIGateway) ───────────────────────────────

    def generate(self, *, instructions: str, input_text: str) -> GenerationResult[str]:
        self.generate_calls.append({"instructions": instructions, "input_text": input_text})
        return self._play_script()

    def generate_json(
        self, *, instructions: str, input_text: str
    ) -> GenerationResult[dict[str, Any]]:
        self.json_calls.append({"instructions": instructions, "input_text": input_text})
        return self._play_script(extract_json=True)

    # ── internal ─────────────────────────────────────────────────────────

    def _play_script(self, *, extract_json: bool = False) -> GenerationResult[Any]:
        script = self._next_script()
        attempts: list[ResponseAttempt] = []
        terminal_error: ErrorRecord | None = None
        parse_error: str | None = None
        value: Any = None
        now = f"{time.time():.3f}"

        for i, att in enumerate(script.attempts, 1):
            usage = UsageDetails(
                input_tokens=att.input_tokens,
                output_tokens=att.output_tokens,
                total_tokens=att.input_tokens + att.output_tokens,
                cached_input_tokens=att.cached_input_tokens,
                reasoning_tokens=att.reasoning_tokens,
            )

            if att.is_error:
                err = ErrorRecord(
                    category=att.error_category or ErrorCategory.UNKNOWN,
                    message=att.error_message or "Scripted error",
                    http_status=att.error_http_status,
                    provider_code=att.error_provider_code,
                    request_id=att.request_id,
                    retryable=att.error_retryable,
                    raw_error=att.error_body,
                )
                attempts.append(
                    ResponseAttempt(
                        attempt_number=i,
                        started_at=now,
                        completed_at=now,
                        request_id=att.request_id,
                        error=err,
                    )
                )
                terminal_error = err
            elif att.is_refusal:
                attempts.append(
                    ResponseAttempt(
                        attempt_number=i,
                        started_at=now,
                        completed_at=now,
                        response_id=att.response_id,
                        request_id=att.request_id,
                        provider_status=att.provider_status,
                        finish_reason=att.finish_reason,
                        output_text=att.output_text,
                        refusal=att.refusal or att.output_text,
                        usage=usage,
                    )
                )
                terminal_error = ErrorRecord(
                    category=ErrorCategory.REFUSAL,
                    message=att.refusal or att.output_text or "Model refused",
                    retryable=False,
                )
            else:
                attempts.append(
                    ResponseAttempt(
                        attempt_number=i,
                        started_at=now,
                        completed_at=now,
                        response_id=att.response_id,
                        request_id=att.request_id,
                        provider_status=att.provider_status,
                        finish_reason=att.finish_reason,
                        output_text=att.output_text,
                        usage=usage,
                        raw_response=att.raw_response,
                    )
                )
                terminal_error = None
                if i == len(script.attempts) and value is None:
                    raw_value = att.output_text
                    if extract_json:
                        if att.json_result is not None:
                            value = att.json_result
                        elif att.output_text:
                            try:
                                value = _parse_json(att.output_text)
                            except ValueError as exc:
                                parse_error = str(exc)
                        else:
                            parse_error = "No output text to parse"
                    else:
                        value = raw_value

        return GenerationResult(
            value=value,
            attempts=attempts,
            terminal_error=terminal_error,
            parse_error=parse_error,
            logical_calls=1,
            total_http_attempts=len(script.attempts),
        )

    def _next_script(self) -> CallScript:
        if self._next_idx >= len(self._scripts):
            return CallScript(
                attempts=[
                    AttemptScript(
                        error_category=ErrorCategory.UNKNOWN,
                        error_message="No more scripted responses — test script is too short",
                    )
                ]
            )
        r = self._scripts[self._next_idx]
        self._next_idx += 1
        return r

    # ── audit helpers ─────────────────────────────────────────────────────

    @property
    def remaining(self) -> int:
        return max(0, len(self._scripts) - self._next_idx)

    def assert_exhausted(self) -> None:
        if self.remaining > 0:
            raise AssertionError(f"{self.remaining} scripted call(s) were not consumed")


# ── shorthand builders ────────────────────────────────────────────────────


def attempt(
    output_text: str = "",
    *,
    response_id: str | None = None,
    request_id: str | None = None,
    finish_reason: str | None = "stop",
    input_tokens: int = 10,
    output_tokens: int = 20,
    cached_input_tokens: int = 0,
    reasoning_tokens: int = 0,
    refusal: str | None = None,
) -> AttemptScript:
    return AttemptScript(
        output_text=output_text,
        response_id=response_id,
        request_id=request_id,
        finish_reason=finish_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        reasoning_tokens=reasoning_tokens,
        refusal=refusal,
    )


def error_attempt(
    category: ErrorCategory,
    message: str = "",
    *,
    http_status: int | None = None,
    provider_code: str | None = None,
    request_id: str | None = None,
    retryable: bool = False,
    body: dict[str, Any] | None = None,
) -> AttemptScript:
    return AttemptScript(
        error_category=category,
        error_message=message,
        error_http_status=http_status,
        error_provider_code=provider_code,
        error_body=body,
        error_retryable=retryable,
        request_id=request_id,
    )


def json_attempt(
    data: dict[str, Any],
    *,
    response_id: str | None = None,
    request_id: str | None = None,
    input_tokens: int = 10,
    output_tokens: int = 20,
) -> AttemptScript:
    return AttemptScript(
        output_text=json.dumps(data),
        json_result=data,
        response_id=response_id,
        request_id=request_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


# ── legacy-compatible script builders (return CallScript directly) ─────────


def text_response(
    text: str,
    *,
    response_id: str | None = None,
    request_id: str | None = None,
    input_tokens: int = 10,
    output_tokens: int = 20,
) -> CallScript:
    return single_attempt(
        attempt(
            text,
            response_id=response_id,
            request_id=request_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    )


def json_response(
    data: dict[str, Any],
    *,
    response_id: str | None = None,
    request_id: str | None = None,
    input_tokens: int = 10,
    output_tokens: int = 20,
) -> CallScript:
    return single_attempt(
        json_attempt(
            data,
            response_id=response_id,
            request_id=request_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    )


def empty_response(
    *,
    response_id: str | None = None,
    request_id: str | None = None,
) -> CallScript:
    return single_attempt(attempt("", response_id=response_id, request_id=request_id))


def refusal_response(
    refusal_text: str = "I'm sorry, I cannot help with that request.",
    *,
    response_id: str | None = None,
    request_id: str | None = None,
) -> CallScript:
    return single_attempt(
        attempt(
            refusal_text,
            response_id=response_id,
            request_id=request_id,
            finish_reason="refusal",
            refusal=refusal_text,
        )
    )


def error_response(
    category: ErrorCategory = ErrorCategory.PROVIDER,
    message: str = "Provider error",
    *,
    http_status: int | None = 500,
    request_id: str | None = None,
    retryable: bool = False,
) -> CallScript:
    return single_attempt(
        error_attempt(
            category,
            message,
            http_status=http_status,
            request_id=request_id,
            retryable=retryable,
        )
    )


def timeout_response(
    message: str = "Request timed out",
    *,
    request_id: str | None = None,
) -> CallScript:
    return single_attempt(
        error_attempt(
            ErrorCategory.TIMEOUT,
            message,
            http_status=408,
            request_id=request_id,
            retryable=True,
        )
    )


def rate_limit_response(
    message: str = "Rate limited",
    *,
    request_id: str | None = None,
) -> CallScript:
    return single_attempt(
        error_attempt(
            ErrorCategory.RATE_LIMIT,
            message,
            http_status=429,
            request_id=request_id,
            retryable=True,
        )
    )


def transport_error_response(
    message: str = "Connection error",
    *,
    request_id: str | None = None,
) -> CallScript:
    return single_attempt(
        error_attempt(
            ErrorCategory.TRANSPORT,
            message,
            request_id=request_id,
            retryable=True,
        )
    )


def policy_error(
    code: str = "cyber_policy",
    message: str = "Content filtered by policy",
    *,
    http_status: int = 400,
    request_id: str | None = None,
    nested: bool = True,
) -> CallScript:
    if nested:
        body: dict[str, Any] = {"error": {"code": code, "message": message}}
    else:
        body = {"code": code, "message": message}
    return single_attempt(
        error_attempt(
            ErrorCategory.POLICY,
            message,
            http_status=http_status,
            provider_code=code,
            request_id=request_id,
            retryable=False,
            body=body,
        )
    )


def malformed_json_response(
    raw_text: str = "not valid json {{{",
    *,
    response_id: str | None = None,
    request_id: str | None = None,
) -> CallScript:
    return single_attempt(
        attempt(
            raw_text,
            response_id=response_id,
            request_id=request_id,
        )
    )


def schema_invalid_json_response(
    data: dict[str, Any] | None = None,
    *,
    response_id: str | None = None,
    request_id: str | None = None,
) -> CallScript:
    payload = data if data is not None else {"unknown_field": 42}
    return single_attempt(
        json_attempt(
            payload,
            response_id=response_id,
            request_id=request_id,
        )
    )


# ── helpers ───────────────────────────────────────────────────────────────


def _parse_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("Model output did not contain a valid JSON object")
