# BenchDeck local agent skills

BenchDeck keeps third-party prompt frameworks out of runtime-critical paths by translating useful ideas into narrow, repository-owned skills.

These skills adapt the taste-skill pattern to BenchDeck's actual constraints:

- evidence-preserving benchmark artifacts
- curses TUI behavior
- narrow SSH and Termius-on-iPhone usage
- bounded `.opencode` agents
- no source, golden, CI, dependency, or release changes unless explicitly approved

## Skills

| Skill | Primary use | Safe default agents |
| --- | --- | --- |
| `benchdeck-terminal-taste` | TUI layout, hierarchy, legibility, and narrow-width polish | `tui-precision-editor` |
| `benchdeck-screenshot-quality` | Screenshot candidate quality, README/demo visual evidence, artifact validation language | `tui-screenshot` |
| `benchdeck-readme-polish` | README and docs positioning, screenshot captions, product-story clarity | `repository-docs` |
| `benchdeck-output-completeness` | Complete plans, handoffs, docs, and bounded code outputs without placeholder shortcuts | `tui-precision-editor`, `repository-docs`, `repo-auditor` |

## Usage policy

Prefer these local skills over generic external UI/design skills when working inside BenchDeck. External skills can inspire future local rules, but they must not override repository permissions, artifact safety, current source, tests, schemas, or explicit user instructions.

Load only the narrow skill needed for the task. Do not stack visual skills on source-editing agents unless the task actually changes user-visible UI or documentation presentation.
