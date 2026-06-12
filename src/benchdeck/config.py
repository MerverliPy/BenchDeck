from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def load_config(explicit_path: str | None = None) -> dict[str, Any]:
    """Load configuration from benchdeck.toml files.

    Search order (later files override earlier):
    1. ~/.config/benchdeck/config.toml
    2. ./benchdeck.toml (current directory)
    3. explicit --config path if provided

    Returns empty dict if no config file found.
    """
    merged: dict[str, Any] = {}
    search_paths = [
        Path.home() / ".config" / "benchdeck" / "config.toml",
        Path("benchdeck.toml"),
    ]
    if explicit_path:
        search_paths.append(Path(explicit_path))

    for path in search_paths:
        if not path.is_file():
            continue
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            _deep_merge(merged, data)
        except (tomllib.TOMLDecodeError, OSError):
            continue

    return merged


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
