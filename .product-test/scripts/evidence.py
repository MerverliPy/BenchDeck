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
