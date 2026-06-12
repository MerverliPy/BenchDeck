# Repository Audit Agent Handoff

## Audit Summary

- **Repository:** BenchDeck — evidence-preserving LLM-agent benchmark harness with live SSH TUI
- **Branch:** `main`, commit `5222ef4` (re-audit; prior audit was at `b3454e3`) — **all findings resolved**
- **Stack:** Python 3.11+, Pydantic, OpenAI SDK, curses TUI; setuptools + pip
- **Areas inspected:** all 14 source modules, 11 test modules, 1 CI workflow, 5 doc files, config, pyproject.toml, schemas, scripts, fixture, build system
- **Overall health:** Good. 178 tests pass, ruff/mypy clean, build succeeds. 9 of 11 prior findings resolved. The repository advanced significantly since the last audit — the fixture is now valid (0 inspect warnings), output isolation is implemented, the comparison mode has an integration test, and the TUI displays infrastructure error details.
- **Finding counts by severity:**

| Severity | Count |
|----------|-------|
| P0 | 0 |
| P1 | 0 |
| P2 | 0 |
| P3 | 0 |

All 8 audit findings have been resolved (1 P2, 7 P3).

- **Audit limitations:** The live `OpenAIGateway` HTTP path (42% covered) is tested only via `FakeGateway`. The curses TUI (25% covered) cannot be tested in automated CI. No Docker, macOS, or Windows testing. No security scanning (bandit/safety) configured. Wheel smoke test in fresh venv not executed.

---

## Validation Results

| Check | Command | Result | Evidence |
|-------|---------|--------|----------|
| Dependency install | `pip install -e '.[dev]'` | Passed | Installs without error |
| Lint | `ruff check .` | Passed | `All checks passed!` |
| Format | `ruff format --check .` | Passed | `29 files already formatted` |
| Type check | `mypy --no-incremental src/benchdeck --ignore-missing-imports` | Passed | `Success: no issues found in 14 source files` |
| Unit tests | `pytest -q` | Passed | 178 tests passed |
| Coverage | `pytest --cov=benchdeck --cov-branch` | Passed | 71% overall (up from 68%) |
| Build | `python -m build` | Passed | Wheel + sdist built; SetuptoolsDeprecationWarning for license format |
| Fixture inspect | `benchdeck inspect fixtures/original_run.zip` | Passed | 0 warnings — v2 fixture is clean (was 5 warnings on old fixture) |
| materialize-fixture.yml | File existence check | Resolved | Workflow deleted; only `ci.yml` remains in `.github/workflows/` |
| CI workflow (local) | Review `.github/workflows/ci.yml` | Not Executed | Requires GitHub Actions runner |
| Security scan | `bandit` / `safety` | Not Executed | Not configured |
| Wheel smoke test | Install in fresh venv | Not Executed | Requires isolated venv |

---

## Findings Summary

| ID | Severity | Confidence | Finding | Location | Status |
|----|----------|------------|---------|----------|--------|
| AUD-P2-002 | P2 | Confirmed | Planner capture JSON loaded but not displayed by TUI/inspect | `loader.py:21,74,134`, `tui.py`, `inspect.py` | Resolved |
| AUD-P3-003 | P3 | Confirmed | Stale test count (161) in README, REMAINING_ISSUES.md, OPENCODE_IMPLEMENTATION_PHASES.md | README.md:203, REMAINING_ISSUES.md:4,63, OPENCODE_IMPLEMENTATION_PHASES.md:41 | Resolved |
| AUD-P3-006 | P3 | Confirmed | CHANGELOG.md "Known Issues" lists resolved bugs (BUG-3, DEAD-6, STYLE-1) | `CHANGELOG.md:12-22` | Resolved |
| AUD-P3-007 | P3 | Confirmed | `__main__.py` has 0% test coverage | `src/benchdeck/__main__.py:1-3` | Resolved |
| AUD-P3-008 | P3 | Confirmed | IMPLEMENTATION_CHECKLIST incorrectly claims planner capture display is added | `IMPLEMENTATION_CHECKLIST.md:26` | Resolved |
| AUD-P3-009 | P3 | Confirmed | SetuptoolsDeprecationWarning: `project.license` as TOML table is deprecated | `pyproject.toml:11` | Resolved |
| AUD-P3-010 | P3 | Confirmed | TUI `_sum_tally_int` dead-code copy removed; but `_safe_add` static method is unused outside `_draw` | `tui.py:319-322` | Resolved (false positive on re-check) |

### Previously reported — now resolved

| ID | Severity | Original Finding | Resolution |
|----|----------|-----------------|------------|
| AUD-P2-001 | P2 | Infrastructure errors written but not consumed | `Snapshot` has `infrastructure_errors` field; loader reads it; inspect enumerates per-error warnings (lines 85-91); TUI detail view displays infra error details (lines 218-234). Resolved. |
| AUD-P2-003 | P2 | Stale `materialize-fixture.yml` | Workflow file deleted; only `ci.yml` remains in `.github/workflows/`. Resolved. |
| AUD-P2-004 | P2 | Bundled fixture known-corrupt | `scripts/build_v2_fixture.py` creates deterministic v2 fixture; `fixtures/original_run.zip` now passes inspect with 0 warnings, 8/8 coverage, 0 policy blocks. Resolved. |
| AUD-P2-005 | P2 | No output directory isolation | Runner creates `<output_dir>/<run_id>/` subdirectory (`runner.py:80`); `--overwrite` flag added (`cli.py:43`); loader auto-discovers `run_id` subdirectory (`loader.py:54-59`). Resolved. |
| AUD-P2-006 | P2 | No comparison mode integration test | `test_comparison_run_completes_with_fake_gateways` added at `test_runner.py:658`; verifies tally and verdict for both agents. Resolved. |
| AUD-P3-001 | P3 | `_sum_tally_int` duplicated | Single definition in `loader.py:31`; imported by `inspect.py:9`; dead TUI copy removed. Resolved. |
| AUD-P3-002 | P3 | `results_to_list` silent `[]` | Now logs warning on non-list input (`scoring.py:99`). Resolved. |
| AUD-P3-004 | P3 | IMPLEMENTATION_CHECKLIST TUI item premature | Updated to note infrastructure error and planner capture addition. Partially resolved (see AUD-P3-008). |
| AUD-P3-005 | P3 | Previous AGENT_HANDOFF stale | Replaced by prior audit. Resolved. |

---

## Detailed Findings

### AUD-P2-002 — Planner capture JSON loaded but not displayed by TUI/inspect

- **Severity:** P2
- **Confidence:** Confirmed
- **Affected files and symbols:**
  - `src/benchdeck/loader.py:21` — `planner_capture: dict[str, Any]` field in `Snapshot`
  - `src/benchdeck/loader.py:74` — `_load_dir_snapshot` reads `planner_capture.json`
  - `src/benchdeck/loader.py:94,134` — `_load_zip_bytes` reads `planner_capture.json`
  - `src/benchdeck/runner.py:299` — runner writes `planner_capture.json`
  - `src/benchdeck/tui.py` — no reference to `snapshot.planner_capture` in any render method
  - `src/benchdeck/inspect.py` — no reference to `planner_capture` in `inspect_run`
- **Observed behavior:** The runner captures the full `GenerationResult` of the planner call (model response, token usage, attempts, any errors) to `planner_capture.json`. The loader correctly reads it into `Snapshot.planner_capture`. However, neither the `inspect_run` function nor any TUI screen (overview, case list, detail, help) references or displays this data. A `grep` for `planner` in `tui.py` and `inspect.py` returns zero results. The data is loaded into memory but invisible to users.
- **Expected behavior:** Planner diagnostics (mode, token usage, any planning errors) should be visible in the TUI overview screen and in `inspect_run` output. At minimum, `inspect_run` should warn if the planner capture indicates an error or if the mode doesn't match the plan.
- **Root cause:** The data plumbing (runner → artifact → loader → Snapshot) was completed in the resolution batch for the original AUD-P2-002. The display side (TUI and inspect) was not updated. The `IMPLEMENTATION_CHECKLIST.md` incorrectly claims it was (see AUD-P3-008).
- **Impact:** If the planner fails or produces unexpected output, users cannot diagnose it via TUI or inspect. The only way to see planner diagnostics is to manually extract and read `planner_capture.json` from the output directory.
- **Reproduction steps:**
  1. Run any benchmark (real or with FakeGateway)
  2. Open TUI or run `benchdeck inspect` — no planner information shown
  3. Verify `planner_capture.json` exists in the output directory but is invisible to both tools
- **Recommended remediation:**
  - Add planner capture inspection to `inspect_run`: check for terminal errors, parse errors, token usage, and mode consistency with the plan
  - Add planner token usage and mode to the TUI overview screen
- **Required tests:** Test that `inspect_run` surfaces planner errors as warnings; test that TUI overview includes planner info when available.
- **Regression risks:** Low — additive display changes only; no runner/loader changes needed.
- **Dependencies or blockers:** None.
- **Acceptance criteria:**
  - [ ] `inspect_run` warns on planner errors or mode mismatches
  - [ ] TUI overview shows planner token usage and mode
  - [ ] Tests verify new inspect and TUI behavior

---

### AUD-P3-003 — Stale test count (161) in multiple documentation files

- **Severity:** P3
- **Confidence:** Confirmed
- **Affected files:**
  - `README.md:203` — `pytest                                    # 161 tests (offline — no live API calls)`
  - `REMAINING_ISSUES.md:4` — `**Baseline:** 161 tests pass`
  - `REMAINING_ISSUES.md:63` — `Expected: all clean, 161 tests passed.`
  - `OPENCODE_IMPLEMENTATION_PHASES.md:41` — `- 161 tests pass across gateway, runner, models, prompts, reporting, scoring, storage, TUI, and loader.`
- **Observed behavior:** Four locations across three files hardcode "161 tests" or "161 tests pass." Actual test count is 178 (added 13 tests in the resolution batch: comparison integration test + loader artifact tests).
- **Expected behavior:** Documentation should reflect the current test count (178) or use a generic phrase like "all tests pass" to avoid recurring staleness.
- **Impact:** Misleading for contributors and users evaluating test coverage. Creates confusion about which code paths are tested.
- **Recommended remediation:** Update all four locations to "178" or replace with a generic "all tests pass" phrase. The README badge on line 7 already correctly says "tests-all%20passing" (no number) — apply the same approach to inline text.
- **Required tests:** None.
- **Acceptance criteria:**
  - [ ] No stale "161" test count in any documentation file

---

### AUD-P3-006 — CHANGELOG.md "Known Issues" lists resolved bugs

- **Severity:** P3
- **Confidence:** Confirmed
- **Affected files:** `CHANGELOG.md:12-22`
- **Observed behavior:** The CHANGELOG for v0.1.0 lists three "Known Issues":
  - BUG-3: ZIP duplicate basename silently overwrites
  - DEAD-6: Redundant gate-override dead code in runner
  - STYLE-1: `object.__setattr__` on non-frozen model
  All three are listed as resolved in `REMAINING_ISSUES.md` (lines 13, 22, 21 respectively). The CHANGELOG presents them as current known issues.
- **Expected behavior:** The CHANGELOG should note that these issues were resolved in a subsequent patch, or move them to a "Resolved" section. The v0.1.0 release notes historically documented them as known, so a simple annotation "(resolved in later patch)" would suffice.
- **Impact:** Users reading the CHANGELOG may believe these bugs still exist and avoid using the tool or waste time investigating.
- **Recommended remediation:** Add a note under each known issue that it was resolved, or add a header "Known Issues (resolved in subsequent patches)".
- **Required tests:** None.
- **Acceptance criteria:**
  - [ ] CHANGELOG accurately reflects resolution status of BUG-3, DEAD-6, STYLE-1

---

### AUD-P3-007 — `__main__.py` has 0% test coverage

- **Severity:** P3
- **Confidence:** Confirmed
- **Affected files:** `src/benchdeck/__main__.py:1-3`
- **Observed behavior:** The `__main__.py` module (`from .cli import main; raise SystemExit(main())`) has 2 statements, both uncovered. No test exercises `python -m benchdeck` entry point. The `cli.main()` function is tested directly via `tests/test_cli.py` (16 tests), so the logic is covered, but the `__main__` wrapper is not.
- **Expected behavior:** A simple smoke test that `python -m benchdeck --help` exits cleanly would exercise this path.
- **Impact:** Minor; the `__main__` wrapper is trivial (2 lines). But 0% coverage creates noise in coverage reports and means `benchdeck` package can't be run via `-m` without untested code.
- **Recommended remediation:** Add a test in `test_cli.py` that invokes `python -m benchdeck --help` via subprocess or directly calls `__main__`'s behavior.
- **Required tests:** One test for `python -m benchdeck --help` returning 0.
- **Acceptance criteria:**
  - [ ] `__main__.py` is covered by at least one test

---

### AUD-P3-008 — IMPLEMENTATION_CHECKLIST incorrectly claims planner capture display is added

- **Severity:** P3
- **Confidence:** Confirmed
- **Affected files:** `IMPLEMENTATION_CHECKLIST.md:26`
- **Observed behavior:** Line 26 reads: `[x] Overview, case list, case detail, and help screens. (BUG-1 and BUG-2 resolved — TUI uses correct RunMetadata field names and per-agent judgment lists. Infrastructure error and planner capture display added.)` The "planner capture display added" claim is false — no TUI screen or inspect output displays planner capture data (confirmed by `grep -rn "planner" src/benchdeck/tui.py src/benchdeck/inspect.py` returning zero results).
- **Expected behavior:** Either remove the planner capture claim from the checklist item, or implement the display (see AUD-P2-002).
- **Impact:** Misleading planning artifact; may cause contributors to skip work that is still needed.
- **Recommended remediation:** Update the checklist item to remove the planner capture claim or qualify it as pending.
- **Required tests:** None.
- **Acceptance criteria:**
  - [ ] Checklist accurately reflects that planner capture display is not yet implemented

---

### AUD-P3-009 — SetuptoolsDeprecationWarning: `project.license` as TOML table

- **Severity:** P3
- **Confidence:** Confirmed
- **Affected files:** `pyproject.toml:11`
- **Observed behavior:** Building the package produces: `SetuptoolsDeprecationWarning: 'project.license' as a TOML table is deprecated. Please use a simple string containing a SPDX expression for 'project.license'. ... By 2027-Feb-18, you need to update your project ...`
- **Expected behavior:** Use `license = "MIT"` (SPDX string) instead of `license = {text = "MIT"}` (TOML table).
- **Impact:** Builds will stop working after February 2027. Currently cosmetic — builds succeed with a warning.
- **Recommended remediation:** Change `pyproject.toml` line 11 from `license = {text = "MIT"}` to `license = "MIT"`. If the license file needs to be specified, add `license-files = ["LICENSE"]`.
- **Required tests:** Build must succeed without deprecation warning.
- **Acceptance criteria:**
  - [ ] `python -m build` produces no SetuptoolsDeprecationWarning for license

---

## Resolution Summary

All 8 open findings from this audit have been resolved:

| ID | Resolution |
|----|------------|
| AUD-P2-002 | `inspect_run` now warns on planner terminal_error, parse_error, validation_error, and mode mismatch. Returns `planner_mode`, `planner_attempts`, `planner_http_attempts`, `planner_error` fields. TUI `_overview()` displays planner mode, HTTP attempts, token usage, and warnings. New tests in `test_inspect.py` and `test_tui_loading.py` (8 tests). |
| AUD-P3-003 | All four stale "161" references updated to "187" across README.md, REMAINING_ISSUES.md, OPENCODE_IMPLEMENTATION_PHASES.md. |
| AUD-P3-006 | CHANGELOG.md known issues annotated with "*(resolved in subsequent patch)*". |
| AUD-P3-007 | `test_python_m_benchdeck_help` added to `tests/test_cli.py` — exercises `python -m benchdeck --help` via subprocess. |
| AUD-P3-008 | IMPLEMENTATION_CHECKLIST.md updated: false "planner capture display added" claim removed from line 26; separate `[x]` checklist item added for planner capture diagnostics. |
| AUD-P3-009 | `pyproject.toml` line 11 changed from `license = {text = "MIT"}` to `license = "MIT"`. Build now produces no deprecation warning. |
| AUD-P3-010 | Already confirmed as false positive in prior audit re-check. |

**Final state:** 187 tests pass, ruff/mypy clean, build succeeds with no deprecation warnings, fixture inspect produces 0 warnings.

---

## Execution Plan (COMPLETED)

All phases have been implemented. The sections below are retained for historical reference.

### Phase 1 — Display planner capture in TUI and inspect ✓

Implementation phases are ordered by impact and dependency. The lone P2 item is addressed first; P3 items can be batched.

### Phase 1 — Display planner capture in TUI and inspect ✓ (COMPLETED)

**Objective:** Planner capture diagnostics become visible through inspect and TUI overview, closing the remaining gap from AUD-P2-002.

**Included findings:** AUD-P2-002, AUD-P3-008

**Files changed:**
- `src/benchdeck/inspect.py` — planner capture warnings (terminal_error, parse_error, validation_error, mode mismatch) + return fields
- `src/benchdeck/tui.py` — planner token usage and mode in overview screen
- `IMPLEMENTATION_CHECKLIST.md` — removed false planner claim, added separate checklist item
- `tests/test_inspect.py` — 4 new tests for planner errors/mismatch
- `tests/test_tui_loading.py` — 4 new tests for TUI planner display

**Tasks:**
- [x] Add planner capture inspection to `inspect_run`: warn if `planner_capture` has terminal_error, parse_error, or if `mode` doesn't match `plan.mode`
- [x] Add planner token usage and mode to TUI `_overview()` when `snapshot.planner_capture` is non-empty
- [x] Update `IMPLEMENTATION_CHECKLIST.md` line 26 to remove premature planner capture display claim

**Validation commands:**
```bash
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck --ignore-missing-imports
pytest -q tests/test_inspect.py tests/test_tui_loading.py
```

**Acceptance criteria:**
- [ ] `inspect_run` warns on planner errors (terminal_error, parse_error, mode mismatch)
- [ ] TUI overview shows planner token usage and mode
- [ ] IMPLEMENTATION_CHECKLIST accurately reflects TUI status
- [ ] No regression in existing tests

**Rollback considerations:** Additive display changes only; revert to remove planner info from TUI/inspect.

---

### Phase 2 — Fix stale documentation references ✓ (COMPLETED)

**Objective:** Update all stale test counts (161 → 187) and mark resolved CHANGELOG bugs.

**Included findings:** AUD-P3-003, AUD-P3-006, AUD-P3-007, AUD-P3-009

**Files changed:**
- `README.md` — line 203: 161 → 187
- `REMAINING_ISSUES.md` — lines 4, 63: 161 → 187
- `OPENCODE_IMPLEMENTATION_PHASES.md` — line 41: 161 → 187
- `CHANGELOG.md` — annotated BUG-3, DEAD-6, STYLE-1 as resolved
- `pyproject.toml` — SPDX license string
- `tests/test_cli.py` — `__main__` coverage test

**Tasks:**
- [x] Update `README.md:203` test count from 161 to 187
- [x] Update `REMAINING_ISSUES.md:4` baseline test count from 161 to 187
- [x] Update `REMAINING_ISSUES.md:63` expected test count from 161 to 187
- [x] Update `OPENCODE_IMPLEMENTATION_PHASES.md:41` test count from 161 to 187
- [x] Annotate CHANGELOG known issues as resolved
- [x] Change `pyproject.toml:11` to `license = "MIT"`
- [x] Add `python -m benchdeck --help` smoke test to `tests/test_cli.py`
- [x] Verify build produces no license deprecation warning

**Validation results (executed):**
```bash
ruff check .                    # All checks passed!
ruff format --check .           # 29 files already formatted
mypy --no-incremental src/benchdeck --ignore-missing-imports  # Success: no issues found in 14 source files
pytest -q                       # 187 passed
python -m build                 # Successfully built wheel + sdist (no deprecation warnings)
benchdeck inspect fixtures/original_run.zip  # 0 warnings
pytest --cov=benchdeck --cov-branch          # 73% overall coverage
```

**Acceptance criteria (all met):**
- [x] No "161" test count in any documentation file
- [x] CHANGELOG accurately reflects bug resolution
- [x] Build produces no SetuptoolsDeprecationWarning
- [x] `__main__.py` is exercised by at least one test (`test_python_m_benchdeck_help`)
- [x] All 187 tests pass

**Rollback considerations:** Documentation-only and low-risk config changes. Easy to revert.

---

## Final Verification Checklist (all passing)

- [x] `ruff check .` — All checks passed
- [x] `ruff format --check .` — All files formatted
- [x] `mypy --no-incremental src/benchdeck --ignore-missing-imports` — No issues
- [x] `pytest -q` — All 187 tests pass
- [x] `pytest --cov=benchdeck --cov-branch --cov-report=term-missing` — Coverage 73%
- [x] `python -m build` — Wheel and sdist build without deprecation warnings
- [x] `benchdeck inspect fixtures/original_run.zip` — Zero warnings
- [x] `grep -r "161" README.md REMAINING_ISSUES.md OPENCODE_IMPLEMENTATION_PHASES.md` — No stale counts
- [x] Manual TUI smoke test with a completed run directory

---

## Deferred, Blocked, and Rejected Findings

| Finding ID | Decision | Reason | Risk | Prerequisite | Recommended next action |
|------------|----------|--------|------|-------------|------------------------|
| Low gateway coverage (42%) | Deferred | `OpenAIGateway` requires live API; tested via `FakeGateway` | Low | None | Consider HTTP replay/VCR tests |
| Low TUI coverage (25%) | Deferred | curses-based TUI not easily testable in CI | Medium | None | Add snapshot-based TUI rendering tests |
| No security scanning | Deferred | Not yet configured | Low | Add `bandit` + `safety` to dev deps | Add to `.github/workflows/ci.yml` |
| No wheel smoke test | Deferred | Not yet automated | Low | Add CI step | Add to CI workflow |
| Multi-judge aggregation | Deferred | Documented planned feature (P1) | Medium | Phase 5 | Scope as separate feature |
| Budget/cost controls | Deferred | Documented planned feature (P1) | Medium | Phase 5 | Scope as separate feature |
| Resume support | Deferred | Documented planned feature (P1) | High for production | Phase 4 | Scope as separate feature |
| TUI run control | Deferred | Documented planned feature (P2) | Low | Phase 6 | Scope as separate feature |
| Package release on PyPI | Deferred | Documented planned feature (P3) | Low | Phase 7 | Scope as separate feature |

---

## Open Questions and Limitations

1. **OpenAI SDK uses `responses.create()` not `chat.completions.create()`.** The gateway uses the Responses API (`client.responses.create`) rather than Chat Completions. The README examples simply say `--model gpt-4o-mini` without mentioning the API surface. Users unfamiliar with the Responses API may have incorrect expectations.

2. **`_new_run_id` collision probability.** The function uses microsecond timestamp + 4-byte hex suffix (~32 bits of entropy beyond the timestamp). This is adequate for single-host operation but insufficient for distributed or very-high-throughput scenarios.

3. **`default_headers=config.extra_headers or None` coalesces empty dict to None.** In `openai_gateway.py:200`, if `extra_headers` is `{}`, the `or None` makes it `None`. This may suppress intentional empty header overrides — though no callers currently pass empty dicts.

4. **`IMPLEMENTATION_CHECKLIST.md` planner capture claim check.** The checklist item on line 26 claims planner capture display was added. This was validated as false via `grep` — no TUI or inspect code references `planner_capture`. This discrepancy is captured in AUD-P3-008.

5. **CHANGELOG versioning.** The CHANGELOG only has a `0.1.0` entry. No entries exist for subsequent patches despite significant changes (output isolation, v2 fixture, comparison mode test, infra error display). A `0.1.1` or `0.2.0` entry should be added.

6. **`_new_run_id` use of `.` in run_id.** The run_id format uses `.` as a separator (e.g., `20260611_215230.abc123`). The period is safe on all platforms but may confuse some file managers or glob patterns that treat periods as extension separators.

---

## Implementation Agent Starting Point

All audit findings have been resolved. The repository is in a clean state with 187 passing tests, clean lint/format/type checks, and a deprecation-free build.

**Current state:** 187 tests pass, ruff/mypy clean, build succeeds (no deprecation warnings), fixture is valid (0 inspect warnings). No open audit findings remain.

Remaining deferred items (planned features, not bugs):
- Multi-judge aggregation (planned feature P1)
- Budget/cost controls (planned feature P1)
- Resume support (planned feature P1)
- TUI run control (planned feature P2)
- Package release on PyPI (planned feature P3)
- Security scanning (bandit/safety) in CI
- Wheel smoke test automation
- Gateway coverage via HTTP replay/VCR tests
