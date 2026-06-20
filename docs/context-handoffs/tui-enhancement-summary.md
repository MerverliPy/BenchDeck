# TUI enhancement handoff summary

## Purpose

Plan and implement BenchDeck TUI improvements without overloading agent context with the full structured enhancement plan.

## Current state

| Item | State |
|---|---|
| Canonical doc | `docs/tui-enhancement-plan.md` |
| Detailed reference shards | `docs/reference/tui-enhancement/` |
| Completed work | Phase 0 and Phase 1 sequence through merged documentation updates. |
| Approval gates | Phase 2 behavior changes and Phase 3 screenshot/golden work require explicit approval. |
| Main tests | `tests/test_tui_render.py`, `tests/test_tui_loading.py`, `tests/test_screenshots.py`. |

## TUI surfaces

| Surface | Notes |
|---|---|
| Tabs | Overview, Cases, Detail, Help. |
| Keys | `h/l`, `j/k`, `Enter`, `e`, `n`, `x`, `r`, `q`. |
| Constraints | Hard minimum viewport is 32×10; narrow footer/tab behavior must remain safe. |
| Snapshot data | Metadata, plan cases, tally, judgments, results, policy blocks, infra errors, planner capture, manifest status. |

## Reference routing

| Need | Open |
|---|---|
| Current-state matrix, branch history, test map | `docs/reference/tui-enhancement/status-and-current-state.md` |
| Discoverability, cases, detail, overview, live feedback, color, robustness gaps | `docs/reference/tui-enhancement/gap-inventory.md` |
| Phase 0–3 enhancement plan and recommended sequence | `docs/reference/tui-enhancement/enhancement-phases-and-sequence.md` |
| Out-of-scope items, validation commands, open questions | `docs/reference/tui-enhancement/validation-and-open-questions.md` |
| Risk mitigations, commit procedure, rollback, promotion gates | `docs/reference/tui-enhancement/risks-and-implementation-procedure.md` |

## Safe next-work pattern

1. Choose one narrow UI change.
2. Confirm whether it is Phase 0/1 safe work or Phase 2/3 gated work.
3. Add or update focused tests first when practical.
4. Run targeted TUI tests.
5. Run full quality gates before merge.

## Validation commands

```bash
python -m pytest tests/test_tui_render.py tests/test_tui_loading.py -q
python -m pytest tests/test_screenshots.py -q
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy src/benchdeck/
```
