---
name: benchdeck-readme-polish
description: BenchDeck-specific documentation and README presentation rules. Improves product story, screenshot captions, hierarchy, and install clarity from verified repository evidence only.
---

# BenchDeck README polish

Use this skill for README, docs, and repository-presentation work where BenchDeck needs clearer product positioning, screenshot narrative, or technical onboarding. It does not authorize source, tests, CI, generated artifacts, release, security, or dependency changes.

## Documentation read

Before editing, state one line:

> Reading this as: evidence-first developer-tool documentation for AI-agent benchmarking users who need trustworthy artifacts, narrow-terminal monitoring, and reproducible inspection.

## Evidence hierarchy

Prefer current evidence in this order:

1. observed behavior from safe commands
2. passing tests
3. CLI help and public interfaces
4. implementation and schemas
5. maintained examples and fixtures
6. CI/package metadata
7. existing docs
8. roadmap, comments, or historical notes

Never upgrade a claim from planned to supported without current evidence.

## Product-story rules

BenchDeck should read as:

- evidence-preserving
- benchmark-oriented
- agent-workflow-aware
- terminal-first
- mobile SSH conscious
- explicit about ambiguity and failure classification
- conservative about claims

Prefer specific language over generic marketing language. Avoid unsupported hype unless current evidence supports it.

## README hierarchy rules

A strong BenchDeck README should quickly answer:

1. What is BenchDeck?
2. Why is it different from ad hoc eval scripts?
3. What can I run in two minutes?
4. What artifacts are produced?
5. What does the TUI show?
6. What limitations remain?
7. How do I validate or contribute safely?

## Screenshot caption rules

Captions should say what the screenshot proves:

- Overview: progress, ratings, policy blocks, token usage, run state
- Cases: per-case status, blocked/pending/judged visibility, rating distribution
- Detail: prompt, judgment, gate check, and agent output attribution
- Help: narrow-terminal and phone-keyboard control model

Do not make screenshots appear as mockups if they are runtime captures. Include source run or fixture context when it matters.

## Style rules

- Keep commands copy-pasteable.
- Keep limitations honest and visible.
- Keep benchmark numbers tied to the run that produced them.
- Do not polish away failure states. Failures are part of BenchDeck's value proposition.
- Keep badges and counts honest. Snapshot counts must be labeled as snapshots.
- Avoid broad rewrites when a narrow wording fix is enough.

## Validation checklist

Before completion, verify or disclose:

- edited claims match current evidence
- commands still match documented CLI shape
- screenshot paths exist when referenced
- limitation wording is not contradicted by current docs/source
- no generated artifact was changed unless approved
- no planned behavior is documented as current
- final diff is documentation-scoped

## Completion report

Report:

1. Result
2. Docs changed
3. Material claims changed
4. Evidence used
5. Validation
6. Remaining documentation risks
