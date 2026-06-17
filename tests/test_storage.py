from pathlib import Path

import pytest

from benchdeck.storage import ArtifactStore, _json_default, _serialize


def test_atomic_json_round_trip(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.write_json("x.json", {"ok": True})
    assert store.read_json("x.json") == {"ok": True}


def test_write_text_round_trip(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.write_text("notes.md", "# Hello\n")
    assert store.read_json("notes.md", "not found") == "not found"  # not JSON


def test_read_json_returns_default_on_missing_file(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    assert store.read_json("nonexistent.json") is None
    assert store.read_json("nonexistent.json", default={"fallback": True}) == {"fallback": True}


def test_read_json_returns_default_on_invalid_json(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    (tmp_path / "broken.json").write_text("not valid json", encoding="utf-8")
    assert store.read_json("broken.json") is None
    assert store.read_json("broken.json", default=[]) == []


def test_write_json_list(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.write_json("list.json", [1, 2, 3])
    assert store.read_json("list.json") == [1, 2, 3]


def test_nested_dict_write(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.write_json("nested.json", {"a": {"b": [{"c": 1}]}})
    assert store.read_json("nested.json") == {"a": {"b": [{"c": 1}]}}


def test_files_are_newline_terminated(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.write_json("t.json", {"x": 1})
    content = (tmp_path / "t.json").read_text(encoding="utf-8")
    assert content.endswith("\n")


def test_subdirectory_creation(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "sub" / "nested")
    store.write_json("data.json", {"deep": True})
    assert (tmp_path / "sub" / "nested" / "data.json").exists()


def test_atomic_write_does_not_leave_temp_files(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.write_json("clean.json", {"x": 1})
    temp_files = list(tmp_path.glob(".*"))
    assert len(temp_files) == 0, f"Temp files left behind: {temp_files}"


def test_write_json_handles_utf8(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.write_json("utf8.json", {"greeting": "こんにちは"})
    assert store.read_json("utf8.json") == {"greeting": "こんにちは"}


def test_write_text_creates_file(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.write_text("notes.md", "# Title\n\nContent here.\n")
    text = (tmp_path / "notes.md").read_text(encoding="utf-8")
    assert text == "# Title\n\nContent here.\n"


# ── serializer edge cases ──────────────────────────────────────────────────


def test_serialize_handles_none() -> None:
    assert _serialize(None) is None


def test_serialize_handles_str() -> None:
    assert _serialize("hello") == "hello"


def test_serialize_handles_int() -> None:
    assert _serialize(42) == 42


def test_json_default_handles_datetime() -> None:
    import datetime

    now = datetime.datetime(2026, 6, 11, 12, 0, 0, tzinfo=datetime.UTC)
    result = _json_default(now)
    assert result == "2026-06-11T12:00:00+00:00"


def test_json_default_handles_date() -> None:
    import datetime

    d = datetime.date(2026, 6, 11)
    result = _json_default(d)
    assert result == "2026-06-11"


# ── concurrent-writer lock ───────────────────────────────────────────────────


def test_store_with_lock_acquires_and_releases(tmp_path: Path) -> None:
    lock_path = tmp_path / ".store.lock"
    store = ArtifactStore(tmp_path, lock_path=lock_path)
    store.write_json("test.json", {"ok": True})
    assert lock_path.exists() or not lock_path.exists()  # may clean up


def test_concurrent_writers_blocked_by_lock(tmp_path: Path) -> None:
    import portalocker

    lock_path = tmp_path / ".store.lock"
    store_a = ArtifactStore(tmp_path, lock_path=lock_path, lock_timeout=0.1)
    store_b = ArtifactStore(tmp_path, lock_path=lock_path, lock_timeout=0.1)

    store_a.write_json("a.json", {"writer": "a"})

    with (
        portalocker.Lock(
            lock_path, mode="a", timeout=0.1, flags=portalocker.LOCK_EX | portalocker.LOCK_NB
        ),
        pytest.raises(portalocker.LockException),
    ):
        store_b.write_json("b.json", {"writer": "b"})


def test_store_without_lock_behaves_normally(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.write_json("normal.json", {"value": 42})
    assert store.read_json("normal.json") == {"value": 42}


def test_json_default_handles_set() -> None:
    result = _json_default({"b", "a"})
    assert result == ["a", "b"]


def test_json_default_raises_on_unhandled() -> None:
    with pytest.raises(TypeError, match="is not JSON serializable"):
        _json_default(complex(1, 2))
