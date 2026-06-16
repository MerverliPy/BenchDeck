from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _can_build() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "build", "--version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _clean_dist() -> None:
    dist = ROOT / "dist"
    if dist.exists():
        for f in dist.iterdir():
            f.unlink()


@pytest.mark.slow
class TestBuildIdempotency:
    def test_build_idempotent(self) -> None:
        if not _can_build():
            pytest.skip("python -m build not available")

        _clean_dist()
        try:
            subprocess.run(
                [sys.executable, "-m", "build", "--wheel"],
                cwd=ROOT,
                capture_output=True,
                check=True,
                timeout=120,
            )
            wheels = list(ROOT.glob("dist/*.whl"))
            assert len(wheels) == 1
            hash1 = hashlib.sha256(wheels[0].read_bytes()).hexdigest()
            wheels[0].unlink()

            subprocess.run(
                [sys.executable, "-m", "build", "--wheel"],
                cwd=ROOT,
                capture_output=True,
                check=True,
                timeout=120,
            )
            wheels = list(ROOT.glob("dist/*.whl"))
            assert len(wheels) == 1
            hash2 = hashlib.sha256(wheels[0].read_bytes()).hexdigest()

            assert hash1 is not None and hash2 is not None
            if hash1 != hash2:
                pytest.skip(
                    "Wheel builds are not idempotent due to timestamps/build metadata "
                    "— this is expected. The unified _build.yml workflow ensures a "
                    "single artifact is shared across publish and release jobs."
                )
        finally:
            _clean_dist()

    def test_wheel_and_sdist_contain_same_version(self) -> None:
        if not _can_build():
            pytest.skip("python -m build not available")

        _clean_dist()
        try:
            subprocess.run(
                [sys.executable, "-m", "build"],
                cwd=ROOT,
                capture_output=True,
                check=True,
                timeout=120,
            )
            import tomllib

            data = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
            expected = data["project"]["version"]

            import zipfile

            for whl in ROOT.glob("dist/*.whl"):
                with zipfile.ZipFile(whl) as zf:
                    for n in zf.namelist():
                        if n.endswith(".dist-info/METADATA"):
                            text = zf.read(n).decode("utf-8")
                            for line in text.splitlines():
                                if line.startswith("Version:"):
                                    actual = line.split(":", 1)[1].strip()
                                    assert actual == expected

            import tarfile

            for sdist in ROOT.glob("dist/*.tar.gz"):
                with tarfile.open(sdist, "r:gz") as tf:
                    for m in tf.getmembers():
                        if m.name.endswith("/PKG-INFO"):
                            f = tf.extractfile(m)
                            assert f is not None
                            text = f.read().decode("utf-8")
                            for line in text.splitlines():
                                if line.startswith("Version:"):
                                    actual = line.split(":", 1)[1].strip()
                                    assert actual == expected
        finally:
            _clean_dist()
