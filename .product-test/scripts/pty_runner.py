#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

from sandbox_manager import ProductTestError, evidence_root, load_state, repo_root, run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--rows", type=int, default=24)
    parser.add_argument("--cols", type=int, default=80)
    parser.add_argument("--actions-json", default="[]")
    parser.add_argument("--term", default="xterm-256color")
    args = parser.parse_args()
    root = repo_root()
    state = load_state(root)
    spec = {
        "command": f"export PATH=/state/venv/bin:$PATH; {args.command}",
        "rows": args.rows,
        "cols": args.cols,
        "term": args.term,
        "actions": json.loads(args.actions_json),
        "terminate": True,
    }
    encoded = base64.b64encode(json.dumps(spec).encode()).decode()
    started = dt.datetime.now(dt.UTC)
    result = run(
        [
            "docker", "exec", "--workdir", "/workspace", state["container"],
            "/state/venv/bin/python",
            "/workspace/.product-test/scripts/pty_inside.py",
            "--spec-b64", encoded,
        ],
        timeout=300,
        check=False,
    )
    ended = dt.datetime.now(dt.UTC)
    command_id = "pty-" + uuid.uuid4().hex[:10]
    directory = evidence_root(root) / state["run_id"] / "pty"
    directory.mkdir(parents=True, exist_ok=True)
    raw_path = directory / f"{command_id}.json"
    raw_path.write_text(result.stdout, encoding="utf-8")
    stderr_path = directory / f"{command_id}.stderr.txt"
    stderr_path.write_text(result.stderr, encoding="utf-8")
    summary = {
        "run_id": state["run_id"],
        "command_id": command_id,
        "evidence_class": "PTY_EVIDENCE",
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "exit_code": result.returncode,
        "record_path": str(raw_path),
        "record_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "stderr_path": str(stderr_path),
    }
    print(json.dumps(summary, indent=2))
    return 0 if result.returncode == 0 else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProductTestError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
