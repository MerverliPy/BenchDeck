#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_record(evidence_dir: Path, record: dict[str, Any]) -> Path:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    record = dict(record)
    record.setdefault("recorded_at", dt.datetime.now(dt.UTC).isoformat())
    output = evidence_dir / "results.jsonl"
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return output


def generate_manifest(directory: Path, manifest_name: str = "manifest.sha256") -> Path:
    lines: list[str] = []
    for fpath in sorted(directory.rglob("*")):
        if fpath.is_file() and fpath.name != manifest_name:
            rel = fpath.relative_to(directory)
            h = sha256_file(fpath)
            lines.append(f"{h}  {rel}")
    manifest_path = directory / manifest_name
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path


def verify_manifest(directory: Path, manifest_name: str = "manifest.sha256") -> tuple[bool, list[str]]:
    manifest_path = directory / manifest_name
    if not manifest_path.is_file():
        return False, ["Manifest file not found"]
    errors: list[str] = []
    expected: dict[str, str] = {}
    for line in manifest_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        h, sep, rel = line.partition("  ")
        if sep:
            expected[rel] = h
    actual_files: set[str] = set()
    for fpath in sorted(directory.rglob("*")):
        if fpath.is_file() and fpath != manifest_path:
            rel = str(fpath.relative_to(directory))
            actual_files.add(rel)
            actual_hash = sha256_file(fpath)
            if rel not in expected:
                errors.append(f"Missing from manifest: {rel}")
            elif expected[rel] != actual_hash:
                errors.append(f"Hash mismatch: {rel}")
    for rel in expected:
        if rel not in actual_files:
            errors.append(f"Missing from filesystem: {rel}")
    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--record-json", required=True)
    args = parser.parse_args()
    record = json.loads(args.record_json)
    path = append_record(args.evidence_dir, record)
    print(json.dumps({"ok": True, "path": str(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
