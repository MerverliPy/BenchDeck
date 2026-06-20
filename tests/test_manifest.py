"""Tests for the manifest module.

Covers Manifest init, record, verify, load, to_dict, and _ManifestEntry
without mocks — all filesystem operations are real.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

from benchdeck.manifest import Manifest, _ManifestEntry

# ── Manifest.__init__ ──────────────────────────────────────────────────────


def test_init_creates_root_directory(tmp_path: Path) -> None:
    root = tmp_path / "new_manifest_root"
    assert not root.exists()
    m = Manifest(root)
    assert root.is_dir()
    assert m.root == root


def test_init_uses_existing_directory(tmp_path: Path) -> None:
    root = tmp_path / "existing_root"
    root.mkdir()
    m = Manifest(root)
    assert root.is_dir()
    assert m.root == root


# ── Manifest.record ────────────────────────────────────────────────────────


def test_record_returns_entry(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    entry = m.record("data.txt", "hello")
    assert isinstance(entry, _ManifestEntry)
    assert entry.filename == "data.txt"
    assert entry.sha256 == hashlib.sha256(b"hello").hexdigest()
    assert entry.byte_size == 5
    assert entry.generation == 1


def test_record_increments_generation(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    assert m.generation == 0
    m.record("a.txt", "a")
    assert m.generation == 1
    m.record("b.txt", "bb")
    assert m.generation == 2
    m.record("c.txt", "ccc")
    assert m.generation == 3


def test_record_writes_manifest_json(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    m.record("hello.txt", "world")
    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.is_file()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "generation" in data
    assert "entries" in data
    assert data["generation"] == 1
    assert "hello.txt" in data["entries"]
    assert data["entries"]["hello.txt"]["filename"] == "hello.txt"
    assert data["entries"]["hello.txt"]["byte_size"] == 5


def test_record_with_str_content(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    entry = m.record("utf8.txt", "caf\u00e9")
    assert entry.byte_size == len("caf\u00e9".encode("utf-8"))
    assert entry.sha256 == hashlib.sha256("caf\u00e9".encode("utf-8")).hexdigest()


def test_record_with_bytes_content(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    payload = bytes([0x00, 0x01, 0x02, 0xFF])
    entry = m.record("binary.bin", payload)
    assert entry.byte_size == 4
    assert entry.sha256 == hashlib.sha256(payload).hexdigest()


def test_record_manifest_json_newline_terminated(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    m.record("x.txt", "x")
    content = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    assert content.endswith("\n")


def test_record_atomic_no_temp_files_left_behind(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    m.record("clean.txt", "clean")
    temp_files = list(tmp_path.glob(".manifest.*"))
    assert len(temp_files) == 0, f"Temp files left behind: {temp_files}"


# ── Manifest.verify ────────────────────────────────────────────────────────


def test_verify_empty_when_all_match(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")
    m.record("a.txt", "alpha")
    m.record("b.txt", "beta")
    assert m.verify() == []


def test_verify_detects_missing_file(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    (tmp_path / "present.txt").write_text("here", encoding="utf-8")
    m.record("present.txt", "here")
    m.record("missing.txt", "gone")
    issues = m.verify()
    assert any("missing on disk" in issue for issue in issues)
    assert len(issues) == 1


def test_verify_detects_checksum_mismatch(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    (tmp_path / "data.txt").write_text("original", encoding="utf-8")
    m.record("data.txt", "original")
    (tmp_path / "data.txt").write_text("corrupted", encoding="utf-8")
    issues = m.verify()
    assert any("checksum mismatch" in issue for issue in issues)


def test_verify_detects_size_mismatch(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    (tmp_path / "data.txt").write_text("hello", encoding="utf-8")
    m.record("data.txt", "hello")
    (tmp_path / "data.txt").write_text("hi", encoding="utf-8")
    issues = m.verify()
    assert any("size mismatch" in issue for issue in issues)


def test_verify_nonexistent_root_handled_gracefully(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    m.record("phantom.txt", "ghost")
    issues = m.verify()
    assert any("missing on disk" in issue for issue in issues)


# ── Manifest.load ──────────────────────────────────────────────────────────


def test_load_empty_when_no_manifest(tmp_path: Path) -> None:
    m = Manifest.load(tmp_path)
    assert m.generation == 0
    assert m._entries == {}
    assert m.to_dict() == {"generation": 0, "entries": {}}


def test_load_empty_when_corrupt_json(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text("not json {{{", encoding="utf-8")
    m = Manifest.load(tmp_path)
    assert m.generation == 0
    assert m._entries == {}


def test_load_restores_entries(tmp_path: Path) -> None:
    payload = json.dumps(
        {
            "generation": 2,
            "entries": {
                "one.txt": {
                    "filename": "one.txt",
                    "sha256": hashlib.sha256(b"111").hexdigest(),
                    "byte_size": 3,
                    "generation": 1,
                },
                "two.txt": {
                    "filename": "two.txt",
                    "sha256": hashlib.sha256(b"2222").hexdigest(),
                    "byte_size": 4,
                    "generation": 2,
                },
            },
        }
    )
    (tmp_path / "manifest.json").write_text(payload, encoding="utf-8")
    m = Manifest.load(tmp_path)
    assert m.generation == 2
    assert len(m._entries) == 2
    assert "one.txt" in m._entries
    assert "two.txt" in m._entries
    assert m._entries["one.txt"].byte_size == 3
    assert m._entries["two.txt"].byte_size == 4


def test_load_restores_generation(tmp_path: Path) -> None:
    payload = json.dumps({"generation": 42, "entries": {}})
    (tmp_path / "manifest.json").write_text(payload, encoding="utf-8")
    m = Manifest.load(tmp_path)
    assert m.generation == 42


def test_load_handles_missing_keys_gracefully(tmp_path: Path) -> None:
    # Missing both generation and entries
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    m = Manifest.load(tmp_path)
    assert m.generation == 0
    assert m._entries == {}

    # Missing generation only
    entry_data = {"filename": "x.txt", "sha256": "abc", "byte_size": 1, "generation": 1}
    payload = json.dumps({"entries": {"x.txt": entry_data}})
    (tmp_path / "manifest.json").write_text(payload, encoding="utf-8")
    m = Manifest.load(tmp_path)
    assert m.generation == 0
    assert len(m._entries) == 1

    # Missing entries only
    payload = json.dumps({"generation": 7})
    (tmp_path / "manifest.json").write_text(payload, encoding="utf-8")
    m = Manifest.load(tmp_path)
    assert m.generation == 7
    assert m._entries == {}


def test_load_handles_missing_entry_fields(tmp_path: Path) -> None:
    payload = json.dumps(
        {
            "generation": 1,
            "entries": {
                "bare.txt": {"filename": "bare.txt"},
            },
        }
    )
    (tmp_path / "manifest.json").write_text(payload, encoding="utf-8")
    m = Manifest.load(tmp_path)
    assert m.generation == 1
    entry = m._entries["bare.txt"]
    assert entry.sha256 == ""
    assert entry.byte_size == 0
    assert entry.generation == 1


# ── Manifest.to_dict ───────────────────────────────────────────────────────


def test_to_dict_empty(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    d = m.to_dict()
    assert d == {"generation": 0, "entries": {}}


def test_to_dict_with_entries(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    m.record("a.txt", "aaa")
    m.record("b.txt", "bb")
    d = m.to_dict()
    assert d["generation"] == 2
    assert "a.txt" in d["entries"]
    assert "b.txt" in d["entries"]
    assert d["entries"]["a.txt"]["byte_size"] == 3
    assert d["entries"]["b.txt"]["byte_size"] == 2


def test_to_dict_matches_manifest_json_on_disk(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    m.record("x.txt", "xxx")
    m.record("y.txt", "yy")
    on_disk = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert m.to_dict() == on_disk


# ── _ManifestEntry.to_dict ─────────────────────────────────────────────────


def test_manifest_entry_to_dict() -> None:
    entry = _ManifestEntry(
        filename="test.dat",
        sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        byte_size=1024,
        generation=5,
    )
    d = entry.to_dict()
    assert d == {
        "filename": "test.dat",
        "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "byte_size": 1024,
        "generation": 5,
    }


# ── Round-trip ─────────────────────────────────────────────────────────────


def test_round_trip_record_load_verify(tmp_path: Path) -> None:
    m1 = Manifest(tmp_path)
    (tmp_path / "file.txt").write_text("round-trip content", encoding="utf-8")
    m1.record("file.txt", "round-trip content")

    m2 = Manifest.load(tmp_path)
    assert m2.generation == 1
    assert len(m2._entries) == 1
    assert m2._entries["file.txt"].sha256 == hashlib.sha256(b"round-trip content").hexdigest()
    assert m2.verify() == []


def test_multiple_records_then_verify_all(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    files = {
        "a.txt": b"alpha",
        "b.txt": b"beta",
        "c.txt": b"gamma",
    }
    for name, content in files.items():
        (tmp_path / name).write_bytes(content)
        m.record(name, content)

    assert m.generation == 3
    issues = m.verify()
    assert issues == []


def test_generation_starts_at_zero_and_increments_per_record(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    assert m.generation == 0

    for i in range(1, 6):
        m.record(f"step_{i}.txt", f"content_{i}")
        assert m.generation == i


def test_record_updates_existing_entry_generation(tmp_path: Path) -> None:
    m = Manifest(tmp_path)
    entry1 = m.record("shared.txt", "first")
    assert entry1.generation == 1
    entry2 = m.record("shared.txt", "second")
    assert entry2.generation == 2
    assert m.generation == 2
    assert len(m._entries) == 1
    assert m._entries["shared.txt"].sha256 == hashlib.sha256(b"second").hexdigest()


# ── Concurrent reader safety ───────────────────────────────────────────────


def test_concurrent_reader_sees_consistent_snapshot(tmp_path: Path) -> None:
    error: Exception | None = None

    def writer() -> None:
        try:
            w = Manifest(tmp_path)
            for i in range(1, 51):
                (tmp_path / f"file_{i}.txt").write_text(f"content_{i}", encoding="utf-8")
                w.record(f"file_{i}.txt", f"content_{i}")
        except Exception as exc:
            nonlocal error
            error = exc

    def reader() -> list[int]:
        generations: list[int] = []
        for _ in range(20):
            m = Manifest.load(tmp_path)
            generations.append(m.generation)
            # generation should equal number of entries
            assert m.generation >= len(m._entries)
            time.sleep(0.005)
        return generations

    writer_thread = threading.Thread(target=writer, daemon=False)
    writer_thread.start()

    gen_samples = reader()
    writer_thread.join()

    if error:
        raise error

    # After writer finishes, load should see all 50 entries
    m_final = Manifest.load(tmp_path)
    assert m_final.generation == 50
    assert len(m_final._entries) == 50

    # Generation observed by reader should never decrease
    for i in range(1, len(gen_samples)):
        assert gen_samples[i] >= gen_samples[i - 1], (
            f"Generation decreased from {gen_samples[i - 1]} to {gen_samples[i]}"
        )
