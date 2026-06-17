from __future__ import annotations

import textwrap
from typing import Any


def _wrap(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=max(12, width - 1), replace_whitespace=False) or [""]


def _section(title: str, text: str, width: int, prefix: str = "") -> list[str]:
    lines = [title]
    wrap_width = max(12, width - 1)
    if prefix:
        wrap_width = max(12, width - 1 - len(prefix))
    for paragraph in text.splitlines() or [""]:
        wrapped = _wrap(paragraph, wrap_width)
        if prefix:
            wrapped = [prefix + line for line in wrapped]
        lines.extend(wrapped)
    lines.append("")
    return lines


def _status_mark_for_state(state: str) -> str:
    if state == "BLOCKED":
        return "[X]"
    ratings: list[str] = []
    for token in state.split():
        if "[" in token:
            ratings.append(token.split("[", 1)[0])
    if not ratings:
        return ""
    if any(r == "Fail" for r in ratings):
        return "[X]"
    if any(r in ("Acceptable", "Weak") for r in ratings):
        return "[!]"
    if all(r in ("Excellent", "Strong") for r in ratings):
        return "[✓]"
    return ""


def _filter_matches(filter_str: str, case: dict[str, Any], state: str) -> bool:
    f = filter_str.strip()
    if not f:
        return True
    if ":" in f:
        key, _, val = f.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key == "family":
            return str(case.get("family", "")).lower() == val.lower()
        if key == "state":
            v = val.upper()
            if v == "JUDGED":
                return state != "PENDING" and state != "BLOCKED"
            if v == "PENDING":
                return state == "PENDING"
            return state.upper() == v
        if key == "rating":
            v = val.lower()
            return any(token.lower().startswith(v) for token in state.split())
    return f.lower() in str(case.get("title", "")).lower()


_RATING_ORDER: dict[str, int] = {
    "BLOCKED": 0,
    "Fail": 1,
    "Weak": 2,
    "Acceptable": 3,
    "Strong": 4,
    "Excellent": 5,
    "PENDING": 6,
}


def _rating_order(state: str) -> int:
    if state == "BLOCKED":
        return _RATING_ORDER["BLOCKED"]
    if state == "PENDING":
        return _RATING_ORDER["PENDING"]
    worst = len(_RATING_ORDER)
    for token in state.split():
        if "[" not in token:
            continue
        rating = token.split("[", 1)[0]
        rank = _RATING_ORDER.get(rating, len(_RATING_ORDER))
        if rank < worst:
            worst = rank
    return worst
