from __future__ import annotations

from collections import Counter
from typing import Any

from .models import (
    AgentBenchmarkVerdict,
    AgentTally,
    BenchmarkPlan,
    BenchmarkRunVerdict,
    CaseJudgment,
    ComparisonVerdict,
    CoverageReport,
    RunStatus,
)


def build_per_agent_verdict(
    agent_label: str,
    plan: BenchmarkPlan,
    judgments: list[CaseJudgment],
    tally: AgentTally,
    coverage: CoverageReport,
    status: RunStatus,
) -> AgentBenchmarkVerdict:
    if not coverage.is_complete:
        return AgentBenchmarkVerdict(
            agent_label=agent_label,
            coverage=coverage,
            tally=tally,
            verdict="inconclusive",
            reasons=["Coverage is incomplete: " + "; ".join(coverage.diagnostics)],
        )

    family_scores = tally.family_scores
    required_families_pass = bool(family_scores) and all(
        float(v) >= 3.0 for v in family_scores.values()
    )
    validated = (
        status == RunStatus.COMPLETED
        and tally.gate_failures == 0
        and len([j for j in judgments if j.agent_label == agent_label]) >= len(plan.cases)
        and required_families_pass
    )
    reasons: list[str] = []
    if tally.gate_failures > 0:
        reasons.append(f"{tally.gate_failures} gate failure(s)")
    if not required_families_pass:
        reasons.append("Required family threshold not met (at least 3.0 needed per family)")
    if tally.policy_blocks > 0:
        reasons.append(f"{tally.policy_blocks} policy block(s) excluded from scoring")
    if tally.infrastructure_failures > 0:
        reasons.append(f"{tally.infrastructure_failures} infrastructure failure(s)")

    return AgentBenchmarkVerdict(
        agent_label=agent_label,
        coverage=coverage,
        tally=tally,
        verdict="validated" if validated else "not_validated",
        reasons=reasons,
    )


def build_run_verdict(
    status: RunStatus,
    agent_verdicts: dict[str, AgentBenchmarkVerdict],
    plan: BenchmarkPlan,
    judgments: list[CaseJudgment],
) -> BenchmarkRunVerdict:
    comparison = None
    labels = list(agent_verdicts.keys())
    if len(labels) == 2:
        a_label, b_label = labels[0], labels[1]
        verdict_a = agent_verdicts[a_label]
        verdict_b = agent_verdicts[b_label]
        if verdict_a.coverage.is_complete and verdict_b.coverage.is_complete:
            comparison = _build_comparison(
                a_label, b_label, plan, judgments, verdict_a.tally, verdict_b.tally
            )
        else:
            comparison = ComparisonVerdict(
                agent_a_label=a_label,
                agent_b_label=b_label,
                notes=["Comparison skipped: one or both agents have incomplete coverage."],
                valid=False,
            )
    return BenchmarkRunVerdict(status=status, agents=agent_verdicts, comparison=comparison)


def _build_comparison(
    a_label: str,
    b_label: str,
    plan: BenchmarkPlan,
    judgments: list[CaseJudgment],
    tally_a: AgentTally,
    tally_b: AgentTally,
) -> ComparisonVerdict:
    case_ids = sorted({c.id for c in plan.cases})
    wins: dict[str, int] = {a_label: 0, b_label: 0}
    losses: dict[str, int] = {a_label: 0, b_label: 0}
    ties = 0
    family_wins: dict[str, dict[str, int]] = {}

    # Build judgment lookup by (agent_label, case_id)
    j_map: dict[tuple[str, int], CaseJudgment] = {}
    for j in judgments:
        j_map[(j.agent_label, j.case_id)] = j

    for family in sorted({case.normalized_family.value for case in plan.cases}):
        family_wins[family] = {a_label: 0, b_label: 0, "ties": 0}

    for cid in case_ids:
        ja = j_map.get((a_label, cid))
        jb = j_map.get((b_label, cid))
        if ja is None or jb is None:
            continue
        score_a = ja.overall_rating.score
        score_b = jb.overall_rating.score
        case_family = _family_for_case(plan, cid)
        if score_a > score_b:
            wins[a_label] += 1
            losses[b_label] += 1
            if case_family:
                family_wins[case_family][a_label] += 1
        elif score_b > score_a:
            wins[b_label] += 1
            losses[a_label] += 1
            if case_family:
                family_wins[case_family][b_label] += 1
        else:
            ties += 1
            if case_family:
                family_wins[case_family]["ties"] += 1

    return ComparisonVerdict(
        agent_a_label=a_label,
        agent_b_label=b_label,
        wins_by_agent=wins,
        losses_by_agent=losses,
        ties=ties,
        family_wins=family_wins,
    )


def _family_for_case(plan: BenchmarkPlan, case_id: int) -> str:
    for case in plan.cases:
        if case.id == case_id:
            return case.normalized_family.value
    return ""


# ── legacy dict-style output (used by runner and TUI) ─────────────────────


def build_final_verdict(
    plan: BenchmarkPlan,
    judgments: list[CaseJudgment],
    tally: dict[str, Any],
    status: RunStatus,
) -> dict[str, Any]:
    ratings = Counter(j.overall_rating.value for j in judgments)
    gate_failures = int(tally.get("gate_failures", 0))
    family_scores = tally.get("family_scores") or {}
    required_families_pass = bool(family_scores) and all(
        float(v) >= 3.0 for v in family_scores.values()
    )
    validated = (
        status == RunStatus.COMPLETED
        and gate_failures == 0
        and len(judgments) >= len(plan.cases)
        and required_families_pass
    )
    strongest = [
        j.case_verdict for j in judgments if j.overall_rating.value in {"Excellent", "Strong"}
    ][:5]
    weak = [j.why for j in judgments if j.overall_rating.value in {"Weak", "Fail"}][:5]
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
    strongest = verdict.get("strongest_capabilities", [])
    lines += [f"- {item}" for item in strongest] or ["- None recorded."]
    lines += ["", "## Remaining weak spots", ""]
    weak_spots = verdict.get("remaining_weak_spots", [])
    lines += [f"- {item}" for item in weak_spots] or ["- None recorded."]
    lines += ["", "## Confidence", "", verdict.get("confidence_notes", "")]
    return "\n".join(lines) + "\n"


def case_judgments_markdown(judgments: list[CaseJudgment]) -> str:
    lines = ["# Case Judgments", ""]
    for judgment in judgments:
        lines += [
            f"## Case {judgment.case_id} ({judgment.agent_label}) "
            f"— {judgment.overall_rating.value}",
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
