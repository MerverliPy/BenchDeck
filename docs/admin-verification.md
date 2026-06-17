# Admin Verification — GitHub Hosted Settings

> These controls are configured through the GitHub UI or API and **cannot be verified from repository contents alone.** Run this checklist with admin access before a release or after repository governance changes.

## Prerequisites

- [ ] GitHub admin or maintain access to `https://github.com/MerverliPy/BenchDeck`
- [ ] `gh` CLI installed and authenticated
- [ ] `jq` installed for JSON parsing

## 1. Branch protection

### Default branch and release branches

```bash
gh api repos/MerverliPy/BenchDeck/branches/main/protection --jq '.required_pull_request_reviews' 2>/dev/null
gh api repos/MerverliPy/BenchDeck/branches/main/protection --jq '.required_status_checks' 2>/dev/null
gh api repos/MerverliPy/BenchDeck/branches/main/protection --jq '.enforce_admins' 2>/dev/null
```

| Check | Expected | Found |
|-------|----------|-------|
| Pull request reviews required | `required_approving_review_count > 0` | |
| Status checks required before merge | includes ci, lint, typecheck, test | |
| Admin enforcement enabled | `enabled: true` | |
| Force pushes blocked | — | |
| Deletions blocked | — | |

## 2. Rulesets

If branch protection rules are not visible, the repository may use rulesets instead:

```bash
gh api repos/MerverliPy/BenchDeck/rulesets --jq '.[] | {id, name, target, enforcement}'
```

## 3. CODEOWNERS enforcement

```bash
gh api repos/MerverliPy/BenchDeck/branches/main/protection --jq '.required_pull_request_reviews.require_code_owner_reviews'
```

| Check | Expected | Found |
|-------|----------|-------|
| CODEOWNERS reviews required | `true` | |

## 4. Environment protection

```bash
gh api repos/MerverliPy/BenchDeck/environments --jq '.environments[] | {name, protection_rules}'
```

| Environment | Expected | Found |
|-------------|----------|-------|
| `product-test` | Required reviewers configured | |
| `pypi` | Required reviewers configured | |

## 5. GitHub security features

```bash
# Dependency graph (public repos only)
gh api repos/MerverliPy/BenchDeck --jq '{has_discussions, visibility}'

# Security & analysis settings
gh api repos/MerverliPy/BenchDeck/automated-security-fixes --jq '.'
```

| Feature | Available | Enabled |
|---------|-----------|---------|
| Dependency graph | | |
| Dependabot alerts | | |
| Dependabot security updates | | |
| Secret scanning | | |
| Push protection | | |
| Code scanning | | |

## 6. Dependabot

Confirm that `.github/dependabot.yml` configuration is being applied:

- Check repository Settings → Security → Dependabot → Enabled
- Verify a recent Dependabot PR exists (pip or GitHub Actions updates)

## 7. Tag protection

```bash
gh api repos/MerverliPy/BenchDeck/tags/protection --jq '.'
```

| Check | Expected | Found |
|-------|----------|-------|
| Tag `v*` patterns protected | No unauthorised creation/deletion | |

## 8. Artifact attestation

```bash
gh api repos/MerverliPy/BenchDeck/attestations --jq '.'
```

| Check | Expected | Found |
|-------|----------|-------|
| Attestations enabled and verifiable | (requires a published release) | |

## 9. Verified actions pinning

Ensure workflow files use SHA-pinned actions. The test `test_workflow_policy.py` enforces this at push time, but verify no stale or bypassed workflows exist:

```bash
grep -rn 'uses: [a-z_-]*/[a-z_-]*@' .github/workflows/ | grep -v '[0-9a-f]\{40\}'
```

Expected: no output (all actions pinned to 40-char SHA).

## Report template

```markdown
# Hosted-Settings Verification Report

Date: YYYY-MM-DD
Verified by: @username

## Settings verified
- [ ] Branch protection (main)
- [ ] CODEOWNERS enforcement
- [ ] Environment protection (product-test, pypi)
- [ ] Dependabot alerts & security updates
- [ ] Secret scanning & push protection
- [ ] Code scanning
- [ ] Tag protection
- [ ] Actions SHA pinning

## Settings not assessable
- (list with reason)

## Findings
- P0/P1/P2 as applicable

## Approval
- [ ] All required controls verified
- [ ] Deviations documented and risk-accepted
```
