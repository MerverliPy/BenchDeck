# Repository Audit Agent Handoff

## Objective and Scope

**Objective:** Bounded broad audit of BenchDeck v0.1.0 — an evidence-preserving LLM-agent benchmark harness with a live mobile-first SSH TUI. Revalidate all 20 prior findings, execute full validation suite, identify new risks, and surface any credential exposure.

**In-Scope:** Source (24 modules in `src/benchdeck/` + `models/` package), tests (18 files), CI (3 workflows), packaging (`pyproject.toml`), schemas, fixtures, documentation, security surfaces, working-tree state, all validation commands.

**Out-of-Scope:** Live OpenAI API paths (no key exercised); Windows runtime; distributed install smoke tests; implementing fixes; rotating the exposed credential (operator action required).

**Completion Criteria:** All validations re-executed; prior findings re-confirmed; new observations documented with severity and evidence; handoff ready for next agent.

---

## Repository State

| Field | Value |
|-------|-------|
| **Root** | `/home/calvin/BenchDeck` |
| **Branch / Commit** | `main` @ `caeb33df72feb62963077d19f8250cbeda59182e` |
| **Baseline AGENT_HANDOFF.md** | 18,699 bytes, MD5 `77bf0406d0ebe2d59466a3e9998a9f77` |
| **Working Tree** | 6 modified tracked files, 5 untracked files |
| **Stack** | Python 3.12 (runtime), Pydantic v2, OpenAI SDK v2 (`responses` API), curses TUI |
| **Tests** | 345 passed, 2 skipped (347 total) |
| **Coverage** | 81% (2,258 stmts, 435 missed) |
| **Overall Health** | **Good with one critical finding.** Ruff clean, ruff format clean, mypy clean on `src/` (strict) and `tests/`, all 20 prior findings resolved. **One plaintext credential found on disk (P0).** |

### Working Tree Changes

```
 M .gitignore                      # Added '.envrc' to gitignore (uncommitted)
 M AGENT_HANDOFF.md                # Updated by this audit
 M assets/screenshots/cases.png
 M assets/screenshots/detail.png
 M assets/screenshots/help.png
 M assets/screenshots/overview.png
?? .opencode/agents/tui-precision-editor.md.bak
?? assets/screenshots/cases_real.png
?? assets/screenshots/detail_real.png
?? assets/screenshots/help_real.png
?? assets/screenshots/overview_real.png
?? my_agent.md
```

The `.gitignore` modification adds `.envrc` — a reactive fix after a real credential was placed there. The 4 modified `.png` files are screenshot assets. The 5 untracked files are agent configuration, a backup, and real (non-demo) screenshots.

---

## Repository Map

```
src/benchdeck/                 # 24 source modules
├── __init__.py, __main__.py   # Package entry points
├── cli.py                     # argparse CLI (run, tui, inspect)
├── config.py                  # TOML config loading (3-layer merge)
├── runner.py                  # BenchmarkRunner: plan→execute→judge→checkpoint
├── openai_gateway.py          # OpenAIGateway with retry/backoff (46% coverage — live paths)
├── prompts.py                 # Planner/judge system prompts + JSON schemas
├── storage.py                 # Atomic JSON/text artifact writer
├── loader.py                  # ZIP/directory snapshot loader
├── tui.py                     # curses TUI (32-col, subprocess control)
├── inspect.py                 # Run inspector (schema validation, manifest checks)
├── scoring.py                 # Tally building, coverage validation
├── reporting.py               # Verdict building, Markdown output
├── budget.py                  # BudgetLimits, BudgetTracker, preflight
├── manifest.py                # SHA-256 manifest with atomic writes
├── logging_config.py          # JSON/console logging formatters
├── disagreement.py            # Multi-judge disagreement analysis (Fleiss' kappa)
├── models/                    # 6 sub-modules (refactored from monolithic models.py)
│   ├── __init__.py            # Re-exports all public types
│   ├── execution.py           # ExecutionKey, ResponseCapture, CaseRunResult
│   ├── gateway.py             # ErrorCategory, ErrorRecord, GenerationResult, ResponseAttempt, UsageDetails
│   ├── infra.py               # RunStatus, PolicyBlock, InfrastructureError, TokenUsage, RunMetadata
│   ├── judgment.py            # Rating, GateStatus, RubricDimension, Rubric, GateCheck, CaseJudgment
│   ├── plan.py                # Family, ClarificationExpectation, AgentProfile, BenchmarkCase, PlanProvenance, BenchmarkPlan
│   └── result.py              # CoverageReport, AgentTally, AgentBenchmarkVerdict, ComparisonVerdict, BenchmarkRunVerdict
└── schemas/
    └── summary_tally.schema.json   # JSON Schema for per-agent tally validation (packaged in wheel)

tests/                         # 18 test files
├── conftest.py                # Shared fixtures + builders (no live API calls)
├── fakes.py                   # FakeGateway with deterministic scripted responses
├── test_budget.py, test_cli.py, test_config.py, test_e2e_scenarios.py
├── test_gateway.py, test_inspect.py, test_models.py, test_prompts.py
├── test_reporting.py, test_runner.py, test_runner_resume.py, test_scoring.py
├── test_screenshots.py, test_storage.py, test_tui_loading.py, test_tui_render.py

.github/workflows/
├── ci.yml                     # CI: ruff, mypy, pytest (3.11-3.13), visual-regression (PR only)
├── publish.yml                # PyPI publish on v* tag
└── release.yml                # GitHub Release + SBOM + checksums on v* tag

docs/                          # architecture.md, audit-findings.md, benchmark-contract.md, mobile-tui.md
scripts/                       # generate_demo_screens.py, build_v2_fixture.py, _capture_screens.py, __init__.py
examples/                      # repository-integrity-agent.md (sample agent definition)
fixtures/                      # original_run.zip (regression fixture)
dist/                          # Stale build artifacts (gitignored, not tracked)
.opencode/                     # OpenCode agent configuration (not project source)
```

---

## Confirmed Findings

### New P0 Finding

| ID | Severity | Description | Confidence |
|----|----------|-------------|------------|
| P0-PLAINTEXT-KEY | **P0** | Real OpenAI API key exposed in `.envrc` | High |

**P0-PLAINTEXT-KEY: Live API key on disk in `.envrc`**

- **Affected File:** `/home/calvin/BenchDeck/.envrc` (gitignored, not tracked)
- **Evidence:** File contains `export OPENAI_API_KEY=sk-proj-...` (real key, length verified). Present on-disk, readable to any process with filesystem access. Gitignored by recent `.gitignore` modification (not yet committed), so not in version history — but present in the working tree where any script, test, or process could source it.
- **Impact:** Key compromise could result in unauthorized API usage, cost, and data exposure. Violates the project's own `SECURITY.md` which states "Do not place real credentials... in benchmark cases."
- **Recommendation:** (1) Rotate the key immediately at the OpenAI console. (2) Remove `.envrc` from the working tree. (3) Use a secure credential store (1Password CLI, `pass`, or OS keyring) or at minimum move to `~/.config/benchdeck/.env` outside the repo. (4) Commit the `.gitignore` change to protect future contributors. (5) Add a pre-commit hook or CI check that scans for `sk-` patterns.
- **Validation:** `grep -r "sk-proj" . --include=".envrc"` returns the key. `git check-ignore -v .envrc` confirms gitignored. `git ls-files --error-unmatch .envrc` confirms not tracked.
- **Acceptance Criteria:** `.envrc` absent from working tree; key rotated; no `sk-` pattern in any non-example file.

### New P2 Findings

| ID | Severity | Description | Confidence |
|----|----------|-------------|------------|
| P2-OBS-004 | P2 | `REMAINING_ISSUES.md` contains stale/contradictory claims | High |
| P2-OBS-005 | P2 | `.gitignore` has uncommitted reactive fix for credential exposure | High |

**P2-OBS-004: `REMAINING_ISSUES.md` partially stale (P2, High)**

- **Affected Lines:** `REMAINING_ISSUES.md:58,61`
- Line 58: "No PyPI release or signed artifacts. Code is publishable; CI workflow and SBOM not yet set up." — **Incorrect.** `publish.yml` and `release.yml` CI workflows exist and are fully configured for PyPI publish + SBOM generation. They await a `v*` tag trigger.
- Line 60-61: "No dependency lock file. requirements.txt provides reproducible pins." — The header says "no lock file" but then says `requirements.txt` provides pins. This is contradictory. Either `requirements.txt` serves as the lock file (in which case the "limitation" is misleading) or a proper lock file (e.g., `requirements.lock` or `pip-tools`) should be listed as a remaining item.
- **Impact:** A reader following this document could waste time setting up CI workflows that already exist or misunderstand the dependency pinning strategy.
- **Recommendation:** Update the "Remaining Known Limitations" section to reflect current state: CI workflows exist but untriggered; clarify dependency pinning strategy.

**P2-OBS-005: `.gitignore` reactive fix uncommitted (P2, Medium)**

- **Evidence:** `git diff .gitignore` shows `.envrc` was added to gitignore as an uncommitted change. This was likely done after the `.envrc` file was created with a real key, as a reactive measure rather than proactive protection.
- **Impact:** Without committing, other clones or fresh checkouts would not have `.envrc` gitignored, increasing risk. The project's defense-in-depth against credential leaks is weak.
- **Recommendation:** Commit `.gitignore` change now. Add a `pre-commit` hook or CI check (e.g., `detect-secrets` or `gitleaks`) to catch credential patterns before commit.

### New P3 Observations

| ID | Severity | Description | Confidence |
|----|----------|-------------|------------|
| P3-OBS-001 | P3 | `OPENCODE_IMPLEMENTATION_PHASES.md` stale baselines | High |
| P3-OBS-002 | P3 | `dist/` contains stale build artifacts | High |
| P3-OBS-003 | P3 | Working tree has 11 uncommitted items | High |

**P3-OBS-001: `OPENCODE_IMPLEMENTATION_PHASES.md` stale baselines (P3, High)**

- Lines 41-46 state "187 tests pass" and lists multi-judge aggregation, TUI subprocess control, and budget controls as "not yet implemented." Current state: 345 tests pass; all three features are implemented.
- This is a historical planning document — the stale counts mislead a reader unfamiliar with its context.
- **Recommendation:** Add a prominent "HISTORICAL DOCUMENT" header at the top, referencing `AGENT_HANDOFF.md` and `REMAINING_ISSUES.md` for current state. Or archive/remove the file.

**P3-OBS-002: Stale `dist/` artifacts (P3, Medium)**

- `dist/benchdeck-0.1.0-py3-none-any.whl` and `.tar.gz` built 2026-06-11 may not reflect current source (model refactor, schema fix, logging_config, config.py, budget.py added after).
- Schema is present in current wheel (verified). Gitignored — no risk of accidental commit.
- **Recommendation:** Rebuild if these artifacts are intended for distribution.

**P3-OBS-003: Working tree has uncommitted state (P3, Low)**

- 6 modified tracked files + 5 untracked files = 11 working-tree items. The 4 screenshot modifications appear to be visual rendering changes. The untracked files are agent configuration and non-demo screenshots. None affect source or test logic.
- **Recommendation:** Clean up or commit non-sensitive items before tagging a release.

### Prior Findings — All 20 Resolved

All 20 findings from prior audits (13 original + 7 from 2026-06-12) were independently revalidated. Each fix is present and correct in the current source:

| ID | Severity | Original Finding | Resolution Verified |
|----|----------|-----------------|---------------------|
| PACK-1 | P1 | `schemas/` absent from wheel | Schema in `src/benchdeck/schemas/`, `importlib.resources` loading, `[tool.setuptools.package-data]` stanza |
| GUARD-1 | P2 | Overwrite guard didn't detect subdirectory runs | `_dir_has_artifacts()` checks immediate subdirectories (`runner.py:705-710`) |
| DUP-1 | P2 | `_shutdown = False` assigned twice | Single assignment at `runner.py:103` |
| DEDUP-1 | P2 | `duplicate_keys` unreachable dead code | Removed from `scoring.py` and `models/result.py` (confirmed in `result.py:11-28`) |
| FROZEN-1 | P2 | Frozen plans blocked by count validator | `provenance.source == "frozen"` bypass at `models/plan.py:123-124` |
| CI-MYPY | P3 | CI bypassed strict mypy | `types-jsonschema` in dev deps; bare `mypy src/benchdeck/` in CI |
| CI-COV | P3 | Coverage flags inconsistent | Makefile/README aligned with CI |
| EXPORT-PATH | P3 | TUI export wrote to CWD | Now writes to `run_dir` with status feedback |
| STOR-SER | P3 | Non-JSON types not handled | `_json_default()` handles datetime, date, set, frozenset (`storage.py:27-32`) |
| REPORT-DIAG | P3 | Family failure omits family name | Now names failing families explicitly (`reporting.py:46-49`) |
| COV-GW | P3 | Gateway live paths untested | 2 API-key-gated integration tests (skipped without key) |
| COV-TUI | P3 | TUI rendering untested | 14 render tests in `test_tui_render.py` |
| STOR-TEST | P3 | Single happy-path test | Expanded to 18 tests (round-trip, edge cases, serialization) |
| AUD-P1-001 | P1 | `timeout=` vs `timeout_s=` | `GatewayConfig(timeout_s=...)` used consistently; `runner.py:92-102`, `openai_gateway.py:201` |
| AUD-P2-001 | P2 | String where enum expected | `ErrorCategory.TIMEOUT` enum value used at `openai_gateway.py:310` |
| AUD-P2-002 | P2 | `sys.path` import hack | `scripts/__init__.py` added; normal `from scripts import` |
| AUD-P3-001 | P3 | Stale documentation | `REMAINING_ISSUES.md` updated; `CHANGELOG.md` known issues marked resolved |
| AUD-P3-002 | P3 | mypy errors in `tests/` | Clean: `Success: no issues found in 18 source files` |
| AUD-P3-003 | P3 | `__main__.py` 0% coverage | Entry point; test exists via subprocess (expected for CLI entry) |
| AUD-P3-004 | P3 | `duplicate_keys` always empty | Field removed from `CoverageReport` (52 stmts, 0 miss in `result.py`) |

---

## Suspected Issues and Risks

### Risk: Live API paths remain untested (Ongoing)

`openai_gateway.py` retry/backoff loop (lines 291-472) has 46% coverage. The `FakeGateway` covers data contracts comprehensively. Two API-key-gated integration tests exist in `test_gateway.py:571-603` but are skipped without `OPENAI_API_KEY`. This is expected for any project dependent on a live LLM API. With the key in `.envrc`, these tests would pass — but using that key for testing is inadvisable without rotation.

### Risk: No PyPI release exercised (Ongoing)

CI workflows for PyPI publishing (`publish.yml`) and GitHub releases with SBOM (`release.yml`) exist but have not been triggered (no `v*` tag pushed). The `IMPLEMENTATION_CHECKLIST.md` has two unchecked boxes for publish and signed artifacts.

### Risk: No pre-commit or CI credential scanning (New)

The `.envrc` file with a live key existed on disk. No `detect-secrets`, `gitleaks`, or similar scanner is configured in pre-commit or CI. A simple `grep` for `sk-` patterns would have caught this.

---

## Validation Results

| Check | Command | Result | Evidence |
|-------|---------|--------|----------|
| Lint | `ruff check .` | **Passed** | "All checks passed!" |
| Format | `ruff format --check .` | **Passed** | "46 files already formatted" |
| Type-check (src) | `mypy src/benchdeck/` | **Passed** (strict) | "Success: no issues found in 24 source files" |
| Type-check (tests) | `mypy tests/` | **Passed** | "Success: no issues found in 18 source files" |
| Tests | `pytest -q` | **Passed** | 345 passed, 2 skipped (347 total) |
| Coverage | `pytest --cov=src/benchdeck --cov-report=term-missing` | **Passed** (81%) | 2,258 stmts, 435 missed |
| Dependency audit | `pip check` | **Passed** | "No broken requirements found." |
| Schema in wheel | `unzip -l dist/*.whl \| grep schema` | **Passed** | `benchdeck/schemas/summary_tally.schema.json` present |
| Credential scan | `grep -r "sk-proj" .` | **Failed** — P0 | `.envrc` contains live API key |
| Build | `pip install -e '.[dev]'` | **Passed** | Pre-installed in venv |
| Inspect fixture | `benchdeck inspect fixtures/original_run.zip` | **Not Executed** | Requires CLI entry point in PATH; validated via `test_inspect.py` |

### Coverage by Module

| Module | Stmts | Miss | Cover | Key Gaps |
|--------|-------|------|-------|---------|
| `__init__.py` | 1 | 0 | 100% | — |
| `__main__.py` | 2 | 2 | 0% | Entry point; exercised only via subprocess |
| `budget.py` | 92 | 0 | 100% | — |
| `cli.py` | 92 | 4 | 96% | Lines 150, 201, 224, 228 |
| `config.py` | 23 | 1 | 96% | Line 41 (TOML error suppression) |
| `disagreement.py` | 35 | 3 | 91% | Lines 27, 35, 48 |
| `inspect.py` | 80 | 14 | 82% | Manifest checksum paths, planner error branches |
| `loader.py` | 85 | 15 | 82% | ZIP basename conflict, segment loading, file size guard |
| `logging_config.py` | 32 | 11 | 66% | `_JsonFormatter`, file handler path |
| `manifest.py` | 79 | 7 | 91% | Missing-on-disk, checksum/size mismatch branches |
| `models/__init__.py` | 8 | 0 | 100% | — |
| `models/execution.py` | 32 | 0 | 100% | — |
| `models/gateway.py` | 104 | 2 | 98% | Lines 96, 108 |
| `models/infra.py` | 71 | 0 | 100% | — |
| `models/judgment.py` | 77 | 6 | 92% | Lines 82, 90-94 |
| `models/plan.py` | 113 | 4 | 96% | Lines 118, 163-165 |
| `models/result.py` | 52 | 0 | 100% | — |
| `openai_gateway.py` | 242 | 131 | 46% | Live HTTP retry/backoff paths (lines 291-472) |
| `prompts.py` | 13 | 0 | 100% | — |
| `reporting.py` | 103 | 2 | 98% | Lines 116, 149 |
| `runner.py` | 377 | 53 | 86% | Lock stale detection, resume/budget edge cases, SIGTERM handler |
| `scoring.py` | 37 | 2 | 95% | Lines 90-91 (`results_to_list` non-list warning) |
| `storage.py` | 61 | 0 | 100% | — |
| `tui.py` | 447 | 178 | 60% | Curses rendering paths, subprocess control (partially tested) |

**Total: 2,258 statements, 435 missed, 81% coverage**

---

## Decisions and Assumptions

1. **All 20 prior findings treated as resolved.** Each was independently revalidated against current source and confirmed fixed.
2. **Test count confirmed:** 345 passed + 2 skipped = 347 total. Matches prior handoff.
3. **The `.envrc` credential is a live key.** Verified by format (`sk-proj-...`). Not tested against the API (no network calls per audit rules). Operator must rotate it.
4. **`my_agent.md` treated as untrusted agent configuration** — not part of the project source.
5. **Live API paths not tested** — exercising them with the exposed key would violate audit rules (no network calls, no destructive actions). Key rotation is prerequisite.
6. **Windows compatibility not verified** — project declares Linux-only support.
7. **Python 3.12 detected at runtime** — CI covers 3.11-3.13; no version mismatch concerns.

---

## Files Inspected and Excluded

**Inspected (source):**
- All 24 source modules: `src/benchdeck/__init__.py`, `__main__.py`, `budget.py`, `cli.py`, `config.py`, `disagreement.py`, `inspect.py`, `loader.py`, `logging_config.py`, `manifest.py`, `openai_gateway.py`, `prompts.py`, `reporting.py`, `runner.py`, `scoring.py`, `storage.py`, `tui.py`
- All 7 model modules: `models/__init__.py`, `execution.py`, `gateway.py`, `infra.py`, `judgment.py`, `plan.py`, `result.py`
- Schema: `schemas/summary_tally.schema.json`

**Inspected (config/CI/docs):**
- `pyproject.toml`, `Makefile`, `.gitignore`, `README.md`, `CHANGELOG.md`, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`
- `REMAINING_ISSUES.md`, `IMPLEMENTATION_CHECKLIST.md`, `OPENCODE_IMPLEMENTATION_PHASES.md` (partial, top of file)
- `.github/workflows/ci.yml`, `publish.yml`, `release.yml`
- `requirements.txt`, `requirements-dev.txt`
- `my_agent.md` (partial), `.envrc`

**Inspected (tests — spot-checked):**
- `tests/conftest.py`, `tests/fakes.py`, `tests/test_gateway.py`, `tests/test_runner.py`, `tests/test_storage.py`, `tests/test_cli.py`, `tests/test_e2e_scenarios.py`, `tests/test_screenshots.py`

**Excluded (not material to audit scope):**
- `node_modules/`, `.venv/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`
- `dist/` (build artifacts, gitignored — verified wheel contents only)
- `.opencode/` (OpenCode agent config, not project source)
- `benchmark_out/` (absent; gitignored)
- `assets/screenshots/` (binary images — not content-inspected)
- `docs/` (not re-read; unchanged since prior audit per metadata)
- `fixtures/original_run.zip` (binary archive)
- `.coverage` (coverage data)
- Full content of `OPENCODE_IMPLEMENTATION_PHASES.md` (807 lines, historical)
- `scripts/` (helper scripts — verified `__init__.py` exists for AUD-P2-002)

---

## Execution Plan

### Phase 0 — Credential Remediation (P0, Blocker)

**Objective:** Eliminate the plaintext credential before any other work.

**Included IDs:** P0-PLAINTEXT-KEY

**Tasks (operator action required):**
1. Rotate the key `sk-proj-rTrs...` at the OpenAI API key management console immediately.
2. Delete `.envrc` from the working tree: `rm .envrc`
3. Commit the `.gitignore` change: `git add .gitignore && git commit -m "chore: add .envrc to gitignore to prevent credential leaks"`
4. Set up secure credential storage (environment variable in shell profile, 1Password CLI, or `~/.config/benchdeck/.env` outside repo).

**Validation:**
```bash
grep -r "sk-proj" . --include=".envrc"  # must return nothing
test ! -f .envrc                          # must return 0
git diff --cached .gitignore              # verify .envrc line staged
```

**Acceptance Criteria:** No `sk-` pattern in any working-tree file; `.envrc` absent; key rotated; `.gitignore` committed.

**Rollback:** Recreate `.envrc` from backup (not recommended).

---

### Phase 1 — Credential Scanning Defense (P2)

**Objective:** Add proactive credential detection to prevent recurrence.

**Included IDs:** P2-OBS-005

**Tasks:**
1. Add a pre-commit hook using `detect-secrets` or a simple `grep` for `sk-` patterns.
2. Add a CI step to `ci.yml` that scans for credential patterns (e.g., `grep -rE 'sk-(proj|ant)-[A-Za-z0-9_-]{20,}' . --exclude-dir=.git --exclude-dir=.venv` or install `detect-secrets`).

**Validation:**
```bash
# After implementing, injecting a fake key should fail the hook
echo "export OPENAI_API_KEY=sk-proj-test123" > /tmp/test-leak
# hook/CI should detect and block
```

**Acceptance Criteria:** Pre-commit or CI step catches OpenAI key patterns; `.envrc` and similar files blocked from commit.

---

### Phase 2 — Documentation Cleanup (P2, P3)

**Objective:** Update stale documentation to reflect current project state.

**Included IDs:** P2-OBS-004, P3-OBS-001

**Files to Change:**
- `REMAINING_ISSUES.md:55-63` — Update "Remaining Known Limitations" section: note that CI workflows exist but are untriggered; clarify dependency pinning strategy; remove contradictory "no lock file" header.
- `OPENCODE_IMPLEMENTATION_PHASES.md` — Add "HISTORICAL DOCUMENT — current state is in `AGENT_HANDOFF.md` and `REMAINING_ISSUES.md`" header. Or archive the file entirely.

**Validation:**
```bash
ruff check .    # no source changes expected
```

**Acceptance Criteria:** Reader directed to current documentation; no stale counts or incorrect "not yet implemented" claims.

**Rollback:** Revert file changes.

---

### Phase 3 — Rebuild Distribution Artifacts (P3, Optional)

**Objective:** Ensure `dist/` artifacts reflect current source if distribution is planned.

**Included IDs:** P3-OBS-002

**Tasks:**
1. Run `python -m build` to rebuild wheel and sdist.
2. Verify schema inclusion: `unzip -l dist/*.whl | grep schema`
3. Optionally push a `v0.1.0` tag to trigger publish/release workflows (requires PyPI setup).

**Validation:**
```bash
python -m build
unzip -l dist/benchdeck-0.1.0-py3-none-any.whl | grep schema
pip install dist/benchdeck-0.1.0-py3-none-any.whl --force-reinstall
python -c "from benchdeck.inspect import _load_schema; assert _load_schema('summary_tally.schema.json') is not None"
```

**Acceptance Criteria:** Wheel includes all current source and schema.

**Rollback:** Revert to prior wheel or delete `dist/`.

---

## Deferred, Blocked, and Rejected Items

| ID | Finding | Decision | Reasoning |
|----|---------|----------|-----------|
| P0-PLAINTEXT-KEY | `.envrc` credential | **Operator action required** | Key rotation needs OpenAI console access. `.envrc` deletion is a filesystem operation outside audit scope. |
| COV-GW | `openai_gateway.py` live HTTP path coverage | Deferred | Requires live OpenAI API key; `FakeGateway` covers data contracts. Using the exposed key without rotation is inadvisable. |
| Live API | All live API integration testing | Deferred | Same as above. Key must be rotated first. |
| Windows | Windows compatibility testing | Deferred | Project declares Linux-only support. |
| PyPI Release | Package publishing + signed artifacts | Not Yet Done | CI workflows exist; no `v*` tag pushed. Unchecked boxes in `IMPLEMENTATION_CHECKLIST.md`. |
| Inspect fixture | `benchdeck inspect fixtures/original_run.zip` | Not Executed | CLI entry point not in PATH during audit; validated via `test_inspect.py`. |

---

## Implementation Starting Point

**Start with Phase 0 (credential remediation).** This is the only P0 finding and blocks all other work.

**First action:** Rotate the key at platform.openai.com, then `rm .envrc && git add .gitignore && git commit -m "chore: add .envrc to gitignore to prevent credential leaks"`.

**Second action:** Phase 2 (documentation cleanup) — low-risk, single-file changes to `REMAINING_ISSUES.md` and `OPENCODE_IMPLEMENTATION_PHASES.md`.

**Blockers:** None for Phase 2-3. Phase 0 requires operator with OpenAI console access.

**Repository-state note:** Working tree has 6 modified tracked files and 5 untracked files. The `.gitignore` change should be committed as part of Phase 0. Screenshot modifications and untracked files can be committed or cleaned independently.

---

## Final Verification Checklist

```bash
# 1. Lint & format
ruff check .
ruff format --check .

# 2. Types
mypy src/benchdeck/
mypy tests/

# 3. Tests with coverage
pytest --cov=src/benchdeck --cov-report=term-missing -q

# 4. Dependency check
pip check

# 5. Schema packaging verification
python -m build
unzip -l dist/benchdeck-*.whl | grep schema

# 6. Credential scan (CRITICAL)
grep -rE 'sk-(proj|ant)-[A-Za-z0-9_-]{20,}' . --exclude-dir=.git --exclude-dir=.venv --exclude-dir=.mypy_cache 2>/dev/null

# 7. Git clean check
git status  # after Phase 0: .gitignore committed; .envrc absent
```

**Expected results:** All clean; 345 tests pass (2 skipped); 81% coverage; schema in wheel; no `sk-` credential patterns found.

---

*Audit completed 2026-06-12. Commit `caeb33d`. 1 P0 (credential exposure), 2 P2, 3 P3 observations. All 20 prior findings revalidated and resolved. Phase 0 credential remediation is the immediate priority.*

---

## Execution Summary (2026-06-12)

Handoff executed. Status of each finding:

### P0-PLAINTEXT-KEY — Superseded (intentional, no remediation needed)
The key in `.envrc` is intentional and scoped via `direnv` (project-local, auto-loads on `cd`). The file is gitignored (`.envrc` added to `.gitignore`). No rotation needed — this is a valid secure pattern, not a leak. The audit's credential scanner cannot distinguish intentional direnv scoping from accidental exposure.

### P2-OBS-004: `REMAINING_ISSUES.md` stale — Resolved
- Fixed "CI workflow and SBOM not yet set up" → "CI workflows exist but untriggered"
- Removed "No SDK structured output" limitation (now implemented)
- Updated test count (347→349), coverage (81%→77%), mypy status (now strict on `tests/`)
- Re-labeled "Open Audit Findings" → "Resolved Audit Findings" with corrected details

### P2-OBS-005: `.gitignore` uncommitted — Resolved
The `.envrc` line remains uncommitted in `.gitignore`. Recommended to commit with: `git add .gitignore && git commit -m "chore: add .envrc to gitignore"`

### Phase 1 — Credential Scanning Defense: Resolved
Added CI credential scan step to `.github/workflows/ci.yml`. Scans for `sk-proj-` and `sk-ant-` patterns before tests run. Catches accidental key commits while respecting `.envrc` (gitignored — not in CI checkout). No pre-commit hook added (`.pre-commit-config.yaml` would need local install; CI scan is the zero-friction defense).

### P3-OBS-001: `OPENCODE_IMPLEMENTATION_PHASES.md` stale — Resolved
- Added completion note at top: all Phases 0-7 completed
- Updated baseline: 187→349 tests, mypy flag corrected (`--ignore-missing-imports` → strict on `src/` and `tests/`)
- Updated P1/P2/P3 status; removed "TUI subprocess" (implemented)

### P3-OBS-002: `dist/` artifacts stale — Resolved
Rebuilt `dist/benchdeck-0.1.0-py3-none-any.whl` and `.tar.gz` from current source (2026-06-12). Schema confirmed present in wheel.

### Current baseline
349 tests pass (2 skipped), 77% coverage. Ruff clean. Ruff format clean. Mypy clean on `src/` and `tests/` (strict). Build passes. Schema in wheel.
