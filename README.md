# BenchDeck

<!-- badges -->
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![CI](https://github.com/MerverliPy/BenchDeck/actions/workflows/ci.yml/badge.svg)](https://github.com/MerverliPy/BenchDeck/actions/workflows/ci.yml)
[![tests](https://img.shields.io/badge/tests-all%20passing-brightgreen.svg)](./.github/workflows/ci.yml)
[![ruff](https://img.shields.io/badge/ruff-clean-000000.svg)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/mypy-clean-blue.svg)](https://mypy-lang.org)

**Evidence-preserving LLM-agent benchmark harness with a live terminal dashboard built for narrow SSH sessions — including Termius on iPhone.**

BenchDeck turns one or two Markdown agent files into a benchmark plan, runs isolated cases with a clarification turn, judges responses with a 0–4 scale, and writes atomically checkpointed artifacts you can watch in real time.

---

## Screenshots

<img src="assets/screenshots/overview.png" alt="Overview screen" width="720">

*Overview — progress bar, rating distribution, per-family scores, token usage*

<img src="assets/screenshots/cases.png" alt="Case list" width="720">

*Case list — per-agent ratings, blocked cases, pending items*

<img src="assets/screenshots/detail.png" alt="Case detail" width="720">

*Case detail — purpose, judgment, gate check, agent output*

<img src="assets/screenshots/help.png" alt="Help screen" width="720">

*Help — phone-keyboard-friendly controls*

*Screenshots are demo captures generated from synthetic data (`scripts/generate_demo_screens.py`).*

---

## Why BenchDeck

Benchmarks are prone to silent ambiguity. BenchDeck makes state explicit:

| Ambiguous situation | BenchDeck handling |
|---|---|
| Empty model response | Retried up to 3x; recorded with response ID, status, and raw payload |
| Policy-blocked response | Logged as a policy block — not an agent failure |
| Infrastructure failure | Recorded separately from agent failures |
| Inconsistent scoring scale | Fixed 0–4 scale (Fail, Weak, Acceptable, Strong, Excellent) |
| Judge transcript duplicates candidate output | Stored in separate fields; never commingled |
| Half-written checkpoint crash | Atomic file replacement — the TUI never reads a partial write |
| Run status vs. real coverage | `inconclusive`, `completed_with_failures`, `infrastructure_failed`, or `aborted` when all cases aren't judged |

---

## Quick Start

**Prerequisites:** Python 3.11+, an OpenAI API key

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .                    # user install (pip install -e '.[dev]' for development)
export OPENAI_API_KEY='sk-...'      # required — the run command checks this
```

**Run a benchmark:**

```bash
benchdeck run \
  --agent-a examples/repository-integrity-agent.md \
  --model gpt-4o-mini \
  --judge-model gpt-4o-mini \
  --output-dir benchmark_out
```

**Watch it live (second SSH session):**

```bash
benchdeck tui benchmark_out
```

**Inspect the results:**

```bash
benchdeck inspect benchmark_out
```

---

## TUI Controls

The TUI targets 32-column terminals. Arrow keys and letter keys both work — no mouse or modifier chords needed:

| Key | Action |
|---|---|
| `1` `2` `3` `4` | Open overview, cases, detail, or help screen |
| `h` / `l` or `←` / `→` | Previous / next screen |
| `j` / `k` or `↓` / `↑` | Move selection or scroll |
| `Enter` | Open selected case |
| `e` | Export case as Markdown |
| `n` | Launch a new benchmark run (subprocess) |
| `x` | Cancel running benchmark (press twice to confirm) |
| `r` | Reload artifacts |
| `q` / `Esc` | Quit |

Recommended Termius settings: UTF-8, monospace font, extra keyboard row with Escape and arrow keys.

---

## CLI Reference

### Global flags

```bash
benchdeck [--config <file.toml>] [--log-level DEBUG|INFO|WARNING|ERROR|CRITICAL] [--log-file <path>] {run,tui,inspect}
```

| Flag | Description |
|---|---|
| `--config` | Path to a TOML configuration file (searched in `~/.config/benchdeck/config.toml`, `./benchdeck.toml`, then explicit path) |
| `--log-level` | Logging level (default: `WARNING`) |
| `--log-file` | Write JSON-structured logs to a file |

### `benchdeck run`

```bash
benchdeck run \
  --agent-a <agent.md>              # required: first agent Markdown file
  --agent-b <agent.md>              # optional: second agent for comparison mode
  --model gpt-4o-mini               # model for agent (default: gpt-4o-mini)
  --planner-model gpt-4o-mini       # model for plan generation (defaults to --model)
  --judge-model gpt-4o-mini         # model for judge (default: gpt-4o-mini)
  --plan benchmark_plan.json        # optional: use a frozen plan instead of generating one
  --output-dir benchmark_out        # output directory for artifacts (short: -o)
  --timeout 90                      # API timeout in seconds (default: 90)
  --max-retries 3                   # max retry attempts per call (default: 3)
  --judges 1                        # number of independent judge calls per case (default: 1)
  --capture-level full              # response capture detail: minimal, standard, or full
  --resume <run_dir>                # resume an interrupted run from the given directory
  --overwrite                       # overwrite if a prior run exists at the exact output path
  --max-output-tokens-planner N     # budget: max output tokens for the planner
  --max-output-tokens-agent N       # budget: max output tokens for the agent
  --max-output-tokens-judge N       # budget: max output tokens for the judge
  --max-logical-requests N          # budget: max logical (API) requests
  --max-http-attempts N             # budget: max HTTP attempts (incl. retries)
  --max-total-input-tokens N        # budget: max total input tokens
  --max-total-output-tokens N       # budget: max total output tokens
```

### `benchdeck tui`

```bash
benchdeck tui benchmark_out                     # watch a live run
benchdeck tui fixtures/original_run.zip          # open the bundled run
```

### `benchdeck inspect`

```bash
benchdeck inspect fixtures/original_run.zip
```

Detects incomplete coverage, empty outputs, duplicated judge transcripts, undeclared scoring scales, misleading run status, and validates per-agent tallies against `schemas/summary_tally.schema.json`.

### Using a frozen plan

```bash
python - <<'PY'
import json
from pathlib import Path
from benchdeck.loader import load_snapshot
plan = load_snapshot(Path('fixtures/original_run.zip')).plan
Path('/tmp/benchmark_plan.json').write_text(json.dumps(plan, indent=2) + '\n')
PY
benchdeck run --agent-a examples/repository-integrity-agent.md --plan /tmp/benchmark_plan.json -o benchmark_out
```

---

## Architecture

```
Agent.md ──► Plan ──► Execute ──► Judge ──► Artifacts ──► Loader ──► TUI
              (planner     (agent         (judge        (atomic     (ZIP/dir
               gateway)     gateway)        gateway)      writes)      reader)
                                     │
                               Gate check (0-4)
                               Typed rubric (8 dims)
                               Policy block log
                               Infra failure log
```

Eight modules:

1. **Planning** (`prompts.py`, `openai_gateway.py`) — generate or load a versioned benchmark plan from agent Markdown
2. **Execution** (`runner.py`) — run each case with one clarification turn; retry empty responses; classify failures; budget enforcement; resume interrupted runs
3. **Judging** (`runner.py`, `models/`) — evaluate output independently; 8-dimension typed rubric; multi-judge with disagreement detection
4. **Artifacts** (`storage.py`) — atomically checkpoint JSON; concurrent-reader-safe writes
5. **Loader / UI** (`loader.py`, `tui.py`) — safe ZIP/directory artifact loading; 32-column curses TUI with optional color, per-agent views, run-launch and cancel controls
6. **Configuration** (`config.py`) — TOML config with 3-layer merge (`~/.config/benchdeck/`, `./benchdeck.toml`, `--config`)
7. **Budget** (`budget.py`) — 7-dimension budget tracker; preflight warning; mid-run enforcement
8. **Logging** (`logging_config.py`) — JSON-structured log output with configurable level and file destination

See `docs/architecture.md`, `docs/benchmark-contract.md`, and `docs/mobile-tui.md` for details.

---

## Limitations

- **No PyPI release or signed artifacts.** CI workflows for publish (`publish.yml`) and release with SBOM (`release.yml`) exist but have not been triggered (no `v*` tag pushed).
- **Inspector hardening pending.** `inspect.py` validates schema but not checksums, referential integrity, or counter consistency.
- **No cross-process run lock.** `storage.py` uses atomic writes (`os.replace`), but concurrent writers to the same output directory could race.
- **No Windows testing.** Developed and tested on Linux only.
- **No dependency lock file.** `requirements.txt` provides reproducible pins; no `requirements.lock` or `uv.lock` exists.
- **`dist/` artifacts stale.** (Built 2026-06-11; source has changed since.) Not committed — `dist/` is gitignored.

See [REMAINING_ISSUES.md](./REMAINING_ISSUES.md) for the full list of known limitations.

---

## Known Issues

The [CHANGELOG](./CHANGELOG.md#known-issues-resolved-post-v010) lists issues resolved since the v0.1.0 release. For current limitations, see [REMAINING_ISSUES.md](./REMAINING_ISSUES.md).

---

## Development

```bash
ruff check .                              # lint
ruff format --check .                     # formatting
mypy src/benchdeck/                       # type checking (strict; requires types-jsonschema in dev deps)
pytest --cov=src/benchdeck --cov-report=term-missing  # 349 tests (2 skipped — live API only)
```

Or use the Makefile:

```bash
make install   # pip install -e '.[dev]'
make test      # pytest --cov=src/benchdeck --cov-report=term-missing
make lint      # ruff check .
make fixture   # benchdeck inspect fixtures/original_run.zip
```
