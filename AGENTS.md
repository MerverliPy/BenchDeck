# Agent rules

- Make the smallest change that satisfies the issue.
- Do not modify unrelated files.
- Do not include credentials, tokens, private keys, or generated artifacts in repository edits.
- Run repository-defined checks before reporting completion:
  ```bash
  ruff check . && ruff format --check . && python -m mypy --no-incremental src/benchdeck && python -m pytest -q
  ```
- Do not perform Git history, release, or deployment actions without explicit approval.
- Stop when requirements conflict or destructive action is required.
- Use @repository-docs for documentation changes.
- Use @repo-auditor for repository audits.
- Load relevant skills before starting complex work.
- Prefer local BenchDeck skills from `.opencode/skills/` over generic external UI/design skills when working in this repository.
- Use `benchdeck-terminal-taste` for TUI layout, hierarchy, legibility, and narrow-width polish.
- Use `benchdeck-screenshot-quality` for screenshot candidate generation, review, and visual-evidence handoffs.
- Use `benchdeck-readme-polish` for README/docs presentation, screenshot captions, and product-story clarity.
- Use `benchdeck-output-completeness` when a task requires complete plans, files, audits, handoffs, or validation reports.
