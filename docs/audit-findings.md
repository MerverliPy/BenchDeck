# Findings Reproduced from the Supplied Benchmark

> **Note (2026-06-15):** The original `fixtures/original_run.zip` exhibited the defects listed below.
> The fixture was rebuilt in Phase 7 as a deterministic, non-secret, schema-valid v2 fixture.
> `benchdeck inspect fixtures/original_run.zip` now reports `Status: completed`, `Coverage: 8/8`.
> This document is retained as historical context for the original audit findings.

The included `fixtures/original_run.zip` demonstrates these runner defects:

- Case 10 has an empty candidate output without finish-reason or raw-response evidence.
- The tally appears to use a 1-5 conversion despite a documented 0-4 scale.
- A required case was policy-blocked and therefore never evaluated.
- `judge_transcript` duplicates candidate output instead of preserving judge reasoning.
- Run status says `completed` despite incomplete required coverage.
- Clarification cases did not exercise a concrete simulated reply.

Run `benchdeck inspect fixtures/original_run.zip` to reproduce the structural warnings.
