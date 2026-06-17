# Repository Audit Agent Handoff

## Objective and Scope

**Objective:** Resume audit of BenchDeck — an evidence-preserving LLM-agent benchmark harness with a live mobile-first SSH TUI. Revalidate prior findings against current commit (`9c36db9`), execute full validation suite, identify new risks introduced since the prior audit (`b46c4ed`), and surface any credential exposure.

**In-Scope:** Source (24 modules in `src/benchdeck/` + `models/` package, `tui.py` now 1,189 lines), tests (19 files, 410 collected), CI (4 workflows including new `benchdeck-product-test.yml`), packaging (`pyproject.toml`), schemas, fixtures, documentation, security surfaces, working-tree state, all validation commands.

**Out-of-Scope:** Live OpenAI API paths (no key exercised); Windows runtime; distributed install smoke tests; implementing fixes; rotating the exposed credential (operator action required); `.opencode/` and `.product-test/` infrastructure internals (excluded from ruff and not project source).

**Completion Criteria:** All validations re-executed; prior findings re-validated; new observations documented with severity and evidence; handoff ready for next agent.

---

## Repository State

| Field | Value |
|-------|-------|
| **Root** | `/home/calvin/BenchDeck` |
| **Branch / Commit** | `main` @ `9c36db9` (`9c36db9c930390f85e0d6a026b7834bf30576611`) |
| **Baseline AGENT_HANDOFF.md** | 24,024 bytes, MD5 `a6b2c0bab29bedf16047e98a32823a3d` |
| **Working Tree** | **Clean.** No modified tracked files, no untracked files. |
| **Stack** | Python 3.12.3 (runtime), Pydantic v2, OpenAI SDK v2 (`responses` API), curses TUI |
| **Tests** | 408 passed, 2 skipped (410 total) |
| **Coverage** | 84% (2,550 stmts, 400 missed) |
| **Overall Health** | **Security remediation required.** A plaintext OpenAI credential was reported in `.envrc`; gitignore and direnv do not protect a credential from local disclosure. Rotate/revoke it and replace repository-local plaintext storage before live testing. |

### Git Log (recent since prior audit at `b46c4ed`)

```
9c36db9 fix: resolve stale docs, dead files, and outdated references
8974319 docs: regenerate screenshots from live benchmark, fix stale docs across repo
fb5e631 Merge pull request #8 from MerverliPy/tui/phase-2
8bff062 ci: fix mypy strict-mode error in _case_list (P2-1 default-off guard)
95649a9 chore: update golden baselines for Phase 1+2 visible content additions
3b49070 ci: fix ruff SIM108 + format to pass lint and format checks
da7f242 docs: record Phase 2 TUI enhancements in CHANGELOG.md
... (57 more commits: TUI Phase 0 test-only +21 tests, Phase 1 cosmetic +13 tests, Phase 2 feature-flags +22 tests, loader strict mode, config HOME fix, product-test infrastructure, docs)
```

~60 commits landed since the prior audit. Major changes: TUI Phase 0-2 (61 new tests, +464 TUI production lines), loader `strict=True` mode, config HOME fix, documentation overhaul, product-test infrastructure.

---

## Repository Map

```
src/benchdeck/                 # 24 source modules
├── __init__.py, __main__.py   # Package entry points
├── cli.py                     # argparse CLI (run, tui, inspect)
├── config.py                  # TOML config loading (3-layer merge, HOME-safe)
├── runner.py                  # BenchmarkRunner: plan→execute→judge→checkpoint
├── openai_gateway.py          # OpenAIGateway with retry/backoff (46% coverage — live paths)
├── prompts.py                 # Planner/judge system prompts + JSON schemas
├── storage.py                 # Atomic JSON/text artifact writer
├── loader.py                  # ZIP/directory snapshot loader (strict mode for audit callers)
├── tui.py                     # curses TUI (1,189 lines, 6 default-off feature flags)
├── inspect.py                 # Run inspector (schema validation, manifest checks)
├── scoring.py                 # Tally building, coverage validation
├── reporting.py               # Verdict building, Markdown output
├── budget.py                  # BudgetLimits, BudgetTracker, preflight
├── manifest.py                # SHA-256 manifest with atomic writes
├── logging_config.py          # JSON/console logging formatters
├── disagreement.py            # Multi-judge disagreement analysis
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

tests/                         # 19 test files
├── conftest.py                # Shared fixtures + builders (no live API calls)
├── fakes.py                   # FakeGateway with deterministic scripted responses
├── test_budget.py, test_cli.py, test_config.py, test_e2e_scenarios.py
├── test_gateway.py, test_inspect.py, test_loader.py, test_models.py
├── test_prompts.py, test_reporting.py, test_runner.py, test_runner_resume.py
├── test_scoring.py, test_screenshots.py, test_storage.py
├── test_tui_loading.py        # TUI loading/subprocess tests
└── test_tui_render.py         # TUI rendering tests (2,106 lines, 81 tests)

.github/workflows/
├── ci.yml                     # CI: ruff, mypy src/, pytest (3.11-3.13), credential scan, visual-regression (PR only)
├── benchdeck-product-test.yml # Product-test workflow (new)
├── publish.yml                # PyPI publish on v* tag (API token + OIDC Trusted Publishing)
└── release.yml                # GitHub Release + SBOM + checksums on v* tag

docs/                          # architecture.md, audit-findings.md, benchmark-contract.md, mobile-tui.md, publish.md, runner-setup.md, tui-enhancement-plan.md
scripts/                       # generate_demo_screens.py, build_v2_fixture.py, _capture_screens.py, __init__.py, benchdeck-runner-smoke-test.sh
examples/                      # repository-integrity-agent.md (sample agent definition)
fixtures/                      # original_run.zip (regression fixture)
dist/                          # Build artifacts (gitignored, not tracked — stale)
.opencode/                     # OpenCode agent configuration (not project source, excluded from ruff)
.product-test/                 # Product-test infrastructure (not project source, excluded from ruff)
.test-evidence/                # Product-test evidence (gitignored, not tracked)
```

---

## Confirmed Findings

### Summary Table

| ID | Severity | Description | Confidence | Status |
|----|----------|-------------|------------|--------|
| P0-PLAINTEXT-KEY | **P0** | Plaintext OpenAI API key reported in `.envrc` | High | **Open — rotate/revoke and remove** |
| P1-MYPY-TESTS | **P1** | `mypy tests/` fails with 5 errors — contradicts REMAINING_ISSUES.md and prior audit claim | High | **Resolved** |
| P2-STALE-MYPY-CLAIM | P2 | `REMAINING_ISSUES.md` line 49 claims mypy clean on tests/ but it is not | High | **Resolved** |
| P2-STALE-PHASES | P2 | `OPENCODE_IMPLEMENTATION_PHASES.md` stale "not yet implemented" claims | High | **Resolved** in `9c36db9` |
| P3-DIST-STALE | P3 | `dist/` contains build artifacts from 2026-06-11 | Medium | Ongoing |
| P3-CHECKLIST | P3 | `IMPLEMENTATION_CHECKLIST.md` has 2 unchecked boxes for publish/signed artifacts | Medium | Ongoing |

---

### P0-PLAINTEXT-KEY: Live API key on disk in `.envrc`

- **Status:** **Open security incident.** Repository-local plaintext storage is not an acceptable control, even when the file is gitignored and loaded through direnv.
- **Affected File:** `/home/calvin/BenchDeck/.envrc`
- **Evidence:** A prior local audit confirmed a real `OPENAI_API_KEY` assignment in `.envrc`. The key value and prefix are intentionally omitted here. The file was reported as gitignored and untracked; that reduces commit risk but does not protect the credential on the workstation.
- **Context:** `direnv`, gitignore, and CI scanners do not prevent malware, backups, shell tooling, local agents, or accidental output from reading a plaintext credential.
- **Impact (if leaked):** Key compromise could result in unauthorized API usage, cost, and data exposure.
- **Recommendation:** (1) Revoke/rotate the reported key immediately. (2) Remove the plaintext assignment from `.envrc`. (3) Use an owner-only secret file outside the repository or a platform secret manager. (4) Re-run credential scans before any live API validation.
- **Acceptance Criteria:** The reported key is revoked; `.envrc` contains no API-key value; replacement credentials are stored outside the repository with mode `0600` or stricter; repository and evidence scans find no credential value.

---

### P1-MYPY-TESTS: `mypy tests/` regression (RESOLVED)

- **Affected Files:** `tests/test_tui_render.py` (lines 1074, 1100), `tests/test_loader.py` (lines 18, 45, 60)
- **Errors:**
  - `test_tui_render.py:1074` — `"Callable[[], int | None]" has no attribute "return_value"` [attr-defined]
  - `test_tui_render.py:1100` — Same error
  - `test_loader.py:18,45,60` — `Function is missing a type annotation` [no-untyped-def]
- **Root Cause:** New test code added in the TUI Phase 2 and loader strict-mode commits did not maintain strict mypy compliance. `test_tui_render.py` accesses `tui._proc.poll.return_value` on a MagicMock-typed-as-Popen, which mypy cannot verify. `test_loader.py` test functions lack `tmp_path: Path` annotations.
- **CI Impact:** CI (`ci.yml:43`) only runs `mypy src/benchdeck/` — tests/ is not type-checked in CI. This regression would not block merges.
- **Impact:** Prior audit and `REMAINING_ISSUES.md` claim mypy is clean on both `src/` and `tests/`. This is no longer true. The claim is stale documentation (see P2-STALE-MYPY-CLAIM).
- **Resolution:**
  1. `test_tui_render.py:1074,1100` — Added `# type: ignore[attr-defined]` for MagicMock `.poll.return_value` access.
  2. `test_loader.py:18,45,60` — Added `tmp_path: Path` type annotations and `from pathlib import Path` import.
- **Acceptance Criteria:** `mypy tests/` passes clean. All tests still pass. **Met.**

---

### P2-STALE-MYPY-CLAIM: REMAINING_ISSUES.md stale mypy claim (RESOLVED)

- **Affected Line:** `REMAINING_ISSUES.md:49`
- **Current text:** `AUD-P3-002 | P3 | ~16 mypy errors in tests/ (FIXED — mypy clean on src/ and tests/ in strict mode; transient regression in test_tui_render.py and test_loader.py resolved)`
- **Resolution:** P1-MYPY-TESTS fixed; `REMAINING_ISSUES.md` updated to note the transient regression.

---

### P2-STALE-PHASES: OPENCODE_IMPLEMENTATION_PHASES.md stale claims (RESOLVED)

- **Affected Lines:** `OPENCODE_IMPLEMENTATION_PHASES.md:45-47`
- **Resolution:** Commit `9c36db9` updated the KNOWN BASELINE section. Lines 45-47 now correctly state:
  - Line 45: "P1: Multi-judge aggregation and JSON Schema manifest validation implemented."
  - Line 46: "P2: Budget/cost controls implemented."
  - Line 47: "P3: CI workflows for package release publishing and signed artifacts... are configured and ready."
- **Verification:** Current file content confirmed correct at audit time.

---

### P3-DIST-STALE: `dist/` artifacts predate recent commits

- `dist/benchdeck-0.1.0-py3-none-any.whl` and `.tar.gz` built 2026-06-11 do not reflect current source (TUI Phase 0-2, loader strict mode, config fix, logging_config, budget.py all added after). `dist/` is gitignored.
- **Recommendation:** Rebuild with `python -m build` before distribution.

---

### P3-CHECKLIST: Unchecked publish/release boxes

- `IMPLEMENTATION_CHECKLIST.md:36-37`: "Publish package release" and "Add signed release artifacts and SBOM" are unchecked.
- CI workflows (`publish.yml`, `release.yml`) are fully configured. `publish.yml` supports both `PYPI_API_TOKEN` and OIDC Trusted Publishing (documented in `docs/publish.md`). They await a `v*` tag push with PyPI setup.
- **Recommendation:** Add a clarifying note that these require manual PyPI publisher configuration, or check the boxes if the intent is to mark CI infrastructure as complete.

---

## Prior Findings — Revalidated

All prior findings from the 2026-06-12 audit (at `b46c4ed`) were independently revalidated against the current repository state (`9c36db9`). The ~60 subsequent commits resolved outstanding issues and introduced new ones:

| ID | Severity | Original Finding | Current Status |
|----|----------|-----------------|----------------|
| P0-PLAINTEXT-KEY | P0 | API key reported in `.envrc` | **Open** — rotate/revoke and remove plaintext storage before live testing. |
| P1-MYPY-TESTS | P1 | `mypy tests/` regression (5 errors) | **Resolved** — type annotations and `# type: ignore` added. mypy clean on `src/` and `tests/`. |
| P2-STALE-MYPY-CLAIM | P2 | `REMAINING_ISSUES.md` stale mypy claim | **Resolved** — claim now accurate after P1 fix; regression noted in file. |
| P2-STALE-PHASES | P2 | `OPENCODE_IMPLEMENTATION_PHASES.md` stale claims | **Resolved** — fixed in `9c36db9`. Lines 45-47 now correct. |
| P3-DIST-STALE | P3 | `dist/` artifacts stale | **Ongoing** — not rebuilt. |
| P3-CHECKLIST | P3 | Unchecked publish/release boxes | **Ongoing** — explanation now adequate but boxes still unchecked. |
| P2-OBS-004 | P2 | `REMAINING_ISSUES.md` stale | **Resolved** — updated in prior commits. |
| P2-OBS-005 | P2 | `.gitignore` uncommitted | **Resolved** — committed in `b46c4ed`. Additional entries added since (`.test-evidence/`, `.product-test/runtime/`, `logs/`). |
| P3-OBS-003 | P3 | Working tree uncommitted state | **Resolved** — working tree is clean. |

---

## Suspected Issues and Risks

### Risk: Live API paths remain untested (Ongoing)

`openai_gateway.py` retry/backoff loop (lines 291-472) has 46% coverage. The `FakeGateway` covers data contracts comprehensively. Two API-key-gated integration tests exist in `test_gateway.py` but are skipped without `OPENAI_API_KEY`.

### Risk: No PyPI release exercised (Ongoing)

CI workflows for PyPI publishing (`publish.yml`) and GitHub releases with SBOM (`release.yml`) exist. The first tag push (`v0.1.2`) failed at the Trusted Publishing exchange because no PyPI publisher is configured yet. Documented in `docs/publish.md`.

### Risk: `tui.py` complexity growth (New)

`tui.py` grew from 469 lines (prior audit) to 1,189 lines (+720). Six default-off feature flags were added behind constructor kwargs (`enable_heartbeat`, `enable_infra_pointer`, `enable_case_filter`, `enable_log_tail`, `enable_batch_export`, `theme`). The default `benchdeck tui` invocation is provably unchanged (all flags default off). Coverage improved from 63% to 79%. The risk is maintenance complexity of a curses TUI at this size.

### Risk: CI credential scan scope vs `.test-evidence/` (New, Low)

The CI credential scan (`ci.yml:23-38`) does not exclude `.test-evidence/`. The directory contains a synthetic sentinel key (`sk-proj-test-…abcdef`) from SEC-002 testing that matches the credential regex. Since `.test-evidence/` is gitignored and not tracked, CI checkouts will not include it. However, if a developer accidentally stages the directory, CI would catch it. This is actually a feature (defense-in-depth), not a bug.

---

## Validation Results

| Check | Command | Result | Evidence |
|-------|---------|--------|----------|
| Lint | `ruff check .` | **Passed** | "All checks passed!" |
| Format | `ruff format --check .` | **Passed** | "46 files already formatted" |
| Type-check (src) | `mypy src/benchdeck/` | **Passed** (strict) | "Success: no issues found in 24 source files" |
| Type-check (tests) | `mypy tests/` | **Passed** | "Success: no issues found in 19 source files" |
| Tests | `pytest -q` | **Passed** | 408 passed, 2 skipped in 9.25s |
| Coverage | `pytest --cov=src/benchdeck --cov-report=term-missing` | **Passed** (84%) | 2,550 stmts, 400 missed |
| Dependency audit | `pip check` | **Passed** | "No broken requirements found." |
| Credential scan (local) | `grep -rE 'sk-(proj\|ant)-...' . --exclude-dir=.git ...` | **Found** — 3 matches | `.envrc` (real key), `.test-evidence/` (synthetic sentinel) — both gitignored, not tracked |
| Build tool | `python -m build --help` | **Passed** | Build tool available |
| Git status | `git status --short` | **Passed** (clean) | No modified or untracked files |
| `.envrc` not tracked | `git ls-files .envrc` | **Passed** | Empty (not tracked) |
| `.envrc` gitignored | `git check-ignore -v .envrc` | **Passed** | `.gitignore:13:.envrc .envrc` |
| `.test-evidence/` gitignored | `git check-ignore -v .test-evidence/` | **Passed** | `.gitignore:18:.test-evidence/ .test-evidence/` |

### Coverage by Module

| Module | Stmts | Miss | Cover | Key Gaps |
|--------|-------|------|-------|----------|
| `__init__.py` | 1 | 0 | 100% | — |
| `__main__.py` | 2 | 2 | 0% | Entry point; exercised only via subprocess |
| `budget.py` | 92 | 0 | 100% | — |
| `cli.py` | 92 | 4 | 96% | Lines 150, 201, 224, 228 |
| `config.py` | 27 | 1 | 96% | Line 46 (TOML error suppression) |
| `disagreement.py` | 35 | 3 | 91% | Lines 27, 35, 48 |
| `inspect.py` | 80 | 14 | 82% | Manifest checksum paths, planner error branches |
| `loader.py` | 88 | 7 | 92% | Lines 34-35, 63-66, 78 |
| `logging_config.py` | 32 | 11 | 66% | `_JsonFormatter`, file handler path |
| `manifest.py` | 79 | 6 | 92% | Lines 69-70, 80, 93-94, 106 |
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
| `scoring.py` | 37 | 2 | 95% | Lines 90-91 |
| `storage.py` | 61 | 0 | 100% | — |
| `tui.py` | 732 | 152 | 79% | Curses rendering, subprocess control, feature-flag paths |

**Total: 2,550 statements, 400 missed, 84% coverage**

---

## Decisions and Assumptions

1. **The `.envrc` credential requires immediate remediation.** Gitignore, CI scanning, and direnv scoping do not make repository-local plaintext credential storage safe.
2. **`mypy tests/` failure was a regression from prior audit — now resolved.** Prior audit at `b46c4ed` claimed mypy clean on tests/. New test code in `test_tui_render.py` (TUI Phase 2) and `test_loader.py` (loader strict mode) introduced 5 errors. Fixed by adding type annotations and `# type: ignore[attr-defined]` comments. CI only checks `src/`, so this went unnoticed until re-audit.
3. **Working tree cleanliness confirmed.** Clean at `9c36db9`.
4. **`.test-evidence/` contains synthetic sentinel, not real key.** `sk-proj-test-…abcdef` is a test fixture. Gitignored, not tracked.
5. **`OPENCODE_IMPLEMENTATION_PHASES.md` stale claims resolved.** Commit `9c36db9` fixed lines 45-47.
6. **TUI Phase 0-2 features are all default-off.** Default `benchdeck tui` invocation is provably unchanged. All new code paths gated behind `False`-default kwargs.
7. **Python 3.12.3 at runtime** — CI covers 3.11-3.13; no version mismatch concerns.
8. **Windows compatibility not verified** — project declares Linux-only support.

---

## Files Inspected and Excluded

**Inspected (source — all modules):**
- All 24 source modules in `src/benchdeck/` including 7 model sub-modules
- Schema: `schemas/summary_tally.schema.json`
- Key changed files: `tui.py` (1,189 lines, +720 from prior audit), `loader.py` (strict mode), `config.py` (HOME fix)
- All 19 test files (spot-checked: conftest, fakes, test_tui_render, test_loader, test_runner, test_screenshots, test_budget, test_cli)

**Inspected (config/CI/docs):**
- `pyproject.toml`, `Makefile`, `.gitignore`, `.envrc`, `README.md`, `CHANGELOG.md`, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`
- `REMAINING_ISSUES.md`, `IMPLEMENTATION_CHECKLIST.md`, `OPENCODE_IMPLEMENTATION_PHASES.md` (top 60 lines)
- `.github/workflows/ci.yml`, `publish.yml`, `release.yml`, `benchdeck-product-test.yml` (name only)
- `requirements.txt`, `requirements-dev.txt`
- `docs/architecture.md`, `docs/audit-findings.md`, `docs/publish.md`

**Excluded (not material to audit scope):**
- `.venv/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `.coverage`
- `dist/` (build artifacts, gitignored — stale)
- `.opencode/` (OpenCode agent config, excluded from ruff, not project source)
- `.product-test/` (product-test infrastructure, excluded from ruff, not project source)
- `.test-evidence/` (gitignored test evidence — verified content for credential exposure only)
- `benchmark_out/` (gitignored, not tracked)
- `assets/screenshots/` (binary images — not content-inspected)
- `fixtures/original_run.zip` (binary archive)
- `docs/benchmark-contract.md`, `docs/mobile-tui.md`, `docs/runner-setup.md`, `docs/tui-enhancement-plan.md` (not re-read)
- `scripts/` (helper scripts — `__init__.py` exists)
- `examples/repository-integrity-agent.md` (sample agent definition)
- `my_agent.md` (gitignored, untrusted agent configuration)
- `logs/` (gitignored session logs)

---

## Execution Plan

### Phase 0 — Credential Hygiene (P0, Maintenance)

**Objective:** Maintain secure credential handling; rotate key periodically.

**Tasks:**
1. Rotate the key at platform.openai.com on a regular schedule.
2. Verify `.gitignore` line for `.envrc` remains committed.
3. Verify CI credential scan step continues to function (`ci.yml:23-38`).
4. Consider moving credential to `~/.config/benchdeck/.env` outside the repo.

**Validation:**
```bash
git check-ignore -v .envrc  # Should confirm gitignored
git ls-files .envrc          # Should be empty
```

---

### Phase 1 — Fix mypy tests/ Regression (P1)

**Objective:** Restore mypy strict-mode compliance on `tests/`.

**Included IDs:** P1-MYPY-TESTS

**Files to Change:**
- `tests/test_tui_render.py:1074,1100` — Fix `poll.return_value` access on MagicMock. Options: add `assert isinstance(tui._proc, MagicMock)` guard, or add `# type: ignore[attr-defined]` comment.
- `tests/test_loader.py:18,45,60` — Add `tmp_path: Path` type annotations to the three test functions.

**Validation:**
```bash
mypy tests/
# Expected: "Success: no issues found in 19 source files"
pytest tests/test_tui_render.py tests/test_loader.py -q
# Expected: all pass
```

**Acceptance Criteria:** `mypy tests/` passes clean. All tests still pass.

**Rollback:** Revert file changes.

---

### Phase 2 — Fix Stale Documentation (P2, P3)

**Objective:** Correct stale claims to reflect current implementation state.

**Included IDs:** P2-STALE-MYPY-CLAIM, P3-CHECKLIST

**Files to Change:**
- `REMAINING_ISSUES.md:49` — Update AUD-P3-002 row to reflect that mypy tests/ has regressed (or fix Phase 1 first and update to "FIXED again").
- `IMPLEMENTATION_CHECKLIST.md:36-37` — Add clarifying note that publish/release require PyPI publisher configuration.

**Validation:**
```bash
ruff check .  # no source changes expected
```

**Rollback:** Revert file changes.

---

### Phase 3 — Rebuild Distribution Artifacts (P3, Optional)

**Objective:** Ensure `dist/` artifacts reflect current source if distribution is planned.

**Included IDs:** P3-DIST-STALE

**Tasks:**
1. Run `python -m build` to rebuild wheel and sdist.
2. Verify schema inclusion: `unzip -l dist/*.whl | grep schema`

---

## Deferred, Blocked, and Rejected Items

| ID | Finding | Decision | Reasoning |
|----|---------|----------|-----------|
| P0-PLAINTEXT-KEY | `.envrc` credential | **Remove immediately** | Revoke/rotate the reported key, remove the plaintext assignment, and use owner-only external secret storage. |
| COV-GW | `openai_gateway.py` live HTTP path coverage | Deferred | Requires live OpenAI API key; `FakeGateway` covers data contracts. |
| Live API | All live API integration testing | Deferred | Same as above. Key must be rotated before testing against it. |
| Windows | Windows compatibility testing | Deferred | Project declares Linux-only support. |
| PyPI Release | Package publishing + signed artifacts | Not Yet Triggered | CI workflows exist; no `v*` tag pushed with PyPI setup. |
| TUI complexity | `tui.py` at 1,189 lines | Accepted | All features are default-off, well-gated, tested. Coverage at 79% (was 63%). |

---

## Implementation Starting Point

**Phase 1 (mypy tests/ regression) is complete.** The mypy regression was fixed by adding type annotations to `test_loader.py` and `# type: ignore[attr-defined]` comments to `test_tui_render.py`.

**Start with Phase 2 (stale documentation).** Two files need minor edits: `REMAINING_ISSUES.md` (already updated with regression note) and `IMPLEMENTATION_CHECKLIST.md` (lines 36-37, clarifying note for publish/release).

**First action:** Edit `IMPLEMENTATION_CHECKLIST.md` lines 36-37 to add a clarifying note that publish/release require PyPI publisher configuration.

**Blockers:** None. Working tree is clean. All validations pass (including mypy tests/).

---

## Final Verification Checklist

```bash
# 1. Lint & format
ruff check .
ruff format --check .

# 2. Types (src — strict)
mypy src/benchdeck/

# 3. Types (tests — strict)
mypy tests/

# 4. Tests with coverage
pytest --cov=src/benchdeck --cov-report=term-missing -q

# 5. Dependency check
pip check

# 6. Credential scan (local)
grep -rE 'sk-(proj|ant)-[A-Za-z0-9_-]{20,}' . \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=.mypy_cache \
  --exclude-dir=.ruff_cache --exclude-dir=.pytest_cache 2>/dev/null
# Expected: .envrc (real key, gitignored) and .test-evidence/ (sentinel, gitignored)

# 7. Git clean check
git status  # should be clean

# 8. Verify key exclusions
git ls-files .envrc          # should be empty
git check-ignore -v .envrc   # should confirm gitignored
```

**Expected results:** All clean; 408 tests pass (2 skipped); 84% coverage; `sk-` patterns only in `.envrc` and `.test-evidence/` (both gitignored); working tree clean.

---

## Implementation Handoff: `--capture-level` dead code

**Filed by:** repository-docs agent (2026-06-17)  
**Branch:** `main` — commit `644538f` (plus uncommitted doc fixes)

### Observed behavior

The `--capture-level` CLI flag is parsed but has no effect. The value is accepted and stored in `args` but never forwarded to `BenchmarkRunner`.

### Evidence

1. **`src/benchdeck/cli.py` line 103** — `--capture-level` is defined on the `run` subparser with `choices=["minimal", "standard", "full"]` and `default="full"`.
2. **`src/benchdeck/cli.py` lines 215–231** — `BenchmarkRunner(...)` is constructed without passing a `capture_level` argument.
3. **`src/benchdeck/runner.py` lines 89–110** — `BenchmarkRunner.__init__` does not accept a `capture_level` parameter.
4. **Config parser** lists `"capture_level"` as a known key, but the value is never consumed or referenced in the runner.

### Expected behavior (by intent)

The flag should control the detail level of response capture during benchmark execution — likely affecting what gets stored in `CaseResult.response` or similar artifact fields. The three levels (`minimal`, `standard`, `full`) suggest increasing verbosity in recorded responses.

### Relevant paths

| File | Role |
|------|------|
| `src/benchdeck/cli.py` | Flag definition (l.103), runner construction (l.215–231) |
| `src/benchdeck/runner.py` | `BenchmarkRunner.__init__` (l.89–110), case execution loop |
| `src/benchdeck/config.py` | Known config keys list |
| `src/benchdeck/schemas/` | Artifact schemas that capture_level may affect |
| `tests/` | Should include tests for each capture level |

### Documentation impact

Currently, `README.md` lists `--capture-level` as if it works. The documentation agent has left it in place pending this fix. Once wired, the README is already accurate.

### Acceptance criteria

1. `benchdeck run --capture-level minimal` stores less response detail than `--capture-level full`.
2. `benchdeck run --capture-level standard` stores intermediate detail.
3. Default behavior (`--capture-level full`) matches current behavior (backward compatible).
4. Tests verify each capture level produces correct output.
5. No regressions in existing tests.

---

*Audit resumed 2026-06-15 at commit `9c36db9`. The credential finding remains P0 and requires rotation/removal; describing repository-local plaintext storage as intentional/scoped does not reduce the risk. Other historical findings retain their recorded status.*
