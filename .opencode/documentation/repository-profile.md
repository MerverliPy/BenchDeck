# BenchDeck Repository Documentation Profile

> Status: **CONFIGURED** from repository evidence on the `main` branch at base commit `b46c4ed6470c1d6a22e46b0ba82a28c0115c9520`. Re-verify facts after material CLI, schema, packaging, CI, or documentation changes.

## Repository identity

- Project name: `BenchDeck`
- One-sentence purpose: Evidence-preserving LLM-agent benchmark harness with a live, narrow-terminal SSH dashboard, including mobile Termius use.
- Primary audiences: people evaluating Markdown-defined LLM agents, developers integrating or inspecting benchmark runs, contributors, and maintainers.
- Repository type: Python 3.11+ CLI application/library with a `curses` terminal UI.
- Current package version: `0.1.0`; no separate supported-release-line policy is defined.
- Default branch: `main`

## Canonical documentation and evidence

- Primary README and user onboarding: `README.md`
- Documentation root: `docs/`
- Documentation index/navigation source: `README.md`
- CLI reference: `src/benchdeck/cli.py`, verified against `tests/test_cli.py`; README CLI examples are secondary evidence.
- Benchmark/artifact contract: `docs/benchmark-contract.md`, model/schema definitions under `src/benchdeck/`, and related tests.
- Architecture source: `docs/architecture.md`, then current implementation under `src/benchdeck/`.
- Mobile TUI source: `docs/mobile-tui.md`, `src/benchdeck/tui.py`, renderer/loading tests, and screenshot tests.
- Configuration source: `src/benchdeck/config.py`, CLI definitions in `src/benchdeck/cli.py`, and `tests/test_config.py`.
- Package metadata/version source: `pyproject.toml`
- Changelog/release source: `CHANGELOG.md`, `pyproject.toml`, and `.github/workflows/release.yml` / `.github/workflows/publish.yml`.
- Development-status and known-issue source: `REMAINING_ISSUES.md`; implementation plans and audit handoffs are internal evidence, not current feature documentation.
- Contribution policy: `CONTRIBUTING.md`
- Security policy: `SECURITY.md`
- Support path: no dedicated `SUPPORT.md` is present. Do not invent a support channel; distinguish private vulnerability reporting in `SECURITY.md` from general project support.

## Verified developer and validation commands

Commands are supported by `Makefile`, `pyproject.toml`, `.github/workflows/ci.yml`, or the CLI entry point. Dependency installation remains approval-gated.

| Purpose | Command | Evidence path | Automatic execution |
|---|---|---|---|
| Development install | `python -m pip install -e '.[dev]'` | `Makefile`, `.github/workflows/ci.yml`, `pyproject.toml` | Ask; modifies the environment |
| Full test suite | `pytest --cov=src/benchdeck --cov-report=term-missing` | `Makefile`, `.github/workflows/ci.yml` | Ask; executes repository code and writes coverage data |
| Focused tests | `pytest -q -p no:cacheprovider <test paths>` | `pyproject.toml`, `tests/` | Ask unless explicitly allowlisted for the invocation |
| Lint | `ruff check .` | `Makefile`, `.github/workflows/ci.yml` | Ask |
| Format check | `ruff format --check .` | `.github/workflows/ci.yml` | Ask |
| Type check | `mypy src/benchdeck/` | `.github/workflows/ci.yml`, `pyproject.toml` | Ask |
| Fixture smoke check | `benchdeck inspect fixtures/original_run.zip` | `Makefile`, `README.md` | Ask |
| CLI help | `benchdeck --help` and `<subcommand> --help` | `pyproject.toml`, `src/benchdeck/cli.py`, `tests/test_cli.py` | Ask |
| Markdown/link check | `[NOT CONFIGURED]` | No repository command identified | Not run unless a maintainer adds one |

## Feature-status sources

- **Supported:** require executable behavior/tests plus active CLI, schema, configuration, or package wiring.
- **Experimental:** use only when current implementation exposes the behavior but stability/support is explicitly limited.
- **Planned:** use `REMAINING_ISSUES.md`, future-facing implementation plans, or explicit maintainer direction; never promote these items from prose alone.
- **Deprecated/removed:** require implementation, changelog, migration, or maintainer evidence; do not infer from age.
- README limitations and feature lists must be rechecked against current `src/benchdeck/` and tests because implementation may advance before prose is updated.

## Repository-specific terminology

| Preferred term | Avoid or qualify | Reason/source |
|---|---|---|
| `BenchDeck` | generic “benchmark runner” when naming the product | `README.md`, `pyproject.toml` |
| `benchmark plan` | `test plan` when referring to the versioned BenchDeck plan artifact | README and runner/model terminology |
| `agent A` / `agent B` | ambiguous “model A” / “model B” | CLI and artifact terminology |
| `judge` / `judgment` | `grader` unless quoting an external interface | source and schema terminology |
| `run directory` or `run ZIP` | generic “results file” | loader, CLI, and TUI interfaces |
| `TUI` or `terminal dashboard` | “web dashboard” | README and implementation |
| `policy block` | `agent failure` | README and run-status accounting |
| `infrastructure failure` | `agent failure` | README and run-status accounting |

## Documentation exclusions and protected evidence

The documentation agent may inspect these areas when evidence is needed but must not edit them:

- `.opencode/**` during normal documentation-maintenance runs;
- `fixtures/**` benchmark fixtures and archived run evidence;
- `assets/screenshots/golden/**` visual-regression baselines;
- `assets/screenshots/ci/**` and other generated screenshot output;
- `benchmark_out/**`, `build/**`, `dist/**`, `*.egg-info/**`, caches, and virtual environments;
- schemas and implementation under `src/**`;
- tests under `tests/**`;
- internal execution/audit artifacts such as `AGENT_HANDOFF.md`, `IMPLEMENTATION_CHECKLIST.md`, `OPENCODE_IMPLEMENTATION_PHASES.md`, and `docs/audit-findings.md`, unless the user explicitly requests internal-document maintenance.

## Additional approval rules

- Any claim that changes artifact backward-compatibility expectations requires explicit approval and implementation/schema evidence.
- Any change to screenshot baselines, generated screenshots, or claims that a screenshot represents a live run requires explicit approval and provenance verification.
- Do not change the package version, release workflows, published release notes, or known-issue resolution status without explicit approval and direct evidence.
