from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import openai
from openai import OpenAI

from .models import ResponseCapture


@dataclass(frozen=True)
class GatewayConfig:
    model: str
    max_empty_retries: int = 2
    retry_backoff_seconds: float = 1.0


class OpenAIGateway:
    def __init__(self, config: GatewayConfig, client: OpenAI | None = None) -> None:
        self.config = config
        self.client = client or OpenAI()

    def generate(self, *, instructions: str, input_text: str) -> ResponseCapture:
        last_capture: ResponseCapture | None = None
        for attempt in range(1, self.config.max_empty_retries + 2):
            try:
                response = self.client.responses.create(
                    model=self.config.model,
                    instructions=instructions,
                    input=input_text,
                )
                raw = response.to_dict()
                usage = raw.get("usage") or {}
                capture = ResponseCapture(
                    text=(response.output_text or "").strip(),
                    response_id=getattr(response, "id", None),
                    request_id=getattr(response, "_request_id", None),
                    status=getattr(response, "status", None),
                    finish_reason=_extract_finish_reason(raw),
                    input_tokens=int(usage.get("input_tokens") or 0),
                    output_tokens=int(usage.get("output_tokens") or 0),
                    raw_response=raw,
                    attempts=attempt,
                )
                if capture.text:
                    return capture
                last_capture = capture
            except openai.APIStatusError as exc:
                error = {
                    "type": type(exc).__name__,
                    "status_code": exc.status_code,
                    "message": str(exc),
                    "request_id": exc.request_id,
                    "body": exc.body,
                }
                return ResponseCapture(
                    request_id=exc.request_id,
                    error=error,
                    attempts=attempt,
                )
            except openai.APIError as exc:
                return ResponseCapture(
                    error={"type": type(exc).__name__, "message": str(exc)},
                    attempts=attempt,
                )
            if attempt <= self.config.max_empty_retries:
                time.sleep(self.config.retry_backoff_seconds * attempt)
        return last_capture or ResponseCapture(
            error={"type": "EmptyResponseError", "message": "No response was captured."}
        )

    def generate_json(self, *, instructions: str, input_text: str) -> tuple[dict[str, Any], ResponseCapture]:
        capture = self.generate(instructions=instructions, input_text=input_text)
        if not capture.text:
            raise RuntimeError(f"Model returned no text: {capture.error or capture.raw_response}")
        return _parse_json_object(capture.text), capture


def _extract_finish_reason(raw: dict[str, Any]) -> str | None:
    for item in raw.get("output") or []:
        if isinstance(item, dict):
            if item.get("status"):
                return str(item["status"])
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") in {"refusal", "output_text"}:
                    if content.get("type") == "refusal":
                        return "refusal"
    return None


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
