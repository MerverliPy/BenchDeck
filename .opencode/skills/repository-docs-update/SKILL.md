---
name: repository-docs-update
description: Apply evidence-backed repository documentation edits with risk classification, approval gates, layered information architecture, and source-code boundaries.
compatibility: opencode
metadata:
  audience: maintainers
  workflow: repository-documentation
---

# Repository documentation update

Use only after completing repository-documentation analysis.

## Preconditions

- Target files and audiences are known.
- Material claims have E1/E2 evidence or are explicitly labeled experimental, partial, planned, deprecated, removed, or unknown.
- Existing unrelated working-tree changes are identified.
- Approval-gated actions have either been excluded or explicitly approved.

## Information architecture

### README

Prioritize:

1. project purpose and verified value;
2. current feature summary with accurate status labels;
3. prerequisites;
4. shortest verified installation path;
5. first successful use;
6. common configuration;
7. links to detailed user, integration, contributor, support, security, and release documentation.

Do not turn the README into the complete reference manual.

### Detailed documentation

Use dedicated documents for architecture, API/reference material, advanced configuration, deployment, troubleshooting, contribution, security, and maintenance procedures.

### Canonical-fact rule

Store each changing fact in one primary location. Link to it elsewhere. Avoid duplicating version requirements, defaults, commands, compatibility matrices, or feature lists across many documents.

## Editing rules

- Preserve repository terminology and tone where accurate.
- Use imperative, ordered steps for procedures.
- State prerequisites before commands.
- Include expected results for critical setup steps.
- Use real paths, commands, flags, keys, and environment-variable names from repository evidence.
- Mark optional steps and destructive consequences clearly.
- Keep planned work out of current-feature sections.
- Keep examples minimal, complete, and consistent with current interfaces.
- Update all affected cross-references when headings or paths change.
- Do not change source code, generated artifacts, lockfiles, release tags, or published history.

## Approval-gated operations

Stop and request approval before any deletion, move, rename, README replacement/restructure, policy change, compatibility/support guarantee change, release/version-history change, major new documentation hierarchy, or commit.

The approval request must include:

- exact action;
- affected paths;
- evidence and reason;
- user-visible impact;
- rollback or safer alternative.

## Implementation conflict handoff

When documentation exposes a likely implementation defect, do not patch code. Produce:

- observed behavior;
- expected behavior supported by repository intent;
- relevant paths/tests;
- documentation impact;
- recommended implementation investigation;
- acceptance criteria for a coding agent.

## Change review

Before validation:

- inspect the documentation diff;
- confirm no unrelated files changed;
- confirm no unsupported claim was introduced;
- confirm status labels and terminology are consistent;
- confirm canonical documents and navigation remain coherent.
