"""Regression tests for the loader ZIP-safety contract (SEC-004/005/006).

Verifies that ``load_snapshot(strict=True)`` re-raises ``ValueError`` for the
three security-relevant archive-violation classes (member cap, oversize
member, duplicate basenames) and that ``load_snapshot()`` (default
``strict=False``) preserves the legacy fail-safe behaviour used by the TUI
(empty ``Snapshot()`` returned, dashboard keeps rendering).
"""

from __future__ import annotations

import struct
import zipfile

from benchdeck.loader import load_snapshot


def test_load_snapshot_strict_raises_on_oversized_zip(tmp_path):
    """SEC-005 regression: 256 MiB+1 byte member should raise ValueError in strict mode."""
    huge_zip = tmp_path / "huge.zip"
    # Use a real loader-known filename so the size check is reached
    with zipfile.ZipFile(huge_zip, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("summary_tally.json", b"x" * 100)  # Actual content
    # Now manipulate the file_size in the central directory so the loader
    # sees a declared size of 256 MiB + 1.
    raw = huge_zip.read_bytes()
    # Central directory file header signature: PK\x01\x02
    idx = raw.find(b"PK\x01\x02")
    if idx >= 0:
        # Uncompressed size is at offset 24 from signature
        new = bytearray(raw)
        struct.pack_into("<I", new, idx + 24, 256 * 1024 * 1024 + 1)
        huge_zip.write_bytes(bytes(new))

    # Default (strict=False) returns empty Snapshot()
    snap = load_snapshot(huge_zip)
    assert snap.metadata == {}
    # Strict raises ValueError (oversize member)
    import pytest

    with pytest.raises(ValueError):
        load_snapshot(huge_zip, strict=True)


def test_load_snapshot_strict_raises_on_duplicate_basenames(tmp_path):
    """SEC-006 regression: duplicate basenames should raise ValueError in strict mode."""
    z = tmp_path / "dup.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("data.json", b"{}")
        zf.writestr("subdir/data.json", b"{}")

    snap = load_snapshot(z)
    assert snap.metadata == {}  # fail-safe default
    import pytest

    with pytest.raises(ValueError):
        load_snapshot(z, strict=True)


def test_load_snapshot_strict_raises_on_overcap(tmp_path):
    """SEC-004 regression: >1000 members should raise ValueError in strict mode."""
    z = tmp_path / "overcap.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for i in range(1001):
            zf.writestr(f"a{i:04d}.txt", b"x")

    snap = load_snapshot(z)
    assert snap.metadata == {}
    import pytest

    with pytest.raises(ValueError):
        load_snapshot(z, strict=True)
