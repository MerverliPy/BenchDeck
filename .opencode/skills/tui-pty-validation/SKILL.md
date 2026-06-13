---
name: tui-pty-validation
description: Defines repeatable PTY action scripts, terminal profiles, frame assertions, resize, signal, export, and child-process checks for the BenchDeck curses TUI
license: MIT
compatibility: opencode
metadata:
  interface: curses-tui
---

## Required terminal profiles

- too narrow: 31x10
- too short: 32x9
- documented minimum: 32x10
- mobile SSH: 40x20
- standard: 80x24
- wide: 120x40

These are terminal-cell profiles, not claims about a specific phone font or pixel layout.

## PTY test structure

1. Start a real `benchdeck tui` command.
2. Record initial raw bytes and normalized screen.
3. Send one explicit key/action at a time.
4. Wait for a stable expected screen state.
5. Record a frame after each action.
6. Verify filesystem or child-process postconditions where applicable.
7. Quit or terminate deliberately.
8. Record exit status and cleanup.

## Required action types

- text/key send;
- Enter, Esc, arrows, Ctrl-C;
- sleep/wait;
- expect visible substring;
- resize rows/columns;
- TERM/KILL;
- frame capture.

## Failure rule

A direct call to `_render`, `_handle_key`, or another TUI method is unit evidence only. It cannot replace a PTY result.
