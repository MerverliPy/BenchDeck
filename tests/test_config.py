"""Tests for the config loader."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from benchdeck.config import load_config


def test_load_config_empty_when_no_file() -> None:
    with patch.object(Path, "is_file", return_value=False):
        cfg = load_config()
    assert cfg == {}


def test_load_config_reads_toml(tmp_path: Path) -> None:
    config_file = tmp_path / "benchdeck.toml"
    config_file.write_text(
        '[run]\nmodel = "gpt-4o"\njudge_model = "gpt-4o"\n'
        '[gateway]\ntimeout_s = 120\n'
    )
    cfg = load_config(explicit_path=str(config_file))
    assert cfg == {
        "run": {"model": "gpt-4o", "judge_model": "gpt-4o"},
        "gateway": {"timeout_s": 120},
    }


def test_load_config_deep_merges(tmp_path: Path) -> None:
    a = tmp_path / "a.toml"
    a.write_text('[run]\nmodel = "gpt-4o"\n[gateway]\ntimeout_s = 60\nmax_retries = 2\n')
    b = tmp_path / "b.toml"
    b.write_text('[gateway]\ntimeout_s = 120\n')

    cfg = load_config(explicit_path=str(a))
    cfg2 = load_config(explicit_path=str(b))
    assert cfg["gateway"]["timeout_s"] == 60
    assert cfg2["gateway"]["timeout_s"] == 120


def test_load_config_handles_bad_toml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("this is not toml {{{")
    cfg = load_config(explicit_path=str(bad))
    assert cfg == {}
