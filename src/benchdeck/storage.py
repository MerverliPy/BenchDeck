from __future__ import annotations

import contextlib
import datetime as _dt
import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from .manifest import Manifest


def _serialize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (_dt.datetime, _dt.date)):
        return obj.isoformat()
    if isinstance(obj, (set, frozenset)):
        return sorted(str(v) for v in obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class ArtifactStore:
    """Atomic JSON/text artifact writer safe for a concurrently watching TUI."""

    def __init__(self, root: Path, manifest: Manifest | None = None) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._manifest: Manifest | None = manifest

    def write_json(self, name: str, value: BaseModel | dict[str, Any] | list[Any]) -> Path:
        payload = _serialize(value)
        text = json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default) + "\n"
        path = self._atomic_write(name, text)
        self._record_manifest(name, text)
        return path

    def write_text(self, name: str, text: str) -> Path:
        content = text.rstrip() + "\n"
        path = self._atomic_write(name, content)
        self._record_manifest(name, content)
        return path

    def _record_manifest(self, name: str, content: str) -> None:
        if self._manifest is not None:
            self._manifest.record(name, content)

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
