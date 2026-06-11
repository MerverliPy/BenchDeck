from __future__ import annotations

from pathlib import Path
from typing import Any

from .tui import load_snapshot


def inspect_run(run_dir: Path) -> dict[str, Any]:
    snapshot = load_snapshot(run_dir)
    metadata = snapshot.metadata
    tally = snapshot.tally
    warnings: list[str] = []

    planned = int(metadata.get("planned_cases") or tally.get("cases_planned") or 0)
    judged = int(
        metadata.get("judged_cases")
        or tally.get("cases_judged")
        or tally.get("cases_completed")
        or 0
    )
    if judged < planned:
        warnings.append(f"Only {judged} of {planned} planned cases were judged.")

    for agent, results in snapshot.results.items():
        for result in results:
            if not result.get("final_output"):
                warnings.append(f"{agent} case {result.get('case_id')} has an empty final output.")
            judge_tx = result.get("judge_transcript")
            final_out = result.get("final_output")
            if judge_tx == final_out and final_out:
                warnings.append(
                    f"{agent} case {result.get('case_id')} stores candidate "
                    "output as judge_transcript."
                )

    scale = tally.get("score_scale")
    if not scale:
        warnings.append("Summary tally does not declare its score scale.")
    if metadata.get("status") == "completed" and (snapshot.policy_blocks or judged < planned):
        warnings.append("Run is marked completed despite blocked or missing required coverage.")

    return {
        "run_dir": str(run_dir),
        "status": metadata.get("status", "unknown"),
        "planned_cases": planned,
        "judged_cases": judged,
        "policy_blocks": len(snapshot.policy_blocks),
        "warnings": warnings,
    }
