# BenchDeck Repository Documentation OpenCode Workflow

BenchDeck now includes an evidence-driven documentation-maintenance workflow for OpenCode. It is calibrated to the repository's Python CLI, benchmark artifacts, configuration, tests, CI, TUI, screenshots, release files, and documentation structure.

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

## BenchDeck configuration status

- `.opencode/documentation/repository-profile.md` is populated with verified BenchDeck paths, terminology, protected evidence, and command sources.
- `.opencode/documentation/validation-profile.md` maps documentation claims to BenchDeck's CI, targeted tests, CLI help, fixture inspection, and static checks.
- The workflow does not replace or modify the existing `repo-auditor`, TUI agents, or their commands.
- `AGENTS_SNIPPET.md` remains optional because BenchDeck currently has no root `AGENTS.md`. Merge it only when adopting repository-wide OpenCode instructions.

Re-verify the profiles after material changes to `src/benchdeck/cli.py`, `src/benchdeck/config.py`, schemas, packaging, CI, release workflows, documentation layout, or test names.

## First use after merge

1. Start or restart OpenCode from the BenchDeck repository root.
2. Confirm `repository-docs` appears as a primary and delegatable agent.
3. Confirm `/docs-audit`, `/docs-update`, `/docs-changed`, `/docs-verify`, and `/docs-release` are discoverable.
4. Run the initial read-only audit below.
5. Review contradictions and approval-gated proposals before running an update.
6. Run the benchmark suite before changing the agent, skills, permissions, or policy.

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
/docs-audit audit all current BenchDeck documentation against source, CLI help, configuration, tests, schemas, fixtures, CI, and release metadata; prioritize README feature and limitation claims, installation, run/tui/inspect commands, benchmark artifacts, mobile TUI behavior, known issues, and stale statements
```

The current README should receive particular scrutiny because current CLI implementation includes configuration, budget, resume, logging, multi-judge, and TUI run-launch surfaces that may be newer than narrative limitation text.

After reviewing the audit:

```text
/docs-update apply all low-risk, E1/E2-supported BenchDeck documentation corrections from the audit; preserve policy, compatibility, release-history, README-restructure, deletion, rename, and commit actions as approval-gated proposals
```

## Approval behavior

Routine evidence-backed documentation corrections may be applied directly. Explicit approval is required before:

- deleting, moving, or renaming documentation;
- materially restructuring or replacing `README.md`;
- changing compatibility, support, stability, deprecation, artifact-format, or schema guarantees;
- changing `SECURITY.md`, `CONTRIBUTING.md`, governance, conduct, or license policy;
- changing package versions, published dates, release history, release workflows, or known-issue resolution status;
- changing screenshot baselines or representing synthetic screenshots as live-run captures;
- creating a major documentation hierarchy;
- committing changes.

The agent never pushes and does not modify implementation source, schemas, tests, fixtures, screenshot baselines, dependencies, or release artifacts.

## Validation behavior

Use the narrowest check that proves each changed claim. BenchDeck's configured profile includes:

- Git diff and changed-path checks;
- local link, anchor, image, and repository-path verification;
- `ruff`, formatting, mypy, and full-test commands from CI;
- focused CLI/config/inspect and TUI test groups;
- CLI help and fixture inspection commands;
- screenshot provenance and secret-exposure checks.

Commands that execute repository code, use the network, install dependencies, generate screenshots, or access model APIs remain approval-gated. Unavailable checks must be reported as **Not run**, never as passing.

## Benchmarking changes to the workflow

Use `.opencode/benchmarks/repository-docs/` after changing the agent or its support files. Release requires:

- all 16 cases evaluated in isolated contexts;
- no critical failure;
- at least 90/100 overall;
- at least 95% of available factual-grounding and safety points;
- no failures in cases 2, 3, 4, 5, 6, 11, 12, or 13.
