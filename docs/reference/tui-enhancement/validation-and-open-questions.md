# TUI enhancement reference — out-of-scope boundaries, validation, and open questions

> Agent context note: this is detailed reference material split out of `docs/tui-enhancement-plan.md` during Cycle 7A. For routine agent context, start with `docs/context-handoffs/tui-enhancement-summary.md` and open this shard only when the specific implementation area is relevant.

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
