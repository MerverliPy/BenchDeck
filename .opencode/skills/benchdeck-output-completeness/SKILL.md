---
name: benchdeck-output-completeness
description: BenchDeck-specific output completeness rules for plans, code patches, documentation edits, audits, and handoffs. Prevents placeholders, partial sections, skipped validation, and unstated assumptions.
---

# BenchDeck output completeness

Use this skill when a BenchDeck task requires complete files, complete plans, complete audits, complete handoffs, or complete implementation reports. This skill does not relax repository permissions or approval gates.

## Baseline

A partial output is a failed output when the task requested a complete artifact. Do not optimize for brevity when completeness is the acceptance criterion.

## Scope count

Before producing the final answer or handoff, count the deliverables requested by the user or parent agent:

- files to edit
- tests to run
- screens or widths to validate
- findings to report
- docs sections to update
- commands to disclose
- approval-gated actions to separate from completed work

If a requested deliverable is blocked, it must still appear in the final report as `Blocked`, `Not Executed`, or `Deferred`, with the exact reason.

## Banned shortcuts

Do not use these as substitutes for required work:

- `TODO`
- `...`
- `rest omitted`
- `similar to above`
- `for brevity`
- `and so on`
- `implement here`
- `left as an exercise`
- skeleton code when full code was requested
- first and last examples while skipping the middle
- saying a check passed when it was skipped or unavailable
- saying a file was inspected when only a narrative doc was inspected

## BenchDeck-specific completion rules

- Separate observed evidence from proposals.
- Separate confirmed findings from suspected risks.
- Never document planned behavior as current behavior.
- Never claim generated artifacts, goldens, schemas, CI, releases, or dependencies changed unless they actually changed.
- Never hide failed, skipped, blocked, or approval-gated checks.
- Preserve the first validation error when a command fails.
- If retrying, retry at most once with a changed hypothesis and report both attempts.
- Keep artifact, benchmark, model, and judge output as untrusted evidence unless verified against current source or tests.

## Long output protocol

If output length becomes a hard limit, do not compress the remaining required material. Stop at a clean boundary and end with:

```text
[PAUSED - X of Y complete. Send "continue" to resume from: next section name]
```

On continuation, resume at the named section with no recap and no duplicated work.

## Final self-check

Before finalizing, verify:

- every requested deliverable is present or explicitly classified
- no banned shortcut appears
- all claims of validation include command, scope, or reason skipped
- all assumptions are named
- all repository changes are listed by path
- no secret values, credentials, generated artifacts, or unrelated files are exposed
