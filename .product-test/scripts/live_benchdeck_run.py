#!/usr/bin/env python3
from __future__ import annotations

import argparse
import atexit
import contextlib
import datetime as dt
import hashlib
import json
import os
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
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

_cleanup_secret_dir: Path | None = None
_cleanup_secret_file: Path | None = None
_CANARY_VALUE = "BENCHDECK_CANARY_NOT_A_REAL_SECRET_7f3a"


def _docker_rootless() -> bool:
    result = run(
        ["docker", "info", "--format", "{{json .SecurityOptions}}"],
        timeout=30,
        check=False,
    )
    return result.returncode == 0 and "rootless" in (result.stdout + result.stderr).lower()


def _register_secret_cleanup(secret_dir: Path, secret_file: Path) -> None:
    global _cleanup_secret_dir, _cleanup_secret_file
    _cleanup_secret_dir = secret_dir
    _cleanup_secret_file = secret_file

    def _clean() -> None:
        with contextlib.suppress(OSError):
            if _cleanup_secret_file and _cleanup_secret_file.exists():
                _cleanup_secret_file.unlink()
        with contextlib.suppress(OSError):
            if _cleanup_secret_dir and _cleanup_secret_dir.exists():
                _cleanup_secret_dir.rmdir()

    atexit.register(_clean)


def _signal_handler(signum: int, frame: object) -> None:
    raise KeyboardInterrupt


def _create_secret_tempdir(key_value: str) -> tuple[Path, Path]:
    is_rootless = _docker_rootless()
    secret_dir = Path(tempfile.mkdtemp(prefix="benchdeck-secret-"))
    if is_rootless:
        secret_dir.chmod(0o711)
        secret_file = secret_dir / "api_key"
        old_umask = os.umask(0o022)
    else:
        secret_dir.chmod(0o700)
        secret_file = secret_dir / "api_key"
        old_umask = os.umask(0o077)
    try:
        secret_file.write_text(key_value, encoding="utf-8")
    finally:
        os.umask(old_umask)
    if is_rootless:
        secret_file.chmod(0o444)
    else:
        secret_file.chmod(0o400)
    _register_secret_cleanup(secret_dir, secret_file)
    return secret_dir, secret_file


def _verify_secret_readable(live_container: str, path: str = "/run/secrets/api_key") -> bool:
    verify = run(
        ["docker", "exec", live_container, "bash", "-c", f"test -r {shlex.quote(path)} && echo OK || echo FAIL"],
        timeout=20,
        check=False,
    )
    return "OK" in verify.stdout


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
        raise ProductTestError("OpenAI test key file must not be readable by other")
    if not path.read_text(encoding="utf-8").strip():
        raise ProductTestError("OpenAI test key file is empty")
    return path


def safe_relative(path: str, *, required: bool = True) -> str | None:
    if not path:
        if required:
            raise ProductTestError("required relative path is empty")
        return None
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ProductTestError(f"path must be relative to the sandbox workspace: {path}")
    return candidate.as_posix()


def _generate_evidence_manifest(output_host: Path) -> Path:
    manifest_lines: list[str] = []
    for fpath in sorted(output_host.rglob("*")):
        if fpath.is_file() and fpath.name != "manifest.sha256":
            h = hashlib.sha256(fpath.read_bytes()).hexdigest()
            manifest_lines.append(f"{h}  {fpath.relative_to(output_host)}")
    manifest_path = output_host / "manifest.sha256"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    return manifest_path


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
    parser.add_argument("--canary", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    canary_mode = bool(args.canary)

    if not os.environ.get("BENCHDECK_LIVE_ENABLED") and not canary_mode:
        raise ProductTestError(
            "Live OpenAI validation is disabled by default. "
            "Set BENCHDECK_LIVE_ENABLED=1 to enable after validating "
            "the secret transport mechanism."
        )

    root = repo_root()
    state = load_state(root)
    if canary_mode:
        openai_key = _CANARY_VALUE
    else:
        secret = key_file()
        openai_key = secret.read_text(encoding="utf-8").strip()
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
    output_host.chmod(0o755)

    live_container = state["container"] + "-live-" + uuid.uuid4().hex[:6]
    proxy = state["proxy"] + "-live"

    openai_key = secret.read_text(encoding="utf-8").strip()
    secret_dir, secret_file = _create_secret_tempdir(openai_key)

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
        'test -r /run/secrets/api_key || '
        "{ echo 'FATAL: Secret file /run/secrets/api_key not readable'"
        " '(bind mount permission issue on this platform)'; exit 1; }; "
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
                "--tmpfs", "/run/secrets:rw,noexec,nosuid,size=4k",
                "-e", "HOME=/home/tester",
                "-e", f"HTTP_PROXY=http://{proxy}:8080",
                "-e", f"HTTPS_PROXY=http://{proxy}:8080",
                "-e", "NO_PROXY=localhost,127.0.0.1",
                "-e", "OPENAI_API_KEY_FILE=/run/secrets/api_key",
                "-v", f"{state['workspace']}:/workspace:ro",
                "-v", f"{state['state_dir']}:/state:ro",
                "-v", f"{output_host}:/evidence:rw",
                "-v", f"{secret_dir}:/run/secrets:ro",
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
        with contextlib.suppress(OSError):
            if secret_file.exists():
                secret_file.unlink()
        with contextlib.suppress(OSError):
            if secret_dir.exists():
                secret_dir.rmdir()

    ended = dt.datetime.now(dt.UTC)
    stdout_path = output_host / "process.stdout.txt"
    stderr_path = output_host / "process.stderr.txt"
    safe_stdout = redact(result.stdout)
    safe_stderr = redact(result.stderr)
    stdout_path.write_text(safe_stdout, encoding="utf-8")
    stderr_path.write_text(safe_stderr, encoding="utf-8")

    manifest_path = _generate_evidence_manifest(output_host)

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
        "manifest_path": str(manifest_path),
        "secret_value_recorded": False,
    }
    if canary_mode:
        canary_in_stdout = _CANARY_VALUE in safe_stdout
        canary_in_stderr = _CANARY_VALUE in safe_stderr
        record["canary_boundary"] = {
            "canary_in_stdout": canary_in_stdout,
            "canary_in_stderr": canary_in_stderr,
            "manifest_generated": manifest_path.exists(),
            "temp_dir_cleaned": not secret_dir.exists()
            if secret_dir is not None
            else True,
            "secret_not_in_evidence": not canary_in_stdout and not canary_in_stderr,
        }
    (output_host / "live-run.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0 if result.returncode == 0 else 2


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    try:
        raise SystemExit(main())
    except (ProductTestError, OSError, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        print(json.dumps({"error": redact(str(exc))}), file=sys.stderr)
        raise SystemExit(2)
    finally:
        with contextlib.suppress(OSError):
            if _cleanup_secret_file and _cleanup_secret_file.exists():
                _cleanup_secret_file.unlink()
        with contextlib.suppress(OSError):
            if _cleanup_secret_dir and _cleanup_secret_dir.exists():
                _cleanup_secret_dir.rmdir()
