"""Tests for the config loader — explicit/implicit diagnostics (Phase 3)."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from benchdeck.config import load_config


def test_load_config_empty_when_no_file() -> None:
    with patch.object(Path, "is_file", return_value=False):
        cfg = load_config()
    assert cfg == {}


def test_load_config_reads_toml(tmp_path: Path) -> None:
    config_file = tmp_path / "benchdeck.toml"
    config_file.write_text(
        '[run]\nmodel = "gpt-4o"\njudge_model = "gpt-4o"\n[gateway]\ntimeout_s = 120\n'
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
    b.write_text("[gateway]\ntimeout_s = 120\n")

    cfg = load_config(explicit_path=str(a))
    cfg2 = load_config(explicit_path=str(b))
    assert cfg["gateway"]["timeout_s"] == 60
    assert cfg2["gateway"]["timeout_s"] == 120


# ═══════════════════════════════════════════════════════════════════════════
# Explicit config — strict errors
# ═══════════════════════════════════════════════════════════════════════════


def test_explicit_config_missing_raises() -> None:
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_config(explicit_path="/nonexistent/path/config.toml")


def test_explicit_config_unreadable_raises(tmp_path: Path) -> None:
    bad = tmp_path / "unreadable.toml"
    bad.write_text("[run]\nmodel = 'x'\n")
    bad.chmod(0o000)
    try:
        with pytest.raises(PermissionError, match="not readable"):
            load_config(explicit_path=str(bad))
    finally:
        bad.chmod(0o644)


def test_explicit_config_malformed_raises_with_cause(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("this is not toml {{{")
    with pytest.raises(ValueError, match="not valid TOML"):
        load_config(explicit_path=str(bad))


def test_explicit_config_valid_unchanged(tmp_path: Path) -> None:
    good = tmp_path / "good.toml"
    good.write_text('[run]\nmodel = "gpt-4o"\n')
    cfg = load_config(explicit_path=str(good))
    assert cfg == {"run": {"model": "gpt-4o"}}


# ═══════════════════════════════════════════════════════════════════════════
# Implicit config — tolerant with warnings
# ═══════════════════════════════════════════════════════════════════════════


def test_implicit_config_missing_silent(tmp_path: Path) -> None:
    with (
        patch.object(Path, "is_file", return_value=False),
        warnings.catch_warnings(record=True) as w,
    ):
        warnings.simplefilter("always")
        cfg = load_config()

    assert cfg == {}
    assert len(w) == 0, f"expected no warnings, got {[str(x.message) for x in w]}"


def test_implicit_config_malformed_warns(tmp_path: Path, monkeypatch: Any) -> None:
    bad = tmp_path / "benchdeck.toml"
    bad.write_text("this is not toml {{{")

    monkeypatch.setattr(Path, "home", lambda: tmp_path / "nonexistent_home")
    monkeypatch.chdir(tmp_path)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        cfg = load_config()
    assert cfg == {}
    malformed = [x for x in w if "malformed" in str(x.message).lower()]
    assert len(malformed) >= 1, f"expected malformed warning, got {[str(x.message) for x in w]}"


# ═══════════════════════════════════════════════════════════════════════════
# Precedence and validation
# ═══════════════════════════════════════════════════════════════════════════


def test_explicit_overrides_implicit(tmp_path: Path) -> None:
    impl = tmp_path / "benchdeck.toml"
    expl = tmp_path / "explicit.toml"
    impl.write_text('[run]\nmodel = "old"\n')
    expl.write_text('[run]\nmodel = "new"\n')

    with patch.object(Path, "is_file", side_effect=lambda: True), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cfg = load_config(explicit_path=str(expl))

    assert cfg["run"]["model"] == "new"


def test_unknown_key_warns(tmp_path: Path) -> None:
    bad = tmp_path / "unknown.toml"
    bad.write_text('bogus_key = 1\nmodel = "gpt-4o"\n')
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        cfg = load_config(explicit_path=str(bad))

    assert cfg["model"] == "gpt-4o"
    key_warnings = [x for x in w if "bogus_key" in str(x.message)]
    assert len(key_warnings) >= 1


def test_diagnostics_no_secret_values(tmp_path: Path) -> None:
    bad = tmp_path / "secret.toml"
    bad.write_text("[run]\nnot_a_secret = 'visible'\n")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        load_config(explicit_path=str(bad))

    for warning in w:
        msg = str(warning.message)
        assert "visible" not in msg, f"warning exposes config value: {msg}"


def test_explicit_config_with_known_keys_ok(tmp_path: Path) -> None:
    good = tmp_path / "known.toml"
    good.write_text("model = 'gpt-4o'\nmax_retries = 5\ntimeout = 90\n")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        cfg = load_config(explicit_path=str(good))

    assert cfg["model"] == "gpt-4o"
    assert cfg["max_retries"] == 5
    key_warnings = [x for x in w if "Unknown config key" in str(x.message)]
    assert len(key_warnings) == 0
