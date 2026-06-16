"""Regression tests for the loader ZIP-safety contract (SEC-004/005/006).

Verifies that ``load_snapshot(strict=True)`` re-raises precise ``LoadError``
subclasses for every malformed-input class (member cap, oversize member,
duplicate basenames, corrupt archive, malformed JSON, invalid UTF-8, missing
members) and that ``load_snapshot()`` (default ``strict=False``) preserves the
legacy fail-safe behaviour used by the TUI.
"""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path

import pytest

from benchdeck.errors import (
    CorruptArchiveError,
    DuplicateBasenameError,
    InvalidUtf8Error,
    LoadError,
    MalformedJsonError,
    MemberCapExceededError,
    OversizeMemberError,
)
from benchdeck.loader import load_snapshot


def test_load_snapshot_strict_raises_on_oversized_zip(tmp_path: Path) -> None:
    huge_zip = tmp_path / "huge.zip"
    with zipfile.ZipFile(huge_zip, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("summary_tally.json", b"x" * 100)
    raw = huge_zip.read_bytes()
    idx = raw.find(b"PK\x01\x02")
    if idx >= 0:
        new = bytearray(raw)
        struct.pack_into("<I", new, idx + 24, 256 * 1024 * 1024 + 1)
        huge_zip.write_bytes(bytes(new))

    snap = load_snapshot(huge_zip)
    assert snap.metadata == {}

    with pytest.raises(OversizeMemberError):
        load_snapshot(huge_zip, strict=True)


def test_load_snapshot_strict_raises_on_duplicate_basenames(tmp_path: Path) -> None:
    z = tmp_path / "dup.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("data.json", b"{}")
        zf.writestr("subdir/data.json", b"{}")

    snap = load_snapshot(z)
    assert snap.metadata == {}

    with pytest.raises(DuplicateBasenameError):
        load_snapshot(z, strict=True)


def test_load_snapshot_strict_raises_on_overcap(tmp_path: Path) -> None:
    z = tmp_path / "overcap.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for i in range(1001):
            zf.writestr(f"a{i:04d}.txt", b"x")

    snap = load_snapshot(z)
    assert snap.metadata == {}

    with pytest.raises(MemberCapExceededError):
        load_snapshot(z, strict=True)


def test_strict_raises_on_corrupt_zip(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.zip"
    corrupt.write_bytes(b"not a zip file at all")

    snap = load_snapshot(corrupt)
    assert snap.metadata == {}

    with pytest.raises(CorruptArchiveError):
        load_snapshot(corrupt, strict=True)


def test_strict_raises_on_malformed_json(tmp_path: Path) -> None:
    z = tmp_path / "badjson.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("run_metadata.json", b"{not valid json}}}")

    snap = load_snapshot(z)
    assert snap.metadata == {}  # fail-safe

    with pytest.raises(MalformedJsonError):
        load_snapshot(z, strict=True)


def test_strict_raises_on_invalid_utf8(tmp_path: Path) -> None:
    z = tmp_path / "badutf8.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("run_metadata.json", b"\xff\xfe\x00\x00")

    snap = load_snapshot(z)
    assert snap.metadata == {}

    with pytest.raises(InvalidUtf8Error):
        load_snapshot(z, strict=True)


def test_strict_nonstrict_valid_zip_still_works(tmp_path: Path) -> None:
    z = tmp_path / "valid.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("run_metadata.json", b'{"status": "completed"}')

    snap = load_snapshot(z, strict=True)
    assert snap.metadata == {"status": "completed"}


def test_strict_raises_are_subclasses_of_load_error() -> None:
    assert issubclass(DuplicateBasenameError, LoadError)
    assert issubclass(MemberCapExceededError, LoadError)
    assert issubclass(OversizeMemberError, LoadError)
    assert issubclass(CorruptArchiveError, LoadError)
    assert issubclass(MalformedJsonError, LoadError)
    assert issubclass(InvalidUtf8Error, LoadError)


def test_strict_also_raises_value_error() -> None:
    with pytest.raises(ValueError):
        raise DuplicateBasenameError("test")
