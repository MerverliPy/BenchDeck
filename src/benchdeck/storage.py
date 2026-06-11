from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def _serialize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


class ArtifactStore:
    """Atomic JSON/text artifact writer safe for a concurrently watching TUI."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write_json(self, name: str, value: BaseModel | dict[str, Any] | list[Any]) -> Path:
        payload = _serialize(value)
        return self._atomic_write(name, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def write_text(self, name: str, text: str) -> Path:
        return self._atomic_write(name, text.rstrip() + "\n")

    def read_json(self, name: str, default: Any = None) -> Any:
        path = self.root / name
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    def _atomic_write(self, name: str, content: str) -> Path:
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp_name)
        return target
