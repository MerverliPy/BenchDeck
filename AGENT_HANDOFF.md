# BenchDeck — Agent Handoff & Audit Findings

**Audit date:** 2026-06-11
**Audited version:** 0.1.0
**Baseline:** 145 tests pass · ruff clean · mypy strict clean · ruff format clean

---

## Instructions for Agents

Read this file top to bottom before touching any code. Work **one task at a time** in the order listed. After completing each task:

1. Mark it `[x]` in the task list below.
2. Run `pytest -q && ruff check .` to confirm nothing regressed.
3. Move to the next task.

**Do not introduce new features.** Every fix is a correction of existing broken or dead code, or a documentation update. Do not refactor beyond the scope of each fix. Do not commit unless the operator explicitly requests it.

---

## Repository Snapshot

BenchDeck is a Python 3.11+ evidence-preserving LLM-agent benchmark harness with a live curses TUI. The package is functionally complete for its stated P0 goals. The overall code quality is high — strict mypy, ruff lint, and ruff format all pass clean, and all 145 tests pass. However the audit found real runtime bugs, design/UX issues, dead-code accumulations, and stale documentation that must be addressed before the project can be considered release-ready.

| Check | Current State |
|---|---|
| `pytest -q` | 145 passed |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 23 files already formatted |
| `mypy --no-incremental src/benchdeck` | Success: no issues found in 12 source files |

---

## Task List

### BUGS — Runtime failures, incorrect behavior

- [ ] **BUG-1** Fix TUI progress bar always showing 0/0 (wrong field names in `_overview`)
- [ ] **BUG-2** Fix TUI case-list silently dropping second agent's judgments in comparison mode
- [ ] **BUG-3** Fix misleading test assertion in `test_tui_loading.py` for duplicate basename case
- [ ] **BUG-4** Fix transient HTTP 5xx errors (500, 502, 503) not being retried in the gateway

### DESIGN ISSUES — Incorrect behavior, poor UX, silent failures

- [ ] **DESIGN-1** Fix default `--model` / `--judge-model` CLI args (`"gpt-5.5"` does not exist; all default runs fail at the first API call)
- [ ] **DESIGN-2** Fix `run_id` collision risk (second-precision timestamp; two runs started in the same second get identical IDs)
- [ ] **DESIGN-3** Fix `prompt_version` mismatch (`BenchmarkPlan` stores `"1"` but `PLANNER_SCHEMA_VERSION` is `"2"`)
- [ ] **DESIGN-4** Add pre-flight check for missing `OPENAI_API_KEY` in `cli.main()` with a clear error message
- [ ] **DESIGN-5** Wrap `runner.run()` in `cli.main()` with a top-level exception handler to prevent raw tracebacks on infrastructure failure

### DEAD CODE — Remove safely; do not change any behavior

- [ ] **DEAD-1** Remove three unused enums from `models.py`: `BenchmarkMode`, `Stage`, `ClarificationState`
- [ ] **DEAD-2** Remove unused constant `REQUIRED_FAMILIES` from `scoring.py`
- [ ] **DEAD-3** Remove unused public method `generate_structured()` from `openai_gateway.py`
- [ ] **DEAD-4** Remove unused constant `JUDGE_PROMPT_VERSION` from `prompts.py`
- [ ] **DEAD-5** Remove unused instance attributes `_external_agent_gateway` / `_external_judge_gateway` from `runner.py`
- [ ] **DEAD-6** Remove redundant gate-override block in `runner.py` after `model_validate()` call

### STYLE / TYPE CLEANUP — Non-breaking

- [ ] **STYLE-1** Replace `object.__setattr__` with plain assignment in `CaseJudgment._gate_fail_forces_fail` (model is not frozen)
- [ ] **STYLE-2** Move inline imports inside test functions to module level in `test_tui_loading.py`

### STALE DOCUMENTATION — Update to match current code

- [ ] **DOCS-1** Update `IMPLEMENTATION_CHECKLIST.md` — TUI screen items marked `[x]` have active known bugs (BUG-1, BUG-2); revert to `[ ]` until those bugs are fixed
- [ ] **DOCS-2** Update `OPENCODE_IMPLEMENTATION_PHASES.md` KNOWN BASELINE section — stale claims about mypy errors and formatting failures
- [ ] **DOCS-3** Update `CHANGELOG.md` — add Known Issues note under v0.1.0 for the bugs found in this audit
- [ ] **DOCS-4** Update `README.md` — replace any `gpt-5.5` references with `gpt-4o` so copy-paste examples work

---

## Detailed Fix Specifications

---

### BUG-1 — TUI Progress Bar Always Shows 0/0

**File:** `src/benchdeck/tui.py`, lines 120–122

**Root cause:** `_overview()` reads field names that do not exist in `RunMetadata`. The code uses `"planned_cases"` and `"judged_cases"` but the actual serialized field names are `"cases_in_plan"` and `"executions_judged"`. The tally fallback also fails because `summary_tally.json` stores per-agent tallies one level deeper (`{"agent_a": {"cases_planned": ...}}`), so `t.get("cases_planned")` always returns `None`.

**Before:**
```python
planned = int(m.get("planned_cases") or t.get("cases_planned") or 0)
judged = int(
    m.get("judged_cases") or t.get("cases_judged") or t.get("cases_completed") or 0
)
```

**After:**
```python
planned = int(m.get("cases_in_plan") or 0)
judged = int(m.get("executions_judged") or 0)
```

**Verification:** Confirm field names against `RunMetadata` in `models.py` before applying. Add or update a test in `test_tui_loading.py` that constructs a `Snapshot` with a realistic `metadata` dict and asserts the rendered overview line contains the correct `judged/planned` count.

---

### BUG-2 — TUI Case List Drops Second Agent's Judgments in Comparison Mode

**File:** `src/benchdeck/tui.py`, line 154

**Root cause:** The dict comprehension keys on `case_id` alone. In comparison mode, two `CaseJudgment` records share the same `case_id` (one per agent). The second overwrites the first silently.

**Before:**
```python
judgments = {j.get("case_id"): j for j in self.snapshot.judgments}
```

**After:** Build a list-of-judgments per case_id so all agents are represented:
```python
from collections import defaultdict
judgment_map: dict[int | None, list[dict[str, object]]] = defaultdict(list)
for j in self.snapshot.judgments:
    judgment_map[j.get("case_id")].append(j)
```

Then in the rendering loop, replace `judgment = judgments.get(case_id)` with `agent_judgments = judgment_map.get(case_id, [])` and render a summary that shows all agents, e.g.:

```python
agent_judgments = judgment_map.get(case_id, [])
if agent_judgments:
    parts = [
        f"{j.get('overall_rating', '?')}[{j.get('agent_label', '?')}]"
        for j in agent_judgments
    ]
    state = " ".join(parts)
elif case_id in blocks:
    state = "BLOCKED"
else:
    state = "PENDING"
```

**Verification:** Update `test_tui_loading.py` to assert that both agents' ratings appear in the case list when two judgments share a `case_id`.

---

### BUG-3 — Misleading Test Assertion for Duplicate ZIP Basename

**File:** `tests/test_tui_loading.py`, test `test_zip_duplicate_basename_not_rejected`

**Root cause:** The assertion `assert snapshot.metadata is not None, "Duplicate basenames should be rejected"` passes when duplicates are silently accepted (last-one-wins). The assertion message claims rejection is desired, but the assertion body verifies the opposite. This is a corrupted documentation-of-intent.

**Fix:** Rename the test to `test_zip_duplicate_basename_silently_overwrites` and update the assertion to explicitly verify the actual (current) behavior — that the snapshot loads without error even with duplicates, and that only one of the two values survived:

```python
def test_zip_duplicate_basename_silently_overwrites(self) -> None:
    """
    Known defect: _load_zip_bytes uses {Path(name).name: name} deduplication.
    Two ZIP entries with the same basename in different subdirectories result
    in the last one winning silently. No error is raised.
    This test documents the current (incorrect) behavior. When the defect is
    fixed (entries with duplicate basenames should raise ValueError), update
    this test to assert the ValueError instead.
    """
    ...
    snapshot = _load_zip_bytes(duplicate_zip)
    # Currently loads without error — documents the known silent-overwrite bug.
    assert snapshot is not None
```

Do not fix the underlying silent-overwrite behavior itself — that is a new feature beyond scope.

---

### BUG-4 — Transient 5xx Errors Not Retried

**File:** `src/benchdeck/openai_gateway.py`, function `_is_retryable`, lines 55–60

**Root cause:** The function returns `False` for any category in `_NON_RETRYABLE`. If `ErrorCategory.PROVIDER` is in `_NON_RETRYABLE`, then HTTP 500/502/503 (which are classified as `PROVIDER`) are never retried.

First, verify by reading `_NON_RETRYABLE` definition in `openai_gateway.py`. If `PROVIDER` is listed there, apply this fix:

**Before:**
```python
def _is_retryable(category: ErrorCategory, http_status: int | None) -> bool:
    if category in _NON_RETRYABLE:
        return False
    if http_status is not None and 400 <= http_status < 500:
        return http_status in {408, 429}
    return True
```

**After:**
```python
def _is_retryable(category: ErrorCategory, http_status: int | None) -> bool:
    # Transient 5xx errors are always retryable regardless of category classification.
    if http_status is not None and 500 <= http_status < 600:
        return True
    if category in _NON_RETRYABLE:
        return False
    if http_status is not None and 400 <= http_status < 500:
        return http_status in {408, 429}
    return True
```

**Verification:** Add tests in `test_gateway.py` for:
- HTTP 500 → retried (should now pass)
- HTTP 502 → retried (should now pass)
- HTTP 503 → retried (should now pass)
- HTTP 400 → not retried (must still pass)
- HTTP 401 → not retried (must still pass)
- HTTP 403 → not retried (must still pass)

---

### DESIGN-1 — Default CLI Model Does Not Exist

**File:** `src/benchdeck/cli.py`, lines 23–24

`"gpt-5.5"` is not a valid OpenAI model identifier. Any user who runs `benchdeck run --agent-a foo.md` without specifying `--model` receives an immediate API error with no helpful context.

**Before:**
```python
run.add_argument("--model", default="gpt-5.5")
run.add_argument("--judge-model", default="gpt-5.5")
```

**After:**
```python
run.add_argument("--model", default="gpt-4o")
run.add_argument("--judge-model", default="gpt-4o")
```

Also search `README.md` for `gpt-5.5` and replace all occurrences with `gpt-4o`.

---

### DESIGN-2 — `run_id` Collision Risk

**File:** `src/benchdeck/models.py`, function `_new_run_id`, line 701

Second-precision timestamps mean two runs started in the same second share an identical `run_id`, which will silently corrupt any system that uses `run_id` as a unique key.

**Before:**
```python
def _new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
```

**After:**
```python
import secrets  # add to imports at top of file if not already present

def _new_run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = secrets.token_hex(4)  # 8 hex chars, 32 bits of entropy
    return f"{ts}-{suffix}"
```

Check that `secrets` is already imported or add it. Do not change the timestamp format — only append the suffix.

---

### DESIGN-3 — `prompt_version` Mismatch in BenchmarkPlan

**File:** `src/benchdeck/models.py`, line 164

`BenchmarkPlan.prompt_version` defaults to `"1"` but `PLANNER_SCHEMA_VERSION` in `prompts.py` is `"2"`. Every generated plan records stale provenance.

**Before:**
```python
prompt_version: str = "1"
```

**After:**
```python
prompt_version: str = "2"
```

After applying: search `test_models.py` and `test_prompts.py` for any assertion that hardcodes the expected value `"1"` for `prompt_version` and update those assertions to `"2"`.

---

### DESIGN-4 — Missing `OPENAI_API_KEY` Pre-flight Check

**File:** `src/benchdeck/cli.py`

Add an `import os` at the top of the file (if not present) and add a check at the start of the `run` command handler, before `BenchmarkRunner` is instantiated:

```python
if args.command == "run":
    import os
    if not os.environ.get("OPENAI_API_KEY"):
        sys.stderr.write(
            "Error: OPENAI_API_KEY environment variable is not set.\n"
            "Set it before running: export OPENAI_API_KEY=sk-...\n"
        )
        return 1
    from .runner import BenchmarkRunner
    ...
```

Note: `os` is already imported in many Python files by convention; check if it is already at the top of `cli.py` before adding a duplicate import.

---

### DESIGN-5 — Raw Traceback on Infrastructure Failure

**File:** `src/benchdeck/cli.py`

`runner.run()` re-raises on infrastructure failures. The exception propagates to the user as a raw Python traceback with no context. Wrap the call:

```python
try:
    status = runner.run()
except Exception as exc:
    sys.stderr.write(f"Error: benchmark run failed — {exc}\n")
    return 1
print(status.value)
return 0 if status.value == "completed" else 2
```

---

### DEAD-1 — Three Unused Enums in `models.py`

**File:** `src/benchdeck/models.py`

The following three enum classes are defined but have **zero references** anywhere in the entire codebase (source or tests):

- `BenchmarkMode` (values: `SINGLE`, `COMPARISON`)
- `Stage` (values: `PLANNER`, `AGENT`, `JUDGE`)
- `ClarificationState` (values: `FINAL_ANSWER`, `CLARIFICATION_REQUEST`, `REFUSAL`, `ERROR`)

**Before removing:** Run the following and confirm zero results:
```bash
grep -r "BenchmarkMode\|Stage\.\|ClarificationState" src/ tests/
```

If zero results, delete all three class definitions. Do not remove `ClarificationExpectation` — that one is used.

---

### DEAD-2 — Unused `REQUIRED_FAMILIES` Constant

**File:** `src/benchdeck/scoring.py`, line 18

**Before removing:** Confirm zero references:
```bash
grep -r "REQUIRED_FAMILIES" src/ tests/
```

If zero results (the constant is defined there, so `scoring.py` itself will appear — that's expected), delete the line. The value is computed inline wherever it's needed via `Family.required_families()`.

---

### DEAD-3 — Unused `generate_structured()` Method

**File:** `src/benchdeck/openai_gateway.py`

**Before removing:** Confirm zero callers:
```bash
grep -r "generate_structured" src/ tests/
```

If the method definition itself is the only result, remove the method from `OpenAIGateway`. Also check `tests/fakes.py` — if `FakeGateway` implements a corresponding stub for `generate_structured`, remove that stub too.

---

### DEAD-4 — Unused `JUDGE_PROMPT_VERSION` Constant

**File:** `src/benchdeck/prompts.py`, line 17

**Before removing:** Confirm zero references:
```bash
grep -r "JUDGE_PROMPT_VERSION" src/ tests/
```

If the constant definition is the only result, delete the line `JUDGE_PROMPT_VERSION = "2"`.

---

### DEAD-5 — Unused `_external_*_gateway` Attributes

**File:** `src/benchdeck/runner.py`, lines 63–64

```python
self._external_agent_gateway = agent_gateway   # set but never read
self._external_judge_gateway = judge_gateway   # set but never read
```

The functional attributes are `self.agent_gateway` and `self.judge_gateway` on the lines immediately below. The `_external_*` variants serve no purpose.

**Before removing:** Confirm no other code reads these:
```bash
grep -r "_external_agent_gateway\|_external_judge_gateway" src/ tests/
```

If only the assignment lines appear, delete both lines.

---

### DEAD-6 — Redundant Gate Override After `model_validate()`

**File:** `src/benchdeck/runner.py`

After the `judgment = CaseJudgment.model_validate(payload)` call, there are lines that re-apply the gate-fail logic:

```python
if judgment.gate_check.status == GateStatus.FAIL:
    judgment.overall_rating = Rating.FAIL
```

The `CaseJudgment._gate_fail_forces_fail` model validator in `models.py` already enforces this constraint during `model_validate()`. These lines are dead code.

Search for this pattern and remove just these two lines. Do not touch the `model_validate()` call or anything around it.

---

### STYLE-1 — `object.__setattr__` on a Non-Frozen Model

**File:** `src/benchdeck/models.py`, inside `CaseJudgment._gate_fail_forces_fail` validator

`object.__setattr__` is only necessary for frozen Pydantic models (`model_config = ConfigDict(frozen=True)`). `CaseJudgment` is not frozen. A plain attribute assignment is identical in behavior and clearer in intent.

**Before:**
```python
object.__setattr__(self, "overall_rating", Rating.FAIL)
```

**After:**
```python
self.overall_rating = Rating.FAIL
```

---

### STYLE-2 — Inline Imports Inside Test Functions

**File:** `tests/test_tui_loading.py`

Imports of `BenchDeckTUI` (and any other `benchdeck` symbols) appear inside individual test method bodies. Move all such imports to the module-level import block at the top of the file per PEP 8.

Search for the pattern:
```bash
grep -n "^\s*from benchdeck" tests/test_tui_loading.py
```

Move each result to the top-level import section.

---

### DOCS-1 — IMPLEMENTATION_CHECKLIST.md Accuracy

**File:** `IMPLEMENTATION_CHECKLIST.md`

The P2 TUI section marks this item as complete:
```
- [x] Overview, case list, case detail, and help screens.
```

BUG-1 (progress always 0/0) and BUG-2 (judgment overwrite in comparison mode) are bugs in exactly those screens. This item should not be marked complete until both bugs are fixed.

**Fix:** Change the line to:
```
- [ ] Overview, case list, case detail, and help screens. (blocked: see AGENT_HANDOFF.md BUG-1, BUG-2)
```

After BUG-1 and BUG-2 are resolved and verified, re-mark this `[x]`.

---

### DOCS-2 — OPENCODE_IMPLEMENTATION_PHASES.md Stale Baseline

**File:** `OPENCODE_IMPLEMENTATION_PHASES.md`, KNOWN BASELINE section (approximately lines 40–46)

The current text states claims that are no longer true. Replace the KNOWN BASELINE block with accurate current state:

**Current (stale):**
```
KNOWN BASELINE
- Existing tests are minimal.
- Core runner and OpenAI gateway currently have no meaningful coverage.
- Strict mypy reports errors in the gateway and TUI.
- Formatting check is not clean.
- The bundled frozen plan is invalid.
- Comparison-mode data is not agent-scoped.
```

**Replacement:**
```
KNOWN BASELINE (updated 2026-06-11 after full audit)
- 145 tests pass across gateway, runner, models, prompts, reporting, scoring, storage, and TUI.
- ruff check, ruff format --check, and mypy --strict all pass clean.
- Known runtime bugs remain: see AGENT_HANDOFF.md for BUG-1 through BUG-4.
- P1 items not yet implemented: multi-judge aggregation, JSON Schema manifest validation.
- P2 items not yet implemented: TUI subprocess launch/cancel, case Markdown export.
- P3 items not yet implemented: package release publishing, signed artifacts, SBOM.
```

---

### DOCS-3 — CHANGELOG.md Known Issues

**File:** `CHANGELOG.md`

Add a Known Issues subsection under the `[0.1.0]` entry:

```markdown
### Known Issues

- **TUI progress bar always shows 0/0** — `_overview()` reads wrong field names from `RunMetadata`; the correct names are `cases_in_plan` and `executions_judged` (BUG-1).
- **TUI case list drops second agent in comparison mode** — judgment dict is keyed on `case_id` only; Agent B's results silently overwrite Agent A's (BUG-2).
- **Default CLI model `gpt-5.5` does not exist** — all users must supply `--model` explicitly or the first API call fails (DESIGN-1; fixed in next release).
- **HTTP 5xx transient errors are not retried** — 500/502/503 responses from the provider are classified as non-retryable and fail immediately (BUG-4).
```

---

### DOCS-4 — README.md Model Name

**File:** `README.md`

Search for all occurrences of `gpt-5.5`:
```bash
grep -n "gpt-5.5" README.md
```

Replace every occurrence with `gpt-4o`. This ensures that any copy-paste command from the README actually works.

---

## Final Verification Sequence

After all tasks above are marked `[x]`, run this full sequence and confirm every line passes:

```bash
ruff check .
ruff format --check .
python -m mypy --no-incremental src/benchdeck
pytest -q
```

Expected outcome:
- `ruff check .` → `All checks passed!`
- `ruff format --check .` → all files formatted
- `mypy` → `Success: no issues found in 12 source files`
- `pytest -q` → all tests passed (count must be >= 145; new tests added for BUG-4 may increase the count)

---

## Items Intentionally Deferred (Out of Scope)

The following were identified during the audit but are **not addressed here** — they are non-breaking style concerns or genuinely new features:

- `_execute()` callback parameters typed as `Any` instead of `Callable` — mypy passes, low risk
- `runner.py` loop variables typed as `dict[str, Any]` instead of concrete model types — mypy passes
- `build_final_verdict` legacy `dict` interface — only used in tests, low risk
- Empty-response backoff uses a separate counter from error-retry backoff — edge case, no user-visible impact in practice
- `_validate_plan` complexity (14 branches) — functional, not causing failures
- Magic HTTP status code integer literals without named constants — style only
- ZIP duplicate basename silent-overwrite (underlying behavior) — new feature, out of scope
- Unimplemented P1/P2/P3 checklist items — new features, out of scope
