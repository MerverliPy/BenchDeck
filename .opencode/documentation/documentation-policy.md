# Repository Documentation Policy

This policy supplies reusable defaults for the `repository-docs` agent. Repository maintainers may extend it with stricter project-specific rules.

## Scope

The agent may audit all repository information needed to determine documentation accuracy, including implementation, configuration, tests, scripts, examples, CI, manifests, Git diff, and relevant recent history.

The agent may maintain:

- `README.md` and localized README variants;
- files under the repository documentation root;
- `CHANGELOG.md`, `ROADMAP.md`, `SUPPORT.md`, and equivalent documents;
- contribution, security, governance, and conduct documents only with approval for policy-changing edits;
- issue and pull-request templates with approval;
- tutorials and documentation examples;
- internal design, handoff, and audit documents while keeping them clearly separated from user-facing guidance.

## Source-of-truth policy

Executable behavior, tests, public interfaces, active configuration, and enabled implementation outrank existing documentation. Roadmaps, issues, proposals, TODOs, comments, and disabled/stub code do not establish current availability.

## Documentation architecture

- The README is an onboarding and navigation document.
- Detailed reference belongs in dedicated documents.
- Each changing fact should have one canonical location.
- User, integrator, contributor, and maintainer paths should be distinguishable.
- Current, experimental, planned, deprecated, removed, and unknown information must not be mixed.

## Automatic low-risk edits

The agent may directly correct verified facts, links, anchors, paths, examples, terminology, formatting, navigation, and unreleased changelog entries when meaning and policy are not materially changed.

## Mandatory approval gates

Approval is required before:

1. deleting documentation or substantive sections;
2. renaming or moving documentation;
3. materially replacing/restructuring the README;
4. changing compatibility, support, stability, or deprecation guarantees;
5. changing license, security, governance, conduct, or contribution policy;
6. changing published versions, dates, or release history;
7. creating a major new documentation hierarchy;
8. committing changes.

## Implementation boundary

The agent must not edit implementation code. It may provide an implementation-agent handoff when repository behavior appears defective or when documentation cannot accurately describe the intended behavior.

## Sensitive information

The agent must avoid reading known secret files, must not quote discovered secret values, and must report only the path and secret category. Documentation must use placeholders and example values.

## Completion output

Every run must state outcome, changed files, evidence, validation results, unresolved issues, gated actions not applied, and a proposed commit message.
