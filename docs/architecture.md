# Architecture

BenchDeck has eight bounded modules:

1. **Planning** (`prompts.py`, `openai_gateway.py`) — generate or load a versioned benchmark plan from agent Markdown
2. **Execution** (`runner.py`) — run each case with one clarification turn; retry empty responses; classify failures; budget enforcement; resume interrupted runs
3. **Judging** (`runner.py`, `models/`) — evaluate output independently; 8-dimension typed rubric; multi-judge with disagreement detection
4. **Artifacts** (`storage.py`) — atomically checkpoint JSON; concurrent-reader-safe writes
5. **Loader / UI** (`loader.py`, `tui/`) — safe ZIP/directory artifact loading; 32-column curses TUI with optional color, per-agent views, run-launch and cancel controls
6. **Configuration** (`config.py`) — TOML config with 3-layer merge (`~/.config/benchdeck/`, `./benchdeck.toml`, `--config`)
7. **Budget** (`budget.py`) — 7-dimension budget tracker; preflight warning; mid-run enforcement
8. **Logging** (`logging_config.py`) — JSON-structured log output with configurable level and file destination

The runner distinguishes model completion, judging, policy blocks, and infrastructure failures. An empty
text response is retried and cannot silently become an agent failure without diagnostic evidence.
