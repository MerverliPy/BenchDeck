#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
import uuid
from pathlib import Path
from typing import Any

SENSITIVE_PARTS = {".git", ".env", ".envrc", ".npmrc", ".pypirc", ".netrc", "id_rsa", "id_ed25519"}
SENSITIVE_SUFFIXES = {".pem", ".key"}
SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{10,}")


class ProductTestError(RuntimeError):
    pass


def run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 120,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    if check and result.returncode != 0:
        raise ProductTestError(
            f"command failed ({result.returncode}): {' '.join(argv)}\n"
            f"stdout: {redact(result.stdout)}\nstderr: {redact(result.stderr)}"
        )
    return result


def redact(text: str) -> str:
    return SECRET_RE.sub("[REDACTED_API_KEY]", text)


def repo_root() -> Path:
    result = run(["git", "rev-parse", "--show-toplevel"], timeout=20)
    return Path(result.stdout.strip()).resolve()


def repo_key(root: Path) -> str:
    return hashlib.sha256(str(root).encode()).hexdigest()[:12]


def runtime_root(root: Path) -> Path:
    configured = os.environ.get("BENCHDECK_PRODUCT_TEST_RUNTIME")
    if configured:
        return Path(configured).expanduser().resolve() / repo_key(root)
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache / "benchdeck-product-test" / repo_key(root)


def evidence_root(root: Path) -> Path:
    return root / ".test-evidence"


def state_path(root: Path) -> Path:
    return runtime_root(root) / "state.json"


def load_state(root: Path) -> dict[str, Any]:
    path = state_path(root)
    if not path.exists():
        raise ProductTestError("No active sandbox. Run sandbox_create first.")
    return json.loads(path.read_text(encoding="utf-8"))


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def _atomic_private_write(path: Path, content: str) -> None:
    _private_directory(path.parent)
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


def save_state(root: Path, state: dict[str, Any]) -> None:
    path = state_path(root)
    _atomic_private_write(path, json.dumps(state, indent=2) + "\n")


def docker_rootless() -> bool:
    result = run(
        ["docker", "info", "--format", "{{json .SecurityOptions}}"],
        timeout=30,
        check=False,
    )
    return result.returncode == 0 and "rootless" in (result.stdout + result.stderr).lower()


def assert_rootless() -> None:
    if not docker_rootless():
        raise ProductTestError(
            "Rootless Docker was not detected. Refusing to create the product-test sandbox."
        )


def is_sensitive(rel: Path) -> bool:
    lowered = [part.lower() for part in rel.parts]
    if any(part in SENSITIVE_PARTS for part in lowered):
        return True
    if any(part.endswith(tuple(SENSITIVE_SUFFIXES)) for part in lowered):
        return True
    joined = "/".join(lowered)
    return (
        "credential" in joined
        or "secret" in joined
        or "token" in joined
        or joined.endswith(".env")
        or "/.env." in joined
    )


def nul_paths(root: Path, argv: list[str]) -> list[Path]:
    result = subprocess.run(argv, cwd=root, capture_output=True, check=True)
    return [Path(item.decode()) for item in result.stdout.split(b"\0") if item]


def validate_workspace_symlinks(workspace: Path) -> None:
    root = workspace.resolve()
    unsafe: list[str] = []
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        raw_target = os.readlink(path)
        if os.path.isabs(raw_target):
            unsafe.append(f"{path.relative_to(root)} -> {raw_target} (absolute)")
            continue
        resolved = (path.parent / raw_target).resolve(strict=False)
        try:
            rel_target = resolved.relative_to(root)
        except ValueError:
            unsafe.append(f"{path.relative_to(root)} -> {raw_target} (escapes workspace)")
            continue
        if is_sensitive(rel_target):
            unsafe.append(f"{path.relative_to(root)} -> {raw_target} (sensitive target)")
    if unsafe:
        preview = "; ".join(unsafe[:10])
        raise ProductTestError(f"Unsafe repository symlink(s) rejected: {preview}")


def project_requirements(workspace: Path) -> list[str]:
    pyproject = workspace / "pyproject.toml"
    if not pyproject.is_file():
        raise ProductTestError("BenchDeck pyproject.toml is required for dependency isolation")
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project") or {}
    dependencies = list(project.get("dependencies") or [])
    optional = project.get("optional-dependencies") or {}
    dependencies.extend(optional.get("dev") or [])
    dependencies.extend(["pexpect==4.9.0", "pyte==0.8.2"])
    cleaned: list[str] = []
    for item in dependencies:
        if not isinstance(item, str):
            raise ProductTestError("Non-string dependency entry rejected")
        value = item.strip()
        lowered = value.lower()
        if not value or any(ch in value for ch in "\r\n\x00"):
            raise ProductTestError("Malformed dependency entry rejected")
        if " @ " in value or "://" in value or lowered.startswith(("file:", "git+", "hg+", "svn+")):
            raise ProductTestError(f"Direct-reference dependency rejected: {value}")
        cleaned.append(value)
    return cleaned


def create_isolated_copy(source: Path, destination: Path) -> list[str]:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--local", "--no-hardlinks", str(source), str(destination)], timeout=300)

    copied: list[str] = []
    candidates = nul_paths(
        source,
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
    )
    for rel in candidates:
        if is_sensitive(rel):
            continue
        src = source / rel
        dst = destination / rel
        if src.is_symlink():
            target = os.readlink(src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            os.symlink(target, dst)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(rel.as_posix())

    deleted = set(
        nul_paths(source, ["git", "diff", "--name-only", "--diff-filter=D", "-z"])
        + nul_paths(source, ["git", "diff", "--cached", "--name-only", "--diff-filter=D", "-z"])
    )
    for rel in deleted:
        target = destination / rel
        if target.is_file() or target.is_symlink():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
    validate_workspace_symlinks(destination)
    return copied



def prepare_rootless_bind_tree(path: Path) -> None:
    """Make a disposable bind tree writable by a remapped non-root UID.

    Rootless Docker can present host-user-owned bind paths as root-owned
    inside the container. The sandbox runs as UID/GID 1000, so its
    disposable workspace and state directory need other-write permission.

    The common parent is kept mode 0700 by command_create(), preventing
    other host users from traversing into these writable trees.
    """
    if not path.exists():
        raise ProductTestError(f"Disposable bind path does not exist: {path}")

    paths = [path, *path.rglob("*")]

    for current in paths:
        if current.is_symlink():
            continue

        try:
            mode = current.stat().st_mode
        except FileNotFoundError:
            continue

        if current.is_dir():
            current.chmod(0o777)
        elif current.is_file():
            executable = bool(mode & 0o111)
            current.chmod(0o777 if executable else 0o666)


def repository_state(root: Path) -> dict[str, Any]:
    def git(*args: str) -> str:
        return run(["git", *args], cwd=root, timeout=30).stdout.strip()

    status = git("status", "--short")
    return {
        "repository_root": str(root),
        "branch": git("branch", "--show-current"),
        "commit": git("rev-parse", "HEAD"),
        "dirty": bool(status),
        "status_short": status.splitlines(),
        "python_requires": read_python_requires(root),
        "ci_workflows": sorted(
            str(path.relative_to(root))
            for path in (root / ".github" / "workflows").glob("*")
            if path.is_file()
        ),
        "rootless_docker": docker_rootless(),
    }


def read_python_requires(root: Path) -> str | None:
    path = root / "pyproject.toml"
    if not path.exists():
        return None
    match = re.search(r'requires-python\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def image_cache_key(root: Path, python_version: str) -> str:
    """Return a deterministic image tag based on build inputs."""
    build_context = root / ".product-test" / "sandbox"
    hasher = hashlib.sha256()
    hasher.update(python_version.encode())
    for path in sorted(build_context.rglob("*")):
        if path.is_file():
            hasher.update(path.read_bytes())
    req = root / "requirements.txt"
    if req.is_file():
        hasher.update(req.read_bytes())
    dev = root / "requirements-dev.txt"
    if dev.is_file():
        hasher.update(dev.read_bytes())
    digest = hasher.hexdigest()[:16]
    py = python_version.replace(".", "")
    return f"benchdeck-product-test:{repo_key(root)}-py{py}-{digest}"


def unique_names(run_id: str) -> tuple[str, str, str]:
    short = re.sub(r"[^a-z0-9]", "", run_id.lower())[:18]
    return (
        f"benchdeck-pt-{short}",
        f"benchdeck-pt-{short}-internal",
        f"benchdeck-pt-{short}-proxy",
    )


def docker_remove(name: str) -> None:
    run(["docker", "rm", "-f", name], timeout=60, check=False)


def network_remove(name: str) -> None:
    run(["docker", "network", "rm", name], timeout=60, check=False)


def start_proxy(
    *,
    image: str,
    network: str,
    name: str,
    allowlist: list[str],
) -> None:
    docker_remove(name)
    run(
        [
            "docker", "run", "-d",
            "--name", name,
            "--network", network,
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--read-only",
            "--pids-limit", "128",
            "--memory", "256m",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
            "-e", "ALLOWLIST=" + ",".join(allowlist),
            image,
            "python", "/opt/product-test/allowlist_proxy.py",
        ],
        timeout=60,
    )
    run(["docker", "network", "connect", "bridge", name], timeout=30)
    time.sleep(0.5)


def stop_proxy(name: str) -> None:
    docker_remove(name)


def write_command_evidence(
    root: Path,
    run_id: str,
    command_id: str,
    record: dict[str, Any],
    stdout: str,
    stderr: str,
) -> dict[str, str]:
    directory = evidence_root(root) / run_id / "commands"
    _private_directory(directory)
    stdout_path = directory / f"{command_id}.stdout.txt"
    stderr_path = directory / f"{command_id}.stderr.txt"
    safe_stdout = redact(stdout)
    safe_stderr = redact(stderr)
    _atomic_private_write(stdout_path, safe_stdout)
    _atomic_private_write(stderr_path, safe_stderr)
    record["stdout_path"] = str(stdout_path.relative_to(root))
    record["stderr_path"] = str(stderr_path.relative_to(root))
    record["stdout_sha256"] = hashlib.sha256(safe_stdout.encode()).hexdigest()
    record["stderr_sha256"] = hashlib.sha256(safe_stderr.encode()).hexdigest()
    log = evidence_root(root) / run_id / "commands.jsonl"
    _private_directory(log.parent)
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        with contextlib.suppress(OSError):
            os.close(fd)
    return {"stdout": str(stdout_path), "stderr": str(stderr_path), "log": str(log)}


def _image_exists(tag: str) -> bool:
    result = run(["docker", "image", "inspect", tag], timeout=30, check=False)
    return result.returncode == 0


def command_create(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    assert_rootless()
    runtime = runtime_root(root)
    if state_path(root).exists():
        if not args.replace:
            raise ProductTestError("An active sandbox already exists. Use --replace or destroy it.")
        command_destroy(argparse.Namespace(purge=True))

    run_id = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    container, network, proxy = unique_names(run_id)
    workspace = runtime / "workspaces" / run_id / "repo"
    state_dir = runtime / "workspaces" / run_id / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    overlay = create_isolated_copy(root, workspace)

    # Keep the disposable run private on the host while permitting the
    # remapped UID/GID 1000 container user to write the mounted children.
    run_directory = workspace.parent
    run_directory.chmod(0o700)
    prepare_rootless_bind_tree(workspace)
    prepare_rootless_bind_tree(state_dir)

    image = image_cache_key(root, args.python_version)
    if not (args.quick and _image_exists(image)):
        build_context = root / ".product-test" / "sandbox"
        run(
            [
                "docker", "build",
                "--build-arg", f"PYTHON_VERSION={args.python_version}",
                "-t", image,
                str(build_context),
            ],
            timeout=1200,
        )
    else:
        print(f"  (quick) using cached image: {image}", file=sys.stderr)
    image_info = json.loads(
        run(["docker", "image", "inspect", image], timeout=60).stdout
    )[0]
    run(["docker", "network", "create", "--internal", network], timeout=60)
    uid = str(os.getuid())
    gid = str(os.getgid())
    run(
        [
            "docker", "create",
            "--name", container,
            "--network", network,
            "--user", f"{uid}:{gid}",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--pids-limit", "512",
            "--memory", "4g",
            "--cpus", "2",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=512m",
            "--tmpfs", "/home/tester:rw,nosuid,size=64m",
            "-e", "HOME=/home/tester",
            "-v", f"{workspace}:/workspace:rw",
            "-v", f"{state_dir}:/state:rw",
            "-w", "/workspace",
            image,
        ],
        timeout=60,
    )
    run(["docker", "start", container], timeout=60)

    state = {
        "version": 1,
        "run_id": run_id,
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "source_repository": str(root),
        "source_state": repository_state(root),
        "workspace": str(workspace),
        "state_dir": str(state_dir),
        "image": image,
        "image_id": image_info.get("Id"),
        "image_repo_digests": image_info.get("RepoDigests") or [],
        "container": container,
        "network": network,
        "proxy": proxy,
        "python_version": args.python_version,
        "overlay_file_count": len(overlay),
        "evidence_dir": str(evidence_root(root) / run_id),
    }
    save_state(root, state)

    if args.quick and (state_dir / "venv" / "bin" / "python").exists():
        print("  (quick) skipping dependency install — venv already exists", file=sys.stderr)
    elif args.install_dependencies:
        requirements = project_requirements(workspace)
        requirements_path = state_dir / "product-test-requirements.txt"
        requirements_path.write_text("\n".join(requirements) + "\n", encoding="utf-8")
        dependency_container = container + "-deps"
        start_proxy(
            image=image,
            network=network,
            name=proxy,
            allowlist=["pypi.org", "files.pythonhosted.org"],
        )
        try:
            # Dependency packages receive no repository mount. This prevents build/install
            # code from reading or exfiltrating the worktree while network access exists.
            install_dependencies = (
                "python -m venv /state/venv && "
                "/state/venv/bin/python -m pip install --upgrade pip setuptools wheel && "
                "/state/venv/bin/python -m pip install --only-binary=:all: "
                "-r /state/product-test-requirements.txt"
            )
            result = run(
                [
                    "docker", "run", "--rm",
                    "--name", dependency_container,
                    "--network", network,
                    "--user", f"{uid}:{gid}",
                    "--cap-drop", "ALL",
                    "--security-opt", "no-new-privileges:true",
                    "--pids-limit", "256",
                    "--memory", "2g",
                    "--cpus", "2",
                    "--read-only",
                    "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m",
                    "--tmpfs", "/home/tester:rw,nosuid,size=64m",
                    "-e", "HOME=/home/tester",
                    "-e", f"HTTP_PROXY=http://{proxy}:8080",
                    "-e", f"HTTPS_PROXY=http://{proxy}:8080",
                    "-e", "NO_PROXY=localhost,127.0.0.1",
                    "-v", f"{state_dir}:/state:rw",
                    image,
                    "bash", "-lc", install_dependencies,
                ],
                timeout=1200,
                check=False,
            )
            if result.returncode != 0:
                raise ProductTestError(
                    "Dependency installation failed.\n"
                    + redact(result.stdout)
                    + "\n"
                    + redact(result.stderr)
                )
        finally:
            docker_remove(dependency_container)
            stop_proxy(proxy)

        # Install the repository only after egress is removed. The local build backend can
        # execute, but it cannot reach the network and dependencies are already present.
        local_install = run(
            [
                "docker", "exec", container, "bash", "-lc",
                "export PATH=/state/venv/bin:$PATH; "
                "python -m pip install -e '.[dev]' --no-deps --no-build-isolation",
            ],
            timeout=600,
            check=False,
        )
        if local_install.returncode != 0:
            raise ProductTestError(
                "Offline repository installation failed.\n"
                + redact(local_install.stdout)
                + "\n"
                + redact(local_install.stderr)
            )
        freeze = run(
            ["docker", "exec", container, "bash", "-lc", "/state/venv/bin/python -m pip freeze --all"],
            timeout=120,
            check=False,
        )
        state["dependency_requirements"] = requirements
        state["pip_freeze_sha256"] = hashlib.sha256(freeze.stdout.encode()).hexdigest()
        environment_dir = evidence_root(root) / run_id / "environment"
        _private_directory(environment_dir)
        _atomic_private_write(environment_dir / "pip-freeze.txt", redact(freeze.stdout))
        save_state(root, state)

    # Boundary self-test.
    checks = {}
    checks["non_root"] = run(
        ["docker", "exec", container, "bash", "-lc", "test \"$(id -u)\" != 0"],
        check=False,
    ).returncode == 0
    checks["root_read_only"] = run(
        ["docker", "exec", container, "bash", "-lc", "touch /should-fail"],
        check=False,
    ).returncode != 0
    checks["docker_socket_absent"] = run(
        ["docker", "exec", container, "bash", "-lc", "test ! -S /var/run/docker.sock"],
        check=False,
    ).returncode == 0
    checks["external_network_blocked"] = run(
        [
            "docker", "exec", container, "bash", "-lc",
            "python - <<'PY'\nimport socket\ntry:\n socket.create_connection(('1.1.1.1',443),1)\n raise SystemExit(1)\nexcept OSError:\n raise SystemExit(0)\nPY",
        ],
        check=False,
    ).returncode == 0
    if not all(checks.values()):
        command_destroy(argparse.Namespace(purge=False))
        raise ProductTestError(f"Sandbox self-test failed: {checks}")
    state["self_test"] = checks
    save_state(root, state)
    evidence = evidence_root(root) / run_id
    _private_directory(evidence)
    _atomic_private_write(evidence / "sandbox.json", json.dumps(state, indent=2) + "\n")
    return state


def command_exec(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    state = load_state(root)
    cwd = args.cwd.strip("/")
    if cwd.startswith("..") or "/../" in cwd:
        raise ProductTestError("cwd must stay inside /workspace")
    workdir = "/workspace" if not cwd else f"/workspace/{cwd}"
    command_id = dt.datetime.now(dt.UTC).strftime("%H%M%S") + "-" + uuid.uuid4().hex[:8]
    started = dt.datetime.now(dt.UTC)
    inner = [
        "docker", "exec",
        "--workdir", workdir,
        state["container"],
        "bash", "-lc",
        f"export PATH=/state/venv/bin:$PATH; "
        f"timeout --signal=TERM --kill-after=5s {int(args.timeout)}s bash -c {shlex.quote(args.command)}",
    ]
    result = run(inner, timeout=int(args.timeout) + 20, check=False)
    ended = dt.datetime.now(dt.UTC)
    record = {
        "command_id": command_id,
        "run_id": state["run_id"],
        "command": args.command,
        "cwd": workdir,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "exit_code": result.returncode,
        "evidence_class": args.evidence_class,
    }
    paths = write_command_evidence(
        root, state["run_id"], command_id, record, result.stdout, result.stderr
    )
    return {
        **record,
        **paths,
        "stdout_preview": redact(result.stdout)[-4000:],
        "stderr_preview": redact(result.stderr)[-4000:],
    }


def command_patch(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    state = load_state(root)
    result = run(
        [
            "docker", "exec", "--workdir", "/workspace", state["container"],
            "bash", "-lc",
            "git add -N -- . >/dev/null 2>&1 || true; git diff --binary HEAD -- .",
        ],
        timeout=120,
        check=False,
    )
    patch_dir = evidence_root(root) / state["run_id"] / "patches"
    _private_directory(patch_dir)
    patch = patch_dir / "benchdeck-product-test.patch"
    _atomic_private_write(patch, result.stdout)
    return {
        "run_id": state["run_id"],
        "path": str(patch),
        "sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "bytes": len(result.stdout.encode()),
        "stderr": redact(result.stderr),
    }


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    state = load_state(root)
    inspect = run(
        ["docker", "inspect", "-f", "{{.State.Status}}", state["container"]],
        timeout=30,
        check=False,
    )
    state["container_status"] = inspect.stdout.strip() if inspect.returncode == 0 else "missing"
    return state


def command_exec_output(args: argparse.Namespace) -> dict[str, Any]:
    """Execute a command and retrieve matching files from the sandbox."""
    root = repo_root()
    state = load_state(root)
    cwd = args.cwd.strip("/")
    if cwd.startswith("..") or "/../" in cwd:
        raise ProductTestError("cwd must stay inside /workspace")
    workdir = "/workspace" if not cwd else f"/workspace/{cwd}"
    command_id = dt.datetime.now(dt.UTC).strftime("%H%M%S") + "-" + uuid.uuid4().hex[:8]
    started = dt.datetime.now(dt.UTC)
    inner = [
        "docker", "exec",
        "--workdir", workdir,
        state["container"],
        "bash", "-lc",
        f"export PATH=/state/venv/bin:$PATH; "
        f"timeout --signal=TERM --kill-after=5s {int(args.timeout)}s bash -c {shlex.quote(args.command)}",
    ]
    result = run(inner, timeout=int(args.timeout) + 20, check=False)
    ended = dt.datetime.now(dt.UTC)

    files: dict[str, str] = {}
    if args.capture_glob:
        if any(ch in args.capture_glob for ch in "\r\n\x00"):
            raise ProductTestError("capture glob contains an invalid control character")
        glob_cmd = [
            "docker", "exec", state["container"],
            "bash", "-lc",
            'find /workspace -type f -path "$1" -print0 2>/dev/null || true',
            "benchdeck-capture",
            f"*/{args.capture_glob}",
        ]
        paths_result = run(glob_cmd, timeout=30, check=False)
        if paths_result.returncode == 0:
            capture_script = (
                "import json, pathlib, sys; "
                "p=pathlib.Path(sys.argv[1]); "
                "data=p.read_bytes(); max_bytes=262144; "
                "binary=(b'\x00' in data[:8192]); "
                "payload='[OMITTED_BINARY_FILE]' if binary else "
                "data[:max_bytes].decode('utf-8','replace'); "
                "print(json.dumps({'content':payload,'bytes':len(data),'truncated':len(data)>max_bytes}))"
            )
            matched = [path for path in paths_result.stdout.split("\0") if path]
            for rel_path in matched[:20]:
                content = run(
                    [
                        "docker", "exec", state["container"],
                        "python", "-c", capture_script, rel_path,
                    ],
                    timeout=30,
                    check=False,
                )
                if content.returncode != 0:
                    continue
                try:
                    captured = json.loads(content.stdout)
                except json.JSONDecodeError:
                    continue
                key = rel_path.replace("/workspace/", "", 1)
                text = redact(str(captured.get("content", "")))
                if captured.get("truncated"):
                    text += f"\n[TRUNCATED_AT_262144_BYTES; ORIGINAL_BYTES={captured.get('bytes')}]"
                files[key] = text
            if len(matched) > 20:
                files["__capture_limit__"] = (
                    f"[OMITTED_{len(matched) - 20}_ADDITIONAL_FILES; MAX_FILES=20]"
                )

    record = {
        "command_id": command_id,
        "run_id": state["run_id"],
        "command": args.command,
        "cwd": workdir,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "exit_code": result.returncode,
        "evidence_class": args.evidence_class,
        "captured_files": list(files.keys()),
    }
    paths = write_command_evidence(
        root, state["run_id"], command_id, record, result.stdout, result.stderr
    )
    return {
        **record,
        **paths,
        "files": files,
        "stdout_preview": redact(result.stdout)[-4000:],
        "stderr_preview": redact(result.stderr)[-4000:],
    }


def command_destroy(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    path = state_path(root)
    if not path.exists():
        return {"destroyed": False, "reason": "no active sandbox"}
    state = json.loads(path.read_text(encoding="utf-8"))
    docker_remove(state["container"])
    stop_proxy(state["proxy"])
    network_remove(state["network"])
    path.unlink(missing_ok=True)
    if args.purge:
        shutil.rmtree(Path(state["workspace"]).parent, ignore_errors=True)
    return {
        "destroyed": True,
        "run_id": state["run_id"],
        "evidence_preserved": True,
        "workspace_purged": bool(args.purge),
    }


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser()
    sub = top.add_subparsers(dest="action", required=True)

    sub.add_parser("repo-state")

    create = sub.add_parser("create")
    create.add_argument("--python-version", choices=["3.11", "3.12", "3.13"], default="3.12")
    create.add_argument("--install-dependencies", action="store_true")
    create.add_argument("--replace", action="store_true")
    create.add_argument(
        "--quick", action="store_true",
        help="Skip Docker build and dependency install when cached artifacts exist"
    )

    status = sub.add_parser("status")

    execute = sub.add_parser("exec")
    execute.add_argument("--command", required=True)
    execute.add_argument("--cwd", default="")
    execute.add_argument("--timeout", type=int, default=300)
    execute.add_argument(
        "--evidence-class",
        default="LOCAL_BLACK_BOX_EVIDENCE",
        choices=[
            "STATIC_EVIDENCE",
            "SIMULATED_REGRESSION_EVIDENCE",
            "LOCAL_BLACK_BOX_EVIDENCE",
            "PTY_EVIDENCE",
            "LIVE_EXTERNAL_EVIDENCE",
            "INDEPENDENT_REPRODUCTION",
        ],
    )

    exec_output = sub.add_parser("exec-output")
    exec_output.add_argument("--command", required=True)
    exec_output.add_argument("--cwd", default="")
    exec_output.add_argument("--timeout", type=int, default=300)
    exec_output.add_argument("--capture-glob", default="", help="Glob pattern for files to retrieve (e.g. '*.json')")
    exec_output.add_argument(
        "--evidence-class",
        default="LOCAL_BLACK_BOX_EVIDENCE",
        choices=["STATIC_EVIDENCE", "SIMULATED_REGRESSION_EVIDENCE", "LOCAL_BLACK_BOX_EVIDENCE",
                 "PTY_EVIDENCE", "LIVE_EXTERNAL_EVIDENCE", "INDEPENDENT_REPRODUCTION"],
    )

    sub.add_parser("patch")

    destroy = sub.add_parser("destroy")
    destroy.add_argument("--purge", action="store_true")
    return top


def main() -> int:
    args = parser().parse_args()
    try:
        if args.action == "repo-state":
            output = repository_state(repo_root())
        elif args.action == "create":
            output = command_create(args)
        elif args.action == "status":
            output = command_status(args)
        elif args.action == "exec":
            output = command_exec(args)
        elif args.action == "exec-output":
            output = command_exec_output(args)
        elif args.action == "patch":
            output = command_patch(args)
        elif args.action == "destroy":
            output = command_destroy(args)
        else:
            raise ProductTestError(f"unsupported action: {args.action}")
        print(json.dumps(output, indent=2))
        return 0
    except (ProductTestError, subprocess.TimeoutExpired, OSError) as exc:
        print(json.dumps({"error": redact(str(exc))}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
