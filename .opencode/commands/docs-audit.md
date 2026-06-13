---
description: Audit repository documentation against verified implementation without editing files
agent: repository-docs
subtask: true
---

Run in AUDIT mode.

Scope supplied by the user: `$ARGUMENTS`

If no scope is supplied, audit the complete user-facing documentation set using a token-efficient repository map. Inspect implementation, configuration, tests, examples, CI, and current Git state as evidence. Do not edit files.

Return the documentation inventory, stale-confidence findings, claim evidence ratings, contradictions, missing documentation by audience, prioritized low-risk changes, approval-gated changes, and validation gaps.
