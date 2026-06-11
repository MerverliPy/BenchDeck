# OpenCode Implementation Phases — BenchDeck

This document is designed to be pasted directly into an OpenCode agent. It instructs the agent to inspect the repository, confirm the defects, and then implement the repair in controlled phases.

---

## Master execution prompt

```text
You are operating as the principal engineer responsible for repairing the BenchDeck repository.

MISSION
Make BenchDeck a correctness-first, audit-grade benchmark runner. Do not stop at analysis. Inspect the repository, reproduce the documented defects, add regression tests, and implement the phases below in order.

NON-NEGOTIABLE RULES
1. Work test-first for every reproduced defect.
2. Do not make live OpenAI API calls in tests. Build deterministic fake/scripted gateways.
3. Preserve evidence. No provider response, attempt, parse error, policy block, refusal, or infrastructure failure may be silently discarded.
4. Treat (agent_label, case_id) as the canonical execution identity everywhere.
5. Fail closed: missing, duplicate, extra, or unknown execution identities must prevent validation.
6. Maintain a backward-compatible reader/migration path for existing v1 artifacts where practical; all newly written artifacts must use a versioned v2 contract.
7. Do not weaken types or tests to make checks pass. Do not use broad `Any` as a substitute for modeling.
8. Do not add unnecessary dependencies. Remove unused dependencies.
9. Keep provider-specific normalization inside the gateway boundary.
10. Do not commit, push, publish, or make network calls unless the operator explicitly requests it.
11. After each phase, run the stated verification commands and report exact results.
12. When a requirement conflicts with existing behavior, prioritize benchmark correctness, evidence integrity, and explicit migration over silent compatibility.

BASELINE COMMANDS
Run these before editing and preserve their output in your work log:

python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck
pytest -q
pytest --cov=benchdeck --cov-branch --cov-report=term-missing
python -m build

KNOWN BASELINE (updated 2026-06-11)
- 145 tests pass across gateway, runner, models, prompts, reporting, scoring, storage, and TUI.
- ruff check, ruff format --check, and mypy (with --ignore-missing-imports) all pass clean.
- Remaining known issues: see REMAINING_ISSUES.md for BUG-3, DEAD-6, STYLE-1, and STYLE-2.
- P1 items not yet implemented: multi-judge aggregation, JSON Schema manifest validation.
- P2 items not yet implemented: TUI subprocess launch/cancel.
- P3 items not yet implemented: package release publishing, signed artifacts, SBOM.

DELIVERY FORMAT
For each phase:
A. state the defect/invariant being addressed;
B. list files changed;
C. show tests added;
D. implement the code;
E. run verification;
F. summarize residual risk;
G. continue automatically to the next phase unless blocked by an actual repository/environment failure.
```

---

# Phase 0 — Lock the defects with regression tests

## Paste into OpenCode

```text
PHASE 0: CREATE A RELIABLE REGRESSION HARNESS

Goal:
Reproduce and lock the current correctness failures before changing production behavior.

Tasks:
1. Add deterministic fake gateway classes capable of scripting:
   - successful text responses;
   - successful structured responses;
   - empty responses followed by success;
   - malformed JSON;
   - schema-invalid JSON;
   - nested provider policy errors;
   - explicit refusals;
   - timeouts and retryable/non-retryable errors;
   - token usage and request IDs.

2. Add tests proving the current defects. The tests should initially fail against old behavior and pass after later phases:
   - two-agent judgments require agent attribution;
   - Agent A and Agent B results cannot share a judgment lookup;
   - duplicate judgments for case 1 cannot compensate for missing case 2;
   - duplicate plan case IDs are rejected;
   - empty plans are rejected;
   - missing required benchmark families are rejected;
   - nested `body.error.code=cyber_policy` is classified as a policy block;
   - refusal takes precedence over generic `completed` item status;
   - malformed judge JSON retains response capture;
   - schema-invalid planner JSON retains response capture;
   - all retry attempts are preserved;
   - an output directory containing a prior run cannot silently produce a mixed run;
   - the TUI pairs results/judgments by agent and case;
   - ZIP duplicate basename and decompression-limit conditions are rejected;
   - the README frozen-plan path is schema-valid.

3. Create reusable fixtures/builders for:
   - a valid one-agent plan;
   - a valid two-agent plan;
   - all required families;
   - complete execution ledgers;
   - policy/infrastructure terminal outcomes.

4. Do not rewrite production architecture yet except for tiny seams required to inject fake gateways.

Likely files:
- tests/conftest.py
- tests/fakes.py
- tests/test_runner.py
- tests/test_gateway.py
- tests/test_models.py
- tests/test_reporting.py
- tests/test_tui_loading.py
- tests/test_cli.py
- src/benchdeck/runner.py only for dependency-injection seams

Acceptance criteria:
- Tests make each listed invariant explicit.
- No test invokes the network.
- Existing tests remain passing.
- Test names explain the business failure, not only implementation details.

Verification:
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck tests
pytest -q
```

---

# Phase 1 — Repair identity, plan contracts, and comparison semantics

## Paste into OpenCode

```text
PHASE 1: MAKE (AGENT, CASE) THE CANONICAL IDENTITY

Goal:
Eliminate cross-agent data collapse and malformed-plan ambiguity.

Data-model requirements:
1. Add an immutable execution key:

   class ExecutionKey(BaseModel):
       agent_label: str
       case_id: int

2. Add `agent_label` to CaseJudgment and every terminal event/record that can be tied to an execution.
3. Prefer a canonical ExecutionRecord/ExecutionLedger model over unrelated flat arrays.
4. Add `schema_version` and `run_id` to newly persisted artifacts or their envelope.
5. Replace unconstrained strings with enums/literals:
   - benchmark mode;
   - clarification expectation;
   - stage;
   - terminal execution state.

Plan validators:
- cases must be non-empty;
- IDs must be unique positive integers;
- generated plans must have 8–12 cases unless configuration explicitly overrides this;
- required families must all be represented;
- mode must match agent count;
- reject unknown/typo fields in stable v2 contracts;
- validate all case prompts/titles are non-empty;
- require at least one hard-fail or explicitly document why a case has none.

Runtime requirements:
- Construct the complete expected key set before execution.
- Track counters as:
  - cases_in_plan;
  - agents_in_run;
  - executions_planned;
  - executions_attempted;
  - executions_model_completed;
  - executions_judged;
  - policy_blocks;
  - infrastructure_failures.
- Do not overload `planned_cases` to mean both plan cases and executions.

Scoring/reporting requirements:
- Build independent tallies for each agent.
- Build independent validation verdicts for each agent.
- Only create a comparison summary after both sides pass identity integrity checks.
- A comparison result must show wins/losses/ties by matched case key and family.
- Never average Agent A and Agent B together into a single family score.

Backward compatibility:
- Add a v1 reader that can load single-agent artifacts.
- For v1 comparison artifacts with ambiguous judgments, mark attribution as unavailable and the comparison as invalid; do not guess.

Primary files:
- src/benchdeck/models.py
- src/benchdeck/runner.py
- src/benchdeck/scoring.py
- src/benchdeck/reporting.py
- src/benchdeck/inspect.py
- tests/*

Acceptance criteria:
- Exact set equality is required between expected and terminal execution keys.
- Duplicate, missing, extra, and unknown keys produce explicit validation diagnostics.
- Two-agent scoring is fully isolated.
- The previously reproduced cross-agent TUI/scoring failures are impossible at the model/API level.

Verification:
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck tests
pytest -q tests/test_models.py tests/test_scoring.py tests/test_reporting.py tests/test_runner.py
```

---

# Phase 2 — Redesign gateway reliability and evidence preservation

## Paste into OpenCode

```text
PHASE 2: MAKE EVERY PROVIDER ATTEMPT DURABLE AND CLASSIFIABLE

Goal:
No failed response or retry attempt may disappear, and provider behavior must be bounded and reproducible.

Implement typed models similar to:

- UsageDetails
  - input_tokens
  - output_tokens
  - total_tokens
  - cached_input_tokens
  - reasoning_tokens
  - any provider-specific details retained in an extension field

- ErrorRecord
  - category: policy | refusal | timeout | rate_limit | transport | provider | parse | validation | unknown
  - message
  - http_status
  - provider_type
  - provider_code
  - request_id
  - retryable
  - raw_error

- ResponseAttempt
  - attempt_number
  - started_at/completed_at
  - response_id/request_id
  - provider status
  - semantic finish reason
  - output text
  - refusal record
  - usage
  - error
  - raw response reference or raw response according to capture policy

- GenerationResult[T]
  - value: T | None
  - attempts: list[ResponseAttempt]
  - terminal_error: ErrorRecord | None
  - parse_error/validation_error when applicable

Behavior requirements:
1. Persist/carry capture before JSON parsing or Pydantic validation.
2. Preserve every empty response attempt; do not overwrite earlier attempts.
3. Normalize both SDK objects and dictionaries without unsafe `.get()` assumptions.
4. Recursively normalize nested provider errors, including `body.error.code`.
5. Detect refusal before generic completion status.
6. Classify retryability centrally.
7. Configure explicit project-level timeout values.
8. Choose one retry owner:
   - preferred: set SDK `max_retries=0` and implement a fully observable bounded retry loop;
   - acceptable alternative: use SDK retries but capture accurate transport-attempt telemetry through supported hooks.
9. Use bounded exponential backoff with jitter.
10. Never retry policy blocks, refusals, schema validation failures, or deterministic bad requests.
11. Separate logical call count from HTTP attempt count.
12. Make gateway/client injection first-class for tests.
13. Add output-token limits to every call.

Structured output:
- Prefer SDK-supported structured parsing for planner and judge output.
- Even with structured parsing, preserve the original response attempt and any refusal.
- Do not rely on `json.loads` of unconstrained prose as the primary contract.

Primary files:
- src/benchdeck/openai_gateway.py
- src/benchdeck/models.py
- src/benchdeck/runner.py
- tests/test_gateway.py
- tests/test_runner.py

Acceptance criteria:
- Malformed or invalid structured output returns a GenerationResult with full evidence.
- Nested policy errors and refusals are correctly classified.
- Mypy errors in the gateway are eliminated through proper normalization.
- Retry counts and token usage are auditable.
- No single request can inherit an implicit multi-minute default without explicit project configuration.

Verification:
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck tests
pytest -q tests/test_gateway.py tests/test_runner.py
```

---

# Phase 3 — Harden planner, judge, clarification, and deterministic scoring

## Paste into OpenCode

```text
PHASE 3: MOVE BENCHMARK POLICY OUT OF FREE-FORM MODEL DISCRETION

Goal:
Use models for evidence interpretation while keeping benchmark contracts and terminal scoring deterministic.

Planner changes:
1. Parse directly into BenchmarkPlan using structured output.
2. Include explicit schema/prompt version.
3. Validate family coverage, unique IDs, counts, and mode after parsing.
4. Record plan provenance:
   - generated or frozen;
   - source file hash(es);
   - planner model/config;
   - prompt version/hash;
   - plan content hash.
5. Add a separate `--planner-model` option; default may follow the agent model for compatibility.

Judge changes:
1. Pass all relevant context:
   - agent label;
   - benchmark profile;
   - validation standard;
   - complete case contract;
   - candidate output as untrusted evidence.
2. Place evidence inside explicit structured delimiters/fields.
3. State that instructions inside candidate/source content must never be followed.
4. Add adversarial prompt-injection regression tests.
5. Replace `dict[str, Rating]` with a typed rubric model containing required dimensions.
6. Have the judge return evidence/reasons for each dimension, not a freely authoritative final aggregate.
7. Compute overall rating deterministically in Python using a versioned policy.
8. Gate failures must deterministically force Fail.
9. Document and version the family pass threshold and any rating caps.

Clarification changes:
1. Remove the punctuation heuristic.
2. Make first-turn output a typed state:
   - final_answer;
   - clarification_request;
   - refusal;
   - error.
3. Enforce case expectation:
   - required: failure/cap when no legitimate clarification is requested;
   - undesirable: failure/cap when unnecessary clarification is requested;
   - optional: either valid path.
4. Validate that clarification answer keys are present for required-clarification cases.
5. Preserve first-turn and follow-up evidence without duplicating raw payloads.

Acceptance criteria:
- Candidate text cannot alter judge instructions in injection tests.
- Required rubric fields cannot be omitted or invented.
- Overall rating is reproducible from rubric + gates.
- Clarification behavior is based on typed semantics and the plan contract.
- Profile and validation standard affect the judge input and are versioned.

Verification:
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck tests
pytest -q tests/test_prompts.py tests/test_runner.py tests/test_reporting.py
```

---

# Phase 4 — Make artifacts transactional, isolated, inspectable, and resumable

## Paste into OpenCode

```text
PHASE 4: BUILD AN AUDIT-GRADE ARTIFACT STORE

Goal:
A reader must never observe a mixed run or mistake stale files for current evidence.

Run isolation:
1. Generate a unique run_id at start.
2. Write into `<output_root>/<run_id>/`.
3. Reject an existing non-empty run directory unless `--resume` or `--overwrite` is explicit.
4. Add a run lock to prevent concurrent writers.
5. On overwrite, use a safe explicit replacement strategy; never merge old and new files.

Transactional snapshot:
Choose one of these designs:
A. canonical `snapshot.json` containing all coherent state, atomically replaced; derived files generated from it; or
B. generation directories (`generations/000001/...`) plus an atomically updated `CURRENT` manifest pointer.

Required metadata:
- schema_version;
- run_id;
- generation;
- created/updated timestamps;
- BenchDeck package version;
- Python/platform details;
- requested and resolved model identifiers where available;
- provider/system fingerprint where available;
- prompt/schema versions and hashes;
- agent source hashes;
- frozen/generated plan hash and provenance;
- configuration including timeout/retry/budget/capture policy.

Manifest:
- exact expected artifact list;
- SHA-256 and byte size for every artifact;
- canonical generation number;
- terminal/in-progress marker.

Resume:
- reconstruct state from the canonical ledger;
- run only pending/retry-authorized execution keys;
- never duplicate completed judgments;
- validate configuration/source hashes before resuming.

Inspector:
Convert `benchdeck inspect` into a strict validator that checks:
- checksums and generation consistency;
- schema versions;
- expected key equality;
- one terminal outcome per key;
- referential integrity;
- derived counter/tally consistency;
- exact score scale/policy version;
- no ambiguous v1 comparison attribution;
- valid terminal state.
Return non-zero for invalid artifacts and emit machine-readable diagnostics with `--json`.

Capture policy:
- minimal: IDs, status, usage, errors, parsed result; no full raw payload;
- standard: output text plus normalized metadata;
- full: raw provider payload stored once by content hash.
Add configurable redaction before persistence.

Acceptance criteria:
- A forced interruption at any checkpoint leaves either the previous complete generation or the new complete generation, never a mixed snapshot.
- A stale output-directory regression test passes.
- Inspector detects a one-byte mutation through checksum mismatch.
- Resume does not repeat completed work.

Verification:
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck tests
pytest -q tests/test_storage.py tests/test_inspect.py tests/test_runner_resume.py
```

---

# Phase 5 — Control token use, request growth, and cost

## Paste into OpenCode

```text
PHASE 5: ADD EXPLICIT RESOURCE BUDGETS AND REDUCE REPEATED CONTEXT

Goal:
Make request volume and token/cost exposure predictable before a run starts and observable afterward.

CLI/config additions:
- --max-output-tokens-planner
- --max-output-tokens-agent
- --max-output-tokens-judge
- --max-logical-requests
- --max-http-attempts
- --max-total-input-tokens
- --max-total-output-tokens
- optional --max-estimated-cost
- --capture-level minimal|standard|full
- --prompt-cache-retention where supported
- --planner-model

Preflight:
1. Compute planned execution count from agents × cases.
2. Estimate logical calls:
   1 planner + initial calls + possible clarification calls + judge calls.
3. Estimate repeated static input from agent files and judge instructions.
4. Reject before execution when hard request/token ceilings cannot accommodate the plan.
5. Print a clear preflight budget table.

Runtime budgets:
- Check budgets before every logical call and retry.
- Stop with an explicit budget-exhausted terminal reason.
- Persist partial evidence and mark remaining keys pending/not-run.
- Do not classify budget exhaustion as an agent failure.

Prompt optimization:
1. Put stable repeated prefixes before dynamic data.
2. Add stable cache keys/versioned prefixes where supported.
3. Track cached input tokens and cache hit effectiveness.
4. Avoid repeating the first output in multiple nested fields.
5. Store full raw response once by hash in full-capture mode.
6. Use structured clarification deltas rather than redundant prose.
7. Keep output token limits tight and stage-specific.
8. Do not truncate benchmark evidence silently. Emit a typed context-limit outcome.

Usage reporting:
Report:
- logical calls;
- HTTP attempts;
- input/output/cached/reasoning tokens;
- usage by planner/agent/clarification/judge;
- usage by agent;
- usage by case;
- estimated cost only when an explicit price table/version is supplied.

Tests:
- preflight refusal when request ceiling is too low;
- runtime stop before exceeding token ceiling;
- cached/reasoning token fields aggregate correctly;
- retries count as HTTP attempts but not new logical calls;
- capture deduplication preserves referential integrity.

Acceptance criteria:
- Every provider call has an explicit output-token cap.
- A run cannot exceed configured hard budgets.
- Reported logical calls and attempts are independently correct.
- Large raw responses are not duplicated across artifact fields.

Verification:
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck tests
pytest -q tests/test_budget.py tests/test_usage.py tests/test_gateway.py tests/test_runner.py
```

---

# Phase 6 — Repair TUI and user-visible inspection

## Paste into OpenCode

```text
PHASE 6: MAKE THE TUI DISPLAY ONLY COHERENT, ATTRIBUTED DATA

Goal:
The mobile TUI must never pair artifacts from different executions or silently hide corruption.

Identity/UI:
1. Represent rows by ExecutionKey(agent_label, case_id).
2. Show agent label in list and detail views.
3. Add an agent filter/toggle and a side-by-side comparison view where terminal dimensions allow it.
4. Display per-agent tally and verdict separately.
5. Show policy and infrastructure terminal outcomes for the selected execution.
6. Show artifact schema/run/generation and whether inspector validation passed.

Navigation:
- keep selection visible by adjusting viewport;
- clamp selection and scroll offsets;
- handle terminal resize;
- guard optional curses capabilities such as cursor visibility;
- display parse/validation errors rather than converting malformed JSON to empty data.

ZIP safety:
- allow only an approved artifact allowlist;
- cap member count;
- cap per-member and total uncompressed bytes;
- reject duplicate expected basenames/paths;
- reject encrypted or unsupported entries;
- do not repeatedly re-decompress unchanged ZIPs every refresh cycle;
- detect archive changes using stat/hash before reload.

Live directory reads:
- read only the current canonical generation;
- verify manifest before rendering;
- retain the last known-good snapshot if a refresh is invalid and show an error banner.

Tests:
- two-agent case pairing;
- offscreen navigation;
- malformed JSON visible error;
- mixed-generation rejection;
- duplicate ZIP path rejection;
- ZIP size/member limits;
- infrastructure record rendering.

Acceptance criteria:
- No lookup is keyed by case ID alone in comparison mode.
- The TUI never silently defaults corrupt required artifacts to `{}` or `[]`.
- ZIP loading is bounded.
- Strict mypy passes, including the prior TUI Optional/int error.

Verification:
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck tests
pytest -q tests/test_tui.py tests/test_tui_loading.py
```

---

# Phase 7 — Repair fixture, packaging, docs, dependencies, and CI

## Paste into OpenCode

```text
PHASE 7: MAKE THE RELEASE AND REPRODUCTION SURFACE TRUE

Goal:
Every documented command must work from a clean installed package, and the fixture must be internally consistent.

Fixture:
1. Replace `fixtures/original_run.zip` with a deterministic, non-secret, schema-valid v2 fixture.
2. Include a complete plan, execution ledger/results, judgments, tally, verdict, metadata, and manifest.
3. Ensure all counts and hashes reconcile.
4. Add a deterministic fixture-builder script rather than hand-editing binary ZIP content.
5. Remove or repair the stale Base64 materialization workflow and README claims.
6. Add CI that builds the fixture and compares its hash or validates semantic equivalence.

Packaging:
1. Decide which docs/examples/schemas/fixtures are public package assets.
2. Include required assets in wheel and sdist, or expose commands that generate/access them without repository-relative paths.
3. Add wheel install smoke tests in an isolated environment.
4. Verify console entry points.
5. Add a constraints/lock strategy for reproducible CI while maintaining sensible library dependency ranges.
6. Remove `jsonschema` if it remains unused. Otherwise wire it into explicit artifact validation and package the schemas.

README/docs:
1. Execute every shell/Python example in CI where practical.
2. Fix frozen-plan instructions.
3. Document:
   - single vs comparison semantics;
   - exact coverage requirements;
   - policy/infrastructure exclusions;
   - status state machine;
   - rubric and family thresholds;
   - resource budgets;
   - capture/privacy modes;
   - artifact versions and migration;
   - reproducibility limitations.
4. Do not call a synthetic fixture a lossless original run unless it is demonstrably so.

CI gates:
- ruff check .
- ruff format --check .
- mypy --no-incremental src/benchdeck tests
- pytest with branch coverage
- overall coverage >= 85%
- 100% coverage for deterministic identity/scoring/status modules
- python -m build
- install wheel in clean environment
- CLI smoke tests
- fixture build + strict inspect
- README/frozen-plan smoke test

Acceptance criteria:
- The frozen-plan README workflow succeeds from the built wheel.
- Wheel/sdist contain all assets required by documented behavior.
- No declared dependency is unused.
- CI fails on type, format, coverage, fixture, package, or README regressions.

Verification:
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck tests
pytest --cov=benchdeck --cov-branch --cov-report=term-missing --cov-fail-under=85
python -m build
# install and smoke-test the wheel in a fresh virtual environment
```

---

# Phase 8 — Final audit and release gate

## Paste into OpenCode

```text
PHASE 8: PERFORM THE FINAL RELEASE AUDIT

Goal:
Prove that the repaired system satisfies all invariants and no known critical defect remains.

Required scenarios using scripted gateways:
1. Single agent, 8 cases, all families, no clarification, complete success.
2. Single agent with required and undesirable clarification cases.
3. Two agents with different outcomes on the same cases.
4. One policy-blocked execution.
5. One provider timeout that succeeds on retry.
6. One non-retryable provider error.
7. Malformed planner structured output.
8. Schema-invalid judge output.
9. Explicit refusal.
10. Budget exhaustion before a call.
11. Interrupted run resumed without duplicate work.
12. Corrupted artifact detected by inspector.
13. Safe loading of the packaged fixture in TUI.
14. Attempted judge prompt injection in candidate output.

Invariant checks:
- expected execution keys equal terminal execution keys for complete runs;
- no duplicate terminal outcome;
- no cross-agent score contamination;
- no validation with missing family coverage;
- no validation with policy/infrastructure exclusions unless benchmark policy explicitly and versionedly permits it;
- every failed provider/parse/validation attempt has evidence;
- all hard budgets are respected;
- all reports derive from the canonical ledger/snapshot;
- TUI and inspector agree with canonical data;
- package-installed README commands work.

Run the complete gate:
ruff check .
ruff format --check .
mypy --no-incremental src/benchdeck tests
pytest --cov=benchdeck --cov-branch --cov-report=term-missing --cov-fail-under=85
python -m build

Then produce a final engineering report containing:
- files changed;
- migrations introduced;
- exact test counts and coverage;
- benchmark invariants now enforced;
- token/cost controls added;
- known residual risks;
- commands for users to run, inspect, resume, and view a benchmark;
- confirmation that no live API calls were made during tests.

Do not declare release-ready if any P0/P1 invariant remains untested or any quality gate fails.
```

---

# Suggested target interfaces

These are design targets, not mandatory names. Preserve the semantics even if repository conventions suggest different names.

## Runner dependency injection

```python
class BenchmarkRunner:
    def __init__(
        self,
        ...,
        planner_gateway: GatewayProtocol | None = None,
        agent_gateway: GatewayProtocol | None = None,
        judge_gateway: GatewayProtocol | None = None,
        clock: ClockProtocol | None = None,
        sleeper: SleeperProtocol | None = None,
    ) -> None: ...
```

## Gateway protocol

```python
class GatewayProtocol(Protocol):
    def generate_text(self, request: TextGenerationRequest) -> GenerationResult[str]: ...
    def generate_structured(
        self,
        request: StructuredGenerationRequest[T],
    ) -> GenerationResult[T]: ...
```

## Exact coverage validator

```python
def validate_execution_coverage(
    expected: set[ExecutionKey],
    ledger: ExecutionLedger,
) -> CoverageReport:
    # Report missing, extra, duplicate, and conflicting terminal keys.
    ...
```

## Per-agent result

```python
class AgentBenchmarkVerdict(BaseModel):
    agent_label: str
    coverage: CoverageReport
    tally: AgentTally
    verdict: Literal["validated", "not_validated", "inconclusive"]
    reasons: list[str]
```

## Run-level result

```python
class BenchmarkRunVerdict(BaseModel):
    status: RunStatus
    agents: dict[str, AgentBenchmarkVerdict]
    comparison: ComparisonVerdict | None
```

---

# Final implementation cautions

- Do not “fix” comparison mode by merely adding `agent_label` to JSON while retaining case-only dictionaries elsewhere. Search every lookup, grouping, join, counter, report, and TUI selection.
- Do not derive complete coverage from counts. Always compare exact key sets.
- Do not catch broad exceptions and write only `str(exc)` when provider capture exists.
- Do not silently accept old ambiguous comparison artifacts. Mark them invalid/unattributable.
- Do not add caching without recording whether it actually reduced billed/processed input.
- Do not estimate cost from an unversioned hard-coded price table.
- Do not silently truncate agent source, candidate output, or judge evidence.
- Do not let a model decide deterministic bookkeeping, identity, thresholds, or state transitions.
- Do not allow the TUI to be a second independent interpretation of artifacts; it must consume the same validated snapshot/reader as the inspector.
