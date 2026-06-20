# TUI enhancement reference — status and current-state matrix

> Agent context note: this is detailed reference material split out of `docs/tui-enhancement-plan.md` during Cycle 7A. For routine agent context, start with `docs/context-handoffs/tui-enhancement-summary.md` and open this shard only when the specific implementation area is relevant.

## 0. Current Status

**Branch:** `main` (at `e3f1a93`, 7 commits ahead of `origin/main`).
**Last update:** post-P2-4 commit (2026-06-15). **Phase 2 is complete (6/6).**

| Phase | Status | Latest commit | Tests added | Production lines |
|---|---|---|---:|---:|
| Phase 0 | ✅ Complete | `d72033d` | +21 | 0 |
| Phase 1 | ✅ Complete | `82b6c5c` | +13 | ~+113 |
| Phase 2 | ✅ Complete (6/6, no merge commit) | `e3f1a93` | +22 | +464 |
| Phase 3 | ⏳ Not started | — | 0 | 0 |

**Total so far:** 20 items implemented (8 P0 + 6 P1 + 6 P2), 56 new tests, 0 to ~+577 production lines. All 168 TUI + screenshot tests pass; golden baselines unchanged.

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
| P2-2 | `deb5af1` | live stderr-log tail on Overview (3 tests; plan: 2) |
| P2-5 | `d4a21b4` | multi-select for batch export on the Cases tab (4 tests; plan: 3) |
| P2-4 | `e3f1a93` | `NO_COLOR` + theme stub (palette selectable at construction time) (4 tests; plan: 3) |

### Deviations from plan

- **P0-2**: +1 test (`test_detail_disagreement_counts_duplicate_ratings`) for the 2-1-1 split case (per-rating count arithmetic).
- **P0-6**: +1 test (`test_poll_subprocess_noop_when_proc_is_none`) for the early-return branch when `self._proc is None`.
- **P0-7**: +1 test (`test_launch_run_omits_agent_b_when_file_missing`) for the file-existence guard.
- **P1-1**: 2 new tests + 1 P1-6 test (`test_footer_hint_full_form_at_wide_width`) updated to match the new per-tab hint contract (the wide-form tokens changed from a flat list to per-tab hints).
- **P1-2**: +1 test (`test_draw_title_omits_age_before_first_load`) for the `last_load > 0` guard.
- **P1-4**: implementation also added a `Test Prompt` section to `_detail` (it was not previously rendered; the plan's wording assumed it was). The plan's stated test for the Test Prompt block would have failed otherwise.
- **P2-3**: +1 test (`test_overview_omits_heartbeat_when_flag_disabled`) for the Phase 2 default-off contract guard. Asserts that with `enable_heartbeat=False` (the default), neither the `Last refresh` nor the `Run alive` line appears in `_overview`, even when `last_load > 0` and a subprocess is alive. This locks down the Phase 2 default-off guarantee and matches the P0/P1 pattern of adding regression guards for invariant branches.
- **P2-1**: +1 test (`test_case_list_default_off_omits_filter_and_sort`) for the Phase 2 default-off contract guard. Asserts that with `enable_case_filter=False` (the default), `_case_list` ignores `_filter` and `_sort` and that the `f` / `s` keys are no-ops in `_handle_key`. The plan's "three new keybindings" wording is interpreted as two genuinely new keys (`f` to open the filter prompt, `s` to cycle sort) plus the transient use of existing `Enter` (apply) and `Esc` (cancel) inside the prompt — no third new keybinding is added. This matches the P0/P1 pattern of adding regression guards for invariant branches.
- **P2-2**: +1 test (`test_overview_default_off_omits_log_tail`) for the Phase 2 default-off contract guard. Asserts that with `enable_log_tail=False` (the default), the `Subprocess log` section does NOT appear in `_overview`, even if a subprocess is alive and a stderr log file exists with content. The plan text says "~16 lines" but the implementation uses 8 lines per the Q3 accepted default. This matches the P0/P1 pattern of adding regression guards for invariant branches.
- **P2-5**: +1 test (`test_case_list_default_off_omits_mark`) for the Phase 2 default-off contract guard. Asserts that with `enable_batch_export=False` (the default), the `space` and `E` keys are no-ops in `_handle_key` and the case list shows no `*` prefix. The plan does not specify whether marks should persist after a successful export; the implementation uses one-shot semantics (marks are cleared on success) so a second `E` press does not re-export the same set. Mid-implementation issues: (1) the first draft of the `*` column always added a column (using `" "` for unmarked rows), which shifted the `>` marker from column 0 to column 1, breaking the existing `test_case_list_selected_clamps_after_filter` assertion — fixed by gating the column on `enable_batch_export` so the default-off path is byte-identical to the original; (2) the first draft of the two export tests did not set `tui.tab = 1`, so the `E` keypress (gated by `tab == 1`) was a no-op — fixed by setting the tab in both tests.
- **P2-4**: +1 test (`test_init_colors_default_auto_preserves_current_palette`) for the Phase 2 default-off contract guard. Asserts that with `theme="auto"` (the default) and no `NO_COLOR` env var, the palette is byte-identical to the pre-P2-4 default (pair 6 = BLACK on CYAN). The plan text says "WHITE on BLACK for dark" but the test name `test_init_colors_dark_theme_unchanged` and the Q6 default (which only specifies the "light" swap) imply that "dark" should preserve the current default; the implementation follows the test name and Q6, not the plan text. `_init_colors` is refactored from `@staticmethod` to instance method so it can read `self.theme`; the call site in `_main` is unchanged because the new method takes no args other than `self`. This matches the P0/P1 pattern of adding regression guards for invariant branches.
- **Phase 2 commit pattern**: Phase 2 items (P2-3, P2-6, P2-1, P2-2, P2-5, P2-4) landed as individual commits on `main` rather than being merged from a `tui/enhancement` branch with `--no-ff` (the Phase 0/1 pattern). The "Latest commit" column for Phase 2 therefore shows the SHA of the last individual item (P2-4 = `e3f1a93`), not a phase-level merge SHA. Per-item atomicity and review discipline are preserved; only the merge ceremony differs.

### Branch / merge history

- `main` is currently at `e3f1a93` (post-P2-4 commit; 7 ahead of `origin/main`).
- `tui/enhancement` is stale at `747268e` (Phase 2 work has landed on `main` directly).
- Phase 0 and Phase 1 used `--no-ff` merge commits to formalize phase boundaries. Phase 2 was executed as six individual commits on `main` (P2-3, P2-6, P2-1, P2-2, P2-5, P2-4) without a phase-level merge commit. Per-item atomicity is preserved; the merge ceremony is dropped for Phase 2 to keep the per-item review discipline tight.
- Golden baselines at `assets/screenshots/golden/*.png` have not changed (Phase 0 + Phase 1 + Phase 2 are content-only and default-off; no screenshot regeneration).

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
