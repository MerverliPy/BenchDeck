from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable

from .models import BenchmarkCase, CaseJudgment, Family, Rating


def build_tally(
    cases: Iterable[BenchmarkCase],
    judgments: Iterable[CaseJudgment],
    *,
    policy_blocks: int = 0,
    infrastructure_failures: int = 0,
) -> dict[str, object]:
    case_by_id = {case.id: case for case in cases}
    judgments_list = list(judgments)
    counts = Counter(j.overall_rating.value for j in judgments_list)
    families: dict[Family, list[int]] = defaultdict(list)
    for judgment in judgments_list:
        case = case_by_id.get(judgment.case_id)
        if case is not None:
            families[case.normalized_family].append(judgment.overall_rating.score)
    family_scores = {
        family.value: round(sum(scores) / len(scores), 2)
        for family, scores in families.items()
        if scores
    }
    return {
        "score_scale": {"Excellent": 4, "Strong": 3, "Acceptable": 2, "Weak": 1, "Fail": 0},
        "cases_planned": len(case_by_id),
        "cases_judged": len(judgments_list),
        "rating_counts": {rating.value: counts[rating.value] for rating in Rating},
        "gate_failures": sum(j.gate_check.status.value == "Fail" for j in judgments_list),
        "family_scores": family_scores,
        "policy_blocks": policy_blocks,
        "infrastructure_failures": infrastructure_failures,
    }
