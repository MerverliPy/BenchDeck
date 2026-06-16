from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    import tomllib

    data = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    return str(data["project"]["version"])


class TestVersionConsistency:
    def test_version_is_pep440(self) -> None:
        v = _pyproject_version()
        pep440 = re.compile(
            r"^([1-9][0-9]*!)?(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*"
            r"((a|b|rc)(0|[1-9][0-9]*))?(\.post(0|[1-9][0-9]*))?"
            r"(\.dev(0|[1-9][0-9]*))?$"
        )
        assert pep440.match(v), f"version {v!r} is not PEP 440"

    def test_version_matches_verify_script(self) -> None:
        script = ROOT / ".github" / "scripts" / "verify-version-match.sh"
        if not script.exists():
            pytest.skip("verify-version-match.sh not yet created")
        content = script.read_text()
        assert "pyproject.toml" in content or "NEXT_VERSION" in content, (
            "verify-version-match.sh reads version from pyproject.toml dynamically"
        )

    def test_changelog_has_version_heading(self) -> None:
        v = _pyproject_version()
        changelog = ROOT / "CHANGELOG.md"
        content = changelog.read_text()
        assert f"## {v}" in content, f"CHANGELOG.md missing heading for version {v}"


class TestBuildMetadata:
    @pytest.mark.slow
    def test_wheel_metadata_matches_pyproject(self) -> None:
        try:
            subprocess.run(
                ["python", "-m", "build", "--version"],
                cwd=ROOT,
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("python -m build not available")

        subprocess.run(
            ["python", "-m", "build", "--wheel"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        import tomllib

        data = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
        expected = data["project"]["version"]
        wheels = list(ROOT.glob("dist/*.whl"))
        assert wheels, "No wheel produced"
        import zipfile

        with zipfile.ZipFile(wheels[0]) as zf:
            metadata_names = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
            assert metadata_names, "No METADATA in wheel"
            text = zf.read(metadata_names[0]).decode("utf-8")
            for line in text.splitlines():
                if line.startswith("Version:"):
                    actual = line.split(":", 1)[1].strip()
                    assert actual == expected, f"Wheel METADATA Version {actual!r} != {expected!r}"
                    break
            else:
                pytest.fail("Version: not found in wheel METADATA")
        for whl in wheels:
            whl.unlink()

    @pytest.mark.slow
    def test_sdist_metadata_matches_pyproject(self) -> None:
        try:
            subprocess.run(
                ["python", "-m", "build", "--version"],
                cwd=ROOT,
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("python -m build not available")

        subprocess.run(
            ["python", "-m", "build", "--sdist"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        import tomllib

        data = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
        expected = data["project"]["version"]
        sdists = list(ROOT.glob("dist/*.tar.gz"))
        assert sdists, "No sdist produced"
        import tarfile

        with tarfile.open(sdists[0], "r:gz") as tf:
            members = [m for m in tf.getmembers() if m.name.endswith("/PKG-INFO")]
            assert members, "No PKG-INFO in sdist"
            f = tf.extractfile(members[0])
            assert f is not None
            text = f.read().decode("utf-8")
            for line in text.splitlines():
                if line.startswith("Version:"):
                    actual = line.split(":", 1)[1].strip()
                    assert actual == expected, f"Sdist PKG-INFO Version {actual!r} != {expected!r}"
                    break
            else:
                pytest.fail("Version: not found in sdist PKG-INFO")
        for sdist in sdists:
            sdist.unlink()
        if (ROOT / "dist" / "SHA256SUMS").exists():
            (ROOT / "dist" / "SHA256SUMS").unlink()
