from __future__ import annotations

import contextlib
import tomllib
import warnings
from pathlib import Path
from typing import Any

_KNOWN_CONFIG_KEYS = frozenset(
    {
        "model",
        "planner_model",
        "judge_model",
        "timeout",
        "max_retries",
        "max_output_tokens_planner",
        "max_output_tokens_agent",
        "max_output_tokens_judge",
        "max_logical_requests",
        "max_http_attempts",
        "max_total_input_tokens",
        "max_total_output_tokens",
        "capture_level",
        "judges",
        "run",
        "gateway",
    }
)


def load_config(explicit_path: str | None = None) -> dict[str, Any]:
    """Load configuration from benchdeck.toml files.

    Search order (later files override earlier):
    1. ~/.config/benchdeck/config.toml  (implicit — missing/malformed → warning)
    2. ./benchdeck.toml                  (implicit — missing/malformed → warning)
    3. explicit --config path            (explicit — missing/malformed → error)

    Returns empty dict if no config file found.
    """
    merged: dict[str, Any] = {}

    # ── implicit paths — tolerant ────────────────────────────────────────
    with contextlib.suppress(RuntimeError):
        _load_path(
            Path.home() / ".config" / "benchdeck" / "config.toml",
            merged,
            explicit=False,
        )
    _load_path(Path("benchdeck.toml"), merged, explicit=False)

    # ── explicit path — strict ───────────────────────────────────────────
    if explicit_path:
        _load_path(Path(explicit_path), merged, explicit=True)

    _validate_config_keys(merged)

    return merged


def _load_path(path: Path, merged: dict[str, Any], *, explicit: bool) -> None:
    if not path.is_file():
        if explicit:
            raise FileNotFoundError(f"Config file not found: {path}")
        return

    try:
        text = path.read_text(encoding="utf-8")
    except PermissionError as exc:
        if explicit:
            raise PermissionError(f"Config file not readable: {path}") from exc
        warnings.warn(f"Cannot read config file {path}: permission denied", stacklevel=3)
        return
    except OSError as exc:
        if explicit:
            raise OSError(f"Cannot read config file {path}: {exc}") from exc
        warnings.warn(f"Cannot read config file {path}: {exc}", stacklevel=3)
        return

    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        if explicit:
            raise ValueError(f"Config file is not valid TOML: {path} — {exc}") from exc
        warnings.warn(f"Skipping malformed config file {path}: {exc}", stacklevel=3)
        return

    if isinstance(data, dict):
        _deep_merge(merged, data)


def _validate_config_keys(data: dict[str, Any]) -> None:
    unknown: list[str] = []
    for key in data:
        if key not in _KNOWN_CONFIG_KEYS:
            unknown.append(key)
    if unknown:
        warnings.warn(
            f"Unknown config key(s): {', '.join(sorted(unknown))}",
            stacklevel=2,
        )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
