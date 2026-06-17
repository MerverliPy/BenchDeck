# Workflow Action SHA Pinning Checklist

All external `uses:` references in `.github/workflows/*.yml` must be pinned to a reviewed
full 40-character commit SHA. **Verified 2026-06-16.**

## Verification instructions

For each action below, run:

```bash
OWNER="<owner>"
REPO="<repo>"
TAG="v4"  # the mutable tag
curl -sL "https://api.github.com/repos/${OWNER}/${REPO}/git/ref/tags/${TAG}" | jq -r '.object.sha'
```

If the tag contains a slash (e.g. `release/v1`), check if it's a branch instead:
```bash
curl -sL "https://api.github.com/repos/${OWNER}/${REPO}/git/refs/heads/${TAG}" | jq -r '.object.sha'
```

## Verified actions

| # | Action | Repository | Tag | SHA | Verified? |
|---|--------|-----------|-----|-----|-----------|
| 1 | `actions/checkout` | `actions/checkout` | `v4` | `34e114876b0b11c390a56381ad16ebd13914f8d5` | ✅ 2026-06-16 |
| 2 | `actions/setup-python` | `actions/setup-python` | `v5` | `a26af69be951a213d495a4c3e4e4022e16d87065` | ✅ 2026-06-16 |
| 3 | `actions/upload-artifact` | `actions/upload-artifact` | `v4` | `ea165f8d65b6e75b540449e92b4886f43607fa02` | ✅ 2026-06-16 |
| 4 | `actions/download-artifact` | `actions/download-artifact` | `v4` | `d3f86a106a0bac45b974a628896c90dbdf5c8093` | ✅ 2026-06-16 |
| 5 | `pypa/gh-action-pypi-publish` | `pypa/gh-action-pypi-publish` | `release/v1` (branch) | `cef221092ed1bacb1cc03d23a2d87d1d172e277b` | ✅ 2026-06-16 |
| 6 | `anchore/sbom-action` | `anchore/sbom-action` | `v0` | `e22c389904149dbc22b58101806040fa8d37a610` | ✅ 2026-06-16 |
| 7 | `softprops/action-gh-release` | `softprops/action-gh-release` | `v2` | `3bb12739c298aeb8a4eeaf626c5b8d85266b0e65` | ✅ 2026-06-16 |

## Note on pypa/gh-action-pypi-publish

The `release/v1` reference is a **branch**, not a tag. The SHA pinned above
(`cef2210`) is the current head of that branch as of 2026-06-16. When the
branch moves forward, the SHA should be re-verified and updated.

## Verification date

2026-06-16 — all SHAs verified via `api.github.com`.

## Dependabot management

Dependabot opens weekly PRs for pip and GitHub Actions updates. For
action version bumps, the SHA pinning test (`test_workflow_policy.py`)
will fail because Dependabot replaces the pinned SHA with a mutable tag.
To merge a Dependabot action bump:

1. Look at the new tag/version in the PR diff.
2. Verify the corresponding SHA via the GitHub API:
   `curl -sL https://api.github.com/repos/{owner}/{repo}/git/ref/tags/{tag} | jq -r '.object.sha'`
3. Update the workflow file with the verified SHA.
4. Update the verified actions table above.
5. The SHA pinning test will now pass — merge the PR.

For pip dependency bumps, standard review applies (CI must pass).
