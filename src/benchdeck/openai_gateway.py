from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, runtime_checkable

import openai
from openai import OpenAI

from .models import (
    ErrorCategory,
    ErrorRecord,
    GenerationResult,
    ResponseAttempt,
    UsageDetails,
)

T = TypeVar("T")

logger = logging.getLogger("benchdeck.gateway")

# ── project-level timeout constants ───────────────────────────────────────

_DEFAULT_TIMEOUT_S = 90.0
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_INITIAL_BACKOFF_S = 1.0
_DEFAULT_MAX_BACKOFF_S = 30.0
_DEFAULT_JITTER = 0.3


@dataclass(frozen=True)
class GatewayConfig:
    model: str
    timeout_s: float = _DEFAULT_TIMEOUT_S
    max_retries: int = _DEFAULT_MAX_RETRIES
    initial_backoff_s: float = _DEFAULT_INITIAL_BACKOFF_S
    max_backoff_s: float = _DEFAULT_MAX_BACKOFF_S
    jitter: float = _DEFAULT_JITTER
    max_output_tokens: int | None = None
    temperature: float | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    use_structured_output: bool = False
    json_schema: dict[str, Any] | None = None


@runtime_checkable
class GatewayProtocol(Protocol):
    """Protocol for gateway implementations (OpenAIGateway and test fakes)."""

    def generate(self, *, instructions: str, input_text: str) -> GenerationResult[str]: ...
    def generate_json(
        self, *, instructions: str, input_text: str
    ) -> GenerationResult[dict[str, Any]]: ...


# ── retry policy ──────────────────────────────────────────────────────────


_NON_RETRYABLE = {
    ErrorCategory.POLICY,
    ErrorCategory.REFUSAL,
    ErrorCategory.PARSE,
    ErrorCategory.VALIDATION,
}


def _is_retryable(category: ErrorCategory, http_status: int | None) -> bool:
    if category in _NON_RETRYABLE:
        return False
    if http_status is not None and 400 <= http_status < 500:
        return http_status in {408, 429}
    return True


def _backoff(attempt: int, config: GatewayConfig) -> float:
    delay: float = min(config.initial_backoff_s * float(2 ** (attempt - 1)), config.max_backoff_s)
    jitter_val: float = delay * config.jitter * (random.random() * 2 - 1)
    return float(max(0.0, delay + jitter_val))


# ── response normalisation ───────────────────────────────────────────────


def _normalize_usage(raw_usage: dict[str, Any] | None) -> UsageDetails:
    if not isinstance(raw_usage, dict):
        return UsageDetails()
    input_tk = int(raw_usage.get("input_tokens", 0) or 0)
    output_tk = int(raw_usage.get("output_tokens", 0) or 0)
    total_tk = int(raw_usage.get("total_tokens", 0) or 0) or (input_tk + output_tk)
    input_details = raw_usage.get("input_tokens_details")
    output_details = raw_usage.get("output_tokens_details")
    cached = 0
    reasoning = 0
    if isinstance(input_details, dict):
        cached = int(input_details.get("cached_tokens", 0) or 0)
    if isinstance(output_details, dict):
        reasoning = int(output_details.get("reasoning_tokens", 0) or 0)
    return UsageDetails(
        input_tokens=input_tk,
        output_tokens=output_tk,
        total_tokens=total_tk,
        cached_input_tokens=cached,
        reasoning_tokens=reasoning,
        provider_extensions={
            k: v
            for k, v in raw_usage.items()
            if k
            not in {
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "input_tokens_details",
                "output_tokens_details",
            }
        },
    )


def _extract_finish_reason(raw: dict[str, Any]) -> str | None:
    for item in raw.get("output") or []:
        if isinstance(item, dict):
            if item.get("status"):
                return str(item["status"])
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") == "refusal":
                    return "refusal"
    return None


def _extract_refusal(raw: dict[str, Any]) -> str | None:
    for item in raw.get("output") or []:
        if isinstance(item, dict):
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") == "refusal":
                    return str(content.get("refusal", ""))
    return None


def _normalize_error(exc: openai.APIError) -> ErrorRecord:
    status_code: int | None = getattr(exc, "status_code", None)
    message = str(exc)
    body: dict[str, Any] | None = None
    request_id: str | None = getattr(exc, "request_id", None)
    if isinstance(exc, openai.APIStatusError):
        body = exc.body  # type: ignore[assignment]
    return ErrorRecord.from_provider_error(
        exc_type=type(exc).__name__,
        status_code=status_code,
        message=message,
        body=body,
        request_id=request_id,
    )


# ── JSON parsing (structured fallback) ────────────────────────────────────


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
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


# ── gateway ───────────────────────────────────────────────────────────────


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


class OpenAIGateway:
    def __init__(self, config: GatewayConfig, client: OpenAI | None = None) -> None:
        self.config = config
        if client is not None:
            self.client = client
        else:
            self.client = OpenAI(
                max_retries=0,
                timeout=config.timeout_s,
                default_headers=config.extra_headers or None,
            )

    def generate(self, *, instructions: str, input_text: str) -> GenerationResult[str]:
        return self._call_text(instructions=instructions, input_text=input_text)

    def generate_json(
        self, *, instructions: str, input_text: str
    ) -> GenerationResult[dict[str, Any]]:
        result = self._call_text(instructions=instructions, input_text=input_text)
        if result.value is None:
            return GenerationResult(
                attempts=result.attempts,
                terminal_error=result.terminal_error,
                parse_error=result.parse_error,
                logical_calls=result.logical_calls,
                total_http_attempts=result.total_http_attempts,
            )
        try:
            parsed = _parse_json_object(result.value)
            return GenerationResult(
                value=parsed,
                attempts=result.attempts,
                logical_calls=result.logical_calls,
                total_http_attempts=result.total_http_attempts,
            )
        except ValueError as exc:
            return GenerationResult(
                attempts=result.attempts,
                parse_error=str(exc),
                logical_calls=result.logical_calls,
                total_http_attempts=result.total_http_attempts,
            )

    # ── internal ──────────────────────────────────────────────────────────

    def _build_kwargs(self, *, instructions: str, input_text: str) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "instructions": instructions,
            "input": input_text,
        }
        if self.config.max_output_tokens is not None:
            kwargs["max_output_tokens"] = self.config.max_output_tokens
        if self.config.temperature is not None:
            kwargs["temperature"] = self.config.temperature
        if self.config.use_structured_output:
            if self.config.json_schema is not None:
                kwargs["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": "response",
                        "schema": self.config.json_schema,
                        "strict": True,
                    }
                }
            else:
                kwargs["text"] = {"format": {"type": "json_object"}}
        return kwargs

    def _call_text(self, *, instructions: str, input_text: str) -> GenerationResult[str]:
        kwargs = self._build_kwargs(instructions=instructions, input_text=input_text)

        def _make_call() -> Any:
            return self.client.responses.create(**kwargs)

        return self._execute(
            make_call=_make_call,
            extract_text=_extract_output_text,
            extract_raw=_to_dict,
        )

    def _execute(
        self,
        *,
        make_call: Any,
        extract_text: Any,
        extract_raw: Any,
        post_process: Any = None,
    ) -> GenerationResult[Any]:
        attempts: list[ResponseAttempt] = []
        last_error: ErrorRecord | None = None
        empty_attempts = 0
        http_attempts = 0

        for attempt_no in range(1, self.config.max_retries + 2):
            ts_start = time.time()
            try:
                response = make_call()
                http_attempts += 1
            except openai.APIStatusError as exc:
                http_attempts += 1
                err = _normalize_error(exc)
                attempts.append(
                    ResponseAttempt(
                        attempt_number=attempt_no,
                        started_at=f"{ts_start:.3f}",
                        completed_at=f"{time.time():.3f}",
                        request_id=err.request_id,
                        error=err,
                    )
                )
                last_error = err
                if not _is_retryable(err.category, err.http_status):
                    break
            except openai.APITimeoutError as exc:
                http_attempts += 1
                err = ErrorRecord(
                    category=ErrorCategory.TIMEOUT,
                    message=str(exc),
                    retryable=True,
                    raw_error={
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                )
                attempts.append(
                    ResponseAttempt(
                        attempt_number=attempt_no,
                        started_at=f"{ts_start:.3f}",
                        completed_at=f"{time.time():.3f}",
                        error=err,
                    )
                )
                last_error = err
            except openai.APIConnectionError as exc:
                http_attempts += 1
                err = ErrorRecord(
                    category=ErrorCategory.TRANSPORT,
                    message=str(exc),
                    retryable=True,
                    raw_error={
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                )
                attempts.append(
                    ResponseAttempt(
                        attempt_number=attempt_no,
                        started_at=f"{ts_start:.3f}",
                        completed_at=f"{time.time():.3f}",
                        error=err,
                    )
                )
                last_error = err
            except openai.APIError as exc:
                http_attempts += 1
                err = _normalize_error(exc)
                attempts.append(
                    ResponseAttempt(
                        attempt_number=attempt_no,
                        started_at=f"{ts_start:.3f}",
                        completed_at=f"{time.time():.3f}",
                        request_id=err.request_id,
                        error=err,
                    )
                )
                last_error = err
                if not _is_retryable(err.category, err.http_status):
                    break
            except Exception as exc:
                err = ErrorRecord(
                    category=ErrorCategory.UNKNOWN,
                    message=str(exc),
                    retryable=False,
                    raw_error={
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                )
                attempts.append(
                    ResponseAttempt(
                        attempt_number=attempt_no,
                        started_at=f"{ts_start:.3f}",
                        completed_at=f"{time.time():.3f}",
                        error=err,
                    )
                )
                last_error = err
                break
            else:
                raw = extract_raw(response)
                text = extract_text(raw)
                finish_reason = _extract_finish_reason(raw)
                refusal = _extract_refusal(raw)
                usage = _normalize_usage(raw.get("usage") if isinstance(raw, dict) else {})

                is_refusal = refusal is not None or finish_reason == "refusal"
                response_id = raw.get("id") if isinstance(raw, dict) else _get_attr(response, "id")
                request_id = (
                    raw.get("_request_id")
                    if isinstance(raw, dict)
                    else _get_attr(response, "_request_id")
                )
                provider_status = (
                    raw.get("status") if isinstance(raw, dict) else _get_attr(response, "status")
                )

                attempt_record = ResponseAttempt(
                    attempt_number=attempt_no,
                    started_at=f"{ts_start:.3f}",
                    completed_at=f"{time.time():.3f}",
                    response_id=response_id,
                    request_id=request_id,
                    provider_status=provider_status,
                    finish_reason=finish_reason,
                    output_text=text,
                    refusal=refusal or (text if is_refusal else None),
                    usage=usage,
                    raw_response=raw,
                )
                attempts.append(attempt_record)

                if is_refusal:
                    last_error = ErrorRecord(
                        category=ErrorCategory.REFUSAL,
                        message=refusal or text or "Model refused the request",
                        retryable=False,
                        raw_error={
                            "type": "Refusal",
                            "message": (refusal or text or "")[:500],
                        },
                    )
                    break

                if not text:
                    empty_attempts += 1
                    if attempt_no <= self.config.max_retries:
                        delay = _backoff(empty_attempts, self.config)
                        time.sleep(delay)
                        continue
                    last_error = ErrorRecord(
                        category=ErrorCategory.UNKNOWN,
                        message="No output text after all retries",
                        retryable=False,
                    )
                    break

                value: Any = text
                if post_process is not None:
                    try:
                        value = post_process(text)
                    except Exception as exc:
                        return GenerationResult(
                            attempts=attempts,
                            parse_error=str(exc),
                            logical_calls=1,
                            total_http_attempts=http_attempts,
                        )

                return GenerationResult(
                    value=value,
                    attempts=attempts,
                    logical_calls=1,
                    total_http_attempts=http_attempts,
                )

            if (
                attempt_no <= self.config.max_retries
                and last_error
                and _is_retryable(last_error.category, last_error.http_status)
            ):
                delay = _backoff(attempt_no, self.config)
                logger.debug(
                    "Retry %d/%d after %.2fs — %s",
                    attempt_no,
                    self.config.max_retries,
                    delay,
                    last_error.category.value,
                )
                time.sleep(delay)

        logger.warning(
            "All attempts exhausted — terminal error: %s",
            last_error.category.value if last_error else "none",
        )

        return GenerationResult(
            attempts=attempts,
            terminal_error=last_error,
            logical_calls=1,
            total_http_attempts=http_attempts,
        )


# ── raw extraction helpers ────────────────────────────────────────────────


def _extract_output_text(raw: Any) -> str:
    if isinstance(raw, dict):
        return (raw.get("output_text") or "").strip()
    try:
        return (getattr(raw, "output_text", None) or "").strip()
    except Exception:
        return ""


def _to_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        return raw.to_dict()  # type: ignore[no-any-return]
    except Exception:
        return {"_raw": str(raw)}
