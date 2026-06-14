#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shlex
import stat
import subprocess
import sys
import uuid
from pathlib import Path

from sandbox_manager import (
    ProductTestError,
    docker_remove,
    evidence_root,
    load_state,
    repo_root,
    redact,
    run,
    start_proxy,
    stop_proxy,
)


def safe_relative(path: str, *, required: bool = True) -> str | None:
    if not path:
        if required:
            raise ProductTestError("required relative path is empty")
        return None
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ProductTestError(f"path must be relative to the sandbox workspace: {path}")
    return candidate.as_posix()


def key_file() -> Path:
    raw = os.environ.get("BENCHDECK_TEST_OPENAI_KEY_FILE")
    if not raw:
        raise ProductTestError(
            "BENCHDECK_TEST_OPENAI_KEY_FILE is not configured; live testing is blocked."
        )
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise ProductTestError("configured OpenAI test key file does not exist")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o007:
        # Reject only if 'other' has any permission; allow owner+group
        # so the WSL2 9P bind mount of mode 0440 is readable to the
        # container's run-as user (same UID, group read preserved).
        raise ProductTestError("OpenAI test key file must not be readable by other")
    if not path.read_text(encoding="utf-8").strip():
        raise ProductTestError("OpenAI test key file is empty")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-a", required=True)
    parser.add_argument("--agent-b", default="")
    parser.add_argument("--plan", default="")
    parser.add_argument("--model", required=True)
    parser.add_argument("--planner-model", required=True)
    parser.add_argument("--judge-model", required=True)
    parser.add_argument("--judges", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--max-logical-requests", type=int, default=30)
    parser.add_argument("--max-http-attempts", type=int, default=45)
    parser.add_argument("--max-total-input-tokens", type=int, default=120000)
    parser.add_argument("--max-total-output-tokens", type=int, default=30000)
    parser.add_argument("--max-output-tokens-planner", type=int, default=4000)
    parser.add_argument("--max-output-tokens-agent", type=int, default=4000)
    parser.add_argument("--max-output-tokens-judge", type=int, default=4000)
    args = parser.parse_args()

    root = repo_root()
    state = load_state(root)
    secret = key_file()
    agent_a = safe_relative(args.agent_a)
    agent_b = safe_relative(args.agent_b, required=False)
    plan = safe_relative(args.plan, required=False)
    for value_name in (
        "judges", "timeout", "max_retries", "max_logical_requests",
        "max_http_attempts", "max_total_input_tokens", "max_total_output_tokens",
        "max_output_tokens_planner", "max_output_tokens_agent", "max_output_tokens_judge",
    ):
        if getattr(args, value_name) <= 0:
            raise ProductTestError(f"{value_name} must be positive")

    run_id = "live-" + dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    output_host = evidence_root(root) / state["run_id"] / "live" / run_id
    output_host.mkdir(parents=True, exist_ok=True)
    live_container = state["container"] + "-live-" + uuid.uuid4().hex[:6]
    proxy = state["proxy"] + "-live"
    start_proxy(
        image=state["image"],
        network=state["network"],
        name=proxy,
        allowlist=["api.openai.com"],
    )

    command = [
        "benchdeck", "run",
        "--agent-a", f"/workspace/{agent_a}",
        "--output-dir", "/evidence/output",
        "--model", args.model,
        "--planner-model", args.planner_model,
        "--judge-model", args.judge_model,
        "--judges", str(args.judges),
        "--timeout", str(args.timeout),
        "--max-retries", str(args.max_retries),
        "--capture-level", "full",
        "--max-logical-requests", str(args.max_logical_requests),
        "--max-http-attempts", str(args.max_http_attempts),
        "--max-total-input-tokens", str(args.max_total_input_tokens),
        "--max-total-output-tokens", str(args.max_total_output_tokens),
        "--max-output-tokens-planner", str(args.max_output_tokens_planner),
        "--max-output-tokens-agent", str(args.max_output_tokens_agent),
        "--max-output-tokens-judge", str(args.max_output_tokens_judge),
    ]
    if agent_b:
        command += ["--agent-b", f"/workspace/{agent_b}"]
    if plan:
        command += ["--plan", f"/workspace/{plan}"]

    shell_command = (
        'export PATH="/state/venv/bin:$PATH"; '
        'export OPENAI_API_KEY="$(cat /run/secrets/openai_api_key)"; '
        "exec " + " ".join(shlex.quote(item) for item in command)
    )
    started = dt.datetime.now(dt.UTC)
    try:
        result = run(
            [
                "docker", "run", "--rm",
                "--name", live_container,
                "--network", state["network"],
                "--user", f"{os.getuid()}:{os.getgid()}",
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges:true",
                "--pids-limit", "512",
                "--memory", "4g",
                "--cpus", "2",
                "--read-only",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=512m",
                "--tmpfs", "/home/tester:rw,nosuid,size=64m",
                "-e", "HOME=/home/tester",
                "-e", f"HTTP_PROXY=http://{proxy}:8080",
                "-e", f"HTTPS_PROXY=http://{proxy}:8080",
                "-e", "NO_PROXY=localhost,127.0.0.1",
                "-v", f"{state['workspace']}:/workspace:ro",
                "-v", f"{state['state_dir']}:/state:ro",
                "-v", f"{output_host}:/evidence:rw",
                "-v", f"{secret}:/run/secrets/openai_api_key:ro",
                "-w", "/workspace",
                state["image"],
                "bash", "-lc", shell_command,
            ],
            timeout=max(300, args.timeout * args.max_http_attempts),
            check=False,
        )
    finally:
        stop_proxy(proxy)
        docker_remove(live_container)
    ended = dt.datetime.now(dt.UTC)
    stdout_path = output_host / "process.stdout.txt"
    stderr_path = output_host / "process.stderr.txt"
    safe_stdout = redact(result.stdout)
    safe_stderr = redact(result.stderr)
    stdout_path.write_text(safe_stdout, encoding="utf-8")
    stderr_path.write_text(safe_stderr, encoding="utf-8")
    record = {
        "run_id": state["run_id"],
        "live_run_id": run_id,
        "evidence_class": "LIVE_EXTERNAL_EVIDENCE",
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "exit_code": result.returncode,
        "models": {
            "agent": args.model,
            "planner": args.planner_model,
            "judge": args.judge_model,
        },
        "budgets": {
            "max_logical_requests": args.max_logical_requests,
            "max_http_attempts": args.max_http_attempts,
            "max_total_input_tokens": args.max_total_input_tokens,
            "max_total_output_tokens": args.max_total_output_tokens,
        },
        "output_directory": str(output_host),
        "stdout_sha256": hashlib.sha256(safe_stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(safe_stderr.encode()).hexdigest(),
        "secret_value_recorded": False,
    }
    (output_host / "live-run.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0 if result.returncode == 0 else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProductTestError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": redact(str(exc))}), file=sys.stderr)
        raise SystemExit(2)
