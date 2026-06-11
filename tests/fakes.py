"""Deterministic fake gateway classes for Phase 0 regression testing.

No network calls. Every response is scripted. Designed explicitly for
reproducing and locking the documented correctness failures before
production repairs begin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from benchdeck.models import ResponseCapture
from benchdeck.openai_gateway import _parse_json_object


@dataclass
class ScriptedResponse:
    """One turn on a fake gateway.

    Every field maps to a ResponseCapture or `generate_json` return.
    """

    text: str = ""
    error: dict[str, Any] | None = None
    status: str | None = "completed"
    finish_reason: str | None = "stop"
    input_tokens: int = 10
    output_tokens: int = 20
    response_id: str | None = None
    request_id: str | None = None
    raw_response: dict[str, Any] | None = None
    attempts: int = 1

    # --- controls for generate_json -------------------------------------------------
    # When set, `generate_json` returns this dict instead of parsing `text`.
    json_result: dict[str, Any] | None = None
    # When True, `generate_json` raises RuntimeError (parse/validation failure).
    raise_on_json: bool = False
    # When a truthy string, this is used as the error message for the RuntimeError.
    json_error_message: str = ""


class FakeGateway:
    """Deterministic fake that replaces `OpenAIGateway` in tests.

    Every call to `generate` / `generate_json` consumes the next
    `ScriptedResponse` from the supplied list.
    """

    def __init__(self, responses: list[ScriptedResponse] | None = None) -> None:
        self._responses: list[ScriptedResponse] = list(responses) if responses else []
        self._next_idx: int = 0

        # Audit trails ---------------------------------------------------------------
        self.generate_calls: list[dict[str, str]] = []
        self.json_calls: list[dict[str, str]] = []

    # ------------------------------------------------------------------ public API --

    def generate(self, *, instructions: str, input_text: str) -> ResponseCapture:
        self.generate_calls.append({"instructions": instructions, "input_text": input_text})
        r = self._next()
        return ResponseCapture(
            text=r.text,
            response_id=r.response_id,
            request_id=r.request_id,
            status=r.status,
            finish_reason=r.finish_reason,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            raw_response=r.raw_response,
            error=r.error,
            attempts=r.attempts,
        )

    def generate_json(
        self, *, instructions: str, input_text: str
    ) -> tuple[dict[str, Any], ResponseCapture]:
        self.json_calls.append({"instructions": instructions, "input_text": input_text})
        r = self._next()
        capture = ResponseCapture(
            text=r.text,
            response_id=r.response_id,
            request_id=r.request_id,
            status=r.status,
            finish_reason=r.finish_reason,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            raw_response=r.raw_response,
            error=r.error,
            attempts=r.attempts,
        )

        if r.raise_on_json:
            msg = r.json_error_message or "Scripted JSON parse failure"
            raise RuntimeError(msg)

        if r.error:
            raise RuntimeError(f"Scripted gateway error: {r.error}")

        if not r.text:
            raise RuntimeError("Model returned no text: empty scripted response")

        if r.json_result is not None:
            return r.json_result, capture

        return _parse_json_object(r.text), capture

    # ---------------------------------------------------------------- helpers / audit

    def _next(self) -> ScriptedResponse:
        if self._next_idx >= len(self._responses):
            return ScriptedResponse(
                error={
                    "type": "ScriptExhausted",
                    "message": "No more scripted responses — test script is too short",
                }
            )
        r = self._responses[self._next_idx]
        self._next_idx += 1
        return r

    @property
    def remaining(self) -> int:
        """How many scripted responses have not yet been consumed."""
        return max(0, len(self._responses) - self._next_idx)

    def assert_exhausted(self) -> None:
        """Raise if any scripted responses were never consumed."""
        if self.remaining > 0:
            raise AssertionError(f"{self.remaining} scripted response(s) were not consumed")


# ------------------------------------------------------------------ shorthand builders


def text_response(
    text: str,
    *,
    response_id: str | None = None,
    request_id: str | None = None,
    input_tokens: int = 10,
    output_tokens: int = 20,
) -> ScriptedResponse:
    """A successful plain-text response."""
    return ScriptedResponse(
        text=text,
        response_id=response_id,
        request_id=request_id,
        status="completed",
        finish_reason="stop",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def json_response(
    data: dict[str, Any],
    *,
    response_id: str | None = None,
    request_id: str | None = None,
    input_tokens: int = 10,
    output_tokens: int = 20,
) -> ScriptedResponse:
    """A successful structured response returning the given dict."""
    import json

    return ScriptedResponse(
        text=json.dumps(data),
        json_result=data,
        response_id=response_id,
        request_id=request_id,
        status="completed",
        finish_reason="stop",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def empty_response(
    *,
    response_id: str | None = None,
    request_id: str | None = None,
) -> ScriptedResponse:
    """An empty-text response (no error, just no output)."""
    return ScriptedResponse(
        text="",
        response_id=response_id,
        request_id=request_id,
    )


def refusal_response(
    refusal_text: str = "I'm sorry, I cannot help with that request.",
    *,
    response_id: str | None = None,
    request_id: str | None = None,
) -> ScriptedResponse:
    """A model refusal delivered as text with a refusal finish reason."""
    return ScriptedResponse(
        text=refusal_text,
        finish_reason="refusal",
        status="completed",
        response_id=response_id,
        request_id=request_id,
    )


def error_response(
    error: dict[str, Any],
    *,
    response_id: str | None = None,
    request_id: str | None = None,
) -> ScriptedResponse:
    """A provider error (policy, timeout, transport, …)."""
    return ScriptedResponse(
        error=error,
        response_id=response_id,
        request_id=request_id,
        status=None,
        finish_reason=None,
    )


def policy_error(
    code: str = "cyber_policy",
    message: str = "Content filtered by policy",
    *,
    http_status: int = 400,
    request_id: str | None = None,
    nested: bool = True,
) -> ScriptedResponse:
    """A provider policy error.

    When *nested* is True the body contains the realistic nested shape
    `{"error": {"code": ..., "message": ...}}` that the current gateway
    code does not properly descend into.
    """
    if nested:
        body: dict[str, Any] = {"error": {"code": code, "message": message}}
    else:
        body = {"code": code, "message": message}
    return ScriptedResponse(
        error={
            "type": "APIStatusError",
            "status_code": http_status,
            "message": message,
            "request_id": request_id,
            "body": body,
        },
        input_tokens=0,
        output_tokens=0,
    )


def malformed_json_response(
    raw_text: str = "not valid json {{{",
    *,
    response_id: str | None = None,
    request_id: str | None = None,
) -> ScriptedResponse:
    """A response whose text is not valid JSON (not even JSON-ish)."""
    return ScriptedResponse(
        text=raw_text,
        response_id=response_id,
        request_id=request_id,
        status="completed",
        finish_reason="stop",
    )


def schema_invalid_json_response(
    data: dict[str, Any] | None = None,
    *,
    response_id: str | None = None,
    request_id: str | None = None,
) -> ScriptedResponse:
    """Valid JSON that nevertheless is missing required fields."""
    import json

    payload = data if data is not None else {"unknown_field": 42}
    return ScriptedResponse(
        text=json.dumps(payload),
        # Let the *consumer* (runner) hit the schema-invalid case at model level.
        json_result=payload,
        response_id=response_id,
        request_id=request_id,
        status="completed",
        finish_reason="stop",
    )
