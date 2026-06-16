"""Policy tests for GitHub Actions workflow security.

Asserts every external action reference uses a full 40-character commit SHA
and that workflow permissions follow least-privilege.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOW_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"

SHA_RE = re.compile(r"@[0-9a-fA-F]{40}")

_KNOWN_EXTERNAL = {
    "actions/checkout",
    "actions/setup-python",
    "actions/upload-artifact",
    "actions/download-artifact",
    "pypa/gh-action-pypi-publish",
    "anchore/sbom-action",
    "softprops/action-gh-release",
}


def _all_workflows() -> list[Path]:
    return sorted(WORKFLOW_DIR.glob("*.yml"))


def _extract_uses_lines(content: str) -> list[str]:
    refs: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("uses:"):
            value = stripped[len("uses:") :].strip()
            value = value.strip("'\"")
            if value and not value.startswith("./") and not value.startswith("docker://"):
                refs.append(value)
    return refs


def _extract_permissions(content: str) -> list[tuple[str | None, str, str]]:
    """Return (scope, key, value) for permissions. scope=None means top-level."""
    perms: list[tuple[str | None, str, str]] = []
    in_job = ""
    for line in content.splitlines():
        stripped = line.strip()
        indent = len(line) - len(stripped)
        if indent == 0 and re.match(r"^\w", stripped):
            m = re.match(r"^(\w[\w-]*):", stripped)
            if m:
                in_job = m.group(1)
        if "permissions:" in stripped:
            scope = in_job if in_job and indent > 0 else None
            for sub in content.splitlines():
                sub_stripped = sub.strip()
                if ":" in sub_stripped and not sub_stripped.startswith("#"):
                    key_val = sub_stripped.split(":", 1)
                    leading_ok = sub_stripped[0] != " "
                    not_perm = not sub_stripped.startswith("permissions")
                    if len(key_val) == 2 and leading_ok and not_perm:
                        k = key_val[0].strip()
                        v = key_val[1].strip().strip("'\"")
                        perms.append((scope, k, v))
    return perms


class TestActionPinning:
    @pytest.mark.parametrize("path", _all_workflows(), ids=lambda p: p.name)
    def test_all_actions_pinned_to_sha(self, path: Path) -> None:
        content = path.read_text()
        refs = _extract_uses_lines(content)
        if not refs:
            return  # workflow has no external actions

        unpinned = [r for r in refs if not SHA_RE.search(r)]
        if unpinned:
            pytest.fail(
                f"{path.name}: {len(unpinned)} action(s) not pinned to SHA:\n"
                + "\n".join(f"  - uses: {r}" for r in unpinned)
                + "\n\nSee WORKFLOW_SHA_CHECKLIST.md for verification instructions."
            )

    def test_at_least_one_workflow_exists(self) -> None:
        assert len(_all_workflows()) > 0


class TestWorkflowPermissions:
    def test_no_pull_requests_write_in_ci(self) -> None:
        ci = WORKFLOW_DIR / "ci.yml"
        content = ci.read_text()
        assert "pull-requests: write" not in content, "ci.yml should not have pull-requests: write"

    def test_publish_permissions_explicit(self) -> None:
        pub = WORKFLOW_DIR / "publish.yml"
        content = pub.read_text()
        assert "id-token: write" in content
        assert "contents: read" in content

    def test_release_job_level_write(self) -> None:
        rel = WORKFLOW_DIR / "release.yml"
        content = rel.read_text()
        assert "contents: write" in content
        assert "contents: read" in content
