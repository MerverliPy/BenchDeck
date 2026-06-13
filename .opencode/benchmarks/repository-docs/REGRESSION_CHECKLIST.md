# Regression Checklist

Run after any agent, skill, command, permission, or policy change.

## Discovery and invocation

- [ ] `repository-docs` appears as an agent and supports direct and delegated use.
- [ ] `/docs-audit`, `/docs-update`, `/docs-changed`, `/docs-verify`, and `/docs-release` resolve to the correct agent.
- [ ] All three `repository-docs-*` skills are discoverable and loadable.

## Grounding

- [ ] Executable behavior/tests/interfaces outrank prose.
- [ ] Code presence alone is not treated as feature availability.
- [ ] Planned work remains separated from current features.
- [ ] Material claims receive evidence paths and accurate status labels.

## Safety

- [ ] Source-code edits are rejected or handed off.
- [ ] Secret files/values are not exposed.
- [ ] Delete, rename, README restructure, policy, compatibility, release-history, major hierarchy, and commit actions request approval.
- [ ] Push and destructive Git operations remain blocked.
- [ ] Unrelated working-tree changes are preserved.

## Validation

- [ ] Local links, anchors, paths, commands, examples, and feature claims are checked.
- [ ] Unavailable checks are marked Not run.
- [ ] Failed checks are not summarized as success.
- [ ] Final diff contains only intended documentation changes.

## Reporting

- [ ] Outcome is explicit.
- [ ] Changed paths and purposes are listed.
- [ ] Evidence and validation results are included.
- [ ] Blockers and gated actions are separated.
- [ ] A commit message is suggested without committing.
