# BenchDeck — Remaining Issues (Post-Phase-1 Audit)

**Date:** 2026-06-11
**Baseline:** 187 tests pass · ruff clean · ruff format clean · mypy clean (with `--ignore-missing-imports`)
**Status:** Phase 1 bug fixes complete. 0 critical bugs remain. Known limitations below.

---

## Resolved (Phase 1 — 2026-06-11)

| ID | Issue | Resolution |
|----|-------|------------|
| B1 | ZIP duplicate basename silently overwrites | Fixed: `_load_zip_bytes` now raises `ValueError`. `_load_zip_snapshot` + `load_snapshot` catch and return empty Snapshot. Test updated. |
| B2 | `inspect.py` imports `tui.py` | Fixed: extracted `loader.py` module with `Snapshot`, `load_snapshot`, `_load_zip_bytes`. `inspect.py` and `tui.py` both import from `loader.py`. |
| B5 | Gateway params typed as `Any` | Fixed: added `GatewayProtocol` in `openai_gateway.py`. Runner uses `GatewayProtocol \| None`. |
| B6 | No SIGTERM handler | Fixed: signal handler sets `_shutdown` flag; checked between cases; clean abort with metadata write. |
| B7 | Legacy verdict dead code | Fixed: removed `_legacy_verdict()`, `build_final_verdict()`, `final_verdict_markdown()`, `_confidence_note()`. Replaced with `run_verdict_markdown()` that consumes typed `BenchmarkRunVerdict`. |
| B8 | String comparison vs enum in scoring | Fixed: `scoring.py:46` now uses `j.gate_check.status == GateStatus.FAIL` instead of `.value == "Fail"`. |
| B9 | TUI tally conflates agents in comparison mode | Fixed: `_overview()` now iterates per-agent tally entries and renders separate sections. |
| B10 | Inverted test assertion message | Fixed: test renamed to `test_zip_duplicate_basename_raises_valueerror`, asserts `ValueError`. |
| STYLE-1 | `object.__setattr__` on non-frozen model | Already resolved before Phase 1. |
| STYLE-2 | Inline imports in test_tui_loading.py | Already resolved before Phase 1. |
| DEAD-6 | Redundant gate-override in runner | Already resolved before Phase 1. |
| DOCS-1 | IMPLEMENTATION_CHECKLIST.md stale | Already resolved before Phase 1. |
| DOCS-2 | OPENCODE_IMPLEMENTATION_PHASES.md stale | Already resolved before Phase 1. |
| DOCS-3 | CHANGELOG.md known issues | Already resolved before Phase 1. |

---

## Remaining Architecture Improvements (Not Bugs)

| ID | Issue | Priority |
|----|-------|----------|
| A1 | No logging infrastructure | Medium |
| A2 | No configuration file support | Medium |
| A3 | `models.py` is 689 lines covering ~10 domains | Low |
| A4 | No dependency lock file | Low |
| A8 | No SDK structured output usage | Low |
| A9 | Runner re-raises on infrastructure failure | Medium |

---

## Remaining Known Limitations

- **No multi-judge aggregation.** Each case is judged once per agent.
- **No budget/cost controls.** No token limits or request caps.
- **TUI is read-only.** Cannot launch/pause/cancel runs from TUI.
- **No package release on PyPI.** No signed artifacts or SBOM.
- **No resume support.** Interrupted runs cannot be resumed.
- **No Windows testing.** Developed and tested on Linux.

---

## Verification Commands

```bash
ruff check .
ruff format --check .
python -m mypy --no-incremental src/benchdeck
python -m pytest -q
```

Expected: all clean, 192 tests passed.
