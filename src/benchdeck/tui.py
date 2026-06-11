from __future__ import annotations

import base64
import contextlib
import curses
import datetime
import io
import json
import textwrap
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Snapshot:
    metadata: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)
    tally: dict[str, Any] = field(default_factory=dict)
    judgments: list[dict[str, Any]] = field(default_factory=list)
    policy_blocks: list[dict[str, Any]] = field(default_factory=list)
    results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


class BenchDeckTUI:
    """Narrow-terminal TUI designed for SSH clients and phone keyboards."""

    TABS = ("Overview", "Cases", "Detail", "Help")

    def __init__(self, run_dir: Path, refresh_seconds: float = 1.0) -> None:
        self.run_dir = run_dir
        self.refresh_seconds = refresh_seconds
        self.tab = 0
        self.selected = 0
        self.scroll = 0
        self.snapshot = Snapshot()
        self.last_load = 0.0

    def run(self) -> None:
        curses.wrapper(self._main)

    def _main(self, stdscr: Any) -> None:
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.keypad(True)
        while True:
            now = time.monotonic()
            if now - self.last_load >= self.refresh_seconds:
                self.snapshot = load_snapshot(self.run_dir)
                self.last_load = now
            self._draw(stdscr)
            key = stdscr.getch()
            if key in (ord("q"), 27):
                break
            self._handle_key(key)
            time.sleep(0.05)

    def _handle_key(self, key: int) -> None:
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
        elif key == ord("r"):
            self.snapshot = load_snapshot(self.run_dir)
            self.last_load = time.monotonic()
        elif key == ord("e") and self.tab == 1:
            self._export_case()

    def _draw(self, stdscr: Any) -> None:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        if height < 10 or width < 32:
            self._safe_add(stdscr, 0, 0, "Terminal too small (min 32x10)", width)
            stdscr.refresh()
            return
        title = " BENCHDECK "
        status = str(self.snapshot.metadata.get("status", "no run"))
        self._safe_add(stdscr, 0, 0, title + f"[{status}]", width, curses.A_REVERSE)
        tab_line = " ".join(
            f"{i + 1}:{name}" if i != self.tab else f"[{i + 1}:{name}]"
            for i, name in enumerate(self.TABS)
        )
        self._safe_add(stdscr, 1, 0, tab_line, width, curses.A_BOLD)
        lines = self._render(width)
        viewport = lines[self.scroll : self.scroll + height - 4]
        for row, line in enumerate(viewport, start=2):
            self._safe_add(stdscr, row, 0, line, width)
        footer = "h/l tabs  j/k move  Enter detail  e export  r reload  q quit"
        self._safe_add(stdscr, height - 1, 0, footer, width, curses.A_REVERSE)
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
        m, t = self.snapshot.metadata, self.snapshot.tally
        planned = int(m.get("cases_in_plan") or _sum_tally_int(t, "cases_planned") or 0)
        judged = int(m.get("executions_judged") or _sum_tally_int(t, "cases_judged") or 0)
        blocks = int(m.get("policy_blocks") or _sum_tally_int(t, "policy_blocks") or 0)
        infra = int(
            m.get("infrastructure_failures") or _sum_tally_int(t, "infrastructure_failures") or 0
        )
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
            "",
            "Ratings (0-4 scale)",
        ]
        for name in ("Excellent", "Strong", "Acceptable", "Weak", "Fail"):
            count = (t.get("rating_counts") or {}).get(name, 0)
            lines.append(f"  {name:<10} {count}")
        lines += ["", "Family scores"]
        for family, score in (t.get("family_scores") or {}).items():
            lines.append(f"  {family:<23} {score}")
        if self.snapshot.policy_blocks:
            lines += ["", "Policy blocks"]
            for block in self.snapshot.policy_blocks:
                msg = f"  Case {block.get('case_id')}: {block.get('message', '')}"
                lines.extend(_wrap(msg, width))
        return lines

    def _case_list(self, width: int) -> list[str]:
        lines = ["Cases"]
        judgments_by_case: dict[int, list[dict[str, Any]]] = {}
        for j in self.snapshot.judgments:
            cid = j.get("case_id")
            if cid is not None:
                judgments_by_case.setdefault(cid, []).append(j)
        blocks = {b.get("case_id"): b for b in self.snapshot.policy_blocks}
        for index, case in enumerate(self._cases()):
            case_id = case.get("id")
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
            marker = ">" if index == self.selected else " "
            title = str(case.get("title", "Untitled"))
            prefix = f"{marker}{case_id:>2} "
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
                    lines += _section("Agent output", str(result.get("final_output", "")), width)
        elif self._result_for(case_id):
            result = self._result_for(case_id)
            if result and result.get("infrastructure_error"):
                lines += ["Infrastructure error: empty output after retries"]
        else:
            lines += ["No judgment yet."]
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
        filename = f"case_{case_id}_{ts}.md"
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
        with contextlib.suppress(OSError):
            Path(filename).write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _safe_add(stdscr: Any, row: int, col: int, text: str, width: int, attr: int = 0) -> None:
        with contextlib.suppress(curses.error):
            stdscr.addnstr(row, col, text, max(0, width - col - 1), attr)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def load_snapshot(run_path: Path) -> Snapshot:
    """Load a run directory, ZIP archive, or checked-in segmented ZIP fixture."""
    if run_path.suffix.lower() == ".zip":
        if run_path.is_file():
            return _load_zip_snapshot(run_path)
        segments = sorted(run_path.parent.glob(run_path.name + ".b64.*"))
        if segments:
            try:
                encoded = "".join(part.read_text(encoding="ascii") for part in segments)
                return _load_zip_bytes(base64.b64decode(encoded, validate=False))
            except (OSError, ValueError):
                return Snapshot()
    return Snapshot(
        metadata=_read_json(run_path / "run_metadata.json", {}),
        plan=_read_json(run_path / "benchmark_plan.json", {}),
        tally=_read_json(run_path / "summary_tally.json", {}),
        judgments=_read_json(run_path / "case_judgments.json", []),
        policy_blocks=_read_json(run_path / "policy_blocks.json", []),
        results=_read_json(run_path / "run_results.json", {}),
    )


def _load_zip_snapshot(zip_path: Path) -> Snapshot:
    try:
        return _load_zip_bytes(zip_path.read_bytes())
    except OSError:
        return Snapshot()


def _load_zip_bytes(data: bytes) -> Snapshot:
    defaults: dict[str, Any] = {
        "run_metadata.json": {},
        "benchmark_plan.json": {},
        "summary_tally.json": {},
        "case_judgments.json": [],
        "policy_blocks.json": [],
        "run_results.json": {},
    }
    loaded: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = {
                Path(name).name: name for name in archive.namelist() if not name.endswith("/")
            }
            if len(members) > 1000:
                return Snapshot()
            for filename, default in defaults.items():
                member = members.get(filename)
                if member is None:
                    loaded[filename] = default
                    continue
                try:
                    info = archive.getinfo(member)
                    if info.file_size > 256 * 1024 * 1024:
                        loaded[filename] = default
                        continue
                    loaded[filename] = json.loads(archive.read(member).decode("utf-8"))
                except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
                    loaded[filename] = default
    except (OSError, zipfile.BadZipFile):
        loaded = defaults
    return Snapshot(
        metadata=loaded["run_metadata.json"],
        plan=loaded["benchmark_plan.json"],
        tally=loaded["summary_tally.json"],
        judgments=loaded["case_judgments.json"],
        policy_blocks=loaded["policy_blocks.json"],
        results=loaded["run_results.json"],
    )


def _wrap(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=max(12, width - 1), replace_whitespace=False) or [""]


def _sum_tally_int(tally: dict[str, Any], key: str) -> int:
    total = 0
    for agent_tally in tally.values():
        if isinstance(agent_tally, dict):
            total += int(agent_tally.get(key, 0) or 0)
    return total


def _section(title: str, text: str, width: int) -> list[str]:
    lines = [title]
    for paragraph in text.splitlines() or [""]:
        lines.extend(_wrap(paragraph, width))
    lines.append("")
    return lines
