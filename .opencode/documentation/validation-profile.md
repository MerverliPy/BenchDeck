# BenchDeck Documentation Validation Profile

> Status: **CONFIGURED** from `Makefile`, `pyproject.toml`, `.github/workflows/ci.yml`, the CLI entry point, and current tests. Commands that execute repository code still require approval under the agent permission policy unless separately allowlisted.

## Mandatory baseline

For every changed document:

- inspect `git status --short`, `git diff --name-only`, `git diff --stat`, and the final documentation diff;
- run `git diff --check`;
- confirm only intended documentation paths changed and no source, test, schema, fixture, screenshot baseline, release, or dependency files changed;
- verify local links, headings, anchors, image paths, and referenced repository paths;
- verify all documented CLI commands, subcommands, flags, defaults, configuration keys, environment-variable names, package versions, and feature statuses against `src/benchdeck/`, tests, `pyproject.toml`, and active CI;
- verify benchmark-artifact claims against models, schemas, loader/storage behavior, fixtures, and tests rather than narrative prose alone;
- verify TUI claims against `src/benchdeck/tui.py`, loading/render tests, and screenshot provenance;
- verify code-block language tags and shell-command ordering;
- scan changed text for real credentials, private repository data, internal hosts, or copied benchmark content;
- re-check consistency across `README.md`, `docs/`, `CHANGELOG.md`, `REMAINING_ISSUES.md`, `CONTRIBUTING.md`, and `SECURITY.md` as applicable.

## Repository-defined checks

| Check | Command or method | Evidence source | Execution permission |
|---|---|---|---|
| Whitespace/patch integrity | `git diff --check` | Git | Allow |
| Changed-path boundary | `git status --short` and `git diff --name-only` | Git | Allow |
| Markdown syntax/style | Structured static review; no Markdown linter is configured | Repository state | No command; report method |
| Local link/anchor check | Resolve relative paths and generated heading anchors from each changed document | Repository tree | No repository command configured |
| External link check | Check only when network access is explicitly approved | Documentation links | Ask |
| Python lint | `ruff check .` | `Makefile`, `.github/workflows/ci.yml` | Ask |
| Python format check | `ruff format --check .` | `.github/workflows/ci.yml` | Ask |
| Type check | `mypy src/benchdeck/` | `.github/workflows/ci.yml`, `pyproject.toml` | Ask |
| Full test suite | `pytest --cov=src/benchdeck --cov-report=term-missing` | `Makefile`, `.github/workflows/ci.yml` | Ask |
| CLI/config/inspect claims | `pytest -q -p no:cacheprovider tests/test_cli.py tests/test_config.py tests/test_inspect.py` | `tests/` | Ask |
| TUI claims | `pytest -q -p no:cacheprovider tests/test_tui_render.py tests/test_tui_loading.py` | `tests/` | Ask |
| Screenshot claims | `python -m pytest -q -p no:cacheprovider tests/test_screenshots.py` | CI and `tests/test_screenshots.py` | Ask; may require screenshot dependencies/fonts |
| Fixture smoke check | `benchdeck inspect fixtures/original_run.zip` | `Makefile`, `README.md` | Ask |
| CLI help | `benchdeck --help`, `benchdeck run --help`, `benchdeck tui --help`, `benchdeck inspect --help` | `src/benchdeck/cli.py`, `pyproject.toml` | Ask |
| Credential-pattern scan | Use the non-mutating grep pattern and exclusions defined in `.github/workflows/ci.yml` | CI | Ask before shell execution; never echo matched secret values |

## Claim-directed validation

Choose the narrowest checks that prove the changed claims:

- **Installation/package requirements:** verify `pyproject.toml`, `Makefile`, and CI; do not install dependencies solely to confirm prose without approval.
- **CLI/configuration:** inspect `src/benchdeck/cli.py` and `src/benchdeck/config.py`, then request the focused CLI/config tests or help commands when execution would materially increase confidence.
- **Benchmark planning/execution/judging:** inspect the corresponding source, model/schema definitions, and focused tests; use full tests only when the claim spans components.
- **Artifact integrity/loading:** verify storage/loader implementation, schemas, fixtures, and related tests; do not modify fixtures.
- **TUI behavior:** verify implementation and targeted tests. Distinguish synthetic screenshots from real-run captures.
- **Release/version claims:** verify `pyproject.toml`, `CHANGELOG.md`, tags/releases when network access is approved, and release workflows. Never infer a new version.
- **Known limitations:** check current source and tests before preserving README or issue-list claims; a historical limitation may already be implemented.

## Execution policy

- Read-only Git inspection commands explicitly allowed by the agent may run automatically.
- Test, lint, type-check, CLI, package-manager, network, screenshot-generation, and dependency-install commands require approval unless a narrower agent permission explicitly allows the exact command.
- Do not run `benchdeck run` during routine documentation validation because it uses external model APIs, credentials, time, and cost.
- Do not generate or replace screenshots, fixtures, schemas, release artifacts, or benchmark output during documentation validation.
- Destructive commands, source-tree mutation, publishing, release creation, and push operations are outside validation scope.
- When a tool or dependency is unavailable, mark the check **Not run** with the exact reason; do not downgrade it silently to visual inspection.

## Minimum report table

| Check | Status | Command/method | Evidence or failure |
|---|---|---|---|
