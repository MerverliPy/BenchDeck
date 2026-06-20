from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

from .errors import LoadError
from .loader import _sum_tally_int, load_snapshot
from .manifest import Manifest

_SCHEMA_DIR = files("benchdeck") / "schemas"


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
    try:
        snapshot = load_snapshot(run_dir, strict=True)
    except LoadError as exc:
        return {
            "run_dir": str(run_dir),
            "status": "unknown",
            "planned_cases": 0,
            "judged_cases": 0,
            "policy_blocks": 0,
            "planner_mode": None,
            "planner_attempts": 0,
            "planner_http_attempts": 0,
            "planner_error": False,
            "warnings": [f"Load error: {exc}"],
        }
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

    warnings.extend(_referential_integrity_warnings(snapshot))
    warnings.extend(_counter_consistency_warnings(snapshot))

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

    # Manifest checksum validation (only for directory runs, not ZIP)
    if run_dir.is_dir():
        manifest = Manifest.load(run_dir)
        manifest_issues = manifest.verify()
        if manifest_issues:
            warnings.append(
                f"Manifest integrity errors ({len(manifest_issues)}): "
                + "; ".join(manifest_issues[:5])
            )

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


def _referential_integrity_warnings(snapshot: Any) -> list[str]:
    warnings: list[str] = []
    plan_case_ids = _plan_case_ids(snapshot.plan)
    if not plan_case_ids:
        return warnings

    seen_results: set[tuple[str, int]] = set()
    for agent_label, results in snapshot.results.items():
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            case_id = _int_or_none(result.get("case_id"))
            if case_id is None:
                warnings.append(f"Result for {agent_label} lacks an integer case_id.")
                continue
            key = (agent_label, case_id)
            if key in seen_results:
                warnings.append(f"Duplicate result for {agent_label} case {case_id}.")
            seen_results.add(key)
            if case_id not in plan_case_ids:
                warnings.append(
                    f"Result for {agent_label} case {case_id} references a case not in the plan."
                )

    seen_judgments: set[tuple[str, int]] = set()
    for judgment in snapshot.judgments:
        if not isinstance(judgment, dict):
            continue
        agent_label = str(judgment.get("agent_label") or "")
        case_id = _int_or_none(judgment.get("case_id"))
        if case_id is None:
            warnings.append("Judgment lacks an integer case_id.")
            continue
        if case_id not in plan_case_ids:
            warnings.append(f"Judgment for case {case_id} references a case not in the plan.")
        if agent_label:
            key = (agent_label, case_id)
            if key in seen_judgments:
                warnings.append(f"Duplicate judgment for {agent_label} case {case_id}.")
            seen_judgments.add(key)

    for artifact_name, artifacts in (
        ("Policy block", snapshot.policy_blocks),
        ("Infrastructure error", snapshot.infrastructure_errors),
    ):
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            case_id = _int_or_none(item.get("case_id"))
            if case_id is None:
                warnings.append(f"{artifact_name} lacks an integer case_id.")
            elif case_id not in plan_case_ids:
                warnings.append(
                    f"{artifact_name} for case {case_id} references a case not in the plan."
                )

    return warnings


def _counter_consistency_warnings(snapshot: Any) -> list[str]:
    warnings: list[str] = []
    metadata = snapshot.metadata
    if not isinstance(metadata, dict):
        return warnings

    plan_case_ids = _plan_case_ids(snapshot.plan)
    agents_in_run = _int_or_none(metadata.get("agents_in_run"))
    if plan_case_ids and agents_in_run:
        expected_planned = len(plan_case_ids) * agents_in_run
        recorded_planned = _int_or_none(metadata.get("executions_planned"))
        if recorded_planned is not None and recorded_planned != expected_planned:
            warnings.append(
                "Metadata executions_planned is inconsistent with plan cases × agents "
                f"({recorded_planned} != {expected_planned})."
            )

    _append_count_warning(
        warnings,
        metadata,
        field="executions_judged",
        actual=len(snapshot.judgments),
        label="judgment artifact count",
    )
    _append_count_warning(
        warnings,
        metadata,
        field="policy_blocks",
        actual=len(snapshot.policy_blocks),
        label="policy block artifact count",
    )
    _append_count_warning(
        warnings,
        metadata,
        field="infrastructure_failures",
        actual=len(snapshot.infrastructure_errors),
        label="infrastructure error artifact count",
    )
    return warnings


def _append_count_warning(
    warnings: list[str],
    metadata: dict[str, Any],
    *,
    field: str,
    actual: int,
    label: str,
) -> None:
    recorded = _int_or_none(metadata.get(field))
    if recorded is not None and recorded != actual:
        warnings.append(f"Metadata {field} is inconsistent with {label} ({recorded} != {actual}).")


def _plan_case_ids(plan: dict[str, Any]) -> set[int]:
    cases = plan.get("cases") if isinstance(plan, dict) else None
    if not isinstance(cases, list):
        return set()
    ids: set[int] = set()
    for case in cases:
        if isinstance(case, dict):
            case_id = _int_or_none(case.get("id"))
            if case_id is not None:
                ids.add(case_id)
    return ids


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None
