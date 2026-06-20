---
name: benchdeck-screenshot-quality
description: BenchDeck-specific screenshot candidate quality rules. Improves README/demo visual evidence while preserving runtime truth, source safety, golden protections, and artifact validation.
---

# BenchDeck screenshot quality

Use this skill when generating or reviewing BenchDeck TUI screenshot candidates, README screenshot updates, or visual evidence handoffs. It is for artifact quality and validation language, not for source edits.

## Screenshot read

Before generation or review, state one line:

> Reading this as: evidence screenshots for a terminal benchmark dashboard, where clarity, truthfulness, and narrow-width legibility matter more than visual decoration.

## Source of truth

- The current renderer, approved run directory or ZIP, and repository script are the source of truth.
- Screenshots are evidence artifacts, not product specifications.
- Do not invent a second renderer.
- Do not edit source, tests, CI, dependencies, docs, `.opencode`, generated goldens, or Git history.
- Do not replace goldens as troubleshooting.

## Candidate quality rules

A useful BenchDeck screenshot should show:

- the screen or state requested by the parent task
- visible title/status context
- enough benchmark data to demonstrate the surface
- rating or status vocabulary clearly enough to read
- no obvious clipping unless the task is testing clipping behavior
- no leaked secrets, tokens, paths, or credentials
- no viewer window chrome or interactive-only overlay unless explicitly requested
- dimensions that match the requested width profile

## Width guidance

Default screenshot candidates should include:

- `32` columns for minimum/mobile proof
- `80` columns for standard comparison proof

Add wider widths only when the parent task explicitly validates expansion, multi-column layout, or docs presentation.

## README/demo review rules

For screenshots intended for README or docs:

- Prefer a small set of representative states over many redundant captures.
- Caption what the screenshot proves, not just what screen it shows.
- Preserve honest context such as source run, model, case count, or fixture source when available.
- Do not make the screenshot promise behavior that current source/tests do not support.
- Keep visual polish subordinate to evidence value.

## Validation checklist

For every produced or reviewed artifact, record:

- path
- source kind: run directory, ZIP, fixture, or other approved source
- format
- byte size
- hash when available
- dimensions or width profile
- expected count versus actual count
- decode/reload result when applicable
- visible clipping/wrapping/focus/help/status observations
- final Git status or diff metadata when available

Use statuses: `Passed`, `Failed`, `Blocked`, `Not Executed`, `Not Applicable`.

## Completion report

Return to the parent agent:

1. Result
2. Artifacts produced or reviewed
3. Source and command evidence
4. Widths and dimensions
5. Validation results
6. Limitations
7. Approval-gated next actions
