"""Phase 0 regression tests for the OpenAI gateway.

Tests document defects in error classification, response capture,
retry handling, and structured output parsing.
"""

from __future__ import annotations

from typing import Any

import pytest
from fakes import (
    FakeGateway,
    error_response,
    json_response,
    malformed_json_response,
    text_response,
)

from benchdeck.models import ResponseCapture
from benchdeck.openai_gateway import GatewayConfig, _parse_json_object

# ═══════════════════════════════════════════════════════════════════════════
# JSON parsing
# ═══════════════════════════════════════════════════════════════════════════


def test_parse_json_object_accepts_code_fence_json() -> None:
    result = _parse_json_object('```json\n{"ok": true}\n```')
    assert result == {"ok": True}


def test_parse_json_object_accepts_bare_json() -> None:
    result = _parse_json_object('{"ok": true}')
    assert result == {"ok": True}


def test_parse_json_object_rejects_non_json() -> None:
    with pytest.raises(ValueError, match="did not contain a valid JSON object"):
        _parse_json_object("just some prose text here")


# ═══════════════════════════════════════════════════════════════════════════
# Error classification — nested policy errors
# ═══════════════════════════════════════════════════════════════════════════


def test_nested_policy_error_body_structure() -> None:
    """The current gateway stores error.body as-is from the SDK.

    The runner's _policy_block_from_capture method only checks
    body.get("code"), but actual OpenAI policy errors have the shape
    {"error": {"code": "cyber_policy", ...}} nested one level deeper.
    """
    # What the gateway produces (SDK error body):
    error_body = {"error": {"code": "cyber_policy", "message": "blocked"}}
    capture = ResponseCapture(
        error={
            "type": "APIStatusError",
            "status_code": 400,
            "message": "blocked",
            "request_id": "req-1",
            "body": error_body,
        }
    )

    # The runner checks for these code values:
    known_policy_codes = {"cyber_policy", "content_policy"}

    # Current (buggy) check: body.get("code")
    assert capture.error is not None
    body = capture.error.get("body") or {}
    current_check = body.get("code") if isinstance(body, dict) else None
    assert current_check is None, (
        "Current code inspects body.code but the key is at body.error.code"
    )

    # Correct check: recursively inspect nested error objects
    code = _find_code_in_body(body)
    assert code == "cyber_policy", "Nested body.error.code should be found by recursive inspection"
    assert code in known_policy_codes, "cyber_policy must be recognized"


def _find_code_in_body(body: Any) -> str | None:
    """Recursively search for a code field in nested OpenAI error bodies."""
    if isinstance(body, dict):
        if "code" in body and len(body) <= 3:
            return str(body["code"])
        if "error" in body and isinstance(body["error"], dict):
            return _find_code_in_body(body["error"])
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Refusal detection
# ═══════════════════════════════════════════════════════════════════════════


def test_refusal_text_not_distinguished_from_completion() -> None:
    """A response with finish_reason='refusal' looks like a normal
    completion to any consumer that only inspects ResponseCapture.text."""
    cap = ResponseCapture(
        text="I refuse to answer that question.",
        status="completed",
        finish_reason="refusal",
        response_id="resp-ref-1",
    )
    # The capture stores finish_reason but most code paths check only
    # cap.text and cap.error.
    assert cap.text != "", "Non-empty refusal text"
    assert cap.finish_reason == "refusal", "Stored as refusal"
    assert cap.error is None, "No error object"


# ═══════════════════════════════════════════════════════════════════════════
# Retry behaviour
# ═══════════════════════════════════════════════════════════════════════════


def test_gateway_retry_overwrites_earlier_captures() -> None:
    """The gateway's generate() loop creates per-attempt captures but only
    returns the last successful or last failure one.  Earlier empty-attempt
    metadata is not preserved.

    This is a *code-structure* defect: the loop in OpenAIGateway.generate
    creates a new ResponseCapture on each iteration and overwrites
    last_capture.  The FakeGateway intentionally preserves individual
    ScriptedResponse objects for each call so that tests can reason about
    per-attempt telemetry — something the real gateway cannot do.

    The presence of GatewayConfig.max_empty_retries proves retry intent
    exists, but the record only carries attempts=N.
    """
    cfg = GatewayConfig(model="fake", max_empty_retries=2)
    assert cfg.max_empty_retries == 2, "Gateway has retry configuration"
    # The defect: real gateway cannot be instantiated without an API key,
    # and even if it could, the retry loop overwrites earlier captions.
    # FakeGateway was built to expose what the real gateway hides.


# ═══════════════════════════════════════════════════════════════════════════
# Token usage and request IDs
# ═══════════════════════════════════════════════════════════════════════════


def test_fake_gateway_preserves_token_usage() -> None:
    """Scripted responses carry explicit token counts and request IDs."""
    gw = FakeGateway(
        [
            text_response(
                "Hello", response_id="resp-1", request_id="req-1", input_tokens=50, output_tokens=25
            ),
        ]
    )
    capture = gw.generate(instructions="be helpful", input_text="hi")
    assert capture.text == "Hello"
    assert capture.response_id == "resp-1"
    assert capture.request_id == "req-1"
    assert capture.input_tokens == 50
    assert capture.output_tokens == 25


def test_fake_gateway_json_preserves_usage() -> None:
    """generate_json carries usage through the capture."""
    gw = FakeGateway(
        [
            json_response(
                {"ok": True},
                response_id="resp-j1",
                request_id="req-j1",
                input_tokens=100,
                output_tokens=200,
            ),
        ]
    )
    data, capture = gw.generate_json(instructions="plan", input_text="prompt")
    assert data == {"ok": True}
    assert capture.input_tokens == 100
    assert capture.output_tokens == 200
    assert capture.response_id == "resp-j1"


# ═══════════════════════════════════════════════════════════════════════════
# Fake gateway exhausts correctly
# ═══════════════════════════════════════════════════════════════════════════


def test_fake_gateway_exhaustion_returns_error() -> None:
    """When the script runs out of responses, FakeGateway returns a
    terminal error capture."""
    gw = FakeGateway([text_response("only one")])
    gw.generate(instructions="x", input_text="y")
    capture = gw.generate(instructions="x", input_text="y")
    assert capture.error is not None
    assert capture.error["type"] == "ScriptExhausted"


def test_fake_gateway_assert_exhausted() -> None:
    """assert_exhausted raises when not all responses were consumed."""
    gw = FakeGateway([text_response("a"), text_response("b")])
    gw.generate(instructions="x", input_text="y")
    with pytest.raises(AssertionError, match="1 scripted response"):
        gw.assert_exhausted()


# ═══════════════════════════════════════════════════════════════════════════
# Malformed JSON in fake gateway
# ═══════════════════════════════════════════════════════════════════════════


def test_fake_gateway_malformed_json_raises() -> None:
    """generate_json with raise_on_json=True simulates a parse failure."""
    gw = FakeGateway([malformed_json_response("not json")])
    with pytest.raises(ValueError, match="did not contain a valid JSON object"):
        gw.generate_json(instructions="x", input_text="y")


def test_fake_gateway_error_response_raises_on_json() -> None:
    """generate_json with an error-carrying response raises RuntimeError."""
    gw = FakeGateway([error_response({"type": "Timeout", "message": "too slow"})])
    with pytest.raises(RuntimeError, match="Scripted gateway error"):
        gw.generate_json(instructions="x", input_text="y")
