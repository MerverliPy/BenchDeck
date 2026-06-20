from __future__ import annotations

import contextlib
import curses
import datetime
import os
import subprocess as _sp
import time
from pathlib import Path
from typing import Any

from ..loader import Snapshot, load_snapshot
from ..manifest import Manifest
from .helpers import (
    _filter_matches,
    _rating_order,
    _section,
    _status_mark_for_state,
)


class BenchDeckTUI:
    """Narrow-terminal TUI designed for SSH clients and phone keyboards."""

    TABS = ("Overview", "Cases", "Detail", "Help")

    FOOTER_HINTS: dict[int, list[str]] = {
        0: ["h/l tabs", "j/k move", "n run", "r reload", "q quit"],
        1: ["Enter open", "e export", "j/k move", "h/l tabs", "q quit"],
        2: ["j/k scroll", "h/l tabs", "r reload", "q quit"],
        3: ["h/l tabs", "q quit"],
    }

    FOOTER_HINTS_NARROW: dict[int, str] = {
        0: "h/l tabs · j/k scroll · n run · q quit",
        1: "Enter open · e export · j/k move · q quit",
        2: "j/k scroll · h/l tabs · r reload · q quit",
        3: "h/l tabs · q quit",
    }

    def __init__(
        self,
        run_dir: Path,
        refresh_seconds: float = 1.0,
        agent_a_path: Path | None = None,
        agent_b_path: Path | None = None,
        model: str | None = None,
        judge_model: str | None = None,
        enable_heartbeat: bool = False,
        enable_infra_pointer: bool = False,
        enable_case_filter: bool = False,
        enable_log_tail: bool = False,
        enable_batch_export: bool = False,
        theme: str = "auto",
    ) -> None:
        self.run_dir = run_dir
        self.refresh_seconds = refresh_seconds
        self.tab = 0
        self.selected = 0
        self.scroll = 0
        self.snapshot = Snapshot()
        self.last_load = 0.0
        self._status_msg = ""
        self._proc: _sp.Popen[bytes] | None = None
        self._proc_run_dir: Path | None = None
        self._proc_started_at: float = 0.0
        self._agent_a_path = agent_a_path
        self._agent_b_path = agent_b_path
        self._model = model
        self._judge_model = judge_model
        self._cancel_requested_at: float | None = None
        self._has_color = False
        self._stderr_handle: Any = None
        self._stderr_log: Path | None = None
        self.enable_heartbeat = enable_heartbeat
        self.enable_infra_pointer = enable_infra_pointer
        self.enable_case_filter = enable_case_filter
        self._filter: str = ""
        self._sort: str = "id"
        self._filter_mode: bool = False
        self._filter_draft: str = ""
        self.enable_log_tail = enable_log_tail
        self.enable_batch_export = enable_batch_export
        self._marked: set[int] = set()
        self.theme = theme

    @classmethod
    def render_headless(
        cls,
        run_dir: Path,
        width: int = 80,
        tab: int = 0,
        enable_heartbeat: bool = False,
        enable_infra_pointer: bool = False,
        enable_case_filter: bool = False,
        enable_log_tail: bool = False,
        enable_batch_export: bool = False,
        theme: str = "auto",
    ) -> list[str]:
        tui = cls(
            run_dir=run_dir,
            refresh_seconds=0,
            enable_heartbeat=enable_heartbeat,
            enable_infra_pointer=enable_infra_pointer,
            enable_case_filter=enable_case_filter,
            enable_log_tail=enable_log_tail,
            enable_batch_export=enable_batch_export,
            theme=theme,
        )
        tui.snapshot = load_snapshot(run_dir)
        tui.tab = max(0, min(3, tab))
        tui.last_load = time.monotonic()
        return tui._render(width)

    def run(self) -> None:
        curses.wrapper(self._main)

    def _main(self, stdscr: Any) -> None:
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.keypad(True)
        self._has_color = self._init_colors()
        while True:
            now = time.monotonic()
            if now - self.last_load >= self.refresh_seconds:
                active_dir = self._proc_run_dir or self.run_dir
                self.snapshot = load_snapshot(active_dir)
                self.last_load = now
            self._poll_subprocess()
            if self._cancel_requested_at and time.monotonic() - self._cancel_requested_at > 3.0:
                self._cancel_requested_at = None
            self._draw(stdscr)
            key = stdscr.getch()
            if key in (ord("q"), 27):
                if self._proc is not None:
                    self._cancel_run()
                break
            self._handle_key(key)
            time.sleep(0.05)

    def _handle_key(self, key: int) -> None:
        if key != ord("x") and self._cancel_requested_at is not None:
            self._cancel_requested_at = None
        if self._filter_mode and self.enable_case_filter:
            if key in (10, 13):
                self._filter = self._filter_draft
                self._filter_mode = False
                self._status_msg = (
                    f"Filter applied: {self._filter!r}" if self._filter else "Filter cleared"
                )
                return
            if key == 27:
                self._filter_draft = self._filter
                self._filter_mode = False
                self._status_msg = "Filter cancelled"
                return
            if key in (curses.KEY_BACKSPACE, 127, 8):
                self._filter_draft = self._filter_draft[:-1]
                return
            if 0x20 <= key < 0x7F:
                self._filter_draft += chr(key)
                return
            return
        if key in (ord("1"), ord("2"), ord("3"), ord("4")):
            self.tab = key - ord("1")
            self.scroll = 0
        elif key in (curses.KEY_RIGHT, ord("l")):
            self.tab = min(len(self.TABS) - 1, self.tab + 1)
            self.scroll = 0
        elif key in (curses.KEY_LEFT, ord("h")):
            self.tab = max(0, self.tab - 1)
            self.scroll = 0
        elif key in (curses.KEY_DOWN, ord("j")):
            if self.tab == 1:
                self.selected = min(max(0, len(self._cases()) - 1), self.selected + 1)
            else:
                self.scroll += 1
        elif key in (curses.KEY_UP, ord("k")):
            if self.tab == 1:
                self.selected = max(0, self.selected - 1)
            else:
                self.scroll = max(0, self.scroll - 1)
        elif key in (10, 13) and self.tab == 1:
            self.tab = 2
            self.scroll = 0
        elif key == ord("f") and self.tab == 1 and self.enable_case_filter:
            self._filter_mode = True
            self._filter_draft = self._filter
        elif key == ord("s") and self.tab == 1 and self.enable_case_filter:
            cycle = {"id": "family", "family": "rating", "rating": "id"}
            self._sort = cycle.get(self._sort, "id")
            self._status_msg = f"Sort: {self._sort}"
        elif key == ord(" ") and self.tab == 1 and self.enable_batch_export:
            cases = self._cases()
            if cases:
                self.selected = min(self.selected, len(cases) - 1)
                case = cases[self.selected]
                cid = case.get("id")
                if isinstance(cid, int):
                    if cid in self._marked:
                        self._marked.discard(cid)
                    else:
                        self._marked.add(cid)
        elif key == ord("E") and self.tab == 1 and self.enable_batch_export:
            self._export_marked()
        elif key == ord("r"):
            self.snapshot = load_snapshot(self.run_dir)
            self.last_load = time.monotonic()
            if self.enable_case_filter:
                self._filter = ""
                self._sort = "id"
            if self.enable_batch_export:
                self._marked = set()
        elif key == ord("e") and self.tab == 1:
            self._export_case()
        elif key == ord("n"):
            self._launch_run()
        elif key == ord("x"):
            self._handle_cancel_key()

    def _draw(self, stdscr: Any) -> None:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        if height < 10 or width < 32:
            self._safe_add(stdscr, 0, 0, "Terminal too small (min 32x10)", width)
            stdscr.refresh()
            return
        title = " BENCHDECK "
        proc_info = f" PID:{self._proc.pid}" if self._proc else ""
        status = str(self.snapshot.metadata.get("status", "no run"))
        title_str = title + f"[{status}]{proc_info}"
        if self.last_load > 0 and width >= 48:
            elapsed = int(time.monotonic() - self.last_load)
            title_str += f" · {elapsed}s ago"
        title_attr = curses.A_REVERSE
        tab_attr: int = curses.A_BOLD
        footer_attr: int = curses.A_REVERSE
        content_default_attr: int = 0
        if self._has_color:
            title_attr = curses.color_pair(6) | curses.A_BOLD
            tab_attr = curses.color_pair(5) | curses.A_BOLD
            footer_attr = curses.color_pair(6) | curses.A_BOLD
        self._safe_add(stdscr, 0, 0, title_str, width, title_attr)
        tab_names = ("Ov", "Ca", "De", "He") if width < 40 else self.TABS
        tab_line = " ".join(
            f"{i + 1}:{tab_names[i]}" if i != self.tab else f"[{i + 1}:{tab_names[i]}]"
            for i in range(len(self.TABS))
        )
        self._safe_add(stdscr, 1, 0, tab_line, width, tab_attr)
        lines = self._render(width)
        plan_data = self.snapshot.plan
        if plan_data and not plan_data.get("cases") and not self._status_msg:
            self._status_msg = "WARNING: plan loaded but contains no cases"
        elif (
            plan_data
            and plan_data.get("cases")
            and self._status_msg == "WARNING: plan loaded but contains no cases"
        ):
            self._status_msg = ""
        view_height = height - 4
        self.scroll = self._clamp_scroll(lines, view_height, self.scroll, self.tab, self.selected)
        viewport = lines[self.scroll : self.scroll + view_height]
        for row, line in enumerate(viewport, start=2):
            attr = content_default_attr
            if self._has_color:
                attr = self._line_attr(line)
            self._safe_add(stdscr, row, 0, line, width, attr)
        if view_height > 0:
            max_scroll = max(0, len(lines) - view_height)
            if self.scroll > 0:
                self._safe_add(stdscr, 2, width - 2, " ↑", width)
            if self.scroll < max_scroll:
                self._safe_add(stdscr, 2 + view_height - 1, width - 2, " ↓", width)
        if self._filter_mode and self.enable_case_filter:
            status = f"Filter: {self._filter_draft}█  (Enter apply, Esc cancel)"
        else:
            status = self._status_msg
            if not status:
                if width < 56:
                    status = self.FOOTER_HINTS_NARROW.get(self.tab, self.FOOTER_HINTS_NARROW[0])
                    if self.tab == 1 and self.enable_case_filter:
                        status = "Enter · e export · f filter · s sort · q quit"
                else:
                    hints = self.FOOTER_HINTS.get(self.tab, self.FOOTER_HINTS[0])
                    if self.tab == 1 and self.enable_case_filter:
                        hints = [
                            "Enter open",
                            "e export",
                            "f filter",
                            "s sort",
                            "j/k move",
                            "h/l tabs",
                            "q quit",
                        ]
                    status = " | ".join(hints)
        self._safe_add(stdscr, height - 1, 0, status, width, footer_attr)
        stdscr.refresh()

    def _render(self, width: int) -> list[str]:
        if self.tab == 0:
            return self._overview(width)
        if self.tab == 1:
            return self._case_list(width)
        if self.tab == 2:
            return self._detail(width)
        return self._help(width)

    def _overview(self, width: int) -> list[str]:
        m = self.snapshot.metadata
        t = self.snapshot.tally
        agents = sorted(t.keys()) if isinstance(t, dict) and t else []
        planned = int(m.get("cases_in_plan") or 0)
        judged = int(m.get("executions_judged") or 0)
        blocks = int(m.get("policy_blocks") or 0)
        infra = int(m.get("infrastructure_failures") or 0)
        ratio = judged / planned if planned else 0.0
        bar_width = max(8, min(30, width - 16))
        filled = int(bar_width * ratio)
        bar = "#" * filled + "-" * (bar_width - filled)
        usage = m.get("token_usage") or {}
        lines = [
            f"Run: {self.run_dir}",
            f"Progress [{bar}] {judged}/{planned}",
            f"Policy blocks: {blocks}   Infra failures: {infra}",
            f"Requests: {usage.get('requests', 0)}   Tokens: {usage.get('total_tokens', 0):,}",
        ]
        pc = self.snapshot.planner_capture or {}
        if pc:
            value = pc.get("value") or {}
            mode = value.get("mode", "?")
            pc_attempts = pc.get("attempts", [])
            total_in = sum(a.get("usage", {}).get("input_tokens", 0) for a in pc_attempts)
            total_out = sum(a.get("usage", {}).get("output_tokens", 0) for a in pc_attempts)
            pc_tokens = total_in + total_out
            http_attempts = pc.get("total_http_attempts", 0)
            lines.append(f"Planner: {mode} mode, {http_attempts} HTTP attempts, {pc_tokens} tokens")
            if pc.get("terminal_error"):
                err = pc["terminal_error"]
                msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                lines.append(f"  WARNING: planner terminal error: {msg}")
            if pc.get("parse_error"):
                lines.append(f"  WARNING: planner parse error: {pc['parse_error']}")
        if self.enable_infra_pointer and infra > 0:
            lines.append(f"Infra failures: {infra} (see Detail tab)")
        if self.enable_heartbeat:
            if self.last_load > 0:
                refresh_elapsed = int(time.monotonic() - self.last_load)
                lines.append(f"Last refresh: {refresh_elapsed}s ago")
            if self._proc is not None and self._proc_started_at > 0:
                run_elapsed = int(time.monotonic() - self._proc_started_at)
                lines.append(f"Run alive: yes · {run_elapsed}s elapsed")
        lines.append("")
        manifest = Manifest.load(self.run_dir)
        gen = manifest.generation
        if gen > 0:
            manifest_issues = manifest.verify()
            if manifest_issues:
                lines.append(
                    f"Manifest gen {gen}: WARNING — {len(manifest_issues)} integrity issue(s)"
                )
            else:
                lines.append(f"Manifest gen {gen}: valid")
        else:
            lines.append("Manifest: not yet present")
        lines.append("")
        if (
            self.enable_log_tail
            and self._proc is not None
            and self._stderr_log is not None
            and self._stderr_log.exists()
        ):
            try:
                size_bytes = self._stderr_log.stat().st_size
            except OSError:
                size_bytes = 0
            text = ""
            if size_bytes > 0:
                try:
                    text = self._stderr_log.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    text = ""
            if len(text) > 4096:
                text = text[-4096:]
            all_lines = text.splitlines()
            line_count = len(all_lines)
            tail_lines = all_lines[-8:]
            lines.append(
                f"Subprocess log (last {len(tail_lines)} of {line_count} lines, "
                f"{size_bytes} bytes):"
            )
            lines.extend(tail_lines)
        if not agents:
            return lines + ["No tally data yet."]
        if len(agents) == 1:
            agent_tally = t.get(agents[0], {})
            lines += self._render_agent_section(agents[0], agent_tally)
        else:
            for agent_label in agents:
                agent_tally = t.get(agent_label, {})
                lines.append(f"── {agent_label} ──")
                lines += self._render_agent_section(agent_label, agent_tally)
        return lines

    def _render_agent_section(self, agent_label: str, agent_tally: dict[str, Any]) -> list[str]:
        lines = ["Ratings (0-4 scale)"]
        for name in ("Excellent", "Strong", "Acceptable", "Weak", "Fail"):
            count = (agent_tally.get("rating_counts") or {}).get(name, 0)
            lines.append(f"  {name:<10} {count}")
        family_scores = agent_tally.get("family_scores") or {}
        if family_scores:
            lines += ["", "Family scores"]
            for family, score in family_scores.items():
                lines.append(f"  {family:<23} {score}")
        return lines

    def _case_list(self, width: int) -> list[str]:
        cases = self._cases()
        judgments_by_case: dict[int, list[dict[str, Any]]] = {}
        for j in self.snapshot.judgments:
            cid = j.get("case_id")
            if cid is not None:
                judgments_by_case.setdefault(cid, []).append(j)
        blocks = {b.get("case_id"): b for b in self.snapshot.policy_blocks}
        case_ids = {c.get("id") for c in cases if isinstance(c.get("id"), int)}
        total = len(case_ids)
        judged = sum(1 for cid in case_ids if cid in judgments_by_case)
        blocked = sum(1 for cid in case_ids if cid in blocks)
        visible: list[tuple[dict[str, Any], str]] = []
        if self.enable_case_filter:
            for case in cases:
                cid = case.get("id")
                if not isinstance(cid, int):
                    continue
                case_judgments = judgments_by_case.get(cid)
                if case_judgments:
                    state = " ".join(
                        f"{j.get('overall_rating', '?')}[{j.get('agent_label', '')}]"
                        for j in case_judgments
                    )
                elif cid in blocks:
                    state = "BLOCKED"
                else:
                    state = "PENDING"
                if _filter_matches(self._filter, case, state):
                    visible.append((case, state))
            if self._sort == "family":
                visible.sort(
                    key=lambda cs: (str(cs[0].get("family", "")).lower(), cs[0].get("id", 0))
                )
            elif self._sort == "rating":
                visible.sort(key=lambda cs: (_rating_order(cs[1]), cs[0].get("id", 0)))
            if visible:
                self.selected = min(self.selected, len(visible) - 1)
            else:
                self.selected = 0
            f_judged = sum(1 for _, s in visible if s != "PENDING" and s != "BLOCKED")
            f_blocked = sum(1 for _, s in visible if s == "BLOCKED")
            header = (
                f"Cases: {len(visible)} of {total} total · {f_judged} judged · {f_blocked} blocked"
            )
            if self._sort != "id":
                header += f" · sort:{self._sort}"
        else:
            header = f"Cases: {total} total · {judged} judged · {blocked} blocked"
        if len(header) > width:
            header = header[: width - 1] + "\u2026"
        lines = [header]
        if not self.enable_case_filter:
            for index, case in enumerate(cases):
                case_id = case.get("id")
                if not isinstance(case_id, int):
                    continue
                case_judgments = judgments_by_case.get(case_id)
                if case_judgments:
                    parts = []
                    for jj in case_judgments:
                        agent = jj.get("agent_label", "")
                        rating = jj.get("overall_rating", "?")
                        parts.append(f"{rating}[{agent}]")
                    state = " ".join(parts)
                elif case_id in blocks:
                    state = "BLOCKED"
                else:
                    state = "PENDING"
                mark = _status_mark_for_state(state)
                if mark:
                    state = f"{mark} {state}"
                marker = ">" if index == self.selected else " "
                star = ("*" if case_id in self._marked else " ") if self.enable_batch_export else ""
                title = str(case.get("title", "Untitled"))
                prefix = f"{star}{marker}{case_id:>2} "
                available = max(8, width - len(prefix) - len(state) - 1)
                lines.append(prefix + state + " " + title[:available])
        else:
            for index, (case, state) in enumerate(visible):
                case_id = case.get("id")
                if not isinstance(case_id, int):
                    continue
                mark = _status_mark_for_state(state)
                if mark:
                    state = f"{mark} {state}"
                marker = ">" if index == self.selected else " "
                star = ("*" if case_id in self._marked else " ") if self.enable_batch_export else ""
                title = str(case.get("title", "Untitled"))
                prefix = f"{star}{marker}{case_id:>2} "
                available = max(8, width - len(prefix) - len(state) - 1)
                lines.append(prefix + state + " " + title[:available])
        return lines

    def _detail(self, width: int) -> list[str]:
        cases = self._cases()
        if not cases:
            return ["No benchmark plan found."]
        self.selected = min(self.selected, len(cases) - 1)
        case = cases[self.selected]
        case_id = case.get("id")
        case_judgments = [j for j in self.snapshot.judgments if j.get("case_id") == case_id]
        lines = [
            f"Case {case_id}: {case.get('title', '')}",
            f"Family: {case.get('family', '')}",
            "",
        ]
        lines += _section("Purpose", str(case.get("purpose", "")), width)
        lines += _section(
            "Test Prompt",
            str(case.get("test_prompt", "")),
            width,
            prefix="│ ",
        )
        if case_judgments:
            for j_idx, judgment in enumerate(case_judgments):
                if j_idx > 0:
                    lines.append("---")
                agent = judgment.get("agent_label", "")
                lines.append(f"Agent: {agent}")
                lines += _section("Rating", str(judgment.get("overall_rating", "")), width)
                lines += _section("Why", str(judgment.get("why", "")), width)
                gate = judgment.get("gate_check") or {}
                lines += _section("Gate", f"{gate.get('status')}: {gate.get('reason', '')}", width)
                result = self._result_for(case_id, agent)
                if result:
                    lines += _section(
                        "Agent output",
                        str(result.get("final_output", "")),
                        width,
                        prefix="│ ",
                    )
        else:
            agent_results = {}
            for agent_label in self.snapshot.results:
                r = self._result_for(case_id, agent_label=agent_label)
                if r and r.get("infrastructure_error"):
                    agent_results[agent_label] = r
            if agent_results:
                for agent_label in agent_results:
                    lines += [
                        f"Agent {agent_label}: infrastructure error — empty output after retries"
                    ]
            else:
                lines += ["No judgment yet."]
        if len(case_judgments) > 1:
            ratings = {j.get("overall_rating", "?") for j in case_judgments}
            if len(ratings) > 1:
                lines.append("")
                lines.append("Judge disagreement detected:")
                for r in sorted(ratings):
                    count = sum(1 for j in case_judgments if j.get("overall_rating") == r)
                    lines.append(f"  {r}: {count} judge(s)")

        case_infra = [
            ie for ie in self.snapshot.infrastructure_errors if ie.get("case_id") == case_id
        ]
        if case_infra:
            lines.append("")
            lines += ["Infrastructure error details:"]
            for ie in case_infra:
                lines += [
                    f"  Stage: {ie.get('stage', '?')}",
                    f"  Type: {ie.get('error_type', '?')}",
                    f"  Message: {ie.get('message', '')}",
                    f"  Agent: {ie.get('agent_label', '?')}",
                ]
                if ie.get("response_id"):
                    lines.append(f"  Response ID: {ie['response_id']}")
                if ie.get("attempts"):
                    lines.append(f"  Attempts: {ie['attempts']}")
        orphan_errors = [
            ie for ie in self.snapshot.infrastructure_errors if ie.get("case_id") is None
        ]
        if orphan_errors:
            lines.append("")
            lines += ["Pre-execution infrastructure errors:"]
            for ie in orphan_errors:
                lines += [
                    f"  Stage: {ie.get('stage', '?')}",
                    f"  Type: {ie.get('error_type', '?')}",
                    f"  Message: {ie.get('message', '')}",
                    f"  Agent: {ie.get('agent_label', '?')}",
                ]
        return lines

    def _help(self, width: int) -> list[str]:
        return [
            "Mobile SSH controls",
            "",
            "1-4      open a screen",
            "h / l    previous / next screen",
            "j / k    move selection or scroll",
            "Enter    open selected case",
            "e        export case as Markdown",
            "f        filter cases (family: / state: / rating: / text)",
            "s        cycle sort: id / family / rating",
            "n        launch a new benchmark run",
            "x        cancel running subprocess",
            "r        reload artifacts",
            "q / Esc  quit",
            "",
            "The UI uses no mouse and no function keys, making it practical",
            "inside Termius and other phone SSH clients.",
        ]

    def _cases(self) -> list[dict[str, Any]]:
        return list(self.snapshot.plan.get("cases") or [])

    def _result_for(
        self, case_id: int | None, agent_label: str | None = None
    ) -> dict[str, Any] | None:
        for agent_label_key, agent_results in self.snapshot.results.items():
            if agent_label is not None and agent_label_key != agent_label:
                continue
            for result in agent_results:
                if result.get("case_id") == case_id:
                    return result
        return None

    def _export_case(self) -> None:
        cases = self._cases()
        if not cases:
            return
        self.selected = min(self.selected, len(cases) - 1)
        case = cases[self.selected]
        case_id = case.get("id", "unknown")
        case_judgments = [j for j in self.snapshot.judgments if j.get("case_id") == case_id]
        ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        filename = str(self.run_dir / f"case_{case_id}_{ts}.md")
        lines = [
            f"# Case {case_id}: {case.get('title', 'Untitled')}",
            "",
            f"**Family:** {case.get('family', '')}",
            f"**Exported:** {ts}",
            "",
            "## Purpose",
            "",
            str(case.get("purpose", "")),
            "",
            "## Test Prompt",
            "",
            "```",
            str(case.get("test_prompt", "")),
            "```",
            "",
            "## Judgments",
            "",
        ]
        if case_judgments:
            for judgment in case_judgments:
                agent = judgment.get("agent_label", "unknown")
                lines.append(f"### Agent: {agent}")
                lines.append(f"**Rating:** {judgment.get('overall_rating', '?')}")
                gate = judgment.get("gate_check") or {}
                lines.append(f"**Gate:** {gate.get('status', '?')} — {gate.get('reason', '')}")
                lines.append(f"**Why:** {judgment.get('why', '')}")
                lines.append("")
        else:
            lines.append("*No judgments yet.*")
            lines.append("")
        result = self._result_for(case_id)
        if result:
            lines.append("## Agent Output")
            lines.append("")
            lines.append("```")
            lines.append(str(result.get("final_output", "")))
            lines.append("```")
            lines.append("")
        try:
            Path(filename).write_text("\n".join(lines), encoding="utf-8")
            self._status_msg = f"Exported {filename}"
        except OSError as exc:
            self._status_msg = f"Export failed: {exc}"

    def _export_marked(self) -> None:
        if not self._marked:
            self._status_msg = "No marked cases to export"
            return
        cases_by_id: dict[int, dict[str, Any]] = {}
        for case in self._cases():
            cid = case.get("id")
            if isinstance(cid, int):
                cases_by_id[cid] = case
        marked_ids = sorted(cid for cid in self._marked if cid in cases_by_id)
        if not marked_ids:
            self._status_msg = "No marked cases to export (none match plan)"
            return
        ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        filename = str(self.run_dir / f"cases_{ts}.md")
        lines: list[str] = [
            f"# Exported Cases ({len(marked_ids)} marked)",
            "",
            f"**Exported:** {ts}",
            "",
            "---",
            "",
        ]
        for idx, cid in enumerate(marked_ids):
            case = cases_by_id[cid]
            case_judgments = [j for j in self.snapshot.judgments if j.get("case_id") == cid]
            result = self._result_for(cid)
            lines += [
                f"## Case {cid}: {case.get('title', 'Untitled')}",
                "",
                f"**Family:** {case.get('family', '')}",
                "",
                "### Purpose",
                "",
                str(case.get("purpose", "")),
                "",
                "### Test Prompt",
                "",
                "```",
                str(case.get("test_prompt", "")),
                "```",
                "",
                "### Judgments",
                "",
            ]
            if case_judgments:
                for judgment in case_judgments:
                    agent = judgment.get("agent_label", "unknown")
                    lines.append(f"#### Agent: {agent}")
                    lines.append(f"**Rating:** {judgment.get('overall_rating', '?')}")
                    gate = judgment.get("gate_check") or {}
                    lines.append(f"**Gate:** {gate.get('status', '?')} — {gate.get('reason', '')}")
                    lines.append(f"**Why:** {judgment.get('why', '')}")
                    lines.append("")
            else:
                lines.append("*No judgments yet.*")
                lines.append("")
            if result:
                lines.append("### Agent Output")
                lines.append("")
                lines.append("```")
                lines.append(str(result.get("final_output", "")))
                lines.append("```")
                lines.append("")
            if idx < len(marked_ids) - 1:
                lines.append("---")
                lines.append("")
        try:
            Path(filename).write_text("\n".join(lines), encoding="utf-8")
            self._status_msg = f"Exported {len(marked_ids)} cases to {filename}"
            self._marked = set()
        except OSError as exc:
            self._status_msg = f"Export failed: {exc}"

    def _poll_subprocess(self) -> None:
        if self._proc is None:
            return
        rc = self._proc.poll()
        if rc is not None:
            if self._stderr_handle:
                self._stderr_handle.close()
                self._stderr_handle = None
            tag = "ok" if rc == 0 else f"exit={rc}"
            msg = f"Subprocess {self._proc.pid}: {tag}"
            if rc != 0 and self._stderr_log:
                msg += f" (log: {self._stderr_log.name})"
            self._status_msg = msg
            self._proc = None
            self._proc_run_dir = None
            self._stderr_log = None
            self._proc_started_at = 0.0

    def _launch_run(self) -> None:
        if self._proc is not None:
            self._status_msg = "A run is already in progress"
            return
        if self._stderr_handle:
            self._stderr_handle.close()
            self._stderr_handle = None
        base_dir = self.run_dir
        if base_dir.is_file():
            base_dir = base_dir.parent
        ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        run_dir = base_dir / ts
        cfg = self.snapshot.metadata.get("config") or {}
        agent_a = self._agent_a_path or Path(str(cfg.get("agent_a", "")))
        agent_b = self._agent_b_path or (Path(str(cfg["agent_b"])) if cfg.get("agent_b") else None)
        model = self._model or cfg.get("model") or "gpt-4o-mini"
        judge_model = self._judge_model or cfg.get("judge_model") or model
        if not agent_a.exists():
            self._status_msg = f"Agent file not found: {agent_a}"
            return
        cmd: list[str] = [
            "python",
            "-m",
            "benchdeck",
            "run",
            "--agent-a",
            str(agent_a),
            "--output-dir",
            str(run_dir.parent),
            "--model",
            model,
            "--judge-model",
            judge_model,
        ]
        if agent_b and agent_b.exists():
            cmd += ["--agent-b", str(agent_b)]
        try:
            stderr_log = run_dir.parent / f"benchdeck_{run_dir.name}.log"
            self._stderr_log = stderr_log
            self._stderr_handle = open(stderr_log, "wb")  # noqa: SIM115
            self._proc = _sp.Popen(
                cmd,
                stdout=self._stderr_handle,
                stderr=_sp.STDOUT,
            )
            self._proc_run_dir = run_dir
            self._proc_started_at = time.monotonic()
            self._status_msg = f"Launched PID {self._proc.pid} → {run_dir.name}"
        except OSError as exc:
            self._status_msg = f"Launch failed: {exc}"

    def _handle_cancel_key(self) -> None:
        if self._proc is None:
            self._status_msg = "No subprocess to cancel"
            return
        now = time.monotonic()
        if self._cancel_requested_at is not None and now - self._cancel_requested_at < 3.0:
            self._cancel_requested_at = None
            self._cancel_run()
        else:
            self._cancel_requested_at = now
            self._status_msg = "Press x again to confirm cancel"

    def _cancel_run(self) -> None:
        if self._proc is None:
            self._status_msg = "No subprocess to cancel"
            return
        pid = self._proc.pid
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except _sp.TimeoutExpired:
            self._proc.kill()
        if self._stderr_handle:
            self._stderr_handle.close()
            self._stderr_handle = None
        self._status_msg = f"Cancelled PID {pid}"
        self._proc = None
        self._proc_run_dir = None
        self._stderr_log = None
        self._proc_started_at = 0.0

    @staticmethod
    def _clamp_scroll(
        lines: list[str], view_height: int, scroll: int, tab: int, selected: int
    ) -> int:
        max_scroll = max(0, len(lines) - view_height)
        scroll = max(0, min(scroll, max_scroll))
        if tab == 1 and view_height > 0:
            if selected >= scroll + view_height - 1:
                scroll = max(0, selected - view_height + 2)
            elif selected < scroll:
                scroll = selected
            scroll = max(0, min(scroll, max_scroll))
        return scroll

    def _init_colors(self) -> bool:
        if self.theme == "auto" and os.environ.get("NO_COLOR"):
            return False
        if not curses.has_colors():
            return False
        try:
            curses.start_color()
        except curses.error:
            return False
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLACK)
        if self.theme == "light":
            curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE)
        else:
            curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_CYAN)
        return True

    @staticmethod
    def _line_attr(line: str) -> int:
        for rating, pair in [
            ("Excellent", 2),
            ("Strong", 4),
            ("Acceptable", 3),
            ("Weak", 3),
            ("Fail", 1),
        ]:
            if rating in line:
                idx = line.find(rating)
                if idx >= 0:
                    boundary = (" ", "[", ":", "]", ",", "(")
                    before_ok = idx == 0 or line[idx - 1] in boundary
                    after_end = idx + len(rating)
                    after_ok = after_end == len(line) or line[after_end] in boundary
                    if before_ok and after_ok:
                        return curses.color_pair(pair)
        if "BLOCKED" in line:
            return curses.color_pair(1)
        stripped = line.lstrip()
        if stripped.startswith("Progress [") and "#" in stripped:
            return curses.color_pair(2)
        if "WARNING" in line:
            return curses.color_pair(3)
        if "Pass" in line and "Gate" in line:
            return curses.color_pair(2)
        if "Fail" in line and "Gate" in line:
            return curses.color_pair(1)
        return 0

    @staticmethod
    def _safe_add(stdscr: Any, row: int, col: int, text: str, width: int, attr: int = 0) -> None:
        with contextlib.suppress(curses.error):
            stdscr.addnstr(row, col, text, max(0, width - col - 1), attr)
