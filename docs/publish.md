# Publishing `benchdeck` to PyPI

The release is driven by `.github/workflows/publish.yml`, which runs on every
`v*` tag push. The workflow supports **two independent authentication paths**
and picks one at runtime based on whether the `PYPI_API_TOKEN` repository
secret is set:

| Path | Trigger | Requires operator action on PyPI? | Requires repo secret? |
|---|---|---|---|
| **A. API token** | `secrets.PYPI_API_TOKEN` is set | No (after the project exists) | Yes |
| **B. Trusted Publishing (OIDC)** | `secrets.PYPI_API_TOKEN` is empty | Yes (one-time form on pypi.org) | No |

The workflow emits a step-summary line announcing the selected path so a
maintainer can see, after the fact, which one ran.

## Path A — API token (fastest, no PyPI configuration)

Use this if you want the next tag to succeed **without** creating a Trusted
Publisher on PyPI.

1. The PyPI project `benchdeck` must already exist. If it does not, create it
   once at <https://pypi.org/project/benchdeck/> (or via `pyproject.toml`'s
   `name = "benchdeck"` + an initial manual upload).
2. Mint a project-scoped API token at
   <https://pypi.org/manage/account/token/>. Scope: "Project: benchdeck",
   "Upload packages". Copy the token (`pypi-...`) — PyPI shows it only once.
3. Add it as a repository secret:
   * Repo → **Settings** → **Secrets and variables** → **Actions** →
     **New repository secret**
   * Name: **`PYPI_API_TOKEN`** (must match the workflow literal)
   * Value: paste the token
4. Push the next tag (e.g. `git tag v0.1.3 && git push origin v0.1.3`).

The workflow will run the `Publish to PyPI (API token)` step and exit 0.

## Path B — Trusted Publishing (no secret in the repo)

Use this long term. The workflow proves its identity to PyPI via a short-lived
OIDC token; no long-lived secret is stored in GitHub.

### One-time PyPI form

1. Open <https://pypi.org/manage/account/publishing/>.
2. Add a pending publisher (or, for an already-existing project, a publisher
   for that project) with **exactly** these fields:

   | Field | Value |
   |---|---|
   | Owner | `MerverliPy` |
   | Repository | `BenchDeck` |
   | Workflow filename | `publish.yml` |
   | Environment name | `pypi` |

   The environment name must match the `environment: pypi` block in
   `publish.yml:14-16`. The workflow filename must match exactly
   (lowercase, no path prefix).

3. (Optional but recommended) Set a **release manager** for the project so
   trusted-publisher additions still require human approval:
   <https://docs.pypi.org/trusted-publishers/adding-a-publisher/#_3-optional-set-the-project-to-require-manual-approval>.

### What the OIDC claims look like

For debugging, GitHub includes the rendered claims in the action's error
output. The values below are an **illustrative snapshot** captured from a
real run (`v0.1.2`); the only fields that need to match exactly on PyPI
are `owner`, `repository`, the workflow filename, and the environment name.
The numeric IDs and the tag-specific ref fields will differ on each run
and across repos.

* `sub`: `repo:MerverliPy/BenchDeck:environment:pypi`
* `repository`: `MerverliPy/BenchDeck`
* `repository_owner`: `MerverliPy`
* `repository_owner_id`: `194641652`
* `workflow_ref`: `MerverliPy/BenchDeck/.github/workflows/publish.yml@refs/tags/v0.1.2`
* `job_workflow_ref`: `MerverliPy/BenchDeck/.github/workflows/publish.yml@refs/tags/v0.1.2`
* `ref`: `refs/tags/v0.1.2`
* `environment`: `pypi`

If a tag push fails with `invalid-publisher: Publisher with matching claims
was not found`, the most common causes are:

* The form field "Workflow filename" is `Publish to PyPI` (the workflow's
  display name) instead of `publish.yml` (the file name).
* The form field "Environment name" is empty or `Pypi` (capital P); it must
  be exactly `pypi`.
* The PyPI project does not exist yet; Trusted Publishing requires an
  already-registered project. Create the project (Path A step 1) first, then
  add the publisher.

## Verifying locally before tagging

You can confirm the build will succeed without a tag push:

```bash
python -m pip install --upgrade build twine
python -m build
twine check dist/*
```

Expected: `dist/benchdeck-<version>-py3-none-any.whl` and
`dist/benchdeck-<version>.tar.gz` are produced and `twine check` reports
`PASSED` for both.

## Published versions are immutable

Once a version tag is pushed and the package is published to PyPI, the version
must **never** be deleted, re-tagged, or re-published. If a publish step fails,
fix the workflow and bump the version in `pyproject.toml` (following the
`NEXT_VERSION` gate comment at the top of that file). Do not delete the tag
and re-push.

## Release flow (Phase 1)

A unified build workflow (`.github/workflows/_build.yml`) builds the wheel and
sdist exactly once, runs the full test suite, and uploads the artifacts as an
immutable workflow artifact. The `publish.yml` and `release.yml` workflows
consume this single artifact — no rebuilding occurs per destination. See each
workflow file for the exact steps.

## Switching between paths

The two paths are independent. Setting `PYPI_API_TOKEN` does not invalidate
the Trusted Publisher; clearing the secret re-enables the OIDC path. You can
run one tag with the token and the next with OIDC without any other change.
