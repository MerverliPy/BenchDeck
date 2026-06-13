---
name: repository-docs-validation
description: Validate repository documentation links, paths, commands, examples, factual claims, status labels, and change boundaries before completion.
compatibility: opencode
metadata:
  audience: maintainers
  workflow: repository-documentation
---

# Repository documentation validation

Use after documentation edits or during a read-only verification run.

## Validation hierarchy

1. Run repository-defined documentation checks from the validation profile, CI, or manifests.
2. Run focused tests/build/help commands that verify changed claims.
3. Execute safe supported examples.
4. Perform structured static review for checks that have no executable validator.
5. Mark unavailable checks as **Not run** with the reason.

Never invent a passing result.

## Required checks

### Change boundary

- Only intended documentation files changed.
- No source, generated, dependency, lock, or release artifact changed.
- Unrelated user changes remain intact.

### Structure and navigation

- Valid document syntax for the repository's formats.
- Heading hierarchy is coherent.
- Table-of-contents and anchor links resolve.
- Internal relative links and referenced paths exist.
- Renamed headings or files have updated inbound references.

### Claims

- Feature claims trace to E1/E2 evidence or carry an accurate limitation label.
- Versions, defaults, platforms, flags, APIs, config keys, and environment-variable names match repository evidence.
- Planned, experimental, partial, deprecated, and removed statuses are not conflated.
- No contradictory canonical statements remain.

### Procedures and examples

- Commands are ordered and include prerequisites.
- Safe examples execute when supported.
- Expected output is not presented as exact unless verified.
- Commands with destructive or external effects are not executed without approval.
- Examples do not contain secrets or private data.

### Links

- Local links and anchors are mandatory checks.
- External links are checked only when network access is approved.
- A redirected link is acceptable only when the final destination is authoritative and stable.

### Security review

- Scan changed text for credentials, tokens, private keys, internal URLs, private hostnames, personal data, and copied environment values.
- Report secret class and path only; never repeat the value.

## Result format

| Check | Status | Command/method | Evidence or failure |
|---|---|---|---|

Allowed status values:

- **Passed**
- **Failed**
- **Not run**

A failed material factual check blocks a clean completion. Preserve safe edits and report the blocker.
