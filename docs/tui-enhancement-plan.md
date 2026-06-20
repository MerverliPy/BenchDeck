# BenchDeck TUI — Structured Enhancement Plan

> Agent context note: this file is now the concise routing document. Use `docs/context-handoffs/tui-enhancement-summary.md` for agent handoffs. Open the reference shards below only for the specific implementation area being changed.

## Current status

| Area | State |
|---|---|
| Execution branch | TUI work merged through `cycle4b-tui-phase0-7-docs`. |
| Phase 0 observability/tests | Complete. |
| Phase 1 low-risk legibility improvements | Complete through current merged sequence. |
| Phase 2 behavior changes | Requires explicit approval before implementation. |
| Phase 3 screenshot/golden baseline work | Requires explicit approval and screenshot subagent gating. |
| Known deviations | Selection summary uses ASCII fallback in the live TUI; Unicode glyphs are rendered only by screenshot generator. |

## Start here

| Task | File |
|---|---|
| Agent-facing handoff | [`context-handoffs/tui-enhancement-summary.md`](context-handoffs/tui-enhancement-summary.md) |
| Status, branch history, tabs, keybindings, colors, layout, snapshot fields, tests | [`reference/tui-enhancement/status-and-current-state.md`](reference/tui-enhancement/status-and-current-state.md) |
| UX and coverage gap inventory | [`reference/tui-enhancement/gap-inventory.md`](reference/tui-enhancement/gap-inventory.md) |
| Phase 0–3 enhancement plan and recommended sequence | [`reference/tui-enhancement/enhancement-phases-and-sequence.md`](reference/tui-enhancement/enhancement-phases-and-sequence.md) |
| Out-of-scope boundaries, validation, and open questions | [`reference/tui-enhancement/validation-and-open-questions.md`](reference/tui-enhancement/validation-and-open-questions.md) |
| Risk mitigations and implementation procedure | [`reference/tui-enhancement/risks-and-implementation-procedure.md`](reference/tui-enhancement/risks-and-implementation-procedure.md) |

## Current-state summary

| Surface | Summary |
|---|---|
| Tabs | Overview, Cases, Detail, Help. |
| Core keybindings | `h/l` tabs, `j/k` move or scroll, `Enter` detail, `e` export, `n` run, `x` cancel, `r` reload, `q` quit. |
| Rendering constraints | Hard minimum viewport is 32×10; narrow mode affects tab names and footer truncation. |
| Snapshot inputs | Metadata, plan cases, tally, judgments, policy blocks, results, infrastructure errors, planner capture, and manifest verification. |
| Primary test surface | `tests/test_tui_render.py`, `tests/test_tui_loading.py`, and `tests/test_screenshots.py`. |

## Next safe work

1. Keep Phase 2 and Phase 3 behind explicit approval gates.
2. Prefer pure-observability or low-risk legibility work first.
3. Preserve existing text-based assertions unless intentionally updating snapshot/golden output.
4. Add tests before behavior changes when feasible.
5. Validate with targeted TUI tests, screenshot tests when the renderer changes, then full pytest/ruff/mypy.

## Validation commands

```bash
python -m pytest tests/test_tui_render.py tests/test_tui_loading.py -q
python -m pytest tests/test_screenshots.py -q
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy src/benchdeck/
```

## Guardrails

- Do not implement Phase 2 behavior changes without explicit approval.
- Do not run screenshot/golden baseline work unless the screenshot subagent is explicitly invoked and gated.
- Do not alter run execution or cancellation semantics as part of cosmetic work.
- Do not introduce color-only state signals; keep ASCII/text fallbacks.
