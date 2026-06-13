# Implementation Checklist

## P0 — Reliability

- [x] Retry empty model outputs.
- [x] Preserve raw model response, response ID, request ID, status, finish reason, token usage, and errors.
- [x] Classify silent empty output as infrastructure failure rather than agent failure.
- [x] Declare and enforce a single 0-4 rating scale.
- [x] Store candidate output and judge capture separately.
- [x] Use atomic artifact writes for live readers.

## P1 — Coverage semantics

- [x] Track attempted, model-completed, judged, policy-blocked, and infrastructure-failed counts.
- [x] Mark incomplete required coverage as inconclusive.
- [x] Support one concrete simulated clarification reply.
- [x] Include a frozen-plan execution path.
- [x] Add multi-judge aggregation and disagreement reporting.
- [x] Add deterministic JSON Schema validation of agent final manifests.

## P2 — TUI

- [x] Responsive 32-column layout.
- [x] Number and letter controls suitable for phone keyboards.
- [x] Live artifact refresh.
- [x] Overview, case list, case detail, and help screens. (BUG-1 and BUG-2 resolved — TUI uses correct RunMetadata field names and per-agent judgment lists. Infrastructure error display added.)
- [x] Planner capture diagnostics in TUI overview and `benchdeck inspect`.
- [x] Launch/pause/cancel subprocess runs from inside the TUI.
- [x] Export selected case as Markdown.

## P3 — Distribution

- [x] Python package and console entry point.
- [x] CI across Python 3.11-3.13.
- [x] Regression fixture and tests.
- [x] Publish package release.
- [x] Add signed release artifacts and SBOM.
