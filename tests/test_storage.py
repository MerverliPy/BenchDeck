from pathlib import Path

from benchdeck.storage import ArtifactStore


def test_atomic_json_round_trip(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.write_json("x.json", {"ok": True})
    assert store.read_json("x.json") == {"ok": True}
