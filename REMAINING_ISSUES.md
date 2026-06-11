# BenchDeck — Remaining Issues (Post-Audit Cleanup)

**Date:** 2026-06-11
**Baseline:** 145 tests pass · ruff clean · ruff format clean · mypy strict clean (with `--ignore-missing-imports`)
**Status:** 17 of 22 original audit issues resolved. 5 remain (3 code, 1 style, 3 docs, 1 stale baseline block).

---

## Instructions for Agents

Read this file top to bottom before touching any code. Work **one task at a time** in the order listed. After completing each task:

1. Mark it `[x]` in the task list below.
2. Run `pytest -q && ruff check .` to confirm nothing regressed.
3. Move to the next task.

**Do not introduce new features.** Every fix is a correction of a misleading test, dead code, style issue, or stale documentation. Do not refactor beyond the scope of each fix. Do not commit unless the operator explicitly requests it.

---

## Task List

### CODE — Runtime/behavior corrections

- [ ] **BUG-3** Fix misleading test assertion in `test_zip_duplicate_basename_not_rejected`
- [ ] **DEAD-6** Remove redundant gate-override block in `runner.py` after `model_validate()` call
- [ ] **STYLE-1** Replace `object.__setattr__` with plain assignment in `models.py:_gate_fail_forces_fail`

### STYLE — Non-breaking cleanup

- [ ] **STYLE-2** Move inline imports inside test functions to module level in `test_tui_loading.py`

### DOCS — Stale documentation updates

- [ ] **DOCS-1** Update `IMPLEMENTATION_CHECKLIST.md` TUI section — confirm BUG-1/BUG-2 were resolved
- [ ] **DOCS-2** Update `OPENCODE_IMPLEMENTATION_PHASES.md` KNOWN BASELINE block — replace stale claims
- [ ] **DOCS-3** Add Known Issues section to `CHANGELOG.md` v0.1.0 entry

---

## Detailed Fix Specifications

---

### BUG-3 — Misleading Test Assertion for Duplicate ZIP Basename

**File:** `tests/test_tui_loading.py`, lines 100–112

**Root cause:** The assertion at line 112 reads `assert snapshot.metadata is not None, "Duplicate basenames should be rejected"`. The assertion body passes when duplicates are silently accepted (last-one-wins). The assertion message claims rejection is desired, but the body verifies the exact opposite. This is a corrupted documentation-of-intent.

The test name (`test_zip_duplicate_basename_not_rejected`) is also misleading — it describes a behavioral property ("not rejected") rather than the defect being documented ("silently overwrites").

**Before:**
```python
def test_zip_duplicate_basename_not_rejected() -> None:
    """_load_zip_bytes uses Path(name).name as dict key, silently overwriting
    duplicate filenames."""
    # Two entries with the same basename in different directories.
    duplicate_zip = make_zip_bytes(
        {
            "run_metadata.json": {"status": "completed", "planned_cases": 8},
            "subdir/run_metadata.json": {"status": "running", "planned_cases": 0},
        }
    )
    snapshot = _load_zip_bytes(duplicate_zip)
    # Only the last one wins — no error raised about duplicates.
    assert snapshot.metadata is not None, "Duplicate basenames should be rejected"
```

**After:**
```python
def test_zip_duplicate_basename_silently_overwrites() -> None:
    """Known defect: _load_zip_bytes uses Path(name).name as dict key.
    Two ZIP entries with the same basename in different subdirectories
    result in a silent last-one-wins overwrite. No error is raised.
    This test documents the current (incorrect) behavior. When the
    underlying defect is fixed (duplicate basenames should raise
    ValueError), update this test to assert the ValueError instead.
    """
    duplicate_zip = make_zip_bytes(
        {
            "run_metadata.json": {"status": "completed", "planned_cases": 8},
            "subdir/run_metadata.json": {"status": "running", "planned_cases": 0},
        }
    )
    snapshot = _load_zip_bytes(duplicate_zip)
    # Currently loads without error — documents the known silent-overwrite bug.
    assert snapshot is not None
    assert snapshot.metadata is not None
```

**Verification:**
```bash
pytest tests/test_tui_loading.py -q
```

Do not fix the underlying silent-overwrite behavior — that is a new feature beyond scope.

---

### DEAD-6 — Redundant Gate Override After `model_validate()`

**File:** `src/benchdeck/runner.py`, lines 384–385

**Root cause:** After `CaseJudgment.model_validate(payload)` on line 383, lines 384–385 re-apply gate-fail logic:
```python
if judgment.gate_check.status == GateStatus.FAIL:
    judgment.overall_rating = Rating.FAIL
```

The `CaseJudgment._gate_fail_forces_fail` model validator in `models.py:514-518` already enforces `overall_rating = Rating.FAIL` when `gate_check.status == GateStatus.FAIL` during `model_validate()`. These two lines are dead code — the assignment either does nothing (overwrites FAIL with FAIL) or can never be reached (because the validator would have already set it).

**Before:**
```python
        judgment = CaseJudgment.model_validate(payload)
        if judgment.gate_check.status == GateStatus.FAIL:
            judgment.overall_rating = Rating.FAIL
        return judgment
```

**After:**
```python
        judgment = CaseJudgment.model_validate(payload)
        return judgment
```

**Verification:**
```bash
grep -rn "GateStatus.FAIL" src/benchdeck/runner.py  # should show only the tally line (562), not lines 384-385
pytest tests/test_runner.py tests/test_models.py -q
```

---

### STYLE-1 — `object.__setattr__` on a Non-Frozen Pydantic Model

**File:** `src/benchdeck/models.py`, line 517, inside `CaseJudgment._gate_fail_forces_fail`

**Root cause:** `object.__setattr__` is necessary for frozen Pydantic models (`model_config = ConfigDict(frozen=True)`) because frozen models reject normal attribute assignment with a validation error. `CaseJudgment` is not frozen (no `model_config` with `frozen=True`). A plain assignment is identical in behavior and clearer in intent.

**Before:**
```python
    @model_validator(mode="after")
    def _gate_fail_forces_fail(self) -> CaseJudgment:
        if self.gate_check.status == GateStatus.FAIL and self.overall_rating != Rating.FAIL:
            object.__setattr__(self, "overall_rating", Rating.FAIL)
        return self
```

**After:**
```python
    @model_validator(mode="after")
    def _gate_fail_forces_fail(self) -> CaseJudgment:
        if self.gate_check.status == GateStatus.FAIL and self.overall_rating != Rating.FAIL:
            self.overall_rating = Rating.FAIL
        return self
```

**Verification:**
```bash
pytest tests/test_models.py -q -k "judgment or gate"
pytest tests/test_runner.py -q -k "judge"
```

---

### STYLE-2 — Inline Imports Inside Test Functions

**File:** `tests/test_tui_loading.py`

**Root cause:** `from benchdeck.tui import BenchDeckTUI` appears inside three individual test function bodies (lines 28, 57, 252) rather than at the module-level import block (lines 14–18). Per PEP 8, imports should be at the top of the file.

**Before (module-level import block, lines 14–18):**
```python
from benchdeck.tui import (
    Snapshot,
    _load_zip_bytes,
    load_snapshot,
)
```

**After (module-level import block):**
```python
from benchdeck.tui import (
    BenchDeckTUI,
    Snapshot,
    _load_zip_bytes,
    load_snapshot,
)
```

**Then remove the three inline imports:**
- Line 28: remove `from benchdeck.tui import BenchDeckTUI`
- Line 57: remove `from benchdeck.tui import BenchDeckTUI`
- Line 252: remove `from benchdeck.tui import BenchDeckTUI`

**Verification:**
```bash
grep -n "from benchdeck.tui import BenchDeckTUI" tests/test_tui_loading.py
# Should show only ONE match — at the module-level import block (~line 15)
# Should show ZERO matches inside function bodies (no longer at lines 28, 57, 252)
pytest tests/test_tui_loading.py -q
```

---

### DOCS-1 — `IMPLEMENTATION_CHECKLIST.md` TUI Screen Status

**File:** `IMPLEMENTATION_CHECKLIST.md`, line 26

**Root cause:** The P2 TUI section marks "Overview, case list, case detail, and help screens" as `[x]` complete. The original audit flagged this because BUG-1 (progress bar 0/0) and BUG-2 (judgment overwrite in comparison mode) were bugs in those exact screens. Both bugs have since been resolved — the TUI now uses correct `RunMetadata` field names (`cases_in_plan`/`executions_judged`) and per-case judgment lists. The item should remain `[x]` with a note confirming the resolution.

**Before:**
```
- [x] Overview, case list, case detail, and help screens.
```

**After:**
```
- [x] Overview, case list, case detail, and help screens. (BUG-1 and BUG-2 resolved — TUI uses correct RunMetadata field names and per-agent judgment lists.)
```

**Verification:** Confirm BUG-1 and BUG-2 are actually resolved:
```bash
grep -n "cases_in_plan\|executions_judged" src/benchdeck/tui.py
# Should show lines 123-124 using correct field names
grep -n "judgments_by_case" src/benchdeck/tui.py
# Should show line 157 using defaultdict(list) per-case
```

---

### DOCS-2 — `OPENCODE_IMPLEMENTATION_PHASES.md` Stale Baseline

**File:** `OPENCODE_IMPLEMENTATION_PHASES.md`, lines 40–46

**Root cause:** The KNOWN BASELINE block claims "Existing tests are minimal", "Core runner and OpenAI gateway currently have no meaningful coverage", "Strict mypy reports errors", "Formatting check is not clean", "The bundled frozen plan is invalid", and "Comparison-mode data is not agent-scoped". All of these claims are now false — the codebase has 145 tests, all checks pass clean, and agent-scoped identity is enforced throughout.

**Before:**
```
KNOWN BASELINE
- Existing tests are minimal.
- Core runner and OpenAI gateway currently have no meaningful coverage.
- Strict mypy reports errors in the gateway and TUI.
- Formatting check is not clean.
- The bundled frozen plan is invalid.
- Comparison-mode data is not agent-scoped.
```

**After:**
```
KNOWN BASELINE (updated 2026-06-11)
- 145 tests pass across gateway, runner, models, prompts, reporting, scoring, storage, and TUI.
- ruff check, ruff format --check, and mypy (with --ignore-missing-imports) all pass clean.
- Remaining known issues: see REMAINING_ISSUES.md for BUG-3, DEAD-6, STYLE-1, and STYLE-2.
- P1 items not yet implemented: multi-judge aggregation, JSON Schema manifest validation.
- P2 items not yet implemented: TUI subprocess launch/cancel.
- P3 items not yet implemented: package release publishing, signed artifacts, SBOM.
```

**Verification:**
```bash
grep -A10 "KNOWN BASELINE" OPENCODE_IMPLEMENTATION_PHASES.md
# Should show the updated block, not stale claims
```

---

### DOCS-3 — `CHANGELOG.md` Known Issues Section

**File:** `CHANGELOG.md`, after line 10 (end of v0.1.0 entry)

**Root cause:** The v0.1.0 entry lists features but no Known Issues subsection. The original audit identified 4 runtime bugs, all now resolved except BUG-3 (which is a test/documentation issue, not a runtime bug). The Known Issues should document the 3 remaining code-level items so users and maintainers can see them at a glance.

**Before:**
```markdown
## 0.1.0 — 2026-06-10

- Initial benchmark runner and live narrow-terminal TUI.
- Atomic artifact checkpoints.
- Explicit 0-4 scoring scale.
- Empty-response retries and raw response diagnostics.
- Separate policy-block and infrastructure-failure accounting.
- Original benchmark bundle included as a regression fixture.
```

**After:**
```markdown
## 0.1.0 — 2026-06-10

- Initial benchmark runner and live narrow-terminal TUI.
- Atomic artifact checkpoints.
- Explicit 0-4 scoring scale.
- Empty-response retries and raw response diagnostics.
- Separate policy-block and infrastructure-failure accounting.
- Original benchmark bundle included as a regression fixture.

### Known Issues

- **ZIP duplicate basename silently overwrites (BUG-3).** Two ZIP entries sharing the same
  basename in different directories result in a silent last-one-wins overwrite rather than
  raising an error. See `REMAINING_ISSUES.md` BUG-3.
- **Redundant gate-override dead code in runner (DEAD-6).** `runner.py:_judge_case` contains
  a post-hoc gate-fail assignment that the model validator already enforces. See
  `REMAINING_ISSUES.md` DEAD-6.
- **`object.__setattr__` on non-frozen model (STYLE-1).** `CaseJudgment._gate_fail_forces_fail`
  uses `object.__setattr__` for a model that is not frozen. See `REMAINING_ISSUES.md` STYLE-1.
```

**Verification:**
```bash
grep -A5 "Known Issues" CHANGELOG.md
# Should show the new subsection with the three items
```

---

## Final Verification Sequence

After all tasks above are marked `[x]`, run this full sequence and confirm every line passes:

```bash
ruff check .
ruff format --check .
python -m mypy --no-incremental src/benchdeck --ignore-missing-imports
pytest -q
```

Expected outcome:
- `ruff check .` → `All checks passed!`
- `ruff format --check .` → all files formatted
- `mypy` → `Success: no issues found in 12 source files`
- `pytest -q` → all tests passed (count must be >= 145; expected 145)

---

## Items Intentionally Deferred (Out of Scope)

- **ZIP duplicate basename silent-overwrite underlying behavior.** Fixing the actual overwrite (raising ValueError or preserving both entries) is a new feature beyond scope of this cleanup. Only the test documentation is corrected.
- **Multi-judge aggregation.** P1 feature, not yet implemented.
- **TUI subprocess launch/cancel.** P2 feature, not yet implemented.
- **Package release publishing, signed artifacts, SBOM.** P3 items, not yet implemented.
- **`types-jsonschema` stub package.** The `mypy --no-incremental src/benchdeck` invocation (without `--ignore-missing-imports`) reports 1 error about missing stubs for jsonschema. The documented invocation `mypy src/benchdeck/ --ignore-missing-imports` passes clean. Installing `types-jsonschema` is optional.
