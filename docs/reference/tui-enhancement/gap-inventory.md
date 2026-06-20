# TUI enhancement reference — gap inventory

> Agent context note: this is detailed reference material split out of `docs/tui-enhancement-plan.md` during Cycle 7A. For routine agent context, start with `docs/context-handoffs/tui-enhancement-summary.md` and open this shard only when the specific implementation area is relevant.

## 2. Gap Inventory

### a. Discoverability & help

- **Footer hint truncation at narrow widths.** The static hint `"h/l tabs j/k move Enter detail e export n run x cancel r reload q quit"` is 73 characters. At `width=40` it is clipped by `_safe_add`; at `width=32` it is also clipped. The current code does not abbreviate by tab, nor does it switch to a context-sensitive hint per tab.
- **No contextual help.** The Help tab is static. The footer never reflects the active tab's most relevant keys (e.g. on Cases tab, `Enter open` is more salient than `n run`).
- **No keybinding cheatsheet at first launch.** Nothing tells a new user the difference between `j/k` (selection vs. scroll) on different tabs.
- **Status string `[no run]` does not suggest launching one.** If `metadata.status == "no run"` (no run_metadata.json), the title shows `BENCHDECK [no run]`, but the footer still shows the full key list with no nudge to press `n`.

### b. Cases tab density & navigation

- **No filter.** A user with 50+ cases cannot narrow to one family or one rating.
- **No sort.** Cases are always in `plan.cases` insertion order. A user wanting "Fail cases first" or "alphabetical" cannot reorder.
- **No family grouping.** The Overview shows family scores, but the Cases tab is flat.
- **No rating filter.** Cannot show only `BLOCKED` or only `Fail`-rated cases.
- **No multi-select for batch export.** `e` exports the selected case only. There is no way to mark several cases and export them together.
- **Single-line selection only.** Selected case is always a single integer; the visual marker `>` is at column 0 and can collide with the scroll-up `↑` indicator at narrow widths (drawn at `width-2` of row 2 — actually row 2 is the first content row, so the marker is on the selected case line, not row 2 globally; no collision in current code).

### c. Detail view legibility

- **No syntax distinction.** `test_prompt` and `final_output` are wrapped identically to narrative text. No code-fence visual.
- **No rating color in body.** `_line_attr` colors `Rating: Strong` because `Strong` appears in the line, but the body `Why:` text after the rating is not visually grouped. (Verified by inspection of `_line_attr`: it is line-based, not region-based.)
- **Long outputs overflow visually.** A 200-line `final_output` pushes other sections off-screen and the user must scroll; there is no "back to top" or section jump.
- **No case-id colorization.** The `Case N:` line has no color cue.

### d. Overview completeness

- **No per-agent toggle.** Multi-agent runs render all agents stacked. There is no `[`/`]` to fold an agent.
- **No time-elapsed indicator.** The user has no way to see how long the run has been progressing.
- **No ETA.** With `executions_judged` and an inferred rate, no estimate is shown.
- **No cost estimate.** Token usage is shown as a raw total but not a dollar estimate. (Cost would need a pricing model — flagged as a "would need new data field" item; see Out of Scope below.)
- **No snapshot-age indicator.** "Last loaded 12 s ago" is not shown; the user cannot tell whether the TUI is live or stale.

### e. Live-run feedback

- **stderr log captured but not viewable.** `_launch_run` opens `benchdeck_<ts>.log` for the subprocess (502–508), and `_poll_subprocess` mentions the log file name in the footer on non-zero exit (460–462), but there is no in-TUI log viewer.
- **No live tail.** Even during a running subprocess, the log is not tailed.
- **No per-stage progress.** The user sees `judged/planned` aggregate but no breakdown of "in planner", "in agent", "in judge".
- **No live status string change.** During a run the footer says `Launched PID nnn → <ts>` and then goes silent until exit. There is no "still running" heartbeat.

### f. Theme & color

- **Fixed 6-pair palette.** `_init_colors` (561–576) defines exactly 6 ANSI pairs.
- **Themes exist only in the screenshot renderer.** `scripts/generate_demo_screens.py` defines `THEMES = {dark, light, github}` (lines 55–107), and `gds._colourise_line` (682–740) re-implements the rating colorization. The live TUI does not consume this palette.
- **No TUI theme switching.** A user with a light terminal background has no way to invert.
- **No `AUTO` / `NO_COLOR` honoring.** `curses.has_colors()` is checked (562), but `NO_COLOR` (https://no-color.org/) is not respected.

### g. Robustness

- **Narrow terminal footer truncation.** At 32 columns the hint string is cut mid-word; not a crash but a UX cliff.
- **No defensive wrapping in `_safe_add`.** It already suppresses `curses.error` (624), which is correct; this row is informational.
- **Manifest verify cost on every refresh.** `Manifest.load` + `verify` runs on every render tick (≥1 Hz). For large artifacts this could be measurable. Not a bug, but a small inefficiency.

### h. Test coverage gaps

Identified branches currently without a targeted test:

1. `_draw` with `height < 10` → "Terminal too small" message.
2. `_draw` with `width < 32` → same.
3. `_draw` at exactly 32×10 (boundary).
4. Tab-name selection at `width < 40` (currently only `_case_list` is tested at width=32).
5. `_render` dispatch for all four tabs.
6. Multi-judge disagreement in `_detail` (3+ judgments with mixed ratings — currently no test).
7. Manifest `verify()` issues branch from the TUI (no test asserts the WARNING line in `_overview`).
8. Footer status line when `_status_msg` is set vs. cleared.
9. Scroll-up indicator at the top vs. scroll-down indicator at the bottom.
10. `_line_attr` quote-aware matching (currently the screenshot-side `_inside_quotes` is tested; the live curses `_line_attr` is not).
11. `_line_attr` "Gate Pass" / "Gate Fail" detection.
12. `_export_case` when judgments are empty (covered for plan-only) but not for "judgment present, no result".
13. `_launch_run` when `agent_b` is present (currently only single-agent paths tested).
14. `load_snapshot` with segmented `.b64.*` parts (not in `test_tui_loading.py`).
15. `_poll_subprocess` rc != 0 path with `stderr_log` set (status message composition).

---
