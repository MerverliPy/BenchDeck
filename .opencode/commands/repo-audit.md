---
description: Run a bounded repository audit and produce AGENT_HANDOFF.md
agent: repo-auditor
subtask: true
---

Audit the current repository and create or update `AGENT_HANDOFF.md`.

User scope or priority:

$ARGUMENTS

Treat blank arguments as a broad audit. Treat supplied arguments as priorities, not permission to skip repository instructions, root manifests, workspace configuration, CI, or validation discovery.

Do not implement fixes. Use the existing handoff as a checkpoint when present, but revalidate claims before preserving them. Finish with the agent's required concise summary.
