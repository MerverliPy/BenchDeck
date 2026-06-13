# Repository Documentation OpenCode Workflow

This package installs a reusable, evidence-driven documentation-maintenance workflow for OpenCode.

## Included

```text
.opencode/
├── agents/
│   └── repository-docs.md
├── commands/
│   ├── docs-audit.md
│   ├── docs-changed.md
│   ├── docs-release.md
│   ├── docs-update.md
│   └── docs-verify.md
├── skills/
│   ├── repository-docs-analysis/SKILL.md
│   ├── repository-docs-update/SKILL.md
│   └── repository-docs-validation/SKILL.md
├── documentation/
│   ├── AGENTS_SNIPPET.md
│   ├── documentation-policy.md
│   ├── repository-profile.md
│   └── validation-profile.md
└── benchmarks/repository-docs/
    ├── CASES.md
    ├── README.md
    ├── REGRESSION_CHECKLIST.md
    ├── REGRESSION_RECORD.md
    └── RUBRIC.md
```

## Installation

1. Extract or copy the `.opencode` directory into the repository root.
2. Review `.opencode/documentation/repository-profile.md` and replace only values that can be verified.
3. Add verified repository documentation/test commands to `.opencode/documentation/validation-profile.md`.
4. Merge the relevant guidance from `.opencode/documentation/AGENTS_SNIPPET.md` into the repository's existing `AGENTS.md`; do not replace existing project instructions.
5. Start OpenCode from the repository root.
6. Confirm the `repository-docs` agent and documentation commands are discoverable.
7. Run `/docs-audit` before the first update.
8. Run the benchmark suite before treating customized instructions as stable.

## Commands

| Command | Purpose |
|---|---|
| `/docs-audit [scope]` | Read-only repository/documentation audit. |
| `/docs-update [objective]` | Audit, apply low-risk documentation edits, validate, and report. |
| `/docs-changed [base]` | Diff-aware documentation maintenance. |
| `/docs-verify [scope]` | Read-only factual and structural verification. |
| `/docs-release [base/scope]` | Maintain Unreleased changelog or draft release content. |

The agent can also be invoked directly with `@repository-docs` or selected as a primary agent.

## Initial recommended run

```text
/docs-audit complete repository documentation; prioritize README onboarding, verified features, installation, configuration, examples, support paths, and contradictions with current implementation
```

After reviewing the audit:

```text
/docs-update apply all low-risk, evidence-backed documentation corrections from the audit; preserve approval-gated actions as proposals
```

## Approval behavior

Routine evidence-backed documentation corrections may be applied directly. The agent must request explicit approval before deleting, moving, renaming, materially restructuring the README, changing compatibility/support promises, changing policy documents, altering published release history, creating a major documentation hierarchy, or committing.

## Repository intake

For a private or unpublished repository, provide the complete repository as a ZIP or run this package locally inside the repository. For a public repository, provide the GitHub URL or clone the repository before running OpenCode.

## Customization rules

- Keep the main agent model unset so it inherits the active OpenCode model.
- Tighten permissions rather than broadening them when repository constraints are known.
- Add repository-specific validation commands only after verifying them.
- Preserve the evidence hierarchy and approval gates when shortening the prompt.
- Run all release-blocking benchmark cases after any behavior change.
