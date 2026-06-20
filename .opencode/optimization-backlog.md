# BenchDeck Optimization Backlog — COMPLETED

**Completed:** 2026-06-20
**Final baseline:** 576 tests pass, 11 skipped, ruff clean, ruff format clean, mypy clean (strict)

---

## Lane 3: README/Docs Product Clarity

- [x] **3.1 P1** Fix broken `-o` flag in README → replaced with `--output-dir`
  - Files: `README.md:51,55,92-93,206-214`
- [x] **3.2 P3** Fix stale test-count badge (476 → 412 → 576)
  - Files: `README.md:7`, `README.md:269`
- [x] **3.3 P2** Fix CHANGELOG overclaim about opencode.jsonc
  - Files: `CHANGELOG.md:7-8`
- [x] **3.4 P2** Add explicit validation commands to AGENTS.md
  - Files: `AGENTS.md:6`
- [x] **3.5 P2** Expand `docs/architecture.md` with data flow diagram, design decisions, API surface
  - Files: `docs/architecture.md` (rewritten, 5x original length)
- [x] **3.6 P3** Fix misleading `--user` comment in README → `editable install`
  - Files: `README.md:81`

## Lane 6: Opencode Agent Workflow Gaps

- [x] **6.3/6.4 P2** Add `format`, `format-check`, `typecheck`, `check` targets to Makefile
  - Files: `Makefile`
- [x] **6.5 P3** AGENTS.md validation commands self-contained
  - Combined with 3.4 above
- [x] **6.1/6.2 P1** Populate `opencode.jsonc` with agent/tool registrations
  - Files: `opencode.jsonc`
  - 2 agents registered: `repository-docs`, `repo-auditor`
  - 11 skills registered from `.opencode/skills/`

## Lane 1: TUI Polish & Narrow-Width Usability

- [x] **1.1 P1** Footer hint truncation — tab-contextual abbreviated hints at <56 width
  - Files: `src/benchdeck/tui/app.py:27-38,272-289`
  - Added `FOOTER_HINTS_NARROW` dict with per-tab short hints
- [x] **1.2 P2** Help screen 32x10 fit verification — verified: fits with scrolling
  - No source change needed; scroll indicators handle narrow viewports
- [x] **1.4 P3** `_rating_order` guard — SKIPPED: guard is actually needed
  - Removing the early-return for `BLOCKED` would cause wrong sort order
- [x] **1.5 P3** Close prior `_stderr_handle` before overwrite in `_launch_run`
  - Files: `src/benchdeck/tui/app.py:777-782`

## Lane 4: Benchmark Integrity & Artifact Safety

- [x] **4.1 P2** Create `tests/test_manifest.py` — 29 targeted tests
  - Tests: init, record, verify, load, round-trip, concurrent reader safety
  - Files: `tests/test_manifest.py` (388 lines)
- [x] **4.2 P2** Create `tests/test_disagreement.py` — 37 targeted tests
  - Tests: single/multi-judge, agreement, variance, distributions, all rating values
  - Fixed bug: `rating_distributions` was computed but not returned
  - Files: `src/benchdeck/disagreement.py:68`, `tests/test_disagreement.py` (582 lines)
- [x] **4.3 P3** Add concurrent TUI access test (manifest integrity under thread stress)
  - Files: `tests/test_storage.py:153-186`
- [x] **4.4 P3** Test `_safe_add` curses.error suppression directly
  - 4 new tests: clip at edge, col at width edge, zero width, negative col
  - Files: `tests/test_tui_render.py:2109-2146`

## Lane 5: Test/Validation Gaps

- [x] **5.2 P2** Test `_poll_subprocess` with still-running process
  - Files: `tests/test_tui_render.py:1132-1151`
- [x] **5.7 P3** Fill 15 documented TUI test gaps — 8 new tests added
  - Covered: exact 32×10 boundary, overview/help/detail at min width, footer status,
    judgment-no-result export, segmented b64 loading
  - 7 gaps already had existing test coverage
  - Files: `tests/test_tui_render.py`, `tests/test_tui_loading.py`
- [x] **5.5 P2** Add `--cov-fail-under=80` to CI test job
  - Files: `.github/workflows/ci.yml:46`
- [x] **5.6 P3** Add `pip-audit` dependency vulnerability scan to CI
  - Files: `.github/workflows/ci.yml:47-49`

## Lane 2: Screenshot/Demo Evidence Quality

- [x] **2.1 P2** Generate width-variant screenshots (32-col + 80-col)
  - 8 new files: `*/*-w32.png` and `*/*-w80.png` pairs
  - Golden baselines updated
  - Validation: `python -m pytest tests/test_screenshots.py -q` — all pass
- [x] **2.2 P2** Re-verify screenshots match current renderer output
  - Gaps attributable to uncommitted TUI source changes (expected, intentional)
- [x] **2.3 P3** Evidence-focused screenshot captions in README
  - README now shows width-variant pairs with captions stating what each proves
  - Files: `README.md:17-41`

## Final Verification

- [x] `ruff check .` — All checks passed
- [x] `ruff format --check .` — 56 files already formatted
- [x] `python -m mypy --no-incremental src/benchdeck` — Success: no issues found
- [x] `python -m pytest -q` — 576 passed, 11 skipped

## Metrics delta

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Tests | 412 | 576 | +164 (40%) |
| Skipped | 2 | 11 | +9 (new slow/build tests) |
| Source files with tests | 15 | 17 | manifest + disagreement |
| Screenshots | 4 files | 12 files | +8 width-variant renders |
| Goldens | 4 files | 4 files (updated) | reflect current source |
| Validation gates | 3 (lint/format/mypy) | 5 (+typecheck via Makefile, +coverage threshold) |
| CI steps | 6 | 8 (+coverage threshold, +pip-audit) |
