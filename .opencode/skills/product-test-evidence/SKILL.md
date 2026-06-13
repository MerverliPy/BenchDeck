---
name: product-test-evidence
description: Defines durable evidence records, feature traceability, defect classification, severity, retries, and final verdict rules for sandboxed product testing
license: MIT
compatibility: opencode
metadata:
  workflow: product-testing
---

## Test result record

Every result must include:

- run ID and test ID;
- feature ID;
- interface and evidence class;
- repository commit and dirty-state fingerprint;
- environment/image/container identity;
- preconditions;
- exact command or PTY action script;
- expected result;
- actual result;
- status;
- exit code/signal;
- start, end, and duration;
- stdout/stderr/raw terminal evidence paths;
- created/changed file paths and hashes;
- retry history;
- defect classification and severity;
- reproduction instructions;
- verifier status.

## Evidence classes

- `STATIC_EVIDENCE`
- `SIMULATED_REGRESSION_EVIDENCE`
- `LOCAL_BLACK_BOX_EVIDENCE`
- `PTY_EVIDENCE`
- `LIVE_EXTERNAL_EVIDENCE`
- `INDEPENDENT_REPRODUCTION`

## Status values

- `PASSED`
- `FAILED`
- `BLOCKED`
- `SKIPPED_WITH_REASON`
- `NOT_APPLICABLE`
- `FLAKY`
- `INCONCLUSIVE`

## Severity

- `P0`: credential exposure, host/repository corruption, destructive external action, fabricated validation, or severe compromise.
- `P1`: major product function broken, data integrity failure, unreliable verdict, unsafe sandbox escape, or unrecoverable workflow failure.
- `P2`: important edge case, compatibility, performance, accessibility, or recoverability defect.
- `P3`: minor usability, clarity, diagnostics, or maintainability defect.

## Retry rule

Preserve the first failure. Retry only with a changed hypothesis. Record every attempt and never keep only the passing rerun.

## Final verdict

`PASS` requires complete traceability and appropriate real evidence. Use `BLOCKED` when essential external/platform evidence is unavailable. Use `INCONCLUSIVE` when evidence conflicts or cannot be independently reproduced.
