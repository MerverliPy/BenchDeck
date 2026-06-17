from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".product-test" / "scripts"


def load_script(name: str):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(f"benchdeck_test_{name}", SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_record(run_id: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "test_id": "PT-001",
        "feature_id": "FEATURE-001",
        "evidence_class": "LOCAL_BLACK_BOX_EVIDENCE",
        "status": "PASSED",
        "expected": "expected",
        "actual": "actual",
        "severity": "NONE",
    }


def test_evidence_rejects_unstructured_record(tmp_path: Path) -> None:
    evidence = load_script("evidence")
    directory = tmp_path / ".test-evidence" / "run-1"
    with pytest.raises(evidence.EvidenceError):
        evidence.append_record(directory, {"arbitrary": True}, "run-1")


def test_evidence_record_manifest_and_modes(tmp_path: Path) -> None:
    evidence = load_script("evidence")
    directory = tmp_path / ".test-evidence" / "run-1"
    result = evidence.append_record(directory, valid_record("run-1"), "run-1")
    report = evidence.write_report(directory, "# Report\n", "run-1")
    manifest = evidence.generate_manifest(directory)
    ok, errors = evidence.verify_manifest(directory)

    assert ok, errors
    assert result.stat().st_mode & 0o777 == 0o600
    assert report.stat().st_mode & 0o777 == 0o600
    assert manifest.stat().st_mode & 0o777 == 0o600
    assert directory.stat().st_mode & 0o777 == 0o700


def test_manifest_detects_post_finalize_change(tmp_path: Path) -> None:
    evidence = load_script("evidence")
    directory = tmp_path / ".test-evidence" / "run-1"
    evidence.append_record(directory, valid_record("run-1"), "run-1")
    evidence.generate_manifest(directory)
    (directory / "results.jsonl").write_text("modified\n", encoding="utf-8")
    ok, errors = evidence.verify_manifest(directory)
    assert not ok
    assert any("Hash mismatch" in error for error in errors)


def test_key_file_rejects_group_access(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    live = load_script("live_benchdeck_run")
    key = tmp_path / "api_key"
    key.write_text("synthetic-value", encoding="utf-8")
    key.chmod(0o640)
    monkeypatch.setenv("BENCHDECK_TEST_OPENAI_KEY_FILE", str(key))
    with pytest.raises(live.ProductTestError):
        live.key_file()


def test_secret_tempfile_is_owner_only() -> None:
    live = load_script("live_benchdeck_run")
    secret_dir, secret_file = live._create_secret_tempdir("synthetic-value")
    try:
        assert secret_dir.stat().st_mode & 0o777 == 0o700
        assert secret_file.stat().st_mode & 0o777 == 0o400
    finally:
        secret_file.unlink(missing_ok=True)
        secret_dir.rmdir()


def test_tool_wrappers_do_not_forward_complete_host_environment() -> None:
    sources = list((ROOT / ".opencode" / "tools").glob("*.ts"))
    sources.append(ROOT / ".opencode" / "lib" / "product_test_runtime.ts")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    assert "env: process.env" not in combined
    assert "BENCHDECK_TEST_OPENAI_KEY_FILE" in combined
    assert "childEnvironment" in combined


def test_product_agents_explicitly_decide_every_custom_tool() -> None:
    tool_names = {
        "repository_state",
        "sandbox_create",
        "sandbox_status",
        "sandbox_exec",
        "sandbox_exec_with_output",
        "sandbox_pty",
        "sandbox_export_patch",
        "sandbox_destroy",
        "benchdeck_live_run",
        "evidence_record",
        "evidence_write_report",
        "evidence_finalize",
        "evidence_verify",
    }
    for path in sorted((ROOT / ".opencode" / "agents").glob("benchdeck*.md")):
        text = path.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]
        for name in tool_names:
            assert frontmatter.count(f"  {name}:") == 1, f"{path.name}: {name}"
        assert '    ".envrc": deny' in frontmatter
        assert '    "**/.envrc": deny' in frontmatter


def test_current_tui_paths_are_used_in_active_opencode_workflow() -> None:
    for path in (ROOT / ".opencode").rglob("*"):
        if path.is_file() and path.suffix in {".md", ".json", ".jsonc"}:
            assert "src/benchdeck/tui.py" not in path.read_text(encoding="utf-8"), path


def test_canary_main_reaches_execution_without_real_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    live = load_script("live_benchdeck_run")
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".test-evidence").mkdir()
    state_dir = tmp_path / "state"
    workspace = tmp_path / "workspace"
    state_dir.mkdir()
    workspace.mkdir()
    state = {
        "run_id": "run-1",
        "container": "sandbox",
        "proxy": "proxy",
        "image": "image",
        "network": "network",
        "workspace": str(workspace),
        "state_dir": str(state_dir),
    }

    monkeypatch.setattr(live, "repo_root", lambda: root)
    monkeypatch.setattr(live, "load_state", lambda _root: state)
    monkeypatch.setattr(live, "start_proxy", lambda **_kwargs: None)
    monkeypatch.setattr(live, "stop_proxy", lambda _name: None)
    monkeypatch.setattr(live, "docker_remove", lambda _name: None)
    monkeypatch.setattr(live, "_create_live_container", lambda **_kwargs: None)
    monkeypatch.setattr(live, "_install_container_secret", lambda *_args: None)
    monkeypatch.setattr(live, "_copy_container_evidence", lambda *_args: None)
    monkeypatch.setattr(
        live,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "live_benchdeck_run.py",
            "--canary",
            "--agent-a",
            "agent.md",
            "--model",
            "canary",
            "--planner-model",
            "canary",
            "--judge-model",
            "canary",
        ],
    )

    assert live.main() == 0
    records = list((root / ".test-evidence" / "run-1" / "live").glob("*/live-run.json"))
    assert len(records) == 1
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert record["canary_boundary"]["network_request_executed"] is False
    assert record["canary_boundary"]["secret_not_in_evidence"] is True


def test_handoff_does_not_normalize_plaintext_api_key_storage() -> None:
    handoff = (ROOT / "AGENT_HANDOFF.md").read_text(encoding="utf-8")
    assert re.search(r"export\s+OPENAI_API_KEY\s*=\s*sk-[A-Za-z0-9_-]+", handoff) is None
    assert "Intentionally retained" not in handoff
    assert "Open — rotate/revoke and remove" in handoff


def test_live_secret_install_streams_file_over_docker_exec_stdin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    live = load_script("live_benchdeck_run")
    secret_file = tmp_path / "api_key"
    secret_file.write_bytes(b"synthetic-value")
    secret_file.chmod(0o400)
    observed: dict[str, object] = {}

    def fake_subprocess_run(
        argv: list[str],
        **kwargs: object,
    ):
        stream = kwargs["stdin"]
        observed["argv"] = argv
        observed["payload"] = stream.read()
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    def fake_run(
        argv: list[str],
        **_kwargs: object,
    ):
        observed["verification"] = argv
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(
        live.subprocess,
        "run",
        fake_subprocess_run,
    )
    monkeypatch.setattr(live, "run", fake_run)

    live._install_container_secret(
        "live-container",
        secret_file,
    )

    argv = observed["argv"]

    assert argv[:3] == ["docker", "exec", "-i"]
    assert "cp" not in argv
    assert observed["payload"] == b"synthetic-value"
    assert "synthetic-value" not in " ".join(argv)
    assert "OPENAI_API_KEY=" not in " ".join(argv)
    assert "--user" in argv


def test_boundary_secret_transport_uses_stdin_not_docker_cp() -> None:
    source = (SCRIPTS / "boundary_validate.sh").read_text(encoding="utf-8")

    assert 'docker cp "${SECRET_DIR}/api_key"' not in source
    assert ('docker exec -i --user "${UID_VALUE}:${GID_VALUE}"') in source
    assert '< "${SECRET_DIR}/api_key"' in source
    assert 'pass "SECRET_STREAM"' in source
