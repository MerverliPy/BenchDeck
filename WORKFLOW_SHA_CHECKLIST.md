# Workflow Action SHA Pinning Checklist

All external `uses:` references in `.github/workflows/*.yml` must be pinned to a reviewed
full 40-character commit SHA. **Verified 2026-06-16.** Updated 2026-06-16 for Node.js 24
compatibility (newer major versions).

## Verification instructions

For each action below, run:

```bash
OWNER="<owner>"
REPO="<repo>"
TAG="v5"
curl -sL "https://api.github.com/repos/${OWNER}/${REPO}/git/ref/tags/${TAG}" | jq -r '.object.sha'
```

If the tag contains a slash (e.g. `release/v1`), check if it's a branch instead:
```bash
curl -sL "https://api.github.com/repos/${OWNER}/${REPO}/git/refs/heads/${TAG}" | jq -r '.object.sha'
```

## Verified actions (Node.js 24 compatible — 2026-06-16)

| # | Action | Repository | Tag | SHA | Verified |
|---|--------|-----------|-----|-----|----------|
| 1 | `actions/checkout` | `actions/checkout` | `v5` | `93cb6efe18208431cddfb8368fd83d5badbf9bfd` | ✅ 2026-06-16 |
| 2 | `actions/setup-python` | `actions/setup-python` | `v6` | `a309ff8b426b58ec0e2a45f0f869d46889d02405` | ✅ 2026-06-16 |
| 3 | `actions/upload-artifact` | `actions/upload-artifact` | `v5` | `330a01c490aca151604b8cf639adc76d48f6c5d4` | ✅ 2026-06-16 |
| 4 | `actions/download-artifact` | `actions/download-artifact` | `v5` | `634f93cb2916e3fdff6788551b99b062d0335ce0` | ✅ 2026-06-16 |
| 5 | `pypa/gh-action-pypi-publish` | `pypa/gh-action-pypi-publish` | `release/v1` (branch) | `cef221092ed1bacb1cc03d23a2d87d1d172e277b` | ✅ 2026-06-16 |
| 6 | `anchore/sbom-action` | `anchore/sbom-action` | `v0` | `e22c389904149dbc22b58101806040fa8d37a610` | ✅ 2026-06-16 |
| 7 | `softprops/action-gh-release` | `softprops/action-gh-release` | `v3` | `b4309332981a82ec1c5618f44dd2e27cc8bfbfda` | ✅ 2026-06-16 |

## Note on pypa/gh-action-pypi-publish

The `release/v1` reference is a **branch**, not a tag. The SHA pinned above
(`cef2210`) is the current head of that branch as of 2026-06-16. When the
branch moves forward, the SHA should be re-verified and updated.

## Node.js 24 upgrade (2026-06-16)

All actions upgraded to versions that natively support Node.js 24:
- `checkout`: v4 → v5
- `setup-python`: v5 → v6
- `upload-artifact`: v4 → v5
- `download-artifact`: v4 → v5
- `action-gh-release`: v2 → v3
- `sbom-action`: v0 (no newer tag available; v0 still uses Node.js 20 — acceptable since it's release-only, not CI-blocking)
- `pypa-publish`: release/v1 (branch head, already current)

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

## Verification date

2026-06-16 — all SHAs verified via `api.github.com` (Node.js 24 upgrade).
