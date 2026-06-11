from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

from .tui import load_snapshot

_SCHEMA_DIR = Path(__file__).parents[2] / "schemas"


def _load_schema(name: str) -> dict[str, Any] | None:
    path = _SCHEMA_DIR / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
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

    scale = tally.get("score_scale")
    if not scale:
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

    return {
        "run_dir": str(run_dir),
        "status": metadata.get("status", "unknown"),
        "planned_cases": planned,
        "judged_cases": judged,
        "policy_blocks": len(snapshot.policy_blocks),
        "warnings": warnings,
    }


def _sum_tally_int(tally: dict[str, Any], key: str) -> int:
    total = 0
    for agent_tally in tally.values():
        if isinstance(agent_tally, dict):
            total += int(agent_tally.get(key, 0) or 0)
    return total
