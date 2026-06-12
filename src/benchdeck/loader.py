from __future__ import annotations

import base64
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Snapshot:
    metadata: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)
    tally: dict[str, Any] = field(default_factory=dict)
    judgments: list[dict[str, Any]] = field(default_factory=list)
    policy_blocks: list[dict[str, Any]] = field(default_factory=list)
    results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def load_snapshot(run_path: Path) -> Snapshot:
    """Load a run directory, ZIP archive, or checked-in segmented ZIP fixture."""
    if run_path.suffix.lower() == ".zip":
        if run_path.is_file():
            return _load_zip_snapshot(run_path)
        segments = sorted(run_path.parent.glob(run_path.name + ".b64.*"))
        if segments:
            try:
                encoded = "".join(part.read_text(encoding="ascii") for part in segments)
                return _load_zip_bytes(base64.b64decode(encoded, validate=False))
            except (OSError, ValueError):
                return Snapshot()
    return Snapshot(
        metadata=_read_json(run_path / "run_metadata.json", {}),
        plan=_read_json(run_path / "benchmark_plan.json", {}),
        tally=_read_json(run_path / "summary_tally.json", {}),
        judgments=_read_json(run_path / "case_judgments.json", []),
        policy_blocks=_read_json(run_path / "policy_blocks.json", []),
        results=_read_json(run_path / "run_results.json", {}),
    )


def _load_zip_snapshot(zip_path: Path) -> Snapshot:
    try:
        return _load_zip_bytes(zip_path.read_bytes())
    except (OSError, ValueError):
        return Snapshot()


def _load_zip_bytes(data: bytes) -> Snapshot:
    defaults: dict[str, Any] = {
        "run_metadata.json": {},
        "benchmark_plan.json": {},
        "summary_tally.json": {},
        "case_judgments.json": [],
        "policy_blocks.json": [],
        "run_results.json": {},
    }
    loaded: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            raw_names = [name for name in archive.namelist() if not name.endswith("/")]
            if len(raw_names) > 1000:
                return Snapshot()
            members: dict[str, str] = {}
            for name in raw_names:
                basename = Path(name).name
                if basename in members:
                    raise ValueError(
                        f"Duplicate basename {basename!r} from paths "
                        f"{members[basename]!r} and {name!r}"
                    )
                members[basename] = name
            for filename, default in defaults.items():
                member = members.get(filename)
                if member is None:
                    loaded[filename] = default
                    continue
                try:
                    info = archive.getinfo(member)
                    if info.file_size > 256 * 1024 * 1024:
                        loaded[filename] = default
                        continue
                    loaded[filename] = json.loads(archive.read(member).decode("utf-8"))
                except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
                    loaded[filename] = default
    except (OSError, zipfile.BadZipFile):
        loaded = defaults
    return Snapshot(
        metadata=loaded["run_metadata.json"],
        plan=loaded["benchmark_plan.json"],
        tally=loaded["summary_tally.json"],
        judgments=loaded["case_judgments.json"],
        policy_blocks=loaded["policy_blocks.json"],
        results=loaded["run_results.json"],
    )
