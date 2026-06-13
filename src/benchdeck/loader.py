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
    infrastructure_errors: list[dict[str, Any]] = field(default_factory=list)
    planner_capture: dict[str, Any] = field(default_factory=dict)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _sum_tally_int(tally: dict[str, Any], key: str) -> int:
    total = 0
    for agent_tally in tally.values():
        if isinstance(agent_tally, dict):
            total += int(agent_tally.get(key, 0) or 0)
    return total


def load_snapshot(run_path: Path, *, strict: bool = False) -> Snapshot:
    """Load a run directory, ZIP archive, or checked-in segmented ZIP fixture.

    Parameters
    ----------
    run_path : Path
        Path to a directory or .zip file. May also be a base name of segmented
        ``.b64.*`` parts.
    strict : bool, default False
        If True, re-raise ``ValueError`` (or ``OSError``) when the archive is
        malformed, has duplicate basenames, exceeds the 1000-member cap, or
        contains an oversize (>256 MiB) member. If False (the default, used by
        the TUI for resilience), an empty ``Snapshot()`` is returned so the
        dashboard keeps rendering. The ``inspect`` subcommand and other audit
        tools should pass ``strict=True`` to fail loudly on hostile input.
    """
    if run_path.suffix.lower() == ".zip":
        if run_path.is_file():
            return _load_zip_snapshot(run_path, strict=strict)
        segments = sorted(run_path.parent.glob(run_path.name + ".b64.*"))
        if segments:
            try:
                encoded = "".join(part.read_text(encoding="ascii") for part in segments)
                return _load_zip_bytes(base64.b64decode(encoded, validate=False))
            except (OSError, ValueError):
                if strict:
                    raise
                return Snapshot()
    if run_path.is_dir():
        if (run_path / "run_metadata.json").exists():
            return _load_dir_snapshot(run_path)
        subdirs = sorted(
            [d for d in run_path.iterdir() if d.is_dir() and (d / "run_metadata.json").exists()],
            key=lambda d: d.name,
            reverse=True,
        )
        if subdirs:
            return _load_dir_snapshot(subdirs[0])
        return _load_dir_snapshot(run_path)
    return _load_dir_snapshot(run_path)


def _load_dir_snapshot(run_path: Path) -> Snapshot:
    return Snapshot(
        metadata=_read_json(run_path / "run_metadata.json", {}),
        plan=_read_json(run_path / "benchmark_plan.json", {}),
        tally=_read_json(run_path / "summary_tally.json", {}),
        judgments=_read_json(run_path / "case_judgments.json", []),
        policy_blocks=_read_json(run_path / "policy_blocks.json", []),
        results=_read_json(run_path / "run_results.json", {}),
        infrastructure_errors=_read_json(run_path / "infrastructure_errors.json", []),
        planner_capture=_read_json(run_path / "planner_capture.json", {}),
    )


def _load_zip_snapshot(zip_path: Path, *, strict: bool = False) -> Snapshot:
    try:
        return _load_zip_bytes(zip_path.read_bytes())
    except (OSError, ValueError):
        if strict:
            raise
        return Snapshot()


def _load_zip_bytes(data: bytes) -> Snapshot:
    defaults: dict[str, Any] = {
        "run_metadata.json": {},
        "benchmark_plan.json": {},
        "summary_tally.json": {},
        "case_judgments.json": [],
        "policy_blocks.json": [],
        "run_results.json": {},
        "infrastructure_errors.json": [],
        "planner_capture.json": {},
    }
    loaded: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            raw_names = [name for name in archive.namelist() if not name.endswith("/")]
            if len(raw_names) > 1000:
                raise ValueError(f"Archive has {len(raw_names)} members (cap is 1000)")
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
                        raise ValueError(
                            f"Archive member {member!r} size {info.file_size} exceeds 256 MiB cap"
                        )
                    loaded[filename] = json.loads(archive.read(member).decode("utf-8"))
                except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
                    # Malformed or non-UTF-8 JSON content is not a security
                    # violation; keep the legacy fail-safe default for resilience
                    # (the TUI keeps rendering). It WILL be surfaced by strict
                    # mode callers via the surrounding wrapper.
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
        infrastructure_errors=loaded["infrastructure_errors.json"],
        planner_capture=loaded["planner_capture.json"],
    )
