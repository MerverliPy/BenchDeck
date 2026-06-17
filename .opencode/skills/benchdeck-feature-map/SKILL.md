---
name: benchdeck-feature-map
description: Repository-specific map of BenchDeck CLI, curses TUI, OpenAI integration, artifact, configuration, budget, inspection, and reporting surfaces to use during product-test discovery
license: MIT
compatibility: opencode
metadata:
  repository: MerverliPy/BenchDeck
  baseline: e3405fbd072f6213787d616b0c2636b11a2a4095
---

## Authoritative implementation surfaces

- `pyproject.toml`: package metadata, Python support, dependencies, console entry point.
- `src/benchdeck/cli.py`: parser, config merge, key requirement, subcommands, exit codes.
- `src/benchdeck/runner.py`: planning, execution, clarification, judging, budgets, interruption, resume.
- `src/benchdeck/openai_gateway.py`: real provider requests, retry/error/refusal/usage capture.
- `src/benchdeck/config.py`: TOML search and merge.
- `src/benchdeck/storage.py`: atomic artifact writes.
- `src/benchdeck/loader.py`: directory and ZIP loading.
- `src/benchdeck/inspect.py`: output audit.
- `src/benchdeck/tui/app.py` and `src/benchdeck/tui/helpers.py`: curses state, screens, keys, rendering, export, launch, cancellation.
- `src/benchdeck/manifest.py`: artifact manifest/integrity.
- `src/benchdeck/budget.py`: request/token limits.
- `src/benchdeck/reporting.py`, `scoring.py`, `disagreement.py`: verdict and score outputs.
- `src/benchdeck/models/` and `src/benchdeck/schemas/`: data contracts.
- `.github/workflows/ci.yml`: active Python 3.11–3.13 regression checks.

## Current interfaces

### CLI

Global flags: config, log level, log file.

Subcommands:

- `run`: one/two agent files, optional frozen plan, models, timeout, retries, judges, capture level, resume, overwrite, and seven budget controls.
- `tui`: directory/ZIP input, refresh interval, optional launch agent paths and models.
- `inspect`: directory/ZIP input and JSON/text output.

### TUI

Screens: Overview, Cases, Detail, Help.

Inputs:

- 1–4 screen selection;
- h/l and left/right;
- j/k and up/down;
- Enter;
- e export;
- n launch;
- x two-stage cancel;
- r reload;
- q/Esc quit.

Minimum rendering boundary: 32x10.

### Runtime integrations

- OpenAI API through the Python SDK.
- Filesystem directories and ZIP archives.
- Child benchmark subprocess from the TUI.
- Signals and atomic checkpoint writes.

## Evidence warning

`tests/fakes.py`, fake gateways, `unittest.mock`, and monkeypatch-based tests are simulated regression evidence. They do not prove real provider, subprocess, PTY, filesystem race, network, or platform behavior.

## Current absence decisions

No browser application, frontend build, HTTP server, or server API was detected at the baseline. Re-check every run before marking WebUI and server API `NOT_APPLICABLE`.
