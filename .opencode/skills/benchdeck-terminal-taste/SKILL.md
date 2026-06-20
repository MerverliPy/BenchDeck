---
name: benchdeck-terminal-taste
description: BenchDeck-specific terminal UI taste rules for curses TUI changes. Preserves 32-column mobile SSH usability, keyboard-only control, artifact safety, help parity, and validation gates.
---

# BenchDeck terminal taste

Use this skill for BenchDeck curses TUI layout, hierarchy, readability, state visibility, and screenshot-facing polish. Do not use it for benchmark logic, artifact schemas, OpenAI gateway behavior, release configuration, dependencies, CI, or generated golden replacements.

## Design read

Before changing user-visible TUI behavior, state one line:

> Reading this as: terminal-first benchmark monitoring for mobile SSH users, prioritizing evidence, legibility, status clarity, and safe keyboard navigation.

If the requested change could reasonably mean either a cosmetic adjustment or a behavior change, ask one concise approval question before editing.

## Non-negotiables

- Preserve the 32x10 hard minimum.
- Preserve keyboard-only operation.
- Preserve visible escape paths for Back, Help, Cancel, Exit, and Quit where applicable.
- Preserve Help text parity with actual controls.
- Preserve color fallback and do not rely on color alone.
- Preserve wrapping at the actual terminal width.
- Preserve benchmark artifact schemas, public CLI behavior, generated screenshots, and golden baselines unless explicitly approved.
- Do not add decoration that consumes scarce columns without improving comprehension.
- Do not hide status, errors, policy blocks, infrastructure failures, budget signals, or gate failures.
- Do not make screenshots prettier at the cost of runtime truth.

## Terminal hierarchy rules

- Put state before detail.
- Prefer short, stable labels over clever copy.
- Use consistent status tokens: `PASS`, `FAIL`, `BLOCKED`, `PENDING`, `WARN`, `RUNNING`, `DONE`.
- Use symbols only when their meaning is obvious or documented in Help.
- Use the same vocabulary across overview, cases, detail, help, screenshots, and docs.
- Keep scores, counts, ratings, and budget values visually scannable.
- Use tabular alignment where it improves scan speed, but do not force wide tables into 32 columns.

## Layout rules

- At 32 columns, every visible line must justify its existence.
- At 40 columns, mobile-oriented interaction should remain comfortable.
- At 80 columns, add context but do not change the information model.
- At 120 columns, expansion may add columns or richer summaries, never hidden behavior.
- Headers must not push actionable content below the fold.
- Footer hints should show the next useful action, not a generic command dump.
- Long agent output must wrap predictably and remain attributable to the correct case/agent.
- Avoid symmetrical filler. Prefer hierarchy, grouping, and separators that carry meaning.

## Accessibility and interaction rules

- Never rely on mouse input, function keys, or modifier chords.
- Preserve letter-key alternatives when arrow keys exist.
- Selection and focus must remain visible in monochrome terminals.
- Help must fit the supported narrow viewport or degrade gracefully.
- Error and cancel states must be reachable and understandable without color.
- Do not introduce animation, spinners, or repeated redraw noise that makes SSH sessions harder to use.

## Implementation discipline

- Work with the existing renderer and helpers. Do not invent a second renderer.
- Prefer small helper functions over broad rewrites.
- Avoid whole-file formatting churn.
- Keep behavior behind explicit approval when it changes navigation, keybindings, public CLI behavior, artifacts, goldens, or generated screenshots.
- Treat screenshots as validation evidence, not as the source of truth.

## Validation checklist

Before completion, verify or explicitly mark not executed:

- `32x10` behavior checked when layout, clipping, help, navigation, or footer behavior changed.
- `40x20` checked for mobile-oriented interaction changes.
- `80x24` checked for every visible TUI change.
- `120x36` checked when expansion or multi-column layout matters.
- Help text matches actual controls.
- Focus and selection remain visible.
- Monochrome fallback remains usable.
- No source of truth moved from runtime data to screenshot-only evidence.
- No screenshot or golden changes occurred unless approved.
- Targeted tests or headless render evidence are recorded.

## Completion report

Report in this order:

1. Result
2. TUI surfaces changed
3. Widths validated
4. Tests or render evidence
5. Limitations
6. Remaining risks
