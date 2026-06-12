from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


class Manifest:
    """Track all benchmark artifacts with checksums and generation numbers.

    Every artifact write increments the generation counter.  The manifest
    itself is written atomically so a concurrent reader always sees a
    complete generation.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        if not root.is_file():
            self.root.mkdir(parents=True, exist_ok=True)
        self._generation: int = 0
        self._entries: dict[str, _ManifestEntry] = {}

    @property
    def generation(self) -> int:
        return self._generation

    def record(self, filename: str, content: str | bytes) -> _ManifestEntry:
        data = content.encode("utf-8") if isinstance(content, str) else content
        sha = hashlib.sha256(data).hexdigest()
        size = len(data)
        self._generation += 1
        entry = _ManifestEntry(
            filename=filename,
            sha256=sha,
            byte_size=size,
            generation=self._generation,
        )
        self._entries[filename] = entry
        self._flush()
        return entry

    def _flush(self) -> None:
        manifest = {
            "generation": self._generation,
            "entries": {name: entry.to_dict() for name, entry in self._entries.items()},
        }
        text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        target = self.root / "manifest.json"
        fd, temp_name = tempfile.mkstemp(prefix=".manifest.", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp_name)

    def verify(self) -> list[str]:
        issues: list[str] = []
        for filename, entry in self._entries.items():
            path = self.root / filename
            if not path.exists():
                issues.append(f"{filename}: missing on disk")
                continue
            data = path.read_bytes()
            actual_sha = hashlib.sha256(data).hexdigest()
            if actual_sha != entry.sha256:
                issues.append(
                    f"{filename}: checksum mismatch "
                    f"(expected {entry.sha256[:12]}..., got {actual_sha[:12]}...)"
                )
            actual_size = len(data)
            if actual_size != entry.byte_size:
                issues.append(
                    f"{filename}: size mismatch (expected {entry.byte_size}, got {actual_size})"
                )
        return issues

    @classmethod
    def load(cls, root: Path) -> Manifest:
        manifest_path = root / "manifest.json"
        m = cls(root)
        if not manifest_path.exists():
            return m
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return m
        m._generation = int(data.get("generation", 0))
        for name, entry_data in data.get("entries", {}).items():
            m._entries[name] = _ManifestEntry(
                filename=name,
                sha256=str(entry_data.get("sha256", "")),
                byte_size=int(entry_data.get("byte_size", 0)),
                generation=int(entry_data.get("generation", m._generation)),
            )
        return m

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation": self._generation,
            "entries": {name: entry.to_dict() for name, entry in self._entries.items()},
        }


class _ManifestEntry:
    def __init__(self, filename: str, sha256: str, byte_size: int, generation: int) -> None:
        self.filename = filename
        self.sha256 = sha256
        self.byte_size = byte_size
        self.generation = generation

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "generation": self.generation,
        }
