# BenchDeck

<!-- badges -->
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![CI](https://github.com/MerverliPy/BenchDeck/actions/workflows/ci.yml/badge.svg)](https://github.com/MerverliPy/BenchDeck/actions/workflows/ci.yml)
[![tests](https://img.shields.io/badge/tests-145%20passed-brightgreen.svg)](./REMAINING_ISSUES.md)
[![ruff](https://img.shields.io/badge/ruff-clean-000000.svg)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy-lang.org)

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
pip install -e '.[dev]'
export OPENAI_API_KEY='sk-...'
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

The TUI targets 32-column terminals and works with no mouse, no function keys, and no modifier chords:

| Key | Action |
|---|---|
| `1` `2` `3` `4` | Open overview, cases, detail, or help screen |
| `h` / `l` | Previous / next screen |
| `j` / `k` | Move selection or scroll |
| `Enter` | Open selected case |
| `e` | Export case as Markdown |
| `r` | Reload artifacts |
| `q` / `Esc` | Quit |

Recommended Termius settings: UTF-8, monospace font, extra keyboard row with Escape and arrow keys.

---

## CLI Reference

### `benchdeck run`

```bash
benchdeck run \
  --agent-a <agent.md>              # required: first agent Markdown file
  --agent-b <agent.md>              # optional: second agent for comparison mode
  --model gpt-4o-mini               # model for agent (default: gpt-4o-mini)
  --judge-model gpt-4o-mini         # model for judge (default: gpt-4o-mini)
  --plan benchmark_plan.json        # optional: use a frozen plan instead of generating one
  --output-dir benchmark_out        # output directory for artifacts
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
from benchdeck.tui import load_snapshot
plan = load_snapshot(Path('fixtures/original_run.zip')).plan
Path('/tmp/benchmark_plan.json').write_text(json.dumps(plan, indent=2) + '\n')
PY
benchdeck run --agent-a examples/repository-integrity-agent.md --plan /tmp/benchmark_plan.json -o benchmark_out
```

---

## Architecture

```
Agent.md ──► Plan ──► Execute ──► Judge ──► Artifacts ──► TUI
                                    │
                              Gate check (0-4)
                              Policy block log
                              Infra failure log
                              Atomic checkpoint
```

Four bounded layers:
1. **Planning** — infer or load a versioned benchmark plan from agent Markdown
2. **Execution** — run each case with one clarification turn; retry empty responses
3. **Judging** — evaluate output independently with preserved raw judge response
4. **Artifacts / UI** — atomically checkpoint JSON; the TUI safely watches a live run

See `docs/architecture.md`, `docs/benchmark-contract.md`, and `docs/mobile-tui.md` for details.

---

## Limitations

- **No multi-judge aggregation.** Each case is judged once per agent; no ensemble or disagreement reporting yet.
- **No budget cap.** No token or cost limit guards a run.
- **No signed releases or SBOM.** Distribution artifacts have not been published.
- **The TUI cannot launch or cancel runs.** It is read-only; runs are started from the CLI.
- **Comparison mode in the TUI is partial.** Per-agent judgments display but selection/filtering by agent is not yet implemented.
- **No Windows testing.** Developed and tested on Linux and macOS.

---

## Development

```bash
ruff check .              # lint
ruff format --check .     # formatting
mypy src/benchdeck/ --ignore-missing-imports  # type checking
pytest                    # 145 tests
```
