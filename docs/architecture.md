# Architecture

BenchDeck has eight bounded modules organized around a pipeline: Plan → Execute → Judge → Artifacts.

## Module summary

| # | Module | Files | Responsibility |
|---|--------|-------|---------------|
| 1 | Planning | `prompts.py`, `openai_gateway.py` | Generate or load a versioned benchmark plan from agent Markdown |
| 2 | Execution | `runner.py` | Run each case with one clarification turn; retry empty responses; classify failures; budget enforcement; resume interrupted runs |
| 3 | Judging | `runner.py`, `models/` | Evaluate output independently; 8-dimension typed rubric; multi-judge with disagreement detection |
| 4 | Artifacts | `storage.py` | Atomically checkpoint JSON; concurrent-reader-safe writes via `portalocker` |
| 5 | Loader / UI | `loader.py`, `tui/` | Safe ZIP/directory artifact loading; 32-column curses TUI with optional color, per-agent views, run-launch and cancel controls |
| 6 | Configuration | `config.py` | TOML config with 3-layer merge (`~/.config/benchdeck/`, `./benchdeck.toml`, `--config`) |
| 7 | Budget | `budget.py` | 7-dimension budget tracker; preflight warning; mid-run enforcement |
| 8 | Logging | `logging_config.py` | JSON-structured log output with configurable level and file destination |

## Data flow

```
Agent.md ──► Plan (planner gateway) ──► Execute (agent gateway, 1 clarification turn)
                                               │
                    ┌──────────────────────────┘
                    ▼
               Judge (judge gateway, 1-N judges per case)
                    │
          ┌─────────┼──────────┐
          ▼         ▼          ▼
      Scoring    Reporting   Disagreement
          │         │          │
          └─────────┼──────────┘
                    ▼
              ArtifactStore (atomic writes with portalocker lock)
                    │
          ┌─────────┼──────────┐
          ▼         ▼          ▼
      Manifest   Loader    Inspect
      (SHA-256)  (dir/ZIP)  (schema + checksum validation)
```

## Key design decisions

- **Runner distinguishes failure classes**: model completion, judging, policy blocks, and infrastructure failures are recorded separately.
- **Empty responses are retried**: an empty LLM response triggers retry and cannot silently become an agent failure without diagnostic evidence.
- **Atomic writes**: every artifact write uses `tempfile.mkstemp` + `os.replace`; the TUI and concurrent readers never see half-written files.
- **Manifest integrity**: every artifact is checksummed with SHA-256 and recorded in a generation-counter-tracked `manifest.json`.
- **Narrow-terminal UX**: the TUI has a 32x10 hard minimum, progressive degradation across width bands, and keyboard-only controls (no mouse, no modifier chords).

## API surface

### Public subcommands

| Subcommand | Entry | Description |
|-----------|-------|-------------|
| `run` | `cli.py:main` → `runner.run_benchmark()` | Full benchmark: plan → execute → judge → artifacts |
| `tui` | `cli.py:main` → `BenchDeckTUI.run()` | Interactive curses dashboard |
| `inspect` | `cli.py:main` → `inspect.inspect_run()` | Schema + manifest validation report |

### Internal boundaries

- `GatewayProtocol` (in `openai_gateway.py`) abstracts the OpenAI API; runner and tests depend on the protocol, not the concrete gateway.
- `Snapshot` dataclass (in `loader.py`) is the single read-side contract consumed by TUI, inspect, and headless render.
- `Manifest` class (in `manifest.py`) provides `record()` / `verify()` / `load()` for artifact integrity.
- Data models under `models/` use Pydantic for serialization and validation.

## See also

- `docs/benchmark-contract.md` — rating scale and gate failure contract
- `docs/mobile-tui.md` — minimum terminal dimensions, key controls, color palette
- `docs/publish.md` — PyPI publish procedures
- `docs/runner-setup.md` — self-hosted runner setup
