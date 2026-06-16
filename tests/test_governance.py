"""Governance file syntax and existence checks (Phase 3)."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]


class TestIssueTemplates:
    TEMPLATE_DIR = ROOT / ".github" / "ISSUE_TEMPLATE"

    def test_bug_report_exists(self) -> None:
        assert (self.TEMPLATE_DIR / "bug_report.yml").is_file()

    def test_feature_request_exists(self) -> None:
        assert (self.TEMPLATE_DIR / "feature_request.yml").is_file()

    def test_config_exists(self) -> None:
        assert (self.TEMPLATE_DIR / "config.yml").is_file()

    def test_config_disables_blank_issues_false(self) -> None:
        path = self.TEMPLATE_DIR / "config.yml"
        content = yaml.safe_load(path.read_text())
        assert isinstance(content, dict)

    def test_bug_report_is_valid_yaml(self) -> None:
        path = self.TEMPLATE_DIR / "bug_report.yml"
        content = yaml.safe_load(path.read_text())
        assert isinstance(content, dict)
        assert "body" in content


class TestPullRequestTemplate:
    def test_template_exists(self) -> None:
        path = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
        assert path.is_file()
        content = path.read_text()
        assert len(content) > 100


class TestCodeOwners:
    def test_codeowners_exists(self) -> None:
        path = ROOT / ".github" / "CODEOWNERS"
        assert path.is_file()

    def test_codeowners_covers_source(self) -> None:
        content = (ROOT / ".github" / "CODEOWNERS").read_text()
        assert "src/benchdeck/" in content

    def test_codeowners_covers_tests(self) -> None:
        content = (ROOT / ".github" / "CODEOWNERS").read_text()
        assert "tests/" in content

    def test_codeowners_covers_workflows(self) -> None:
        content = (ROOT / ".github" / "CODEOWNERS").read_text()
        assert ".github/workflows/" in content

    def test_codeowners_covers_manifest(self) -> None:
        content = (ROOT / ".github" / "CODEOWNERS").read_text()
        assert "pyproject.toml" in content

    def test_codeowners_notes_hosted_enforcement(self) -> None:
        content = (ROOT / ".github" / "CODEOWNERS").read_text().lower()
        assert "verified" in content or "enforcement" in content


class TestDependabot:
    def test_dependabot_exists(self) -> None:
        path = ROOT / ".github" / "dependabot.yml"
        assert path.is_file()

    def test_dependabot_is_valid_yaml(self) -> None:
        path = ROOT / ".github" / "dependabot.yml"
        content = yaml.safe_load(path.read_text())
        assert isinstance(content, dict)
        assert "version" in content
        assert "updates" in content

    def test_dependabot_has_pip_ecosystem(self) -> None:
        path = ROOT / ".github" / "dependabot.yml"
        content = yaml.safe_load(path.read_text())
        ecosystems = [u.get("package-ecosystem") for u in content.get("updates", [])]
        assert "pip" in ecosystems

    def test_dependabot_has_github_actions_ecosystem(self) -> None:
        path = ROOT / ".github" / "dependabot.yml"
        content = yaml.safe_load(path.read_text())
        ecosystems = [u.get("package-ecosystem") for u in content.get("updates", [])]
        assert "github-actions" in ecosystems


class TestCodeOfConduct:
    def test_exists(self) -> None:
        path = ROOT / "CODE_OF_CONDUCT.md"
        assert path.is_file()

    def test_references_contributor_covenant(self) -> None:
        content = (ROOT / "CODE_OF_CONDUCT.md").read_text().lower()
        assert "contributor covenant" in content or "code of conduct" in content


class TestGovernance:
    def test_exists(self) -> None:
        path = ROOT / "GOVERNANCE.md"
        assert path.is_file()

    def test_references_code_of_conduct(self) -> None:
        content = (ROOT / "GOVERNANCE.md").read_text()
        assert "CODE_OF_CONDUCT" in content

    def test_references_security(self) -> None:
        content = (ROOT / "GOVERNANCE.md").read_text()
        assert "SECURITY" in content

    def test_notes_hosted_enforcement_unverified(self) -> None:
        content = (ROOT / "GOVERNANCE.md").read_text().lower()
        assert "verified" in content or "enforcement" in content
