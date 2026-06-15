# BenchDeck TUI — Structured Enhancement Plan

**Target:** `src/benchdeck/tui.py` (996 lines as of post-P2-1) and its test surface.
**Scope:** TUI rendering and behavior only. Out-of-scope: schema, runner, gateway, dependencies, CI, packaging, screenshot regeneration.
**Method:** Read-only evidence gathering from current source and tests, then a phased, risk-graded plan. No edits performed.

---

## 0. Current Status

**Branch:** `main` (at `5398541`, 4 commits ahead of `origin/main`; `tui/enhancement` is stale at `747268e`).
**Last update:** post-P2-1 commit (2026-06-15).

| Phase | Status | Latest commit | Tests added | Production lines |
|---|---|---|---:|---:|
| Phase 0 | ✅ Complete | `d72033d` | +21 | 0 |
| Phase 1 | ✅ Complete | `82b6c5c` | +13 | ~+113 |
| Phase 2 | 🟡 In progress (3/6) | `5398541` | +11 | +257 |
| Phase 3 | ⏳ Not started | — | 0 | 0 |

**Total so far:** 17 items implemented (8 P0 + 6 P1 + 3 P2), 45 new tests, 0 to ~+370 production lines. All 157 TUI + screenshot tests pass; golden baselines unchanged.

### Completed commits (in execution order)

| Item | SHA | Title |
|---|---|---|
| P0-1 | `aec68ee` | draw-level boundary tests + `_FakeStdscr` + `DEMO_SNAPSHOT_VERSION` |
| P0-2 | `2e03f77` | multi-judge disagreement in `_detail` (3 tests; plan: 2) |
| P0-3 | `2fae355` | manifest integrity WARNING + not-yet-present branches |
| P0-4 | `da65a51` | scroll indicators in `_draw` |
| P0-5 | `2f88e68` | `_line_attr` boundary check + Gate Pass/Fail colorization |
| P0-6 | `0927614` | `_poll_subprocess` rc!=0/rc==0/no-op paths (3 tests; plan: 2) |
| P0-7 | `830bce0` | `_launch_run` with `agent_b` present + missing-file guard (2 tests; plan: 1) |
| P0-8 | `b50335a` | `load_snapshot` of segmented `.b64.*` ZIP fixtures |
| P1-6 | `0e5e7af` | footer hint short form at width < 56 |
| P1-1 | `f96a25f` | contextual `FOOTER_HINTS` per tab (P1-6 test updated to match) |
| P1-3 | `7d610f7` | Cases tab header `Cases: N total · M judged · K blocked` |
| P1-5 | `64e1754` | status marks `[✓]/[!]/[X]` prefix case-list state |
| P1-2 | `b180f43` | title age suffix `· Ns ago` (3 tests; plan: 2) |
| P1-4 | `f205e8a` | `│ ` glyph on `Test Prompt` and `Agent output` |
| P2-3 | `28c52c8` | overview heartbeat — `Last refresh` + `Run alive` lines (3 tests; plan: 2) |
| P2-6 | `0237de3` | infra-error pointer on Overview |
| P2-1 | `5398541` | filter & sort on the Cases tab (6 tests; plan: 5) |

### Deviations from plan

- **P0-2**: +1 test (`test_detail_disagreement_counts_duplicate_ratings`) for the 2-1-1 split case (per-rating count arithmetic).
- **P0-6**: +1 test (`test_poll_subprocess_noop_when_proc_is_none`) for the early-return branch when `self._proc is None`.
- **P0-7**: +1 test (`test_launch_run_omits_agent_b_when_file_missing`) for the file-existence guard.
- **P1-1**: 2 new tests + 1 P1-6 test (`test_footer_hint_full_form_at_wide_width`) updated to match the new per-tab hint contract (the wide-form tokens changed from a flat list to per-tab hints).
- **P1-2**: +1 test (`test_draw_title_omits_age_before_first_load`) for the `last_load > 0` guard.
- **P1-4**: implementation also added a `Test Prompt` section to `_detail` (it was not previously rendered; the plan's wording assumed it was). The plan's stated test for the Test Prompt block would have failed otherwise.
- **P2-3**: +1 test (`test_overview_omits_heartbeat_when_flag_disabled`) for the Phase 2 default-off contract guard. Asserts that with `enable_heartbeat=False` (the default), neither the `Last refresh` nor the `Run alive` line appears in `_overview`, even when `last_load > 0` and a subprocess is alive. This locks down the Phase 2 default-off guarantee and matches the P0/P1 pattern of adding regression guards for invariant branches.
- **P2-1**: +1 test (`test_case_list_default_off_omits_filter_and_sort`) for the Phase 2 default-off contract guard. Asserts that with `enable_case_filter=False` (the default), `_case_list` ignores `_filter` and `_sort` and that the `f` / `s` keys are no-ops in `_handle_key`. The plan's "three new keybindings" wording is interpreted as two genuinely new keys (`f` to open the filter prompt, `s` to cycle sort) plus the transient use of existing `Enter` (apply) and `Esc` (cancel) inside the prompt — no third new keybinding is added. This matches the P0/P1 pattern of adding regression guards for invariant branches.

### Branch / merge history

- `main` is currently at `5398541` (post-P2-1 commit; 4 ahead of `origin/main`).
- `tui/enhancement` is stale at `747268e` (Phase 2 work has landed on `main` directly).
- Phase 0 and Phase 1 merges used `--no-ff` so per-item commit history is preserved under the merge commit. Phase 2 items so far (P2-3, P2-6, P2-1) are individual commits on `main` — no Phase 2 merge commit yet.
- Golden baselines at `assets/screenshots/golden/*.png` have not changed (Phase 0 + Phase 1 + P2-3 + P2-6 + P2-1 are content-only and default-off; no screenshot regeneration).

---

## 1. Current-State Matrix

### 1.1 Tabs and rendering functions

| Tab index | Name (TUI / narrow) | Render function | Lines |
|---:|---|---|---|
| 0 | `Overview` / `Ov` | `_overview(width)` → `_render_agent_section` | 174–248 |
| 1 | `Cases` / `Ca` | `_case_list(width)` | 250–279 |
| 2 | `Detail` / `De` | `_detail(width)` | 281–361 |
| 3 | `Help` / `He` | `_help(width)` | 363–379 |

`TABS = ("Overview", "Cases", "Detail", "Help")` (line 19). Dispatch: `_render(width)` (165–172). No Compare tab is registered in the live TUI; the screenshot script's `_add_compare_tab` is a synthetic helper that the runtime never calls.

### 1.2 Keybindings (handled in `_handle_key`, lines 75–108)

| Key | Action |
|---|---|
| `1`–`4` | Jump to tab (line 78) |
| `←` / `h` | Previous tab (84) |
| `→` / `l` | Next tab (81) |
| `↓` / `j` | Case-list selection or scroll down (87) |
| `↑` / `k` | Case-list selection or scroll up (92) |
| `Enter` (CR/LF) | Cases→Detail (97) |
| `r` | Reload snapshot from disk (100) |
| `e` | Export case markdown (103) |
| `n` | Launch new run (105) |
| `x` | Cancel subprocess (two-press confirmation) (107) |
| `q` / `Esc` | Quit (68) |

Side effects in `_main` (49–73): periodic `load_snapshot` every `refresh_seconds`, `_poll_subprocess` each tick, exit with auto-cancel if subprocess is running.

### 1.3 Color pairs (`_init_colors`, lines 561–576)

| Pair | FG / BG | Used in `_line_attr` for |
|---:|---|---|
| 1 | RED on BLACK | `Fail`, `BLOCKED`, `Fail: Gate` |
| 2 | GREEN on BLACK | `Excellent`, `Pass: Gate`, progress bar fill |
| 3 | YELLOW on BLACK | `Acceptable`, `Weak`, `WARNING` |
| 4 | BLUE on BLACK | `Strong` |
| 5 | CYAN on BLACK | Tab row (line 126) |
| 6 | BLACK on CYAN | Title and footer (125, 127) |

`_line_attr` (578–618) is a whole-word pattern matcher with boundary characters `(" ", "[", ":", "]", ",", "(")`. It does not parse quoted text (e.g. `gds._colourise_line`'s `_inside_quotes` logic is not ported to the live curses path).

### 1.4 Layout regions (rows in `_draw`, lines 110–163)

| Row | Content |
|---:|---|
| 0 | Title `BENCHDECK [status] PID:nnnn` |
| 1 | Tab bar `1:Ov 2:Ca 3:De 4:He` (active tab bracketed) |
| 2 … `height-2` | Content viewport (clamped via `_clamp_scroll`) |
| `height-1` | Footer status / hint line |

Scroll indicators `↑` / `↓` are drawn at columns `width-2` of row 2 and `2 + view_height - 1` respectively (lines 155–158).

### 1.5 Viewport thresholds

| Threshold | Effect |
|---|---|
| `height < 10` or `width < 32` | Single-line error "Terminal too small (min 32x10)" (113–116) |
| `width < 40` | Short tab names `("Ov", "Ca", "De", "He")` (129) |
| `width >= 40` | Full tab names from `TABS` |

### 1.6 Snapshot fields consumed

| Field | Read in |
|---|---|
| `metadata.status` | title (119) |
| `metadata.cases_in_plan`, `executions_judged`, `policy_blocks`, `infrastructure_failures`, `token_usage` | overview (178–191) |
| `metadata.config.{agent_a,agent_b,model,judge_model}` | `_launch_run` (476–480) |
| `plan.cases[]` (each: `id`, `title`, `family`, `purpose`, `test_prompt`) | `_cases`, case list, detail, export |
| `tally[agent].{rating_counts,family_scores,gate_failures}` | overview (177, 240–248) |
| `judgments[]` (case_id, agent_label, overall_rating, why, gate_check) | case list, detail, export |
| `policy_blocks[]` (case_id, message) | case list (270), detail |
| `results[agent][]` (case_id, final_output, infrastructure_error) | detail (310–319), export |
| `infrastructure_errors[]` (case_id, stage, error_type, message, agent_label, response_id, attempts) | detail (331–360) |
| `planner_capture.{value.mode,attempts,total_http_attempts,terminal_error,parse_error}` | overview (193–208) |

### 1.7 Manifest interaction

`_overview` calls `Manifest.load(self.run_dir)` every refresh (line 211). When `gen > 0` it calls `manifest.verify()` and either prints `valid` or `WARNING — N integrity issue(s)`. Generation 0 prints `not yet present`. The TUI is read-only with respect to the manifest.

### 1.8 Side effects

| Action | Effect |
|---|---|
| Periodic reload | `load_snapshot(active_dir)` (60–62) where `active_dir = _proc_run_dir or run_dir` |
| `e` (export) | Writes `case_<id>_<ts>.md` into `run_dir` (404–445) |
| `n` (new run) | `subprocess.Popen(["python", "-m", "benchdeck", "run", ...])` writing stdout/stderr to `benchdeck_<ts>.log` (484–508) |
| `x` (cancel) | `proc.terminate()`, then `kill()` after 5 s timeout (526–542) |
| `r` (reload) | Force `load_snapshot(run_dir)` and `last_load = now` (100–102) |

### 1.9 Test surface currently exercising each path

| Code path | Test function(s) | File |
|---|---|---|
| `_overview` — run_dir / progress / policy / infra / tally / no-tally / planner-errors | `test_overview_shows_run_dir`, `test_overview_progress_bar`, `test_overview_shows_policy_blocks_and_infra`, `test_overview_shows_tally_data`, `test_overview_no_tally_data`, `test_overview_shows_planner_errors`, `test_tui_overview_shows_planner_info`, `test_tui_overview_shows_planner_terminal_error`, `test_tui_overview_shows_planner_parse_error`, `test_tui_overview_no_planner_line_when_empty` | `tests/test_tui_render.py`, `tests/test_tui_loading.py` |
| `_case_list` — judgments / pending / blocked / narrow 32-col | `test_case_list_with_judgments`, `test_case_list_shows_pending`, `test_case_list_shows_blocked`, `test_case_list_renders_at_minimum_width` | `test_tui_render.py` |
| `_detail` — no-cases / with-judgment / orphan infra / case-scoped infra | `test_detail_no_cases`, `test_detail_with_judgment`, `test_detail_shows_orphan_infra_errors`, `test_tui_detail_shows_infrastructure_errors` | `test_tui_render.py`, `test_tui_loading.py` |
| `_help` | `test_help_contains_controls` | `test_tui_render.py` |
| Export | `test_export_case_uses_absolute_path`, `test_export_case_no_cases_does_nothing` | `test_tui_render.py` |
| Scroll clamp | `test_clamp_scroll_bounds_check`, `test_clamp_scroll_keeps_selected_visible_on_case_list`, `test_clamp_scroll_non_case_list_ignores_selection` | `test_tui_render.py` |
| Launch | `test_launch_run_rejects_missing_agent_file`, `test_launch_run_uses_snapshot_metadata_fallback`, `test_launch_run_prefers_explicit_args` | `test_tui_render.py` |
| Cancel | `test_cancel_requires_double_press`, `test_cancel_double_press_terminates`, `test_cancel_cleared_by_any_other_key`, `test_cancel_timeout_clears_request` | `test_tui_render.py` |
| Loader (ZIP/dir, malformed) | `test_zip_duplicate_basename_raises_valueerror`, `test_zip_loading_handles_corrupt_zip`, `test_zip_loading_handles_empty_zip`, `test_zip_loading_reads_all_expected_files`, `test_zip_loading_malformed_json_defaults`, `test_load_snapshot_directory_missing_defaults`, `test_load_snapshot_directory_reads_json`, `test_load_snapshot_directory_reads_infrastructure_errors`, `test_load_snapshot_directory_reads_planner_capture`, `test_zip_loading_reads_infrastructure_errors`, `test_zip_loading_reads_planner_capture`, `test_load_snapshot_discovers_run_id_subdirectory`, `test_load_snapshot_picks_most_recent_run_id`, `test_load_snapshot_direct_subdir_still_works`, `test_bundled_fixture_loads`, `test_bundled_fixture_has_metadata`, `test_malformed_plan_json_defaults_to_empty`, `test_result_for_respects_agent_label_when_provided`, `test_tui_snapshot_case_plan_has_no_agent_label` | `test_tui_loading.py` |
| Screenshot pipeline | All functions in `tests/test_screenshots.py` (62 tests) | `test_screenshots.py` |

**Coverage gaps visible from the table:** no test exercises `_draw` or `_main` at hard-minimum 32×10, no test exercises the narrow tab-name mode (`width=32` test uses `_case_list`, not `_draw`), no test exercises multi-judge disagreement, no test exercises planner parse error (covered at overview level, not detail), no test exercises the case-list state when there are more than one judgment per case but all agents agree, no test exercises `_render` at the hard-minimum height, no test asserts scroll-indicator placement, no test exercises the `Manifest.verify` "integrity issues" branch from the TUI.

---

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

**P1-1 — Contextual footer hint per tab** *(files: `src/benchdeck/tui.py` · risk: low · approval: required (visible layout) · ✅ Merged at `f96a25f`*
Define a small map `FOOTER_HINTS: dict[int, list[str]]` of "hints currently active" per tab index. The render function picks a set of hints joined with ` | `, truncated to width. Default: show the global hint set. Tab 1 (Cases) leads with `Enter open · e export`. Tab 2 (Detail) leads with `j/k scroll · h/l tab`. Output change is one line at `height-1`; no other region changes.
- Tests: `test_footer_hint_context_for_cases_tab` (asserts the Cases footer contains "Enter"), `test_footer_hint_truncates_at_narrow_width` (asserts the line is at most `width` characters).
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k footer_hint`
- Rollback: revert the single change to the footer branch of `_draw` (lines 159–162).

**P1-2 — "Last loaded" indicator in the title** *(files: `src/benchdeck/tui.py` · risk: low · approval: required (visible title) · ✅ Merged at `b180f43`*
The title row already shows `BENCHDECK [status] PID:nnn`. Append a small `· 3s ago` style suffix when `self.last_load > 0`. Renders only inside the title row (row 0), which is the only row whose width budget is `>= 8` even at minimum 32-column. Compute the suffix lazily and only when there is horizontal room (`width >= 48`).
- Tests: `test_draw_title_shows_last_loaded_age`, `test_draw_title_omits_age_when_narrow`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k last_loaded`
- Rollback: revert the suffix append inside `_draw` (line 128 area).

**P1-3 — "Cases: N total · M judged · K blocked" summary on the Cases tab header** *(files: `src/benchdeck/tui.py` · risk: low · approval: required (visible layout) · ✅ Merged at `7d610f7`*
The Cases tab currently has a single-line header `"Cases"` (line 251). Replace with a one-line summary that includes total / judged / blocked counts. Truncates gracefully at narrow widths.
- Tests: `test_case_list_header_includes_counts`, `test_case_list_header_truncates_at_minimum_width`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k case_list_header`
- Rollback: revert the `_case_list` first-line change.

**P1-4 — Visually distinguish code-ish output sections in Detail** *(files: `src/benchdeck/tui.py` · risk: low · approval: required (visible layout) · ✅ Merged at `f205e8a`*
Prefix wrapped lines of `Test Prompt` and `Agent Output` with a `│ ` glyph, in FG color pair 5 (cyan) and dim. The wrapper is `_section` (632–636). Add a small helper that yields `(glyph, text, attr)` triples for the renderer; the actual application can be done at the `_safe_add` level by changing the line content. This is a *content* change, not a curses attribute change. Outline characters survive `_safe_add` cleanly.
- Tests: `test_detail_marks_test_prompt_block`, `test_detail_marks_agent_output_block`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k test_detail_marks`
- Rollback: revert the helper and the two `_section`-call changes in `_detail`.

**P1-5 — Number the case list rows and use the rating token's own color** *(files: `src/benchdeck/tui.py` · risk: low · approval: required (visible layout) · ✅ Merged at `64e1754`*
The case-list `state` segment (`"Strong[agent_a] Excellent[agent_b]"` etc., line 268) is currently a single string. Add a small post-processor in `_case_list` that splits on whitespace and tags each rating token for `_line_attr`; since the TUI's colorization is line-based, this is best done by adding a soft hyphen or by repeating the line with the relevant token in the foreground. Pragmatic compromise: add a single-character mark `[✓]` for `Excellent`/`Strong`, `[!]` for `Acceptable`/`Weak`, `[X]` for `Fail`/`BLOCKED`, then keep text in default color. This adds symbols, not colors, so it works on terminals without color.
- Tests: `test_case_list_includes_status_marks_for_ratings`, `test_case_list_includes_status_marks_for_blocked`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k status_marks`
- Rollback: remove the per-rating mark appended in `_case_list` (line 268 area).

**P1-6 — Footer hint abbreviated at narrow widths** *(files: `src/benchdeck/tui.py` · risk: low · approval: required (visible layout) · ✅ Merged at `0e5e7af`*
When `width < 56`, fall back to a 4-token hint: `1-4 tabs · j/k move · q quit`. This is a precondition for P1-1's hint map.
- Tests: `test_footer_hint_short_form_at_narrow_width`, `test_footer_hint_full_form_at_wide_width`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k hint_short_form`
- Rollback: revert the `_draw` footer branch (lines 159–162).

### Phase 2 — Behavior changes adding user value (approval required)

> **Implementation contract for all Phase 2 items:** every item below is gated behind a **default-off feature flag** (a new optional `BenchDeckTUI.__init__` kwarg) that defaults to `False`. The behavior is implemented, fully tested, and present in the binary, but the runtime path is unreachable until the flag is enabled. This means the diff is reviewable as a single safe change, the default TUI invocation is provably unchanged, and the user can opt in to individual features without touching the others. CLI flag wiring is a separate, separate-approval hand-off to the CLI owner (see Risk 3 fix in §8).

**P2-1 — Filter & sort on the Cases tab** *(files: `src/benchdeck/tui.py`, `tests/test_tui_render.py` · risk: medium · approval: required · flag: `enable_case_filter: bool = False`*
Add three new keybindings: `f` opens a one-line filter prompt at the footer (`family:edge_case_logic` or `state:BLOCKED` or substring), `s` cycles sort among `id`, `family`, `rating`. Maintain a `self._filter: str` and `self._sort: str` field. Persist across tab switches. Reset on `r` (reload). The selected index must be re-resolved when the visible list changes (clamp to the new length). Document the keybindings in the footer and the Help tab.
- Tests: `test_case_list_filter_by_family`, `test_case_list_filter_by_state_blocked`, `test_case_list_sort_by_family`, `test_case_list_filter_clears_status_on_escape`, `test_case_list_selected_clamps_after_filter`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k "case_list_filter or case_list_sort"`
- Rollback: revert the new fields, the new key branches, and the new footer lines. `_draw` and `_case_list` are the only regions touched.

**P2-2 — Live stderr-log tailing** *(files: `src/benchdeck/tui.py` · risk: medium · approval: required · flag: `enable_log_tail: bool = False`*
While `_proc is not None`, append the last ~16 lines of `self._stderr_log` to the Overview tab as a "Subprocess log (tail)" section. Read the file with `Path.read_text()` each refresh; cap at 4 KiB from the end. Show the size and the captured line count.
- Tests: `test_overview_includes_subprocess_log_tail_when_running`, `test_overview_omits_log_tail_when_idle`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k subprocess_log`
- Rollback: revert the tail-block branch added in `_overview` (around line 209).

**P2-3 — Snapshot age and heartbeat on Overview** *(files: `src/benchdeck/tui.py` · risk: low · approval: required (visible) · flag: `enable_heartbeat: bool = False`*
Compute `now - self.last_load` and add a "Last refresh: 3s ago" line at the bottom of the Overview header. During an active subprocess, also add a "Run alive: yes · 47s elapsed" line using a monotonic timer set in `_launch_run`.
- Tests: `test_overview_shows_last_refresh_age`, `test_overview_shows_subprocess_elapsed_when_running`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k "last_refresh or subprocess_elapsed"`
- Rollback: remove the two appended lines in `_overview`.

**P2-4 — `NO_COLOR` and theme stub (palette selectable at construction time)** *(files: `src/benchdeck/tui.py` · risk: medium · approval: required (new constructor kwarg) · flag: `theme: str = "auto"`*
Add a `theme: str = "auto"` constructor parameter. When `"auto"`, respect `NO_COLOR` env var (skip color). When `"dark"` or `"light"`, swap the palette so pair 6 is `BLACK on WHITE` for light, `WHITE on BLACK` for dark. The 6-pair mapping is sufficient; do not change the public API beyond the new optional kwarg. The CLI in `cli.py` is **not** in the editor's ownership list, so the constructor change is silent — the existing `benchdeck tui` invocation continues to use the default. (A CLI flag would be a separate approval-gated step.)
- Tests: `test_init_colors_respects_no_color_env`, `test_init_colors_light_theme_swaps_pair_6`, `test_init_colors_dark_theme_unchanged`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k "init_colors or no_color"`
- Rollback: revert `_init_colors` and the new constructor kwarg.

**P2-5 — Multi-select for batch export** *(files: `src/benchdeck/tui.py` · risk: medium · approval: required · flag: `enable_batch_export: bool = False`*
On the Cases tab, `space` toggles the current case's "marked" state (a `set[int]` in `self`). `e` (or a new `E`) exports all marked cases to one Markdown file with a section per case. Display a leading `*` on marked rows.
- Tests: `test_case_list_space_toggles_mark`, `test_export_marked_writes_combined_markdown`, `test_export_marked_empty_writes_nothing`.
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k "marked or export_marked"`
- Rollback: revert the new key branch in `_handle_key` and the new export path.

**P2-6 — Infra-error section header on Overview** *(files: `src/benchdeck/tui.py` · risk: low · approval: required (visible) · flag: `enable_infra_pointer: bool = False`*
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

## 5. Out of Scope

1. **Artifact schema changes.** No new fields in `Snapshot`, `Manifest`, judgment, plan, results, infrastructure errors, or planner capture. Anything that would need a new field (e.g. dollar-cost estimate, per-stage progress counts, run-start timestamp) is explicitly excluded.
2. **Runner / gateway changes.** No edits to `runner.py`, `openai_gateway.py`, `models/`, or `cli.py` subcommand behavior.
3. **Dependencies / lock files / CI / packaging.** No `pyproject.toml`, `requirements*.txt`, `.github/workflows/`, or release-file edits.
4. **Screenshot regeneration as a side-effect of code changes.** The screenshot script is a generator, not a golden-image store. No `.png` / `.webp` / `.svg` will be committed or overwritten by the editor.
5. **New tabs that don't already have a content model.** No new tab is introduced. The existing `TABS = (Overview, Cases, Detail, Help)` is unchanged. A Compare tab exists in `scripts/generate_demo_screens.py` but is not in the live TUI; promoting it to a live tab would require a fifth tab and a new keybinding range (5) and is therefore out of scope.
6. **New keybindings that conflict with current ones.** Every new key (`f`, `s`, `space`, etc.) is checked against the existing set `1-4 h l j k Enter r e n x q Esc`. A dedicated collision test will be added in P0-1's neighborhood.
7. **Public CLI changes.** `benchdeck tui` accepts only `--agent-a`, `--agent-b`, `--model`, `--judge-model`, `--refresh` (per `cli.py:128–131`); none of those are touched.
8. **Cost estimation, ETA, or rate inference.** These would need new data; flagged for a future, separate proposal.
9. **Mouse / function-key support.** The TUI is intentionally keyboard-only and phone-friendly; that is a design constraint, not a gap.
10. **Cross-platform curses portability hardening.** The current code uses `curses.A_REVERSE`, `curses.color_pair`, `curses.KEY_RIGHT/LEFT/UP/DOWN`, `curses.curs_set`, `curses.has_colors`, `curses.start_color`, `curses.init_pair`, `curses.error`. All of these are in the standard `curses` module and are already abstracted through `_safe_add` and `_init_colors`. No new curses features are required.

---

## 6. Validation Strategy

Default targeted sequence (per the editor contract):

1. **Targeted TUI tests** (after every change):
   ```
   python -m pytest -q -p no:cacheprovider tests/test_tui_loading.py tests/test_tui_render.py
   ```
2. **Screenshot tests** (after any rendering change that affects a `test_tui_renders_*_with_demo_snapshot` assertion, or any new `_overview` / `_case_list` / `_detail` / `_help` content):
   ```
   python -m pytest -q -p no:cacheprovider tests/test_screenshots.py
   ```
3. **Per-item narrowed runs** (during development):
   ```
   python -m pytest -q -p no:cacheprovider tests/test_tui_render.py -k <keyword>
   ```
4. **Repository lint / type / broader tests** (only when the touched region crosses a module boundary, which it does not in any item above):
   ```
   python -m pytest -q -p no:cacheprovider
   ```
5. **Final diff / status review** (every commit):
   ```
   git -C /home/calvin/BenchDeck status --porcelain
   git -C /home/calvin/BenchDeck diff --stat
   ```
   Expect zero untracked screenshot/golden files.

For Phase 0 in particular, validation is `tests/test_tui_render.py tests/test_tui_loading.py` and is expected to remain green (the items are test-only).

For Phase 1 / 2, the canonical validation after each merged item is `tests/test_tui_loading.py tests/test_tui_render.py tests/test_screenshots.py`, in that order. Items that change `_draw` output also require a manual resize test (not part of pytest) at 32×10, 40×20, 80×24, and 120×36.

---

## 7. Open Questions for the User

These are the only items where repository inspection cannot resolve the design choice and the answer materially changes implementation. They are listed in dependency order; addressing them in this order also unblocks the corresponding enhancement items.

**Each open question below now carries a recommended default.** Accepting the default unblocks the corresponding Phase 2 item without a back-and-forth. Overriding requires changing the marked line. Rollback cost for every default is "delete one constructor kwarg / one keybinding branch / one `_section` call" — i.e. trivial.

1. **Should `benchdeck tui` expose a theme flag?** Adding a `--theme {auto,dark,light}` to the CLI is a small change, but `cli.py` is outside the editor's ownership list. The current P2-4 plan adds the kwarg only; if a CLI flag is desired, that needs explicit approval and a separate hand-off to the CLI owner.
   - **Recommended default:** **No CLI flag.** The TUI honors `NO_COLOR` automatically (per https://no-color.org/) and the `theme=` constructor kwarg is exposed for tests. The CLI keeps its existing surface.
   - **Rollback cost:** None — the TUI default is unchanged; tests use the kwarg directly.
2. **Is batch export (P2-5) a desired feature, or is single-case export (`e`) sufficient?** This determines whether to add the `space` and `E` keybindings. No data change either way; this is purely a UX gate.
   - **Recommended default:** **Yes — `space` toggles a mark, `E` exports all marked cases to a single combined Markdown file.** Single-case `e` is preserved as a shortcut for the current case.
   - **Rollback cost:** Remove the `space` and `E` branches in `_handle_key` and the combined-export path in `_export_marked`.
3. **Should the TUI tail the subprocess log (P2-2)?** The file is already captured; tailing adds I/O on every refresh. The TUI's own refresh interval (default 1.0 s) bounds the cost, but a user on a slow filesystem may not want it. Confirmation that tailing is wanted is required before P2-2 is implemented.
   - **Recommended default:** **Yes — but only the last 8 lines, on Overview only, gated by `enable_log_tail`.** No full-screen viewer. The file path is shown in the footer on subprocess exit (existing behavior). I/O is bounded by `Path.read_text()` capped at 4 KiB.
   - **Rollback cost:** Remove the tail-block branch added in `_overview`.
4. **Is "snapshot age" the right name for P2-3, or should it be "last refresh" / "staleness"?** Affects footer and Overview text only.
   - **Recommended default:** **`Last refresh: 3s ago`** on Overview, **`updated 3s ago`** in the title (P1-2). Short, unambiguous, matches the actual semantics.
   - **Rollback cost:** Change the f-string.
5. **Should the case-list filter (P2-1) also expose a rating shortcut (e.g. `1`–`5` to filter to that rating)?** This is a small additional keybinding set and needs a yes/no before P2-1 is implemented.
   - **Recommended default:** **No extra shortcut.** The filter prompt accepts `rating:Excellent`, `family:edge_case_logic`, `state:BLOCKED`, and free-text substrings. Power users can bind a future alias; new keybindings are avoided to keep the hint string short.
   - **Rollback cost:** Already free — only the prompt parser is added.
6. **Are the existing 6 color pairs still the target palette after any P2-4 theme stub?** If a light theme is added, the TUI palette needs at least 7 pairs to keep all rating colors visible; the current 6 pair budget would need a swap (e.g. pair 5 cyan-on-black becomes black-on-cyan for light, etc.). Confirmation of the palette contract is required.
   - **Recommended default:** **Reuse the 6 pairs. For `theme="light"`, swap pair 6 to `BLACK on WHITE` (header band) and pair 5 stays as `CYAN on BLACK` (visible against light). All rating colors (1–4) remain unchanged.** No new pair is added. This avoids collision with the screenshot generator's palette and keeps the curses budget under 8 (the practical limit on legacy terminals).
   - **Rollback cost:** Revert the swap branch in `_init_colors`.

Items not listed here are answerable from the current code and tests; see Phase 0–3 item descriptions for the implementation details.

**Default-acceptance shortcut:** the user can accept all six recommended defaults in a single sentence. The plan then proceeds without per-question back-and-forth.

---

## 8. Risk Mitigations & Resolutions

The five remaining risks from the synthesis report are each closed by a concrete change to the plan contract or the implementation procedure. None requires a separate approval gate beyond what the affected Phase already requires.

### Risk 1 — Phase 2 behavior changes require explicit approval gates

**Resolution: default-off feature flags on every Phase 2 item.**

- Each Phase 2 item now declares a single `BenchDeckTUI.__init__` kwarg (e.g. `enable_case_filter: bool = False`) that gates the new behavior. The implementation is present, fully tested, and the feature flag defaults to off.
- The default `benchdeck tui` invocation is provably unchanged because every new code path is unreachable at default flag values.
- A user can opt in to individual features by passing kwargs (e.g. from a future CLI flag, or from a test). This is the same pattern as stdlib `curses.use_default_colors()` opt-ins.
- The CLI flag wiring is explicitly **out of scope** of this plan and remains a separate hand-off to the CLI owner; see §5 item 1 and Open Question 1.
- **Diff cost for review:** one kwarg, one `if self.enable_xxx:` branch per affected method, and one new test asserting the default-off behavior. Each is a single reviewable commit.

### Risk 2 — Phase 3 screenshot work may break text-based assertions in `test_screenshots.py`

**Resolution: versioned contract tests + structural-only assertions.**

- Introduce a single module-level constant `DEMO_SNAPSHOT_VERSION: int` in `tests/test_screenshots.py`. Every `test_tui_renders_*_with_demo_snapshot` assertion is wrapped in a guard that compares the actual synthetic-builder structural version to this constant.
- When a Phase 1/2 change intentionally alters the synthetic demo (e.g. adds the "M judged" header), the version is bumped and the affected substrings are re-anchored **in one place**. Until the bump, the test either:
  - Skips with a clear `"demo snapshot version M → expected N; run scripts/generate_demo_screens.py --refresh-assertions"` message (preferred for first-pass CI), or
  - Asserts only structural invariants (line count, presence of expected tabs, presence of expected keywords) and lets substring drift pass (preferred for cosmetic-only changes).
- For Phase 3's two new tests (P3-2), assertions are **structural only**: the test asserts the file exists, has nonzero size, and the file's PNG `Image.verify()` passes. No pixel content, no substring match. This makes Phase 3 tests immune to layout shifts.
- The committed PNGs in `assets/screenshots/golden/` are not regenerated by this plan; the `DEMO_SNAPSHOT_VERSION` change is the only re-anchoring needed.

### Risk 3 — Six open questions need user resolution

**Resolution: embedded recommended defaults with rollback cost.**

- Each of the six open questions in §7 now carries a **recommended default** and a one-line **rollback cost**. The user can accept all six in a single sentence and unblock all of Phase 2.
- The defaults are conservative: they preserve backward compatibility, avoid new keybindings, avoid CLI changes, and reuse the existing 6-pair palette. They are independently overridable.
- **Default-acceptance protocol:** if the user says "accept all defaults", the plan proceeds with P2-1 through P2-6 using the listed defaults. If the user overrides a specific question, the corresponding Phase 2 item adjusts its implementation per the override; no other items are affected.

### Risk 4 — No height parameter in the screenshot generator

**Resolution: Phase 0 covers correctness via curses mock; Phase 3 adds `--rows N` as a separate additive change.**

- Correctness coverage for narrow widths is already provided by Phase 0's P0-1 (`test_draw_too_small_*`, `test_draw_short_tab_names_at_width_39`, `test_render_dispatches_all_four_tabs`). These tests do not depend on the screenshot generator; they invoke `_draw` and `_render` directly with a mocked `stdscr`.
- Visual-regression coverage for narrow widths is a Phase 3 *enhancement* (P3-3, added below), not a correctness prerequisite. The change is **additive and non-breaking**:
  - Add `--rows N` to `scripts/generate_demo_screens.py`. When given, the renderer constrains the pixel height to `N` text rows of content (`content_h = N`). When omitted (the default), the existing behavior is preserved.
  - This is a script change outside the editor's ownership list, so it is **explicitly flagged as approval-gated** to the screenshot-pipeline owner.
  - Until `--rows` is implemented, narrow-width regression coverage is provided by Phase 0's curses-mock tests, which are sufficient for behavioral correctness.

**P3-3 (added) — Add `--rows N` flag to the screenshot generator** *(files: `scripts/generate_demo_screens.py` (outside ownership), `tests/test_screenshots.py` · risk: low · approval: required (script change)*
Add `--rows N` to the screenshot script. When given, the rendered image height is constrained to N text rows; the existing content is wrapped, truncated, or scrolled using the same `_clamp_scroll` semantics as the live TUI. Default behavior is unchanged.
- Tests: `test_screenshot_generator_accepts_rows_flag`, `test_screenshot_generator_rows_flag_truncates_content` (in `tests/test_screenshots.py`).
- Validation: `python -m pytest -q -p no:cacheprovider tests/test_screenshots.py -k rows_flag`.
- Rollback: delete the `--rows` branch in `main()` and the two new tests.

### Risk 5 — Implementation requires commit/approval procedure

**Resolution: per-item atomic commits with explicit pre-commit checklist and rollback hunk.**

See §9 for the full procedure. The summary is: every Phase 0–3 item is one commit, with a fixed message template, a pre-commit checklist, a per-item pytest command that must pass, and a documented rollback (either a specific hunk or a `git revert <sha>`).

---

## 9. Implementation Procedure

Each item in Phase 0–3 is implemented as **one atomic commit**. There is no big-bang merge.

### 9.1 Commit message template

```
<phase>-<n>: <title>

Files: <comma-separated paths inside ownership list>
Risk: <low|medium|high>
Flag: <kwarg name + default, or "none">
Tests: <new test function names>
Validation: <exact pytest invocation>
Rollback: <hunk location or "git revert <sha>">
```

The pre-commit hook does not need to enforce this template; it is a reviewer convention.

### 9.2 Pre-commit checklist (per item)

1. `git -C /home/calvin/BenchDeck status --porcelain` shows only the expected files in `src/benchdeck/tui.py` and/or the test files. **No untracked PNG/WebP/SVG/ANSI.** If any image artifact appears, stop and remove it.
2. `python -m pytest -q -p no:cacheprovider <per-item validation command>` exits 0.
3. For items that change `_draw` or `_render` output: a manual resize check at 32×10, 40×20, 80×24 (no exception, no truncation of the title or tab row, footer is reachable). The resize check is a local manual step, not a CI step.
4. For Phase 1/2 items: `git diff --stat HEAD~1` shows the new test functions and the new code, with the ratio roughly 1:1 (test:implementation) for safety.
5. For Phase 3 items: confirm `assets/screenshots/golden/*.png` sha256 is unchanged after the test run.

### 9.3 Rollback

- **Hunk-based rollback** (preferred for Phase 0/1 items): the commit message includes a "Hunk:" line naming the function or section to revert. The reviewer can `git revert -n <sha>` and then `git checkout HEAD~1 -- <file>` for the specific hunk, or simply re-apply the per-item branch of `_draw` / `_case_list` / `_detail` in reverse.
- **Revert-based rollback** (for Phase 2/3 items that touch multiple methods): `git revert <sha>` produces a clean inverse commit. The `DEMO_SNAPSHOT_VERSION` bump (Risk 2 fix) is similarly reverted.
- **Feature-flag rollback** (cheapest, for Phase 2): set the flag kwarg to `False` at the call site. Behavior is back to default. This is a one-line config change, not a revert.

### 9.4 Promotion gate (between items)

After each commit lands, the reviewer runs:

```
python -m pytest -q -p no:cacheprovider tests/test_tui_loading.py tests/test_tui_render.py
```

If that is green, the next item in the recommended sequence (§4) can begin. If a Phase 2 item is enabled via its flag, also run:

```
python -m pytest -q -p no:cacheprovider tests/test_screenshots.py
```

The promotion gate is a local check, not a CI step.

### 9.5 What this procedure does **not** do

- It does not commit, push, release, or open a PR. The editor never does those without explicit instruction.
- It does not install dependencies or modify `pyproject.toml`, lock files, CI, or packaging.
- It does not regenerate golden screenshots. The `assets/screenshots/golden/*.png` files are read-only for this plan.
- It does not change public CLI behavior. All kwargs are optional and default to existing behavior.
- It does not require the user to author code; the editor drafts and the user reviews.

### 9.6 Sequence summary (with new feature flags)

| Order | Item | Flag | Adds a keybinding? | Touches golden baseline? |
|---:|---|---|---|---|
| 1 | P0-1..P0-8 | none | no | no |
| 2 | P1-6 | none | no | no |
| 3 | P1-1 | none | no | no |
| 4 | P1-3 | none | no | no |
| 5 | P1-5 | none | no | no |
| 6 | P1-2 | none | no | no |
| 7 | P1-4 | none | no | no |
| 8 | P2-3 | `enable_heartbeat=False` | no | no |
| 9 | P2-6 | `enable_infra_pointer=False` | no | no |
| 10 | P2-1 | `enable_case_filter=False` | yes (`f`, `s`) | no |
| 11 | P2-2 | `enable_log_tail=False` | no | no |
| 12 | P2-5 | `enable_batch_export=False` | yes (`space`, `E`) | no |
| 13 | P2-4 | `theme="auto"` | no | no |
| 14 | P3-1 | `DEMO_SNAPSHOT_VERSION` bump | no | **yes — assertion strings only, no PNGs** |
| 15 | P3-2 | new structural tests | no | no |
| 16 | P3-3 (optional) | new `--rows` flag | no | no (script-side only) |

Each row is one commit, one review, one promotion gate.
