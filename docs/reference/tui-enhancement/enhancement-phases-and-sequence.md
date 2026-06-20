# TUI enhancement reference — enhancement phases and recommended sequence

> Agent context note: this is detailed reference material split out of `docs/tui-enhancement-plan.md` during Cycle 7A. For routine agent context, start with `docs/context-handoffs/tui-enhancement-summary.md` and open this shard only when the specific implementation area is relevant.

## 3. Enhancement Phases

Each item: **title · files · risk · approval gate · change description · tests to add · validation command · rollback note**.

### Phase 0 — Pure observability / test-coverage (no behavior change)

**P0-1 — Add draw-level boundary tests** *(files: `tests/test_tui_render.py` · risk: low · approval: none) · ✅ Merged at `aec68ee`*
Add tests for the message strings and early-return path of `_draw` at `height<10`, `width<32`, exactly 32×10, and `width=39` (short tab names). Use a mocked `stdscr` (already available via `unittest.mock.MagicMock`).
- Tests: `test_draw_too_small_height`, `test_draw_too_small_width`, `test_draw_short_tab_names_at_width_39`, `test_render_dispatches_all_four_tabs`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k "draw or render_dispatches or short_tab"`
- Rollback: delete the new test functions; no production code change.

**P0-2 — Test multi-judge disagreement in detail** *(files: `tests/test_tui_render.py` · risk: low · approval: none) · ✅ Merged at `2e03f77`*
Construct a Snapshot with 3 judgments on one case with mixed ratings (`Excellent`, `Strong`, `Weak`). Assert the "Judge disagreement detected:" block and per-rating counts.
- Tests: `test_detail_shows_judge_disagreement_when_ratings_diverge`, `test_detail_no_disagreement_block_when_ratings_agree`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k disagreement`
- Rollback: remove the two new tests.

**P0-3 — Test overview manifest integrity WARNING branch** *(files: `tests/test_tui_render.py` · risk: low · approval: none) · ✅ Merged at `2fae355`*
Write a `manifest.json` whose `verify()` reports an issue (e.g. declare an entry with a wrong sha). Assert the WARNING line shows. Also test the `Manifest not yet present` line (gen == 0).
- Tests: `test_overview_manifest_warning_when_verify_fails`, `test_overview_manifest_not_present_when_gen_zero`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k manifest`
- Rollback: remove the two new tests.

**P0-4 — Test scroll indicators in `_draw`** *(files: `tests/test_tui_render.py` · risk: low · approval: none) · ✅ Merged at `da65a51`*
Mock `stdscr` and capture `addnstr` calls. Construct a Snapshot with 50 cases on the Cases tab, scroll to the top, then to the bottom, and assert the `↑` and `↓` markers are emitted in the right rows.
- Tests: `test_draw_scroll_indicator_at_top`, `test_draw_scroll_indicator_at_bottom`, `test_draw_no_indicator_when_fits`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k scroll_indicator`
- Rollback: remove tests.

**P0-5 — Test `_line_attr` quote-false-positive** *(files: `tests/test_tui_render.py` · risk: low · approval: none) · ✅ Merged at `2f88e68`*
Verify that a line such as `Judge said "Excellent" in the report` does not get the green pair (curses mock returning `color_pair` from `addnstr` calls). Confirms the boundary check works; documents the limitation that quoted ratings are not exempted.
- Tests: `test_line_attr_quoted_rating_still_colored` (documenting the current behavior — *not* a behavior change, just a regression guard), `test_line_attr_gate_pass_colored`, `test_line_attr_gate_fail_colored`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k line_attr`
- Rollback: remove tests.

**P0-6 — Test `_poll_subprocess` rc != 0 with stderr log** *(files: `tests/test_tui_render.py` · risk: low · approval: none) · ✅ Merged at `0927614`*
Use `_mock_popen` to set `poll.return_value = 1` and verify `_status_msg` contains the log file name. Also test the rc == 0 path (no log mention).
- Tests: `test_poll_subprocess_nonzero_reports_log`, `test_poll_subprocess_zero_clears_proc`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k poll_subprocess`
- Rollback: remove tests.

**P0-7 — Test launch with `agent_b` present** *(files: `tests/test_tui_render.py` · risk: low · approval: none) · ✅ Merged at `830bce0`*
Construct an `agent_b` markdown file and assert the launched command includes `--agent-b`. Currently only single-agent paths are covered.
- Tests: `test_launch_run_includes_agent_b_when_present`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k agent_b`
- Rollback: remove test.

**P0-8 — Test segmented `.b64.*` ZIP loading** *(files: `tests/test_tui_loading.py` · risk: low · approval: none) · ✅ Merged at `b50335a`*
This is a loader behavior the TUI consumes, already partially covered. Add a test that creates `foo.zip.b64.0` and `foo.zip.b64.1` in `tmp_path` and asserts `load_snapshot` returns a valid Snapshot. Marked as a TUI-loading test because the TUI is the primary consumer.
- Tests: `test_load_snapshot_reads_segmented_b64_zip`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_loading.py -k segmented`
- Rollback: remove test.

### Phase 1 — Low-risk cosmetic / legibility improvements

**P1-1 — Contextual footer hint per tab** *(files: `src/benchdeck/tui/app.py` and `src/benchdeck/tui/helpers.py` · risk: low · approval: required (visible layout) · ✅ Merged at `f96a25f`*
Define a small map `FOOTER_HINTS: dict[int, list[str]]` of "hints currently active" per tab index. The render function picks a set of hints joined with ` | `, truncated to width. Default: show the global hint set. Tab 1 (Cases) leads with `Enter open · e export`. Tab 2 (Detail) leads with `j/k scroll · h/l tab`. Output change is one line at `height-1`; no other region changes.
- Tests: `test_footer_hint_context_for_cases_tab` (asserts the Cases footer contains "Enter"), `test_footer_hint_truncates_at_narrow_width` (asserts the line is at most `width` characters).
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k footer_hint`
- Rollback: revert the single change to the footer branch of `_draw` (lines 159–162).

**P1-2 — "Last loaded" indicator in the title** *(files: `src/benchdeck/tui/app.py` and `src/benchdeck/tui/helpers.py` · risk: low · approval: required (visible title) · ✅ Merged at `b180f43`*
The title row already shows `BENCHDECK [status] PID:nnn`. Append a small `· 3s ago` style suffix when `self.last_load > 0`. Renders only inside the title row (row 0), which is the only row whose width budget is `>= 8` even at minimum 32-column. Compute the suffix lazily and only when there is horizontal room (`width >= 48`).
- Tests: `test_draw_title_shows_last_loaded_age`, `test_draw_title_omits_age_when_narrow`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k last_loaded`
- Rollback: revert the suffix append inside `_draw` (line 128 area).

**P1-3 — "Cases: N total · M judged · K blocked" summary on the Cases tab header** *(files: `src/benchdeck/tui/app.py` and `src/benchdeck/tui/helpers.py` · risk: low · approval: required (visible layout) · ✅ Merged at `7d610f7`*
The Cases tab currently has a single-line header `"Cases"` (line 251). Replace with a one-line summary that includes total / judged / blocked counts. Truncates gracefully at narrow widths.
- Tests: `test_case_list_header_includes_counts`, `test_case_list_header_truncates_at_minimum_width`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k case_list_header`
- Rollback: revert the `_case_list` first-line change.

**P1-4 — Visually distinguish code-ish output sections in Detail** *(files: `src/benchdeck/tui/app.py` and `src/benchdeck/tui/helpers.py` · risk: low · approval: required (visible layout) · ✅ Merged at `f205e8a`*
Prefix wrapped lines of `Test Prompt` and `Agent Output` with a `│ ` glyph, in FG color pair 5 (cyan) and dim. The wrapper is `_section` (632–636). Add a small helper that yields `(glyph, text, attr)` triples for the renderer; the actual application can be done at the `_safe_add` level by changing the line content. This is a *content* change, not a curses attribute change. Outline characters survive `_safe_add` cleanly.
- Tests: `test_detail_marks_test_prompt_block`, `test_detail_marks_agent_output_block`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k test_detail_marks`
- Rollback: revert the helper and the two `_section`-call changes in `_detail`.

**P1-5 — Number the case list rows and use the rating token's own color** *(files: `src/benchdeck/tui/app.py` and `src/benchdeck/tui/helpers.py` · risk: low · approval: required (visible layout) · ✅ Merged at `64e1754`*
The case-list `state` segment (`"Strong[agent_a] Excellent[agent_b]"` etc., line 268) is currently a single string. Add a small post-processor in `_case_list` that splits on whitespace and tags each rating token for `_line_attr`; since the TUI's colorization is line-based, this is best done by adding a soft hyphen or by repeating the line with the relevant token in the foreground. Pragmatic compromise: add a single-character mark `[✓]` for `Excellent`/`Strong`, `[!]` for `Acceptable`/`Weak`, `[X]` for `Fail`/`BLOCKED`, then keep text in default color. This adds symbols, not colors, so it works on terminals without color.
- Tests: `test_case_list_includes_status_marks_for_ratings`, `test_case_list_includes_status_marks_for_blocked`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k status_marks`
- Rollback: remove the per-rating mark appended in `_case_list` (line 268 area).

**P1-6 — Footer hint abbreviated at narrow widths** *(files: `src/benchdeck/tui/app.py` and `src/benchdeck/tui/helpers.py` · risk: low · approval: required (visible layout) · ✅ Merged at `0e5e7af`*
When `width < 56`, fall back to a 4-token hint: `1-4 tabs · j/k move · q quit`. This is a precondition for P1-1's hint map.
- Tests: `test_footer_hint_short_form_at_narrow_width`, `test_footer_hint_full_form_at_wide_width`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k hint_short_form`
- Rollback: revert the `_draw` footer branch (lines 159–162).

### Phase 2 — Behavior changes adding user value (approval required)

> **Implementation contract for all Phase 2 items:** every item below is gated behind a **default-off feature flag** (a new optional `BenchDeckTUI.__init__` kwarg) that defaults to `False`. The behavior is implemented, fully tested, and present in the binary, but the runtime path is unreachable until the flag is enabled. This means the diff is reviewable as a single safe change, the default TUI invocation is provably unchanged, and the user can opt in to individual features without touching the others. CLI flag wiring is a separate, separate-approval hand-off to the CLI owner (see Risk 3 fix in §8).

**P2-1 — Filter & sort on the Cases tab** *(files: `src/benchdeck/tui/app.py` and `src/benchdeck/tui/helpers.py`, `tests/test_tui_render.py` · risk: medium · approval: required · flag: `enable_case_filter: bool = False`*
Add three new keybindings: `f` opens a one-line filter prompt at the footer (`family:edge_case_logic` or `state:BLOCKED` or substring), `s` cycles sort among `id`, `family`, `rating`. Maintain a `self._filter: str` and `self._sort: str` field. Persist across tab switches. Reset on `r` (reload). The selected index must be re-resolved when the visible list changes (clamp to the new length). Document the keybindings in the footer and the Help tab.
- Tests: `test_case_list_filter_by_family`, `test_case_list_filter_by_state_blocked`, `test_case_list_sort_by_family`, `test_case_list_filter_clears_status_on_escape`, `test_case_list_selected_clamps_after_filter`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k "case_list_filter or case_list_sort"`
- Rollback: revert the new fields, the new key branches, and the new footer lines. `_draw` and `_case_list` are the only regions touched.

**P2-2 — Live stderr-log tailing** *(files: `src/benchdeck/tui/app.py` and `src/benchdeck/tui/helpers.py` · risk: medium · approval: required · flag: `enable_log_tail: bool = False`*
While `_proc is not None`, append the last ~16 lines of `self._stderr_log` to the Overview tab as a "Subprocess log (tail)" section. Read the file with `Path.read_text()` each refresh; cap at 4 KiB from the end. Show the size and the captured line count.
- Tests: `test_overview_includes_subprocess_log_tail_when_running`, `test_overview_omits_log_tail_when_idle`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k subprocess_log`
- Rollback: revert the tail-block branch added in `_overview` (around line 209).

**P2-3 — Snapshot age and heartbeat on Overview** *(files: `src/benchdeck/tui/app.py` and `src/benchdeck/tui/helpers.py` · risk: low · approval: required (visible) · flag: `enable_heartbeat: bool = False`*
Compute `now - self.last_load` and add a "Last refresh: 3s ago" line at the bottom of the Overview header. During an active subprocess, also add a "Run alive: yes · 47s elapsed" line using a monotonic timer set in `_launch_run`.
- Tests: `test_overview_shows_last_refresh_age`, `test_overview_shows_subprocess_elapsed_when_running`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k "last_refresh or subprocess_elapsed"`
- Rollback: remove the two appended lines in `_overview`.

**P2-4 — `NO_COLOR` and theme stub (palette selectable at construction time)** *(files: `src/benchdeck/tui/app.py` and `src/benchdeck/tui/helpers.py` · risk: medium · approval: required (new constructor kwarg) · flag: `theme: str = "auto"`*
Add a `theme: str = "auto"` constructor parameter. When `"auto"`, respect `NO_COLOR` env var (skip color). When `"dark"` or `"light"`, swap the palette so pair 6 is `BLACK on WHITE` for light, `WHITE on BLACK` for dark. The 6-pair mapping is sufficient; do not change the public API beyond the new optional kwarg. The CLI in `cli.py` is **not** in the editor's ownership list, so the constructor change is silent — the existing `benchdeck tui` invocation continues to use the default. (A CLI flag would be a separate approval-gated step.)
- Tests: `test_init_colors_respects_no_color_env`, `test_init_colors_light_theme_swaps_pair_6`, `test_init_colors_dark_theme_unchanged`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k "init_colors or no_color"`
- Rollback: revert `_init_colors` and the new constructor kwarg.

**P2-5 — Multi-select for batch export** *(files: `src/benchdeck/tui/app.py` and `src/benchdeck/tui/helpers.py` · risk: medium · approval: required · flag: `enable_batch_export: bool = False`*
On the Cases tab, `space` toggles the current case's "marked" state (a `set[int]` in `self`). `e` (or a new `E`) exports all marked cases to one Markdown file with a section per case. Display a leading `*` on marked rows.
- Tests: `test_case_list_space_toggles_mark`, `test_export_marked_writes_combined_markdown`, `test_export_marked_empty_writes_nothing`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k "marked or export_marked"`
- Rollback: revert the new key branch in `_handle_key` and the new export path.

**P2-6 — Infra-error section header on Overview** *(files: `src/benchdeck/tui/app.py` and `src/benchdeck/tui/helpers.py` · risk: low · approval: required (visible) · flag: `enable_infra_pointer: bool = False`*
Today, infrastructure errors are only visible per-case in the Detail tab. Add a 1-line count + "see Detail" pointer on the Overview when `infrastructure_failures > 0`. (The data field already exists; no schema change.)
- Tests: `test_overview_infra_error_pointer_when_present`, `test_overview_omits_pointer_when_zero`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k infra_error_pointer`
- Rollback: remove the new line in `_overview`.

### Phase 3 — Screenshot / golden baseline work (approval required, screenshot subagent gated)

> **Implementation contract for all Phase 3 items:** every Phase 3 test that asserts on rendered TUI output is wrapped in a `DEMO_SNAPSHOT_VERSION` (an `int` constant in `tests/test_screenshots.py`) guard. When the synthetic-builder's structural content changes intentionally, the version is bumped in a single location and the affected assertions are re-anchored. Until the bump, tests skip with a clear "snapshot version N → expected M" message. This makes test failures actionable (a version mismatch means "expected text needs review") rather than cryptic ("substring 'foo' not found"). See Risk 2 fix in §8 for the contract.

**P3-1 — Refresh SCREEN_SPECS to reflect any new tabs/lines from P1/P2** *(files: `scripts/generate_demo_screens.py` (protected — not in ownership), `tests/test_screenshots.py` · risk: medium · approval: required*
After any P1/P2 change that alters rendered output, the `SCREEN_SPECS` list in `generate_demo_screens.py` does not need updating (it is purely structural metadata), but the `test_tui_renders_*_with_demo_snapshot` and `test_generate_screenshots_*` tests will start failing on the assertion of literal substrings. Update the assertions to match the new content. **No golden images are stored in this repo** (`tests/golden_screens/` and `tests/__snapshots__/` do not exist), so there is no golden-baseline regeneration to do — only the text-based assertions need touching.
- Tests: update `test_tui_renders_overview_with_demo_snapshot`, `test_tui_renders_cases_with_demo_snapshot`, `test_tui_renders_detail_with_demo_snapshot` to match any new substrings (e.g. `M judged`).
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_screenshots.py tests/test_tui_render.py -k "with_demo_snapshot"`
- Rollback: revert the assertion string updates.

**P3-2 — Add screenshot-agent prompt for new visual states** *(files: `tests/test_screenshots.py` (test extensions only) · risk: medium · approval: required*
The screenshot subagent is the only tool that can re-render images, and only when the source is already stable. After P1/P2 settle, add a `tests/test_screenshots.py` function that produces screenshots for the new states (Cases tab with filter active, Overview with subprocess log tail). Use the same `gds.generate_screenshots` API. The test asserts file existence, not pixel content, and **does not** create or update any committed image.
- Tests: `test_generate_screenshots_filtered_cases`, `test_generate_screenshots_overview_with_log_tail`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_screenshots.py -k "filtered or log_tail"`
- Rollback: delete the two new tests.

---

## 4. Recommended Sequence (first 3 phases)

**Phase 0 (always-safe, ship first):** P0-1 → P0-2 → P0-3 → P0-4 → P0-5 → P0-6 → P0-7 → P0-8. No dependencies between items. They share only the test files.

**Phase 1 (visible, in-place rendering):**
1. P1-6 first (abbreviated hint at narrow widths). It is a precondition for P1-1's contextual hints and unblocks graceful rendering at the hard minimum.
2. P1-1 (contextual hint per tab). Depends on P1-6.
3. P1-3 (Cases header summary). Independent of P1-1; safe to ship in either order.
4. P1-5 (status marks on the case list). Independent.
5. P1-2 (last-loaded age in title). Independent.
6. P1-4 (block markers in Detail). Independent.

All P1 items depend on Phase 0 P0-1 having shipped (the new tests for `_draw` and `_render` are the safety net for any rendering change). P1-6 is the only one that is a strict prerequisite for P1-1; the rest are independent and can be done in any order.

**Phase 2 (behavior changes):** Strictly ordered to minimize risk:
1. P2-3 (snapshot age and heartbeat on Overview). Pure data-additive; no new keybindings.
2. P2-6 (infra-error pointer on Overview). Same — no new keybindings, no new fields.
3. P2-1 (filter & sort). This is the largest new-behavior item; it changes the visible case list and the selected-index lifecycle. Ship after the two read-only Overview additions to keep regression scope small.
4. P2-2 (stderr log tail). Adds a new data source (the captured log file) to Overview. Independent of P2-1.
5. P2-5 (multi-select for batch export). Depends on P2-1 only loosely — it is independent of the filter, but a filter and a multi-select both touch the "selected" lifecycle, so sequencing P2-1 first reduces test churn.
6. P2-4 (`NO_COLOR` + theme stub). Last because it changes `_init_colors`, which is foundational for every other rendering test that asserts attribute behavior.

**Phase 3:** ship only after the corresponding Phase 1 or Phase 2 item has been merged and validated. P3-1 follows whichever visible change touched a `test_tui_renders_*_with_demo_snapshot` assertion. P3-2 follows P2-1 (Cases filter) and P2-2 (log tail).

---
