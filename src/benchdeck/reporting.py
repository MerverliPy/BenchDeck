from __future__ import annotations

from collections import Counter
from typing import Any

from .models import BenchmarkPlan, CaseJudgment, RunStatus


def build_final_verdict(
    plan: BenchmarkPlan,
    judgments: list[CaseJudgment],
    tally: dict[str, Any],
    status: RunStatus,
) -> dict[str, Any]:
    ratings = Counter(j.overall_rating.value for j in judgments)
    gate_failures = int(tally.get("gate_failures", 0))
    family_scores = tally.get("family_scores") or {}
    required_families_pass = bool(family_scores) and all(float(v) >= 3.0 for v in family_scores.values())
    validated = (
        status == RunStatus.COMPLETED
        and gate_failures == 0
        and len(judgments) >= len(plan.cases)
        and required_families_pass
    )
    strongest = [
        j.case_verdict
        for j in judgments
        if j.overall_rating.value in {"Excellent", "Strong"}
    ][:5]
    weak = [
        j.why
        for j in judgments
        if j.overall_rating.value in {"Weak", "Fail"}
    ][:5]
    return {
        "overall_verdict": "Validated" if validated else "Not Validated",
        "run_status": status.value,
        "decision": "Ready for use" if validated else "Revise or rerun before use",
        "cases_planned": len(plan.cases),
        "cases_judged": len(judgments),
        "rating_counts": dict(ratings),
        "gate_failures": gate_failures,
        "family_scores": family_scores,
        "strongest_capabilities": strongest,
        "remaining_weak_spots": weak,
        "confidence_notes": _confidence_note(status, len(plan.cases), len(judgments)),
    }


def final_verdict_markdown(verdict: dict[str, Any]) -> str:
    lines = [
        "# Final Benchmark Verdict",
        "",
        f"**Overall:** {verdict['overall_verdict']}",
        f"**Run status:** {verdict['run_status']}",
        f"**Decision:** {verdict['decision']}",
        f"**Coverage:** {verdict['cases_judged']}/{verdict['cases_planned']}",
        f"**Gate failures:** {verdict['gate_failures']}",
        "",
        "## Family scores",
        "",
    ]
    for family, score in verdict.get("family_scores", {}).items():
        lines.append(f"- `{family}`: {score}")
    lines += ["", "## Strongest capabilities", ""]
    lines += [f"- {item}" for item in verdict.get("strongest_capabilities", [])] or ["- None recorded."]
    lines += ["", "## Remaining weak spots", ""]
    lines += [f"- {item}" for item in verdict.get("remaining_weak_spots", [])] or ["- None recorded."]
    lines += ["", "## Confidence", "", verdict.get("confidence_notes", "")]
    return "\n".join(lines) + "\n"


def case_judgments_markdown(judgments: list[CaseJudgment]) -> str:
    lines = ["# Case Judgments", ""]
    for judgment in judgments:
        lines += [
            f"## Case {judgment.case_id} — {judgment.overall_rating.value}",
            "",
            f"**Gate:** {judgment.gate_check.status.value} — {judgment.gate_check.reason}",
            "",
            judgment.why,
            "",
        ]
    return "\n".join(lines)


def _confidence_note(status: RunStatus, planned: int, judged: int) -> str:
    if status == RunStatus.INCONCLUSIVE:
        return (
            f"Confidence is limited because only {judged} of {planned} required cases were judged "
            "or an infrastructure/policy condition prevented complete coverage."
        )
    if status == RunStatus.INFRASTRUCTURE_FAILED:
        return "No agent-level conclusion is supported because the benchmark infrastructure failed."
    return f"Confidence is based on {judged} judged cases with complete required coverage."
