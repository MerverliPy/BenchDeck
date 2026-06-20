from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .models import REQUIRED_RUBRIC_DIMENSIONS, CaseJudgment


def analyze_disagreement(
    judgments: list[CaseJudgment],
) -> dict[str, Any]:
    grouped: dict[tuple[str, int], list[CaseJudgment]] = defaultdict(list)
    for j in judgments:
        key = (j.agent_label, j.case_id)
        grouped[key].append(j)

    multi_judge_count = 0
    high_disagreement: list[dict[str, Any]] = []
    overall_agreement_summary: dict[str, int] = {
        "total_multi_judged": 0,
        "agreed": 0,
        "disagreed": 0,
    }

    for (agent, case_id), group in sorted(grouped.items()):
        if len(group) < 2:
            continue
        multi_judge_count += 1
        overall_agreement_summary["total_multi_judged"] += 1

        ratings_set: set[str] = {j.overall_rating.value for j in group}
        if len(ratings_set) == 1:
            overall_agreement_summary["agreed"] += 1
        else:
            overall_agreement_summary["disagreed"] += 1

        dim_variances: dict[str, float] = {}
        for dim in REQUIRED_RUBRIC_DIMENSIONS:
            scores = [
                d.rating.score for jj in group for d in jj.rubric.dimensions if d.dimension == dim
            ]
            if len(scores) >= 2:
                mean = sum(scores) / len(scores)
                variance = sum((s - mean) ** 2 for s in scores) / len(scores)
                dim_variances[dim] = round(variance, 3)

        if len(ratings_set) > 1:
            high_disagreement.append(
                {
                    "agent": agent,
                    "case_id": case_id,
                    "ratings": sorted(ratings_set),
                    "judge_count": len(group),
                    "dimension_variances": dim_variances,
                }
            )

    rating_distributions: dict[str, Counter[str]] = defaultdict(Counter)
    for j in judgments:
        rdist_key = f"{j.agent_label}:{j.case_id}"
        rating_distributions[rdist_key][j.overall_rating.value] += 1

    return {
        "multi_judged_cases": multi_judge_count,
        "high_disagreement_cases": high_disagreement,
        "overall_agreement": overall_agreement_summary,
        "total_judgments": len(judgments),
        "rating_distributions": {k: dict(v) for k, v in rating_distributions.items()},
    }
