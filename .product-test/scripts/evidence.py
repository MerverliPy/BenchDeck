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
import sys
import tempfile
from pathlib import Path
from typing import Any

EVIDENCE_CLASSES = {
    "STATIC_EVIDENCE",
    "SIMULATED_REGRESSION_EVIDENCE",
    "LOCAL_BLACK_BOX_EVIDENCE",
    "PTY_EVIDENCE",
    "LIVE_EXTERNAL_EVIDENCE",
    "INDEPENDENT_REPRODUCTION",
}
STATUSES = {
    "PASSED",
    "FAILED",
    "BLOCKED",
    "SKIPPED_WITH_REASON",
    "NOT_APPLICABLE",
    "FLAKY",
    "INCONCLUSIVE",
}
SEVERITIES = {"P0", "P1", "P2", "P3", "NONE"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MANIFEST_NAME = "manifest.sha256"


class EvidenceError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def _atomic_write(path: Path, content: str) -> None:
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


def validate_evidence_dir(evidence_dir: Path, expected_run_id: str | None = None) -> Path:
    resolved = evidence_dir.expanduser().resolve()
    if expected_run_id:
        if not expected_run_id or Path(expected_run_id).name != expected_run_id:
            raise EvidenceError("expected run ID is invalid")
        if resolved.name != expected_run_id:
            raise EvidenceError(
                f"evidence directory run ID mismatch: expected {expected_run_id!r}, "
                f"found {resolved.name!r}"
            )
    if ".test-evidence" not in resolved.parts:
        raise EvidenceError("evidence directory must be inside .test-evidence")
    _private_directory(resolved)
    return resolved


def validate_record(record: dict[str, Any], expected_run_id: str | None = None) -> None:
    required = (
        "run_id",
        "test_id",
        "feature_id",
        "evidence_class",
        "status",
        "expected",
        "actual",
    )
    missing = [name for name in required if name not in record]
    if missing:
        raise EvidenceError(f"record is missing required field(s): {', '.join(missing)}")

    for name in ("run_id", "test_id", "feature_id"):
        if not isinstance(record[name], str) or not record[name].strip():
            raise EvidenceError(f"record field {name!r} must be a non-empty string")

    if expected_run_id and record["run_id"] != expected_run_id:
        raise EvidenceError(
            f"record run_id mismatch: expected {expected_run_id!r}, found {record['run_id']!r}"
        )
    if record["evidence_class"] not in EVIDENCE_CLASSES:
        raise EvidenceError("record evidence_class is invalid")
    if record["status"] not in STATUSES:
        raise EvidenceError("record status is invalid")
    if "severity" in record and record["severity"] not in SEVERITIES:
        raise EvidenceError("record severity is invalid")

    for name in ("evidence_paths", "reproduction"):
        if name in record:
            value = record[name]
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise EvidenceError(f"record field {name!r} must be an array of strings")


def append_record(
    evidence_dir: Path,
    record: dict[str, Any],
    expected_run_id: str | None = None,
) -> Path:
    evidence_dir = validate_evidence_dir(evidence_dir, expected_run_id)
    if not isinstance(record, dict):
        raise EvidenceError("record JSON must decode to an object")
    record = dict(record)
    validate_record(record, expected_run_id)
    record.setdefault("recorded_at", dt.datetime.now(dt.UTC).isoformat())

    output = evidence_dir / "results.jsonl"
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    fd = os.open(output, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        # fdopen closes fd; this handles only an exception before fdopen owns it.
        with contextlib.suppress(OSError):
            os.close(fd)
    return output


def _manifest_files(directory: Path, manifest_name: str) -> list[Path]:
    manifest = directory / manifest_name
    return [
        path
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path != manifest and not path.name.startswith(f".{manifest_name}.")
    ]


def generate_manifest(directory: Path, manifest_name: str = MANIFEST_NAME) -> Path:
    directory = validate_evidence_dir(directory)
    lines: list[str] = []
    for fpath in _manifest_files(directory, manifest_name):
        rel = fpath.relative_to(directory).as_posix()
        lines.append(f"{sha256_file(fpath)}  {rel}")
    manifest_path = directory / manifest_name
    _atomic_write(manifest_path, "\n".join(lines) + ("\n" if lines else ""))
    return manifest_path


def verify_manifest(
    directory: Path,
    manifest_name: str = MANIFEST_NAME,
) -> tuple[bool, list[str]]:
    directory = directory.expanduser().resolve()
    manifest_path = directory / manifest_name
    if not manifest_path.is_file():
        return False, ["Manifest file not found"]

    errors: list[str] = []
    expected: dict[str, str] = {}
    for number, raw_line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line:
            continue
        digest, separator, relative = raw_line.partition("  ")
        rel_path = Path(relative)
        if (
            not separator
            or not SHA256_RE.fullmatch(digest)
            or not relative
            or rel_path.is_absolute()
            or ".." in rel_path.parts
        ):
            errors.append(f"Malformed manifest line {number}")
            continue
        normalized = rel_path.as_posix()
        if normalized in expected:
            errors.append(f"Duplicate manifest path: {normalized}")
            continue
        expected[normalized] = digest

    actual_files: set[str] = set()
    for fpath in _manifest_files(directory, manifest_name):
        rel = fpath.relative_to(directory).as_posix()
        actual_files.add(rel)
        actual_hash = sha256_file(fpath)
        if rel not in expected:
            errors.append(f"Missing from manifest: {rel}")
        elif expected[rel] != actual_hash:
            errors.append(f"Hash mismatch: {rel}")
    for rel in expected:
        if rel not in actual_files:
            errors.append(f"Missing from filesystem: {rel}")
    return not errors, errors


def write_report(evidence_dir: Path, content: str, expected_run_id: str) -> Path:
    evidence_dir = validate_evidence_dir(evidence_dir, expected_run_id)
    if not content.strip():
        raise EvidenceError("final report content must not be empty")
    output = evidence_dir / "FINAL_PRODUCT_TEST_REPORT.md"
    _atomic_write(output, content)
    return output


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--expected-run-id", required=True)


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser()
    actions = top.add_subparsers(dest="action", required=True)

    record = actions.add_parser("record")
    _common_arguments(record)
    record.add_argument("--record-json", required=True)

    report = actions.add_parser("write-report")
    _common_arguments(report)

    finalize = actions.add_parser("finalize")
    _common_arguments(finalize)

    verify = actions.add_parser("verify")
    _common_arguments(verify)
    return top


def main() -> int:
    args = parser().parse_args()
    evidence_dir = validate_evidence_dir(args.evidence_dir, args.expected_run_id)

    if args.action == "record":
        raw = json.loads(args.record_json)
        if not isinstance(raw, dict):
            raise EvidenceError("record JSON must decode to an object")
        path = append_record(evidence_dir, raw, args.expected_run_id)
        result = {"ok": True, "path": str(path)}
    elif args.action == "write-report":
        path = write_report(evidence_dir, sys.stdin.read(), args.expected_run_id)
        result = {"ok": True, "path": str(path)}
    elif args.action == "finalize":
        path = generate_manifest(evidence_dir)
        result = {"ok": True, "path": str(path), "sha256": sha256_file(path)}
    elif args.action == "verify":
        ok, errors = verify_manifest(evidence_dir)
        result = {"ok": ok, "errors": errors}
        if not ok:
            print(json.dumps(result, sort_keys=True))
            return 2
    else:  # pragma: no cover
        raise EvidenceError(f"unsupported action: {args.action}")

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2) from None
