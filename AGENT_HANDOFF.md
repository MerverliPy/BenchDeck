# Repository Audit Agent Handoff

## Audit Summary

- **Repository:** BenchDeck — evidence-preserving LLM-agent benchmark harness with live SSH TUI
- **Branch:** `main`, commit `b3454e3`
- **Stack:** Python 3.11+, Pydantic, OpenAI SDK, curses TUI; pip + setuptools
- **Areas inspected:** all 14 source modules, 11 test modules, 4 CI workflows, 5 doc files, config, schemas, scripts, fixture
- **Overall health:** Good. 165 tests pass, ruff/mypy clean, build succeeds. All 22 issues from the previous audit are resolved. The prior `AGENT_HANDOFF.md` was completely stale.
- **Finding counts by severity:**

| Severity | Count |
|----------|-------|
| P0 | 0 |
| P1 | 0 |
| P2 | 6 |
| P3 | 5 |

- **Audit limitations:** The live `OpenAIGateway` HTTP path (42% covered) is tested only via `FakeGateway`. The curses TUI (14% covered) cannot be tested in automated CI. No Docker, macOS, or Windows testing. No security scanning (bandit/safety) configured.

---

## Validation Results

| Check | Command | Result | Evidence |
|-------|---------|--------|----------|
| Dependency install | `pip install -e '.[dev]'` | Passed | Installs without error |
| Lint | `ruff check .` | Passed | `All checks passed!` |
| Format | `ruff format --check .` | Passed | `28 files already formatted` |
| Type check | `mypy --no-incremental src/benchdeck --ignore-missing-imports` | Passed | `Success: no issues found in 14 source files` |
| Unit tests | `pytest -q` | Passed | 165 tests passed |
| Coverage | `pytest --cov=benchdeck --cov-branch` | Passed | 68% overall |
| Build | `python -m build` | Passed | Wheel + sdist built successfully |
| Fixture inspect | `benchdeck inspect fixtures/original_run.zip` | Failed | 5 expected warnings (known fixture corruption) |
| CI workflow (local) | Review `.github/workflows/ci.yml` | Not Executed | Requires GitHub Actions runner |
| Materialize fixture CI | Review `.github/workflows/materialize-fixture.yml` | Blocked | References deleted `.b64.*` segments |
| Security scan | `bandit` / `safety` | Not Executed | Not configured |
| Wheel smoke test | Install in fresh venv | Not Executed | Requires isolated venv |

---

## Findings Summary

| ID | Severity | Confidence | Finding | Location | Status |
|----|----------|------------|---------|----------|--------|
| AUD-P2-001 | P2 | Confirmed | Infrastructure errors written but not consumed by loader/inspector | `runner.py:451`, `loader.py:29-48` | Open |
| AUD-P2-002 | P2 | Confirmed | Planner capture JSON written but not consumed | `runner.py:291`, `loader.py:29-48` | Open |
| AUD-P2-003 | P2 | Confirmed | Stale `materialize-fixture.yml` references deleted `.b64.*` segments | `.github/workflows/materialize-fixture.yml:7,22,25` | Open |
| AUD-P2-004 | P2 | Confirmed | Bundled fixture is known-corrupt; Phase 7 v2 replacement not done | `fixtures/original_run.zip` | Open |
| AUD-P2-005 | P2 | Confirmed | No output directory isolation — repeated runs silently overwrite | `runner.py:69`, `storage.py:23-28` | Open (known limitation) |
| AUD-P2-006 | P2 | Confirmed | No runner integration test for comparison mode | `tests/test_runner.py:290-327` | Open |
| AUD-P3-001 | P3 | Confirmed | `_sum_tally_int` duplicated in `tui.py` and `inspect.py` | `tui.py:312-317`, `inspect.py:91-96` | Open |
| AUD-P3-002 | P3 | Confirmed | `results_to_list` silently returns `[]` on type mismatch | `scoring.py:93-96` | Open |
| AUD-P3-003 | P3 | Confirmed | README hardcodes stale test count badge (161 vs actual 165) | `README.md:7` | Open |
| AUD-P3-004 | P3 | Confirmed | `IMPLEMENTATION_CHECKLIST.md` TUI item marked complete prematurely | `IMPLEMENTATION_CHECKLIST.md:23-28` | Open |
| AUD-P3-005 | P3 | Confirmed | Previous `AGENT_HANDOFF.md` was 100% stale | `AGENT_HANDOFF.md` (old) | Resolved by this audit |

---

## Detailed Findings

### AUD-P2-001 — Infrastructure errors written but not consumed by loader or inspector

- **Severity:** P2
- **Confidence:** Confirmed
- **Affected files and symbols:**
  - `src/benchdeck/runner.py:451` — `self.store.write_json("infrastructure_errors.json", infra_errors)`
  - `src/benchdeck/loader.py:29-48` — `load_snapshot` reads 6 artifact files; `infrastructure_errors.json` is not among them
  - `src/benchdeck/loader.py:13-19` — `Snapshot` dataclass has no `infrastructure_errors` field
  - `src/benchdeck/inspect.py:25-88` — `inspect_run` reads `snapshot.metadata` for infra stats but never inspects per-error records
- **Observed behavior:** The runner writes `infrastructure_errors.json` on every checkpoint containing detailed `InfrastructureError` records (agent label, case_id, stage, error details, raw response). The loader never reads this file. The TUI displays `metadata.infrastructure_failures` count but never shows which cases failed or why. The inspector never inspects this file.
- **Expected behavior:** Loader should read `infrastructure_errors.json` into a `Snapshot` field. TUI should display per-case infrastructure error details. Inspector should validate that infra error records match the metadata count and surface them in warnings.
- **Evidence:** `grep -rn "infrastructure\|infra_error" src/benchdeck/loader.py src/benchdeck/inspect.py` returns no results.
- **Root cause:** The `infrastructure_errors` artifact was added to runner checkpoints during Phase 1 bug fixes but the loader, `Snapshot` dataclass, TUI, and inspector were not updated to consume it.
- **Impact:** Users cannot see why a case had an infrastructure failure via the TUI or inspect output. The information is stored on disk but invisible.
- **Reproduction steps:**
  1. Run `benchdeck run` with any config that produces an infrastructure error (e.g. network failure)
  2. Run `benchdeck inspect <output_dir>` — no per-error details appear
  3. Open TUI — infrastructure failure count is shown but no per-case error details
- **Recommended remediation:** Add `infrastructure_errors: list[dict[str, Any]]` to `Snapshot` dataclass; update `load_snapshot` and `_load_zip_bytes` to read `infrastructure_errors.json`; update `inspect_run` to enumerate per-error warnings; update TUI `_detail()` to display error info for the selected case.
- **Required tests:** Test that `load_snapshot` reads `infrastructure_errors.json`; test that `inspect_run` reports individual infrastructure errors.
- **Regression risks:** Low — reader-side additions only; runner writes unchanged.
- **Dependencies or blockers:** None.
- **Acceptance criteria:**
  - [ ] `Snapshot` has `infrastructure_errors` field
  - [ ] `load_snapshot` reads `infrastructure_errors.json`
  - [ ] `inspect_run` enumerates infrastructure error warnings
  - [ ] TUI displays infrastructure error details in case detail view

---

### AUD-P2-002 — Planner capture JSON written but not consumed

- **Severity:** P2
- **Confidence:** Confirmed
- **Affected files and symbols:**
  - `src/benchdeck/runner.py:291` — `self.store.write_json("planner_capture.json", gen_result.model_dump(mode="json"))`
  - `src/benchdeck/loader.py:29-48` — `load_snapshot` does not read `planner_capture.json`
  - `src/benchdeck/loader.py:13-19` — `Snapshot` has no `planner_capture` field
- **Observed behavior:** The runner captures the full `GenerationResult` of the planner call (model response, token usage, attempts, any errors) to `planner_capture.json`. The loader never reads it. TUI and inspector cannot show planner diagnostics.
- **Expected behavior:** Planner capture should be available via the loader for debugging and TUI display.
- **Root cause:** `planner_capture.json` was added as an evidence-preservation measure but the reader side was not updated.
- **Impact:** Planner failures produce opaque `RuntimeError` messages without the underlying gateway evidence being visible to users.
- **Recommended remediation:** Add `planner_capture: dict[str, Any]` field to `Snapshot`; update `load_snapshot` and `_load_zip_bytes` to read `planner_capture.json`; surface planner info in `inspect_run` output and TUI overview.
- **Required tests:** Test that `load_snapshot` reads `planner_capture.json` when present.
- **Regression risks:** Low — reader-side addition.
- **Dependencies or blockers:** None.
- **Acceptance criteria:**
  - [ ] `Snapshot` has `planner_capture` field
  - [ ] `load_snapshot` reads `planner_capture.json`
  - [ ] Planner diagnostics visible in TUI/inspect output

---

### AUD-P2-003 — Stale `materialize-fixture.yml` references deleted `.b64.*` files

- **Severity:** P2
- **Confidence:** Confirmed
- **Affected files:**
  - `.github/workflows/materialize-fixture.yml:7` — trigger path `fixtures/original_run.zip.b64.*`
  - `.github/workflows/materialize-fixture.yml:22` — `cat fixtures/original_run.zip.b64.* | base64 --decode`
  - `.github/workflows/materialize-fixture.yml:25` — `rm fixtures/original_run.zip.b64.*`
- **Observed behavior:** The workflow is configured to decode Base64-segmented source files into a ZIP, verify a checksum, and commit. The source `.b64.*` files no longer exist — only `original_run.zip` is checked in directly. The workflow is dead code.
- **Expected behavior:** Either remove the workflow, or replace it with a fixture validation workflow that runs `benchdeck inspect` on the committed fixture.
- **Root cause:** The `.b64.*` segmented fixture storage was replaced by a directly committed ZIP, but the CI workflow was not updated.
- **Impact:** CI infrastructure debt. No functional impact since the trigger paths don't match any existing files.
- **Recommended remediation:** Remove the workflow file, or replace it with a fixture-integrity validation job that checks `fixtures/original_run.zip` with `benchdeck inspect`.
- **Required tests:** None.
- **Regression risks:** None.
- **Dependencies or blockers:** AUD-P2-004 (fixture must be valid before adding strict CI validation).
- **Acceptance criteria:**
  - [ ] `materialize-fixture.yml` either removed or updated to validate the existing fixture

---

### AUD-P2-004 — Bundled fixture is known-corrupt; Phase 7 v2 replacement not done

- **Severity:** P2
- **Confidence:** Confirmed
- **Affected files:** `fixtures/original_run.zip`
- **Observed behavior:** `benchdeck inspect fixtures/original_run.zip` reports 5 warnings:
  - Only 9 of 10 planned cases were judged
  - Case 9 stores candidate output as judge_transcript
  - Case 10 has an empty final output
  - Run is marked completed despite blocked/missing required coverage
  - Tally for score_scale fails JSON Schema validation (`'score_scale' is a required property`)
- **Expected behavior:** `OPENCODE_IMPLEMENTATION_PHASES.md` Phase 7 calls for replacing the fixture with a deterministic, schema-valid v2 fixture with reconciled counts and hashes.
- **Root cause:** The fixture was produced by an older version of the runner that had the now-fixed bugs. It was retained intentionally for regression testing but is not suitable as a reference artifact.
- **Impact:** Users inspecting the bundled fixture see warnings that are caused by old runner bugs, not by current defects.
- **Recommended remediation:** Create a deterministic fixture-builder script (`scripts/build_v2_fixture.py`); generate a valid v2 fixture with complete plan, execution ledger, judgments, tally, verdict, metadata, and manifest; replace `fixtures/original_run.zip`; update tests in `test_inspect.py` and `test_tui_loading.py` that depend on the current warning list.
- **Required tests:** Test that new fixture passes `benchdeck inspect` with 0 warnings; test that TUI renders it correctly.
- **Regression risks:** Low — tests that assert on fixture warnings must be updated.
- **Dependencies or blockers:** None.
- **Acceptance criteria:**
  - [ ] New v2 fixture passes `benchdeck inspect` with zero warnings
  - [ ] All dependent tests updated
  - [ ] Fixture can be built deterministically via script

---

### AUD-P2-005 — No output directory isolation; repeated runs silently overwrite

- **Severity:** P2
- **Confidence:** Confirmed
- **Affected files:**
  - `src/benchdeck/runner.py:69` — `self.store = ArtifactStore(output_dir)` writes directly to the user-specified directory
  - `src/benchdeck/storage.py:23-28` — `ArtifactStore.__init__` creates root dir but never checks for prior content
- **Observed behavior:** Running a benchmark twice to the same output directory silently overwrites prior run artifacts. The test `test_output_directory_with_prior_run_silently_produces_mixed_run` in `tests/test_runner.py:329-369` explicitly documents this current behavior — it sets up prior files, runs a new run, and verifies the old files are overwritten with new content.
- **Expected behavior:** Per `OPENCODE_IMPLEMENTATION_PHASES.md` Phase 4: generate a unique `run_id` at start; write into `<output_root>/<run_id>/`; reject an existing non-empty run directory unless `--resume` or `--overwrite` is explicit.
- **Root cause:** This is a planned feature (Phase 4) not yet implemented.
- **Impact:** Data loss if a user accidentally reuses a previous output directory path.
- **Recommended remediation:** Implement Phase 4 run isolation: write into `output_dir / run_id` subdirectory (using `RunMetadata._new_run_id()` which already exists with microsecond + hex suffix); reject if the directory exists and is non-empty without `--overwrite` CLI flag.
- **Required tests:** Test that duplicate run to same dir without `--overwrite` raises an error; test that `--overwrite` cleanly replaces stale data.
- **Regression risks:** Medium — changes output directory structure; requires `load_snapshot` to handle nested `run_id` subdirectories.
- **Dependencies or blockers:** Depends on `RunMetadata.run_id` (already implemented).
- **Acceptance criteria:**
  - [ ] Runs create output in `<output_root>/<run_id>/`
  - [ ] Non-empty existing directories rejected without `--overwrite`
  - [ ] `--overwrite` flag available on `run` subcommand
  - [ ] TUI and inspector can navigate `run_id` subdirectories

---

### AUD-P2-006 — No runner integration test for comparison mode with fake gateways

- **Severity:** P2
- **Confidence:** Confirmed
- **Affected files:** `tests/test_runner.py:290-327`
- **Observed behavior:** The test suite has a single-agent runner integration test (`test_single_agent_run_completes_with_fake_gateways`) but no corresponding two-agent (comparison mode) integration test. Comparison mode scoring, tally building, verdict construction, and markdown output are tested at the unit level in `test_reporting.py` but the full runner pipeline with `agent_b_path` and fake gateways for both agents is never exercised end-to-end.
- **Expected behavior:** A regression test exercising `BenchmarkRunner` with `agent_b_path`, two sets of agent scripts (16 calls), judge scripts (16 calls), and asserting that `final_verdict.json` contains a `comparison` block with `valid: true`.
- **Root cause:** Comparison mode was added to the runner during Phase 1 but integration test coverage did not follow.
- **Impact:** Regressions in comparison mode runner flow (e.g. incorrect agent label propagation, missing per-agent tally) could be introduced without test detection.
- **Recommended remediation:** Add an integration test in `tests/test_runner.py` that:
  1. Creates agent A and B paths in `tmp_path`
  2. Supplies fake gateways with scripts for planner (1 call), agent A (8 calls), agent B (8 calls), judge A (8 calls), judge B (8 calls)
  3. Runs `BenchmarkRunner` with both `agent_a_path` and `agent_b_path`
  4. Asserts `RunStatus.COMPLETED`
  5. Verifies `summary_tally.json` has both agent entries
  6. Verifies `final_verdict.json` has a `comparison` block with `valid: true`
- **Required tests:** `test_comparison_run_completes_with_fake_gateways` in `tests/test_runner.py`.
- **Regression risks:** None — additive test.
- **Dependencies or blockers:** None.
- **Acceptance criteria:**
  - [ ] Integration test exercises full comparison mode through runner
  - [ ] Test verifies `summary_tally.json` has both `agent_a` and `agent_b` entries
  - [ ] Test verifies `comparison` verdict is present and valid

---

### AUD-P3-001 — `_sum_tally_int` duplicated in `tui.py` and `inspect.py`

- **Severity:** P3
- **Confidence:** Confirmed
- **Affected files:**
  - `src/benchdeck/tui.py:312-317`
  - `src/benchdeck/inspect.py:91-96`
- **Observed behavior:** Identical 7-line helper function exists in two modules. Both iterate over tally dict values and sum an integer key. The TUI copy (`tui.py:312`) is also dead code — it is defined but never called within the TUI module.
- **Expected behavior:** Single canonical definition, imported by both consumers.
- **Root cause:** The `loader.py` extraction during Phase 1 moved shared loading logic but did not consolidate this helper.
- **Impact:** Maintenance burden; changes must be synchronized. The TUI copy adds unused code.
- **Recommended remediation:** Move `_sum_tally_int` to `loader.py` or `scoring.py`; import in `tui.py` and `inspect.py`; remove the dead TUI copy.
- **Required tests:** None needed (existing tests cover both).
- **Regression risks:** Low.
- **Acceptance criteria:**
  - [ ] Single definition of `_sum_tally_int` exists
  - [ ] Both `tui.py` and `inspect.py` import from canonical location

---

### AUD-P3-002 — `results_to_list` silently returns `[]` on type mismatch

- **Severity:** P3
- **Confidence:** Confirmed
- **Affected files:** `src/benchdeck/scoring.py:93-96`
- **Observed behavior:** `results_to_list` takes `obj: object`, checks `isinstance(obj, list)`, and returns `obj` if true, else `[]`. If the caller passes a non-list value (e.g. a dict from a malformed `run_results.json`), the function silently returns `[]` and downstream code processes zero results with no diagnostic.
- **Expected behavior:** Either raise `TypeError` or log a warning when a non-list is encountered so structural errors in the results artifact surface.
- **Impact:** Can mask serialization or structural bugs in `run_results.json`.
- **Recommended remediation:** Log a warning via the module logger when non-list input is received.
- **Required tests:** Add a test asserting behavior on dict/tuple/None inputs.
- **Regression risks:** Low — function is only called in `collect_terminal_keys`.
- **Acceptance criteria:**
  - [ ] `results_to_list` warns on non-list input
  - [ ] Existing tests continue to pass

---

### AUD-P3-003 — README hardcodes stale test count badge

- **Severity:** P3
- **Confidence:** Confirmed
- **Affected files:** `README.md:7`
- **Observed behavior:** The badge URL `https://img.shields.io/badge/tests-161%20passed-brightgreen.svg` claims 161 tests passed. Actual test count is 165. The badge is a static image URL with no dynamic update mechanism.
- **Expected behavior:** Update count to 165 or replace with a dynamic CI badge.
- **Impact:** Misleading for users and contributors evaluating test coverage.
- **Recommended remediation:** Update the badge to reflect 165 tests, or replace with a dynamic shield.io badge linked to the CI workflow.
- **Required tests:** None.
- **Acceptance criteria:**
  - [ ] Badge count matches actual test count or is dynamic

---

### AUD-P3-004 — `IMPLEMENTATION_CHECKLIST.md` TUI screen item marked complete prematurely

- **Severity:** P3
- **Confidence:** Confirmed
- **Affected files:** `IMPLEMENTATION_CHECKLIST.md:23-28`
- **Observed behavior:** The checklist marks the P2 TUI section item `[x] Overview, case list, case detail, and help screens. (BUG-1 and BUG-2 resolved ...)` as complete. However AUD-P2-001 (infrastructure error display) and AUD-P2-002 (planner capture display) affect these same screens. Additionally, Phase 6 of `OPENCODE_IMPLEMENTATION_PHASES.md` calls for further TUI hardening (agent filter toggle, side-by-side comparison, parse/validation error display, ZIP safety hardening).
- **Expected behavior:** The item should remain `[ ]` or be qualified with remaining work items.
- **Impact:** Misleading planning artifact; creates false impression of completion.
- **Recommended remediation:** Update the checklist item to note remaining TUI work items.
- **Required tests:** None.
- **Acceptance criteria:**
  - [ ] Checklist accurately reflects current TUI status

---

### AUD-P3-005 — Previous AGENT_HANDOFF.md was completely stale

- **Severity:** P3
- **Confidence:** Confirmed
- **Affected files:** `AGENT_HANDOFF.md` (old version, now replaced)
- **Observed behavior:** The previous AGENT_HANDOFF.md listed 22 tasks (BUG-1 through DOCS-4) across bugs, dead code, design issues, style cleanup, and documentation. All 22 have been resolved in the current codebase. The file served as a misleading inventory of non-existent defects.
- **Resolution:** This document replaces the stale AGENT_HANDOFF.md.
- **Acceptance criteria:**
  - [x] Old stale AGENT_HANDOFF.md replaced with this current audit

---

## Execution Plan

Implementation phases are ordered by impact and dependency. P2 findings are addressed first; P3 findings can be batched independently.

### Phase 1 — Consume infrastructure errors and planner capture in loader/TUI/inspector

**Objective:** Infrastructure error details and planner capture evidence become visible through the loader, TUI, and inspector.

**Included findings:** AUD-P2-001, AUD-P2-002

**Files expected to change:**
- `src/benchdeck/loader.py` — add fields to `Snapshot`, update `load_snapshot` and `_load_zip_bytes`
- `src/benchdeck/inspect.py` — enumerate per-infrastructure-error warnings
- `src/benchdeck/tui.py` — display infrastructure error details in case detail view

**Tasks:**
- [ ] Add `infrastructure_errors: list[dict[str, Any]]` and `planner_capture: dict[str, Any]` fields to `Snapshot` dataclass in `loader.py`
- [ ] Update `load_snapshot` directory reader to load `infrastructure_errors.json` and `planner_capture.json`
- [ ] Update `_load_zip_bytes` defaults dict to include the two new artifact keys
- [ ] Update `_load_zip_bytes` loaded results to populate new Snapshot fields
- [ ] Update `inspect_run` to enumerate infrastructure error records as warnings
- [ ] Update TUI `_detail()` to show infrastructure error details for the selected case
- [ ] Add tests for loader reading new artifacts
- [ ] Add test for inspect reporting infrastructure errors

**Validation commands:**
```bash
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck --ignore-missing-imports
pytest -q tests/test_tui_loading.py tests/test_inspect.py
```

**Acceptance criteria:**
- [ ] `Snapshot` exposes `infrastructure_errors` and `planner_capture`
- [ ] `inspect_run` warns on individual infrastructure errors
- [ ] TUI detail view shows infrastructure error information
- [ ] No regression in existing tests

**Rollback considerations:** Revert the Snapshot field additions and reader changes. The runner writes the artifacts unchanged — only the reader side is modified.

---

### Phase 2 — Add comparison mode runner integration test

**Objective:** Full runner pipeline in comparison mode is covered by an integration test using fake gateways.

**Included findings:** AUD-P2-006

**Files expected to change:**
- `tests/test_runner.py` — add integration test

**Tasks:**
- [ ] Add `test_comparison_run_completes_with_fake_gateways` test in `tests/test_runner.py`
- [ ] Create two agent files in `tmp_path`
- [ ] Provide planner fake (1 call), agent A fake (8 text responses), agent B fake (8 text responses), judge A fake (8 judgment JSON responses), judge B fake (8 judgment JSON responses)
- [ ] Assert `RunStatus.COMPLETED`
- [ ] Verify `summary_tally.json` has both `agent_a` and `agent_b` entries
- [ ] Verify `final_verdict.json` has a `comparison` block with `valid: true`

**Validation commands:**
```bash
pytest -q tests/test_runner.py -k comparison
```

**Acceptance criteria:**
- [ ] Comparison mode runner flow tested end-to-end
- [ ] Artifacts correctly attributed to both agents

**Rollback considerations:** Additive test only; no production code modified.

---

### Phase 3 — Clean up CI workflow, replace fixture, implement output directory isolation

**Objective:** Remove dead CI workflow, replace corrupted fixture with deterministic v2 fixture, implement output directory isolation.

**Included findings:** AUD-P2-003, AUD-P2-004, AUD-P2-005

**Files expected to change:**
- `.github/workflows/materialize-fixture.yml` — removed or replaced with fixture validation
- `fixtures/original_run.zip` — replaced with v2 fixture
- `scripts/build_v2_fixture.py` — new fixture builder script
- `src/benchdeck/runner.py` — subdirectory isolation logic
- `src/benchdeck/cli.py` — add `--overwrite` flag
- `src/benchdeck/loader.py` — handle `run_id` subdirectories
- `tests/test_inspect.py` — update for new fixture
- `tests/test_tui_loading.py` — update for new fixture
- `tests/test_runner.py` — add isolation/overwrite tests

**Tasks:**
- [ ] Remove or replace `materialize-fixture.yml` with fixture validation workflow
- [ ] Create `scripts/build_v2_fixture.py` that generates a valid, deterministic v2 fixture
- [ ] Replace `fixtures/original_run.zip` with newly built v2 fixture
- [ ] Update `test_bundled_fixture_loads` and `test_original_run_defects_are_detected` to match new fixture
- [ ] Implement `--overwrite` CLI flag on `run` subcommand
- [ ] Modify `BenchmarkRunner` to write into `<output_dir>/<run_id>/`
- [ ] Add pre-run check rejecting non-empty existing output dirs without `--overwrite`
- [ ] Update `load_snapshot` to handle auto-discovery of `run_id` subdirectory
- [ ] Add tests for isolation and overwrite behavior

**Validation commands:**
```bash
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck --ignore-missing-imports
pytest -q
python scripts/build_v2_fixture.py
benchdeck inspect fixtures/original_run.zip
```

**Acceptance criteria:**
- [ ] New fixture passes `benchdeck inspect` with zero warnings
- [ ] `materialize-fixture.yml` is removed or updated
- [ ] Repeated runs to same dir without `--overwrite` raises error
- [ ] `--overwrite` cleanly replaces previous run data
- [ ] `load_snapshot` handles `run_id` subdirectories
- [ ] TUI can load a run from a `run_id` subdirectory

**Rollback considerations:** This changes output directory structure. Roll back by reverting the subdirectory change in runner and reverting loader changes. Users with existing output directories would need to move files manually.

---

### Phase 4 — Minor quality fixes (duplication, type safety, documentation)

**Objective:** Resolve duplication issues, improve type safety, update stale documentation.

**Included findings:** AUD-P3-001, AUD-P3-002, AUD-P3-003, AUD-P3-004

**Files expected to change:**
- `src/benchdeck/scoring.py` — consolidate `_sum_tally_int`, improve `results_to_list`
- `src/benchdeck/tui.py` — import consolidated helper, remove local dead copy
- `src/benchdeck/inspect.py` — import consolidated helper
- `README.md` — update test count badge
- `IMPLEMENTATION_CHECKLIST.md` — update TUI item status

**Tasks:**
- [ ] Move `_sum_tally_int` to `loader.py` or `scoring.py` and import at both call sites
- [ ] Remove the dead local copy of `_sum_tally_int` from `tui.py`
- [ ] Add warning log to `results_to_list` when non-list input is received
- [ ] Update README test count badge (165 or dynamic)
- [ ] Update `IMPLEMENTATION_CHECKLIST.md` TUI item to note remaining work

**Validation commands:**
```bash
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck --ignore-missing-imports
pytest -q
```

**Acceptance criteria:**
- [ ] Single canonical definition of `_sum_tally_int`
- [ ] `results_to_list` warns on bad input
- [ ] README badge is accurate
- [ ] Checklist reflects current state

**Rollback considerations:** All changes are cosmetic or additive — low risk to revert.

---

## Final Verification Checklist

- [ ] `ruff check .` — All checks passed
- [ ] `ruff format --check .` — All files formatted
- [ ] `mypy --no-incremental src/benchdeck --ignore-missing-imports` — No issues
- [ ] `pytest -q` — All tests pass (expected >= 165)
- [ ] `pytest --cov=benchdeck --cov-branch --cov-report=term-missing` — Coverage >= 68%
- [ ] `python -m build` — Wheel and sdist build successfully
- [ ] `benchdeck inspect fixtures/original_run.zip` — Zero warnings on new v2 fixture
- [ ] Manual TUI smoke test with a completed run directory

---

## Deferred, Blocked, and Rejected Findings

| Finding ID | Decision | Reason | Risk | Prerequisite | Recommended next action |
|------------|----------|--------|------|-------------|------------------------|
| Low gateway coverage (42%) | Deferred | `OpenAIGateway` requires live API; tested via `FakeGateway` | Low | None | Consider HTTP replay/VCR tests |
| Low TUI coverage (14%) | Deferred | curses-based TUI not easily testable in CI | Medium | None | Add snapshot-based TUI rendering tests |
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

4. **`_sum_tally_int` in `tui.py` is defined but never called.** The TUI copy at `tui.py:312` has zero call-sites within the module. It is dead code.
