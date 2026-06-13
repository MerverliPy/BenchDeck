# Changelog

## 0.1.1 — 2026-06-13

### Fixed

- **Loader ZIP-safety contract (`SEC-004/005/006`, P2).** `load_snapshot()` and
  `_load_zip_snapshot()` silently returned an empty `Snapshot()` for malformed
  ZIP archives (over the 1000-member cap, over the 256 MiB per-member cap,
  duplicate basenames) instead of raising `ValueError`. The security goal was
  met (no data was loaded) but the error signal was wrong, masking hostile
  input from audit callers. Added a new `strict: bool = False` parameter to
  both functions; the inner `_load_zip_bytes()` now `raise ValueError(...)` for
  the three security-relevant violations and the wrapper re-raises when
  `strict=True`. Default behaviour is preserved for the TUI's resilience path
  (empty snapshot returned, dashboard keeps rendering). JSON-decode failures
  keep the silent fallback because they are not security violations. Three new
  regression tests in `tests/test_loader.py` cover the oversize-member,
  duplicate-basename, and over-cap cases for both default and strict modes.
  Tracked as a re-fix of B1 (the 2026-06-11 entry was incomplete).

### Test infrastructure

- Added the full product-test harness under `.opencode/`, `.product-test/`,
  and `.github/workflows/benchdeck-product-test.yml` so the suite can be
  re-run from a fresh clone. The 2026-06-13 full product test (run id
  `20260613T191610Z-a5e38c42`) is the first run under this harness; full
  report archived at `.test-evidence/20260613T191610Z-a5e38c42/` (gitignored).
- The product-test workflow is `workflow_dispatch` only; trigger it manually
  from the Actions tab when you want a full re-run, optionally with a
  dedicated OpenAI test key as a repo secret to close the `BLOCKED` live
  evidence item.
- Excluded `.opencode/` and `.product-test/` from the product ruff config
  (`extend-exclude` in `pyproject.toml`) so the harness scripts can use a
  different style without breaking the product lint/format gates.

### Verification

- 352 tests pass (2 skipped — pre-existing `OPENAI_API_KEY` conditional skips)
- 81% coverage
- `ruff check`, `ruff format --check`, `mypy src/benchdeck/` all clean
- 2026-06-13 product test: 0 P0, 0 P1, 1 P2 (this fix), 5 P3

## 0.1.0 — 2026-06-10

- Initial benchmark runner and live narrow-terminal TUI.
- Atomic artifact checkpoints.
- Explicit 0-4 scoring scale.
- Empty-response retries and raw response diagnostics.
- Separate policy-block and infrastructure-failure accounting.
- Original benchmark bundle included as a regression fixture.

### Known Issues (resolved post-v0.1.0)

- **ZIP duplicate basename silently overwrites (BUG-3).** Two ZIP entries sharing the same
  basename in different directories result in a silent last-one-wins overwrite rather than
  raising an error. See `REMAINING_ISSUES.md` BUG-3. *(resolved in subsequent patch)*
- **Redundant gate-override dead code in runner (DEAD-6).** `runner.py:_judge_case` contains
  a post-hoc gate-fail assignment that the model validator already enforces. See
  `REMAINING_ISSUES.md` DEAD-6. *(resolved in subsequent patch)*
- **`object.__setattr__` on non-frozen model (STYLE-1).** `CaseJudgment._gate_fail_forces_fail`
  uses `object.__setattr__` for a model that is not frozen. See `REMAINING_ISSUES.md`
  STYLE-1. *(resolved in subsequent patch)*
