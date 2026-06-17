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
    redact,
    repo_root,
    run,
    start_proxy,
    stop_proxy,
)

_cleanup_secret_dir: Path | None = None
_cleanup_secret_file: Path | None = None
_CANARY_VALUE = "BENCHDECK_CANARY_NOT_A_REAL_SECRET_7f3a"


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
    del signum, frame
    raise KeyboardInterrupt


def _create_secret_tempdir(key_value: str) -> tuple[Path, Path]:
    secret_dir = Path(tempfile.mkdtemp(prefix="benchdeck-secret-"))
    secret_dir.chmod(0o700)
    secret_file = secret_dir / "api_key"
    old_umask = os.umask(0o077)
    try:
        secret_file.write_text(key_value, encoding="utf-8")
    finally:
        os.umask(old_umask)
    secret_file.chmod(0o400)
    _register_secret_cleanup(secret_dir, secret_file)
    return secret_dir, secret_file


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
    if mode & 0o077:
        raise ProductTestError("OpenAI test key file must not be accessible by group or other")
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


def _atomic_private_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _secure_evidence_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        with contextlib.suppress(OSError):
            if path.is_dir():
                path.chmod(0o700)
            elif path.is_file():
                path.chmod(0o600)
    root.chmod(0o700)


def _generate_evidence_manifest(output_host: Path) -> Path:
    manifest_lines: list[str] = []
    for fpath in sorted(output_host.rglob("*")):
        if fpath.is_file() and fpath.name != "manifest.sha256":
            digest = hashlib.sha256(fpath.read_bytes()).hexdigest()
            manifest_lines.append(f"{digest}  {fpath.relative_to(output_host).as_posix()}")
    manifest_path = output_host / "manifest.sha256"
    _atomic_private_write(
        manifest_path,
        "\n".join(manifest_lines) + ("\n" if manifest_lines else ""),
    )
    return manifest_path


def _contains_secret_value(root: Path, value: str) -> bool:
    needle = value.encode()
    for path in root.rglob("*"):
        if not path.is_file() or path.name == "manifest.sha256":
            continue
        try:
            if needle in path.read_bytes():
                return True
        except OSError:
            return True
    return False


def _copy_container_evidence(container: str, output_host: Path) -> None:
    inspect = run(
        ["docker", "inspect", "-f", "{{.State.Status}}", container],
        timeout=20,
        check=False,
    )
    if inspect.returncode != 0:
        return
    copied = run(
        ["docker", "cp", f"{container}:/evidence/.", str(output_host)],
        timeout=120,
        check=False,
    )
    if copied.returncode != 0:
        _atomic_private_write(
            output_host / "evidence-copy-error.txt",
            redact(copied.stderr or copied.stdout or "docker cp failed"),
        )


def _create_live_container(
    *,
    state: dict[str, object],
    live_container: str,
    proxy: str,
) -> None:
    uid = os.getuid()
    gid = os.getgid()
    created = run(
        [
            "docker",
            "create",
            "--name",
            live_container,
            "--network",
            str(state["network"]),
            "--user",
            f"{uid}:{gid}",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--pids-limit",
            "512",
            "--memory",
            "4g",
            "--cpus",
            "2",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=512m,mode=0700",
            "--tmpfs",
            f"/home/tester:rw,nosuid,nodev,size=64m,mode=0700,uid={uid},gid={gid}",
            "--tmpfs",
            f"/run/secrets:rw,noexec,nosuid,nodev,size=64k,mode=0700,uid={uid},gid={gid}",
            "--tmpfs",
            f"/evidence:rw,nosuid,nodev,size=1g,mode=0700,uid={uid},gid={gid}",
            "-e",
            "HOME=/home/tester",
            "-e",
            f"HTTP_PROXY=http://{proxy}:8080",
            "-e",
            f"HTTPS_PROXY=http://{proxy}:8080",
            "-e",
            "NO_PROXY=localhost,127.0.0.1",
            "-e",
            "OPENAI_API_KEY_FILE=/run/secrets/api_key",
            "-v",
            f"{state['workspace']}:/workspace:ro",
            "-v",
            f"{state['state_dir']}:/state:ro",
            "-w",
            "/workspace",
            str(state["image"]),
            "sleep",
            "infinity",
        ],
        timeout=120,
        check=False,
    )
    if created.returncode != 0:
        raise ProductTestError(
            "failed to create live container: " + redact(created.stderr or created.stdout)
        )
    run(["docker", "start", live_container], timeout=60)


def _install_container_secret(
    live_container: str,
    secret_file: Path,
) -> None:
    uid = os.getuid()
    gid = os.getgid()
    argv = [
        "docker",
        "exec",
        "-i",
        "--user",
        f"{uid}:{gid}",
        live_container,
        "sh",
        "-c",
        (
            "umask 077; "
            "cat > /run/secrets/api_key; "
            "chmod 0400 /run/secrets/api_key"
        ),
    ]

    try:
        with secret_file.open("rb") as secret_stream:
            installed = subprocess.run(
                argv,
                stdin=secret_stream,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )
    except OSError as exc:
        raise ProductTestError(
            "failed to open or stream the host key file"
        ) from exc

    if installed.returncode != 0:
        raise ProductTestError(
            "container secret stdin installation failed"
        )

    verification = run(
        [
            "docker",
            "exec",
            "--user",
            f"{uid}:{gid}",
            live_container,
            "sh",
            "-c",
            (
                "test -r /run/secrets/api_key && "
                'test "$(stat -c %a /run/secrets/api_key)" = 400'
            ),
        ],
        timeout=30,
        check=False,
    )

    if verification.returncode != 0:
        raise ProductTestError(
            "container secret installation or permission verification failed"
        )


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
            "Set BENCHDECK_LIVE_ENABLED=1 only after the canary boundary check passes."
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
        "judges",
        "timeout",
        "max_retries",
        "max_logical_requests",
        "max_http_attempts",
        "max_total_input_tokens",
        "max_total_output_tokens",
        "max_output_tokens_planner",
        "max_output_tokens_agent",
        "max_output_tokens_judge",
    ):
        if getattr(args, value_name) <= 0:
            raise ProductTestError(f"{value_name} must be positive")

    run_id = (
        "live-" + dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    )
    output_host = evidence_root(root) / state["run_id"] / "live" / run_id
    output_host.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_host.chmod(0o700)

    live_container = state["container"] + "-live-" + uuid.uuid4().hex[:6]
    proxy = state["proxy"] + "-live-" + uuid.uuid4().hex[:6]
    secret_dir, secret_file = _create_secret_tempdir(openai_key)

    command = [
        "benchdeck",
        "run",
        "--agent-a",
        f"/workspace/{agent_a}",
        "--output-dir",
        "/evidence/output",
        "--model",
        args.model,
        "--planner-model",
        args.planner_model,
        "--judge-model",
        args.judge_model,
        "--judges",
        str(args.judges),
        "--timeout",
        str(args.timeout),
        "--max-retries",
        str(args.max_retries),
        "--capture-level",
        "full",
        "--max-logical-requests",
        str(args.max_logical_requests),
        "--max-http-attempts",
        str(args.max_http_attempts),
        "--max-total-input-tokens",
        str(args.max_total_input_tokens),
        "--max-total-output-tokens",
        str(args.max_total_output_tokens),
        "--max-output-tokens-planner",
        str(args.max_output_tokens_planner),
        "--max-output-tokens-agent",
        str(args.max_output_tokens_agent),
        "--max-output-tokens-judge",
        str(args.max_output_tokens_judge),
    ]
    if agent_b:
        command += ["--agent-b", f"/workspace/{agent_b}"]
    if plan:
        command += ["--plan", f"/workspace/{plan}"]

    if canary_mode:
        shell_command = (
            'export PATH="/state/venv/bin:$PATH"; '
            'python -c "from pathlib import Path; '
            "p=Path('/run/secrets/api_key'); "
            "assert p.is_file() and p.read_text(); "
            "Path('/evidence/canary-read-ok.txt').write_text('secret transport readable\\n')\""
        )
    else:
        shell_command = (
            'export PATH="/state/venv/bin:$PATH"; '
            "test -r /run/secrets/api_key; exec " + " ".join(shlex.quote(item) for item in command)
        )

    started = dt.datetime.now(dt.UTC)
    result: subprocess.CompletedProcess[str] | None = None
    try:
        start_proxy(
            image=state["image"],
            network=state["network"],
            name=proxy,
            allowlist=["api.openai.com"],
        )
        _create_live_container(state=state, live_container=live_container, proxy=proxy)
        _install_container_secret(live_container, secret_file)
        result = run(
            [
                "docker",
                "exec",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--workdir",
                "/workspace",
                live_container,
                "bash",
                "-lc",
                shell_command,
            ],
            timeout=max(300, args.timeout * args.max_http_attempts),
            check=False,
        )
    finally:
        _copy_container_evidence(live_container, output_host)
        stop_proxy(proxy)
        docker_remove(live_container)
        with contextlib.suppress(OSError):
            secret_file.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            secret_dir.rmdir()
        _secure_evidence_tree(output_host)

    if result is None:
        raise ProductTestError("live container did not execute")

    ended = dt.datetime.now(dt.UTC)
    safe_stdout = redact(result.stdout)
    safe_stderr = redact(result.stderr)
    _atomic_private_write(output_host / "process.stdout.txt", safe_stdout)
    _atomic_private_write(output_host / "process.stderr.txt", safe_stderr)

    secret_exposed = _contains_secret_value(output_host, openai_key)
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
        "manifest_path": str(output_host / "manifest.sha256"),
        "secret_value_recorded": secret_exposed,
    }
    if canary_mode:
        record["canary_boundary"] = {
            "canary_in_evidence": secret_exposed,
            "temp_dir_cleaned": not secret_dir.exists(),
            "secret_not_in_evidence": not secret_exposed,
            "network_request_executed": False,
        }

    _atomic_private_write(output_host / "live-run.json", json.dumps(record, indent=2) + "\n")
    manifest_path = _generate_evidence_manifest(output_host)
    _secure_evidence_tree(output_host)

    record["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    print(json.dumps(record, indent=2))
    if secret_exposed:
        return 3
    return 0 if result.returncode == 0 else 2


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    try:
        raise SystemExit(main())
    except (ProductTestError, OSError, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        print(json.dumps({"error": redact(str(exc))}), file=sys.stderr)
        raise SystemExit(2) from None
    finally:
        with contextlib.suppress(OSError):
            if _cleanup_secret_file and _cleanup_secret_file.exists():
                _cleanup_secret_file.unlink()
        with contextlib.suppress(OSError):
            if _cleanup_secret_dir and _cleanup_secret_dir.exists():
                _cleanup_secret_dir.rmdir()
