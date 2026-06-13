# Documentation Validation Profile

> Status: reusable baseline. Add repository-specific commands only after verifying them from manifests, CI, or successful execution.

## Mandatory baseline

For every changed document:

- inspect the final Git diff;
- confirm only intended documentation paths changed;
- verify local links, anchors, and referenced repository paths;
- verify commands, flags, configuration keys, environment-variable names, versions, defaults, and feature statuses against repository evidence;
- verify code-block language tags and example consistency;
- scan changed text for sensitive values;
- re-check canonical-document consistency.

## Repository-defined checks

Populate only with verified commands.

| Check | Command | Evidence source | Execution permission |
|---|---|---|---|
| Markdown lint | `[NOT CONFIGURED]` | `[VERIFY]` | Ask |
| Link check | `[NOT CONFIGURED]` | `[VERIFY]` | Ask |
| Documentation build | `[NOT CONFIGURED]` | `[VERIFY]` | Ask |
| Spell/style check | `[NOT CONFIGURED]` | `[VERIFY]` | Ask |
| Example tests | `[NOT CONFIGURED]` | `[VERIFY]` | Ask |
| Focused implementation tests | `[NOT CONFIGURED]` | `[VERIFY]` | Ask |

## Execution policy

- Read-only Git inspection commands may run automatically under the agent permissions.
- Build, test, package-manager, network, and dependency-install commands require approval unless a repository-specific agent permission explicitly allows them.
- Destructive commands, source-tree mutation, publishing, and push operations are outside validation scope.
- When a check is unavailable, report **Not run** and explain why.

## Minimum report table

| Check | Status | Command/method | Evidence or failure |
|---|---|---|---|
