from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

from .loader import _sum_tally_int, load_snapshot

_SCHEMA_DIR = Path(__file__).parents[2] / "schemas"


def _load_schema(name: str) -> dict[str, Any] | None:
    path = _SCHEMA_DIR / name
    try:
        result: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            return None
        return result
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def inspect_run(run_dir: Path) -> dict[str, Any]:
    snapshot = load_snapshot(run_dir)
    metadata = snapshot.metadata
    tally = snapshot.tally
    warnings: list[str] = []

    planned = int(
        metadata.get("cases_in_plan")
        or metadata.get("planned_cases")
        or _sum_tally_int(tally, "cases_planned")
        or 0
    )
    judged = int(
        metadata.get("executions_judged")
        or metadata.get("judged_cases")
        or _sum_tally_int(tally, "cases_judged")
        or 0
    )
    if judged < planned:
        warnings.append(f"Only {judged} of {planned} planned cases were judged.")

    for agent_key, results in snapshot.results.items():
        for result in results:
            if not result.get("final_output"):
                warnings.append(
                    f"{agent_key} case {result.get('case_id')} has an empty final output."
                )
            judge_tx = result.get("judge_transcript")
            final_out = result.get("final_output")
            if judge_tx == final_out and final_out:
                warnings.append(
                    f"{agent_key} case {result.get('case_id')} stores candidate "
                    "output as judge_transcript."
                )

    for j in snapshot.judgments:
        if not j.get("agent_label"):
            warnings.append(f"Judgment for case {j.get('case_id')} lacks agent_label attribution.")

    scale_missing = False
    for agent_tally in tally.values():
        if isinstance(agent_tally, dict) and not agent_tally.get("score_scale"):
            scale_missing = True
            break
    if not tally or scale_missing:
        warnings.append("Summary tally does not declare its score scale.")
    if metadata.get("status") == "completed" and (snapshot.policy_blocks or judged < planned):
        warnings.append("Run is marked completed despite blocked or missing required coverage.")

    # JSON Schema validation of per-agent tallies
    tally_schema = _load_schema("summary_tally.schema.json")
    if tally_schema and isinstance(tally, dict):
        for agent_label, agent_tally in tally.items():
            if not isinstance(agent_tally, dict):
                continue
            try:
                validate(instance=agent_tally, schema=tally_schema)
            except ValidationError as exc:
                warnings.append(f"Tally for {agent_label} fails schema validation: {exc.message}")

    for ie in snapshot.infrastructure_errors:
        meta = (
            f"[{ie.get('agent_label', '?')}] case {ie.get('case_id', '?')}"
            f" ({ie.get('case_title', '?')}) — {ie.get('stage', '?')}:"
            f" {ie.get('error_type', '?')} / {ie.get('message', '')}"
        )
        warnings.append(f"Infrastructure error: {meta}")

    pc = snapshot.planner_capture or {}
    if pc:
        if pc.get("terminal_error"):
            err = pc["terminal_error"]
            if isinstance(err, dict):
                warnings.append(
                    f"Planner terminal error: {err.get('message', str(err))}"
                    f" (category: {err.get('category', '?')})"
                )
            else:
                warnings.append(f"Planner terminal error: {err}")
        if pc.get("parse_error"):
            warnings.append(f"Planner parse error: {pc['parse_error']}")
        if pc.get("validation_error"):
            warnings.append(f"Planner validation error: {pc['validation_error']}")
        plan_mode = snapshot.plan.get("mode")
        planner_mode = (pc.get("value") or {}).get("mode")
        if plan_mode and planner_mode and plan_mode != planner_mode:
            warnings.append(
                f"Planner mode mismatch: plan declares {plan_mode!r}"
                f" but planner returned {planner_mode!r}"
            )

    return {
        "run_dir": str(run_dir),
        "status": metadata.get("status", "unknown"),
        "planned_cases": planned,
        "judged_cases": judged,
        "policy_blocks": len(snapshot.policy_blocks),
        "planner_mode": (pc.get("value") or {}).get("mode"),
        "planner_attempts": len(pc.get("attempts", [])),
        "planner_http_attempts": pc.get("total_http_attempts", 0),
        "planner_error": bool(pc.get("terminal_error") or pc.get("parse_error")),
        "warnings": warnings,
    }
