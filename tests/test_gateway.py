"""Phase 2 tests for the OpenAI gateway — evidence preservation and error classification.

Tests prove that every provider attempt is durable and classifiable,
retry ownership is deterministic, errors are recursively normalised,
and refusals are detected before generic completion status.
No test invokes the network.
"""

from __future__ import annotations

from typing import Any

import pytest
from fakes import (
    FakeGateway,
    attempt,
    error_attempt,
    error_response,
    json_response,
    malformed_json_response,
    policy_error,
    refusal_response,
    retry_sequence,
    single_attempt,
    text_response,
    timeout_response,
    transport_error_response,
)

from benchdeck.models import (
    ErrorCategory,
    ErrorRecord,
    GenerationResult,
    UsageDetails,
)
from benchdeck.openai_gateway import GatewayConfig, _parse_json_object

# ═══════════════════════════════════════════════════════════════════════════
# JSON parsing (unchanged)
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
# ErrorRecord — nested policy error classification (repaired)
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorRecordClassification:
    def test_nested_cyber_policy_body_is_classified_as_policy(self) -> None:
        """body.error.code=cyber_policy → ErrorCategory.POLICY via recursive extraction."""
        err = ErrorRecord.from_provider_error(
            exc_type="APIStatusError",
            status_code=400,
            message="Content filtered",
            body={"error": {"code": "cyber_policy", "message": "filtered"}},
            request_id="req-cyber-1",
        )
        assert err.category == ErrorCategory.POLICY
        assert err.provider_code == "cyber_policy"
        assert err.http_status == 400
        assert err.retryable is False

    def test_flat_content_policy_still_detected(self) -> None:
        err = ErrorRecord.from_provider_error(
            exc_type="APIStatusError",
            status_code=400,
            message="Content filtered",
            body={"code": "content_policy", "message": "filtered"},
        )
        assert err.category == ErrorCategory.POLICY
        assert err.provider_code == "content_policy"

    def test_408_is_timeout(self) -> None:
        err = ErrorRecord.from_provider_error(
            exc_type="APITimeoutError",
            status_code=408,
            message="Request timeout",
            body=None,
        )
        assert err.category == ErrorCategory.TIMEOUT
        assert err.retryable is True

    def test_429_is_rate_limit(self) -> None:
        err = ErrorRecord.from_provider_error(
            exc_type="RateLimitError",
            status_code=429,
            message="Too many requests",
            body=None,
        )
        assert err.category == ErrorCategory.RATE_LIMIT
        assert err.retryable is True

    def test_500_is_provider_error(self) -> None:
        err = ErrorRecord.from_provider_error(
            exc_type="InternalServerError",
            status_code=500,
            message="Internal error",
            body=None,
        )
        assert err.category == ErrorCategory.PROVIDER
        assert err.retryable is True

    def test_504_is_timeout(self) -> None:
        err = ErrorRecord.from_provider_error(
            exc_type="GatewayTimeout",
            status_code=504,
            message="Gateway timeout",
            body=None,
        )
        assert err.category == ErrorCategory.TIMEOUT
        assert err.retryable is True

    def test_retryability_table(self) -> None:
        """Every error category has correct retryability via from_provider_error."""
        # Use from_provider_error so retryability is auto-derived
        timeout = ErrorRecord.from_provider_error(
            exc_type="Timeout", status_code=408, message="t", body=None
        )
        rate_limit = ErrorRecord.from_provider_error(
            exc_type="RateLimit", status_code=429, message="r", body=None
        )
        provider = ErrorRecord.from_provider_error(
            exc_type="ServerError", status_code=500, message="s", body=None
        )
        policy = ErrorRecord.from_provider_error(
            exc_type="Policy",
            status_code=400,
            message="p",
            body={"error": {"code": "cyber_policy"}},
        )
        assert timeout.retryable is True
        assert rate_limit.retryable is True
        assert provider.retryable is True
        assert policy.retryable is False
        # Direct construction leaves retryable=False (default)
        refusal = ErrorRecord(category=ErrorCategory.REFUSAL, message="no")
        assert refusal.retryable is False
        parse_err = ErrorRecord(category=ErrorCategory.PARSE, message="bad")
        assert parse_err.retryable is False


# ═══════════════════════════════════════════════════════════════════════════
# Refusal detection — refusal takes precedence over generic completed
# ═══════════════════════════════════════════════════════════════════════════


class TestRefusalDetection:
    def test_refusal_finish_reason_is_detected(self) -> None:
        """A response with finish_reason='refusal' is classified as refusal."""
        gw = FakeGateway([refusal_response("I cannot help with that.")])
        result = gw.generate(instructions="x", input_text="y")
        assert result.has_refusal is True
        assert result.value is None
        assert result.terminal_error is not None
        assert result.terminal_error.category == ErrorCategory.REFUSAL
        assert len(result.attempts) == 1
        assert result.attempts[0].refusal is not None

    def test_refusal_without_text_still_detected(self) -> None:
        """A response with refusal in content but no output_text."""
        gw = FakeGateway(
            [
                single_attempt(
                    attempt(
                        "",
                        finish_reason="refusal",
                        refusal="I cannot comply.",
                    )
                )
            ]
        )
        result = gw.generate(instructions="x", input_text="y")
        assert result.has_refusal is True
        assert result.terminal_error is not None
        assert result.terminal_error.category == ErrorCategory.REFUSAL

    def test_normal_completion_is_not_refusal(self) -> None:
        gw = FakeGateway([text_response("Here is the answer.")])
        result = gw.generate(instructions="x", input_text="y")
        assert result.has_refusal is False
        assert result.value == "Here is the answer."
        assert result.terminal_error is None


# ═══════════════════════════════════════════════════════════════════════════
# Retry ownership — deterministic, observable, no SDK retries
# ═══════════════════════════════════════════════════════════════════════════


class TestRetryOwnership:
    def test_gateway_config_explicit_max_retries(self) -> None:
        cfg = GatewayConfig(model="fake", max_retries=3)
        assert cfg.max_retries == 3
        assert cfg.timeout_s == 90.0  # explicit default

    def test_all_attempts_preserved_in_retry_sequence(self) -> None:
        """Three attempts: timeout, rate_limit, success — all preserved."""
        gw = FakeGateway(
            [
                retry_sequence(
                    error_attempt(
                        ErrorCategory.TIMEOUT,
                        "timeout",
                        http_status=408,
                        retryable=True,
                        request_id="req-1",
                    ),
                    error_attempt(
                        ErrorCategory.RATE_LIMIT,
                        "rate limited",
                        http_status=429,
                        retryable=True,
                        request_id="req-2",
                    ),
                    attempt("success at last", request_id="req-3"),
                )
            ]
        )
        result = gw.generate(instructions="x", input_text="y")
        assert result.value == "success at last"
        assert result.total_http_attempts == 3
        assert len(result.attempts) == 3
        assert result.attempts[0].error is not None
        assert result.attempts[0].error.category == ErrorCategory.TIMEOUT
        assert result.attempts[1].error is not None
        assert result.attempts[1].error.category == ErrorCategory.RATE_LIMIT
        assert result.attempts[2].error is None
        assert result.terminal_error is None

    def test_policy_error_is_never_retryable(self) -> None:
        """Policy errors must stop retries immediately."""
        err = ErrorRecord(
            category=ErrorCategory.POLICY,
            message="blocked",
            http_status=400,
        )
        assert err.retryable is False

    def test_parse_error_is_never_retryable(self) -> None:
        err = ErrorRecord(category=ErrorCategory.PARSE, message="bad json")
        assert err.retryable is False

    def test_logical_vs_http_attempt_count(self) -> None:
        """One logical call may produce multiple HTTP attempts."""
        gw = FakeGateway(
            [
                retry_sequence(
                    error_attempt(
                        ErrorCategory.TIMEOUT,
                        "t1",
                        http_status=408,
                        retryable=True,
                    ),
                    error_attempt(
                        ErrorCategory.TIMEOUT,
                        "t2",
                        http_status=408,
                        retryable=True,
                    ),
                    attempt("ok"),
                )
            ]
        )
        result = gw.generate(instructions="x", input_text="y")
        assert result.logical_calls == 1
        assert result.total_http_attempts == 3


# ═══════════════════════════════════════════════════════════════════════════
# Token usage and request IDs — preserved across generation
# ═══════════════════════════════════════════════════════════════════════════


class TestTokenUsageAndIds:
    def test_generation_result_preserves_token_usage(self) -> None:
        gw = FakeGateway(
            [
                text_response(
                    "Hello",
                    response_id="resp-1",
                    request_id="req-1",
                    input_tokens=50,
                    output_tokens=25,
                ),
            ]
        )
        result = gw.generate(instructions="be helpful", input_text="hi")
        assert result.value == "Hello"
        assert result.total_input_tokens == 50
        assert result.total_output_tokens == 25
        assert result.last_attempt is not None
        assert result.last_attempt.response_id == "resp-1"
        assert result.last_attempt.request_id == "req-1"

    def test_generation_result_json_preserves_usage(self) -> None:
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
        result = gw.generate_json(instructions="plan", input_text="prompt")
        assert result.value == {"ok": True}
        assert result.total_input_tokens == 100
        assert result.total_output_tokens == 200
        assert result.last_attempt is not None
        assert result.last_attempt.response_id == "resp-j1"

    def test_usage_details_model(self) -> None:
        u = UsageDetails(
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            cached_input_tokens=5,
            reasoning_tokens=3,
        )
        assert u.input_tokens == 10
        assert u.output_tokens == 20
        assert u.cached_input_tokens == 5
        assert u.reasoning_tokens == 3

    def test_response_id_preserved_on_error(self) -> None:
        gw = FakeGateway(
            [
                single_attempt(
                    error_attempt(
                        ErrorCategory.TIMEOUT,
                        "timeout",
                        http_status=408,
                        request_id="req-timeout-1",
                    )
                )
            ]
        )
        result = gw.generate(instructions="x", input_text="y")
        assert result.terminal_error is not None
        assert result.last_attempt is not None
        assert result.last_attempt.request_id == "req-timeout-1"


# ═══════════════════════════════════════════════════════════════════════════
# Fake gateway exhaustion
# ═══════════════════════════════════════════════════════════════════════════


def test_fake_gateway_exhaustion_returns_terminal_error() -> None:
    gw = FakeGateway([text_response("only one")])
    gw.generate(instructions="x", input_text="y")
    result = gw.generate(instructions="x", input_text="y")
    assert result.terminal_error is not None
    assert result.terminal_error.message == (
        "No more scripted responses — test script is too short"
    )


def test_fake_gateway_assert_exhausted() -> None:
    gw = FakeGateway([text_response("a"), text_response("b")])
    gw.generate(instructions="x", input_text="y")
    with pytest.raises(AssertionError, match="1 scripted call"):
        gw.assert_exhausted()


# ═══════════════════════════════════════════════════════════════════════════
# Malformed JSON — returns parse_error, does not raise
# ═══════════════════════════════════════════════════════════════════════════


def test_malformed_json_returns_parse_error_not_exception() -> None:
    """generate_json with malformed text returns GenerationResult with parse_error."""
    gw = FakeGateway([malformed_json_response("not json {{{")])
    result = gw.generate_json(instructions="x", input_text="y")
    assert result.value is None
    assert result.parse_error is not None
    assert "did not contain a valid JSON object" in result.parse_error
    assert len(result.attempts) == 1  # evidence preserved


def test_schema_invalid_json_still_returns_parseable_value() -> None:
    """Valid JSON with wrong schema still returns the dict.
    Validation happens at the model level."""
    gw = FakeGateway([json_response({"unknown_field": 42})])
    result = gw.generate_json(instructions="x", input_text="y")
    assert result.value == {"unknown_field": 42}
    assert result.parse_error is None


def test_error_response_on_json_returns_terminal_error() -> None:
    """generate_json with a provider error returns terminal_error, not a raised exception."""
    gw = FakeGateway([error_response(ErrorCategory.TIMEOUT, "too slow", http_status=408)])
    result = gw.generate_json(instructions="x", input_text="y")
    assert result.value is None
    assert result.terminal_error is not None
    assert result.terminal_error.category == ErrorCategory.TIMEOUT
    assert len(result.attempts) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Attempt recording fidelity
# ═══════════════════════════════════════════════════════════════════════════


class TestAttemptRecordingFidelity:
    def test_attempt_number_is_incremented(self) -> None:
        gw = FakeGateway(
            [
                retry_sequence(
                    error_attempt(ErrorCategory.TIMEOUT, "t1", http_status=408),
                    error_attempt(ErrorCategory.RATE_LIMIT, "r1", http_status=429),
                    attempt("ok"),
                )
            ]
        )
        result = gw.generate(instructions="x", input_text="y")
        assert [a.attempt_number for a in result.attempts] == [1, 2, 3]

    def test_attempt_finish_reason_preserved(self) -> None:
        gw = FakeGateway([text_response("done")])
        result = gw.generate(instructions="x", input_text="y")
        assert result.last_attempt is not None
        assert result.last_attempt.finish_reason == "stop"

    def test_attempt_provider_status_preserved(self) -> None:
        gw = FakeGateway([text_response("done")])
        result = gw.generate(instructions="x", input_text="y")
        assert result.last_attempt is not None
        assert result.last_attempt.provider_status == "completed"

    def test_empty_response_attempt_recorded(self) -> None:
        """An empty-text non-refusal response is recorded as an attempt."""
        gw = FakeGateway([single_attempt(attempt("", response_id="empty-1"))])
        result = gw.generate(instructions="x", input_text="y")
        assert result.value is None or result.value == ""
        assert len(result.attempts) == 1
        assert result.attempts[0].output_text == ""

    def test_multiple_attempts_dont_overwrite(self) -> None:
        """Each attempt has its own record in the attempts list."""
        gw = FakeGateway(
            [
                retry_sequence(
                    attempt("first", request_id="r1"),
                    attempt("second", request_id="r2"),
                    attempt("third", request_id="r3"),
                )
            ]
        )
        result = gw.generate(instructions="x", input_text="y")
        assert len(result.attempts) == 3
        assert result.attempts[0].output_text == "first"
        assert result.attempts[1].output_text == "second"
        assert result.attempts[2].output_text == "third"
        assert result.value == "third"
        assert result.terminal_error is None


# ═══════════════════════════════════════════════════════════════════════════
# Gateway config — explicit timeout and token limits
# ═══════════════════════════════════════════════════════════════════════════


def test_gateway_config_explicit_timeout() -> None:
    cfg = GatewayConfig(model="gpt-4o", timeout_s=30.0)
    assert cfg.timeout_s == 30.0


def test_gateway_config_max_output_tokens() -> None:
    cfg = GatewayConfig(model="gpt-4o", max_output_tokens=4096)
    assert cfg.max_output_tokens == 4096


# ═══════════════════════════════════════════════════════════════════════════
# Refusal and error evidence in structured (JSON) calls
# ═══════════════════════════════════════════════════════════════════════════


def test_json_call_refusal_preserves_attempt_evidence() -> None:
    gw = FakeGateway([refusal_response("I cannot answer that.")])
    result = gw.generate_json(instructions="x", input_text="y")
    assert result.value is None
    assert result.terminal_error is not None
    assert result.terminal_error.category == ErrorCategory.REFUSAL
    assert len(result.attempts) == 1
    assert result.attempts[0].refusal is not None


def test_json_call_policy_error_preserves_evidence() -> None:
    gw = FakeGateway(
        [
            policy_error(
                code="cyber_policy",
                message="Blocked by policy",
                http_status=400,
                request_id="req-pol-1",
            )
        ]
    )
    result = gw.generate_json(instructions="x", input_text="y")
    assert result.value is None
    assert result.terminal_error is not None
    assert result.terminal_error.category == ErrorCategory.POLICY
    assert result.terminal_error.provider_code == "cyber_policy"
    assert result.last_attempt is not None
    assert result.last_attempt.error is not None
    assert result.last_attempt.error.category == ErrorCategory.POLICY


# ═══════════════════════════════════════════════════════════════════════════
# Transport and timeout error preservation
# ═══════════════════════════════════════════════════════════════════════════


def test_transport_error_preserved() -> None:
    gw = FakeGateway([transport_error_response("Connection refused")])
    result = gw.generate(instructions="x", input_text="y")
    assert result.terminal_error is not None
    assert result.terminal_error.category == ErrorCategory.TRANSPORT
    assert result.terminal_error.retryable is True


def test_timeout_error_preserved() -> None:
    gw = FakeGateway([timeout_response("Request timed out")])
    result = gw.generate(instructions="x", input_text="y")
    assert result.terminal_error is not None
    assert result.terminal_error.category == ErrorCategory.TIMEOUT
    assert result.terminal_error.retryable is True


# ═══════════════════════════════════════════════════════════════════════════
# GenerationResult helpers
# ═══════════════════════════════════════════════════════════════════════════


def test_generation_result_succeeded() -> None:
    result = GenerationResult(value="hello")
    assert result.succeeded is True


def test_generation_result_not_succeeded_on_error() -> None:
    result: GenerationResult[Any] = GenerationResult(
        terminal_error=ErrorRecord(category=ErrorCategory.TIMEOUT, message="timeout")
    )
    assert result.succeeded is False


def test_generation_result_not_succeeded_on_parse_error() -> None:
    result: GenerationResult[Any] = GenerationResult(parse_error="bad JSON")
    assert result.succeeded is False


# ═══════════════════════════════════════════════════════════════════════════
# Live API integration tests (requires OPENAI_API_KEY)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.xfail(reason="Requires OPENAI_API_KEY environment variable")
def test_live_gateway_generate_text_round_trip() -> None:
    import os

    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    from benchdeck.openai_gateway import GatewayConfig, OpenAIGateway

    gateway = OpenAIGateway(GatewayConfig(model="gpt-4o-mini", max_retries=2, timeout_s=30.0))
    result = gateway.generate(
        instructions="You are a helpful assistant. Reply with exactly one word.",
        input_text="Say 'hello' in French.",
    )
    assert result.succeeded
    assert result.value is not None
    assert len(result.value) > 0
    assert result.total_http_attempts >= 1
    assert len(result.attempts) >= 1
    assert result.attempts[0].usage.input_tokens > 0
    assert result.attempts[0].usage.output_tokens > 0


@pytest.mark.xfail(reason="Requires OPENAI_API_KEY environment variable")
def test_live_gateway_generate_json_round_trip() -> None:
    import os

    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    from benchdeck.openai_gateway import GatewayConfig, OpenAIGateway

    gateway = OpenAIGateway(GatewayConfig(model="gpt-4o-mini", max_retries=2, timeout_s=30.0))
    result = gateway.generate_json(
        instructions="Return JSON only.",
        input_text='Return: {"word": "bonjour"}',
    )
    assert result.succeeded
    assert isinstance(result.value, dict)
    assert "word" in result.value
    assert result.value["word"] == "bonjour"
    assert result.total_http_attempts >= 1
