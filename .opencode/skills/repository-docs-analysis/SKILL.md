---
name: repository-docs-analysis
description: Map repository evidence, classify feature status, detect stale documentation, and identify contradictions before documentation is edited.
compatibility: opencode
metadata:
  audience: maintainers
  workflow: repository-documentation
---

# Repository documentation analysis

Use this skill before proposing or applying documentation changes.

## Inputs

- requested documentation scope;
- current Git state and comparison base when relevant;
- repository profile and documentation policy, if configured;
- existing documentation;
- implementation, tests, configuration, examples, CI, and release metadata relevant to public behavior.

## Analysis sequence

1. Identify audience and requested outcome.
2. Build a high-signal repository map rather than reading every file.
3. Inventory existing documentation and determine canonical sources.
4. Extract material claims from target documents.
5. Trace each claim to implementation, test, interface, configuration, or runtime evidence.
6. Assign evidence rating E1–E5 and feature status.
7. Detect contradictions, missing onboarding information, duplicate facts, broken navigation, and stale examples.
8. Assign stale confidence: High, Medium, or Low.
9. Produce a prioritized edit plan with risk classification.

## Repository map priorities

Inspect in this order unless repository structure indicates otherwise:

1. changed files and current diff;
2. manifests, entry points, exported/public APIs, CLI definitions, and schemas;
3. tests and executable examples;
4. CI/build/release configuration;
5. root README and documentation index;
6. deep reference documents;
7. roadmap, issues, TODOs, proposals, and historical notes.

Expand only when a claim depends on another component.

## Claim ledger format

For each material claim, retain a compact record:

| Claim | Evidence paths | Rating | Status | Validation | Conflict |
|---|---|---|---|---|---|

Do not include unsupported speculation. Do not expose sensitive values.

## Contradiction rules

- Passing runtime/test evidence overrides prose.
- Active public interface/configuration overrides comments and roadmap text.
- A stub, disabled branch, placeholder, or unreferenced module is not an available feature.
- A test name alone is insufficient; inspect what it actually proves.
- Modification timestamps are signals, not truth.
- Historical Git content may explain intent but does not prove current behavior.

## Audit output

Return:

- scope examined;
- documentation inventory;
- high-confidence stale items;
- medium/low-confidence review items;
- missing documentation by audience;
- contradictions and required decisions;
- prioritized low-risk edits;
- approval-gated edits;
- evidence gaps and suggested verification commands.
