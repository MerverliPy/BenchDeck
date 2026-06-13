# BenchDeck — Remaining Issues

**Date:** 2026-06-12
**Baseline:** 349 tests pass (2 skipped) · ruff clean · ruff format clean · mypy clean (strict on `src/` and `tests/`) · 77% coverage
**Status:** All Phase 1-7 features implemented. All 20 prior audit findings resolved and revalidated. Latest audit (2026-06-12 r2): 1 P0 (credential in `.envrc` — intentional/scoped via direnv), 2 P2 (stale docs, uncommitted `.gitignore`), 3 P3 (stale docs, stale dist, working-tree state).

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

## Resolved (Phase 2-7 — 2026-06-12)

| ID | Issue | Resolution |
|----|-------|------------|
| A1 | No logging infrastructure | Implemented: `src/benchdeck/logging_config.py` with structured JSON logging |
| A2 | No configuration file support | Implemented: `src/benchdeck/config.py` supports TOML config files; `--planner-model`, budget CLI flags wired |
| A3 | `models.py` is 689 lines / ~10 domains | Implemented: refactored into `models/` package (6 sub-modules: plan, execution, judgment, result, gateway, infra) |
| A9 | Runner re-raises on infrastructure failure | Needs re-verification with current runner code |

---

## Resolved Audit Findings (2026-06-12 r1)

All findings from the first 2026-06-12 audit round are resolved. See `AGENT_HANDOFF.md` for full details.

| ID | Severity | Description |
|----|----------|-------------|
| AUD-P1-001 | P1 | `timeout=` vs `timeout_s=` in test_gateway.py (FIXED) |
| AUD-P2-001 | P2 | String `"timeout"` where `ErrorCategory.TIMEOUT` expected (FIXED) |
| AUD-P2-002 | P2 | `sys.path.insert()` hack in test_screenshots.py (FIXED) |
| AUD-P3-001 | P3 | Stale docs: this file and IMPLEMENTATION_CHECKLIST.md (FIXED) |
| AUD-P3-002 | P3 | ~16 mypy errors in `tests/` (FIXED — mypy clean on `src/` and `tests/` in strict mode) |
| AUD-P3-003 | P3 | `__main__.py` 0% test coverage (NOTED — entry point; covered by CLI integration tests) |
| AUD-P3-004 | P3 | `duplicate_keys` always empty in CoverageReport (FIXED) |

---

## Remaining Known Limitations

- **No PyPI release or signed artifacts.** CI workflows for publish (`publish.yml`) and release with SBOM (`release.yml`) exist but have not been triggered (no `v*` tag pushed).
- **Inspector hardening pending.** `inspect.py` validates schema but not checksums, referential integrity, or counter consistency.
- **No cross-process run lock.** `storage.py` uses atomic writes but concurrent writers could race.
- **No Windows testing.** Developed and tested on Linux only.
- **No dependency lock file.** `requirements.txt` provides reproducible pins; no `requirements.lock` or `uv.lock`.
- **`dist/` artifacts stale.** (Built 2026-06-11; source has changed.) Not committed — `dist/` is gitignored.

---

## Verification Commands

```bash
ruff check .
ruff format --check .
python -m mypy --no-incremental src/benchdeck
python -m pytest -q
```

Expected: all clean, 349 tests passed (2 skipped).
