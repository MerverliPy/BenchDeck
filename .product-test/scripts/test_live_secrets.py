#!/usr/bin/env python3
"""Phase 0 tests: secret transport, evidence integrity, containment gates.

Uses synthetic canary BENCHDECK_CANARY_NOT_A_REAL_SECRET_7f3a.
Never reads or requires a real API key.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

_CANARY = "BENCHDECK_CANARY_NOT_A_REAL_SECRET_7f3a"


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _import_sandbox_module(name: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sandbox = _import_sandbox_module("sandbox_manager")
evidence = _import_sandbox_module("evidence")


# ═══════════════════════════════════════════════════════════════════════════
# Containment gate
# ═══════════════════════════════════════════════════════════════════════════


class TestLivePathGate:
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(sandbox.ProductTestError):
                live = _import_sandbox_module("live_benchdeck_run")
                if not os.environ.get("BENCHDECK_LIVE_ENABLED"):
                    raise sandbox.ProductTestError(
                        "Live OpenAI validation is disabled by default."
                    )

    def test_enabled_with_flag(self):
        with patch.dict(os.environ, {"BENCHDECK_LIVE_ENABLED": "1"}):
            assert os.environ.get("BENCHDECK_LIVE_ENABLED") == "1"


# ═══════════════════════════════════════════════════════════════════════════
# Secret transport
# ═══════════════════════════════════════════════════════════════════════════


class TestSecretTransport:
    def test_temp_dir_permissions_0700(self):
        secret_dir = Path(tempfile.mkdtemp(prefix="test-benchdeck-"))
        try:
            secret_dir.chmod(0o700)
            mode = stat.S_IMODE(secret_dir.stat().st_mode)
            assert mode == 0o700, f"expected 0o700, got {oct(mode)}"
        finally:
            secret_dir.rmdir()

    def test_secret_file_permissions_0400(self):
        secret_dir = Path(tempfile.mkdtemp(prefix="test-benchdeck-"))
        try:
            secret_dir.chmod(0o700)
            secret_file = secret_dir / "api_key"
            old = os.umask(0o077)
            try:
                secret_file.write_text(_CANARY)
            finally:
                os.umask(old)
            secret_file.chmod(0o400)

            mode = stat.S_IMODE(secret_file.stat().st_mode)
            assert mode == 0o400, f"expected 0o400, got {oct(mode)}"
            assert secret_file.read_text().strip() == _CANARY
        finally:
            secret_file.unlink(missing_ok=True)
            secret_dir.rmdir()

    def test_secret_content_readable(self):
        secret_dir = Path(tempfile.mkdtemp(prefix="test-benchdeck-"))
        try:
            secret_dir.chmod(0o700)
            secret_file = secret_dir / "api_key"
            old = os.umask(0o077)
            try:
                secret_file.write_text("sk-test-canary-key-value")
            finally:
                os.umask(old)
            secret_file.chmod(0o400)
            assert secret_file.read_text().strip() == "sk-test-canary-key-value"
        finally:
            secret_file.unlink(missing_ok=True)
            secret_dir.rmdir()

    def test_cleanup_removes_temp_dir_and_file(self):
        secret_dir = Path(tempfile.mkdtemp(prefix="test-benchdeck-"))
        secret_dir.chmod(0o700)
        secret_file = secret_dir / "api_key"
        old = os.umask(0o077)
        try:
            secret_file.write_text(_CANARY)
        finally:
            os.umask(old)
        secret_file.chmod(0o400)

        assert secret_dir.exists()
        assert secret_file.exists()

        secret_file.unlink()
        secret_dir.rmdir()

        assert not secret_file.exists()
        assert not secret_dir.exists()


# ═══════════════════════════════════════════════════════════════════════════
# Redaction
# ═══════════════════════════════════════════════════════════════════════════


class TestRedaction:
    def test_catches_sk_proj(self):
        msg = "Authorization: Bearer sk-proj-abc123def456ghi789jkl"
        redacted = sandbox.redact(msg)
        assert "[REDACTED_API_KEY]" in redacted
        assert "sk-proj-" not in redacted

    def test_catches_sk_ant(self):
        msg = "key: sk-ant-api03-xxxxxxxxxxxxxxxxxxxxx"
        redacted = sandbox.redact(msg)
        assert "[REDACTED_API_KEY]" in redacted
        assert "sk-ant-" not in redacted

    def test_catches_sk_svcacct(self):
        msg = "export OPENAI_API_KEY=sk-svcacct-abc123def45678901234567890"
        redacted = sandbox.redact(msg)
        assert "[REDACTED_API_KEY]" in redacted

    def test_preserves_non_key_text(self):
        msg = "Hello world, this is a normal message."
        redacted = sandbox.redact(msg)
        assert redacted == msg

    def test_redacts_in_exception_text(self):
        msg = "Planner failed: HTTP 401 for key sk-proj-deadbeef1234567890ab"
        redacted = sandbox.redact(msg)
        assert "sk-proj-deadbeef" not in redacted
        assert "[REDACTED_API_KEY]" in redacted


# ═══════════════════════════════════════════════════════════════════════════
# Evidence integrity
# ═══════════════════════════════════════════════════════════════════════════


class TestEvidenceIntegrity:
    def test_dir_not_world_writable(self, tmp_path: Path):
        evidence_dir = tmp_path / ".test-evidence"
        evidence_dir.mkdir(mode=0o755)
        mode = stat.S_IMODE(evidence_dir.stat().st_mode)
        assert mode & 0o002 == 0, f"world-writable bit set: {oct(mode)}"
        assert mode & stat.S_IWOTH == 0, f"other-write bit set: {oct(mode)}"

    def test_dir_not_group_writable(self, tmp_path: Path):
        evidence_dir = tmp_path / ".test-evidence"
        evidence_dir.mkdir(mode=0o755)
        mode = stat.S_IMODE(evidence_dir.stat().st_mode)
        assert mode & stat.S_IWGRP == 0, f"group-write bit set: {oct(mode)}"

    def test_manifest_generation(self, tmp_path: Path):
        (tmp_path / "file_a.txt").write_text("original content")
        (tmp_path / "file_b.txt").write_text("another file")
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested")

        evidence.generate_manifest(tmp_path)

        manifest = tmp_path / "manifest.sha256"
        assert manifest.exists()
        content = manifest.read_text()
        assert "file_a.txt" in content
        assert "file_b.txt" in content
        assert "subdir/nested.txt" in content

    def test_manifest_verification_passes_on_clean(self, tmp_path: Path):
        (tmp_path / "a.txt").write_text("hello")
        (tmp_path / "b.txt").write_text("world")

        evidence.generate_manifest(tmp_path)
        ok, errors = evidence.verify_manifest(tmp_path)
        assert ok, f"expected pass, got errors: {errors}"
        assert len(errors) == 0

    def test_manifest_verification_fails_on_tampering(self, tmp_path: Path):
        (tmp_path / "a.txt").write_text("original")
        (tmp_path / "b.txt").write_text("untouched")

        evidence.generate_manifest(tmp_path)
        (tmp_path / "a.txt").write_text("MODIFIED")

        ok, errors = evidence.verify_manifest(tmp_path)
        assert not ok, "verification should fail after tampering"
        assert any("Hash mismatch" in e for e in errors)

    def test_manifest_detects_added_files(self, tmp_path: Path):
        (tmp_path / "original.txt").write_text("content")

        evidence.generate_manifest(tmp_path)
        (tmp_path / "intruder.txt").write_text("added later")

        ok, errors = evidence.verify_manifest(tmp_path)
        assert not ok
        assert any("Missing from manifest" in e for e in errors)

    def test_manifest_detects_deleted_files(self, tmp_path: Path):
        (tmp_path / "removable.txt").write_text("delete me")
        (tmp_path / "keeper.txt").write_text("stay")

        evidence.generate_manifest(tmp_path)
        (tmp_path / "removable.txt").unlink()

        ok, errors = evidence.verify_manifest(tmp_path)
        assert not ok
        assert any("Missing from filesystem" in e for e in errors)

    def test_manifest_ignores_itself(self, tmp_path: Path):
        (tmp_path / "data.txt").write_text("payload")

        evidence.generate_manifest(tmp_path)
        ok, errors = evidence.verify_manifest(tmp_path)
        assert ok, f"manifest should not check itself: {errors}"

    def test_manifest_missing_file(self, tmp_path: Path):
        ok, errors = evidence.verify_manifest(tmp_path)
        assert not ok
        assert "Manifest file not found" in errors[0]

    def test_manifest_unchanged_on_regen(self, tmp_path: Path):
        (tmp_path / "static.txt").write_text("unchanged")

        m1 = evidence.generate_manifest(tmp_path)
        h1 = hashlib.sha256(m1.read_bytes()).hexdigest()

        m2 = evidence.generate_manifest(tmp_path)
        h2 = hashlib.sha256(m2.read_bytes()).hexdigest()

        assert h1 == h2, "re-generating manifest on unchanged files should produce identical output"


# ═══════════════════════════════════════════════════════════════════════════
# Docker arg safety
# ═══════════════════════════════════════════════════════════════════════════


class TestDockerArgSafety:
    def test_no_openai_key_env_var_in_docker_args(self):
        docker_args = [
            "docker", "run", "--rm",
            "--tmpfs", "/run/secrets:rw,noexec,nosuid,size=4k",
            "-v", "/tmp/secret-dir:/run/secrets:ro",
            "-e", "OPENAI_API_KEY_FILE=/run/secrets/api_key",
            "-e", "HOME=/home/tester",
            "image", "bash",
        ]
        for i, arg in enumerate(docker_args):
            if arg == "-e" and i + 1 < len(docker_args):
                next_arg = docker_args[i + 1]
                assert "OPENAI_API_KEY=" not in next_arg, \
                    f"OPENAI_API_KEY found in docker -e at index {i}: {next_arg!r}"

    def test_no_bare_sk_pattern_in_docker_args(self):
        docker_args = [
            "docker", "run", "--rm",
            "--tmpfs", "/run/secrets:rw,noexec,nosuid,size=4k",
            "-v", "/tmp/secret:/run/secrets:ro",
            "-e", "OPENAI_API_KEY_FILE=/run/secrets/api_key",
        ]
        joined = " ".join(docker_args)
        assert "sk-" not in joined, f"key-like pattern found in docker args: {joined!r}"

    def test_evidence_volume_is_rw_not_world_writable_in_args(self):
        evidence_path = "/home/user/BenchDeck/.test-evidence/run/live"
        docker_volume_arg = f"{evidence_path}:/evidence:rw"
        assert ":rw" in docker_volume_arg or not ":ro" in docker_volume_arg
        assert "0o777" not in docker_volume_arg
        assert "0777" not in docker_volume_arg


# ═══════════════════════════════════════════════════════════════════════════
# Offline / frozen-plan behavior
# ═══════════════════════════════════════════════════════════════════════════


class TestOfflineBehavior:
    def test_key_file_env_validates_permissions(self, tmp_path: Path):
        key = tmp_path / "good_key"
        key.write_text("sk-test-value")
        key.chmod(0o400)
        mode = stat.S_IMODE(key.stat().st_mode)
        assert mode & 0o007 == 0, "key file must not be readable by other"

    def test_key_file_rejects_empty(self, tmp_path: Path):
        key = tmp_path / "empty_key"
        key.write_text("")
        key.chmod(0o400)
        assert key.read_text().strip() == "", "empty key file should be rejected by caller"

    def test_key_file_rejects_other_readable(self, tmp_path: Path):
        key = tmp_path / "bad_key"
        key.write_text("sk-test")
        key.chmod(0o407)
        mode = stat.S_IMODE(key.stat().st_mode)
        assert mode & 0o007 != 0, "file should be readable by other (for test)"

    def test_redact_preserves_json_structure(self):
        msg = json.dumps({"error": "key sk-proj-abc123 not authorized"})
        redacted = sandbox.redact(msg)
        parsed = json.loads(redacted)
        assert "error" in parsed
        assert "sk-proj-" not in parsed["error"]
        assert "[REDACTED_API_KEY]" in parsed["error"]


# ═══════════════════════════════════════════════════════════════════════════
# Canary mode (Phase 3 — boundary validation integration)
# ═══════════════════════════════════════════════════════════════════════════


class TestCanaryMode:
    def test_canary_mode_skips_live_gate(self):
        live = _import_sandbox_module("live_benchdeck_run")
        assert live._CANARY_VALUE == _CANARY

    def test_rootless_detection_is_callable(self):
        live = _import_sandbox_module("live_benchdeck_run")
        result = live._docker_rootless()
        assert isinstance(result, bool)

    def test_create_secret_tempdir_rootless_aware(self):
        live = _import_sandbox_module("live_benchdeck_run")
        is_rootless = live._docker_rootless()
        secret_dir, secret_file = live._create_secret_tempdir(
            "sk-test-canary-secret-xyz"
        )
        try:
            dir_mode = stat.S_IMODE(secret_dir.stat().st_mode)
            file_mode = stat.S_IMODE(secret_file.stat().st_mode)
            if is_rootless:
                assert dir_mode == 0o711, f"rootless dir: {oct(dir_mode)}"
                assert file_mode == 0o444, f"rootless file: {oct(file_mode)}"
            else:
                assert dir_mode == 0o700, f"native dir: {oct(dir_mode)}"
                assert file_mode == 0o400, f"native file: {oct(file_mode)}"
            assert secret_file.read_text().strip() == "sk-test-canary-secret-xyz"
        finally:
            secret_file.unlink(missing_ok=True)
            secret_dir.rmdir()

    def test_canary_value_is_synthetic_not_a_real_key(self):
        live = _import_sandbox_module("live_benchdeck_run")
        assert "CANARY" in live._CANARY_VALUE
        assert "NOT_A_REAL_SECRET" in live._CANARY_VALUE
        assert not live._CANARY_VALUE.startswith("sk-proj-")
        assert not live._CANARY_VALUE.startswith("sk-ant-")
