# Mobile SSH TUI

The interface targets narrow Termius sessions on an iPhone-class display:

- Minimum terminal size: 32 columns by 10 rows.
- No mouse, function keys, or modifier chords are required.
- Number keys open screens; `j/k` move; `h/l` change screens; Enter opens details; `e` exports the current case as Markdown.
- `n` launches a new benchmark run as a subprocess; `x` cancels a running benchmark (press twice to confirm).
- 8-color palette color-codes ratings and statuses; falls back to monochrome when the terminal lacks color support.
- Artifacts reload every second while a benchmark is running.
- Long content wraps to the actual terminal width.

Recommended Termius settings: UTF-8, a monospace font at a readable size, and an extra keyboard row
containing Escape and arrow keys. The letter controls remain available when arrows are inconvenient.
