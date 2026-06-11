# Findings Reproduced from the Supplied Benchmark

The included `fixtures/original_run.zip` demonstrates these runner defects:

- Case 10 has an empty candidate output without finish-reason or raw-response evidence.
- The tally appears to use a 1-5 conversion despite a documented 0-4 scale.
- A required case was policy-blocked and therefore never evaluated.
- `judge_transcript` duplicates candidate output instead of preserving judge reasoning.
- Run status says `completed` despite incomplete required coverage.
- Clarification cases did not exercise a concrete simulated reply.

Run `benchdeck inspect fixtures/original_run.zip` to reproduce the structural warnings.
