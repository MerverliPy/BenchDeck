from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

from .models import (
    AgentTally,
    BenchmarkCase,
    CaseJudgment,
    CoverageReport,
    ExecutionKey,
    Family,
    PolicyBlock,
    Rating,
)


def build_tally(
    cases: Iterable[BenchmarkCase],
    judgments: Iterable[CaseJudgment],
    *,
    agent_label: str,
    policy_blocks: int = 0,
    infrastructure_failures: int = 0,
) -> AgentTally:
    case_by_id = {case.id: case for case in cases}
    judgments_list = [j for j in judgments if j.agent_label == agent_label]
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
    return AgentTally(
        agent_label=agent_label,
        score_scale={"Excellent": 4, "Strong": 3, "Acceptable": 2, "Weak": 1, "Fail": 0},
        cases_planned=len(case_by_id),
        cases_judged=len(judgments_list),
        rating_counts={rating.value: counts[rating.value] for rating in Rating},
        gate_failures=sum(j.gate_check.status.value == "Fail" for j in judgments_list),
        family_scores=family_scores,
        policy_blocks=policy_blocks,
        infrastructure_failures=infrastructure_failures,
    )


def validate_execution_coverage(
    expected: set[ExecutionKey],
    terminal_keys: set[ExecutionKey],
) -> CoverageReport:
    missing = expected - terminal_keys
    extra = terminal_keys - expected
    seen: dict[ExecutionKey, int] = {}
    duplicates: list[ExecutionKey] = []
    for key in terminal_keys:
        if key not in seen:
            seen[key] = 0
        seen[key] += 1
        if seen[key] == 2:
            duplicates.append(key)
    return CoverageReport(
        expected_keys=expected,
        terminal_keys=terminal_keys,
        missing_keys=missing,
        extra_keys=extra,
        duplicate_keys=duplicates,
    )


def collect_terminal_keys(
    results: dict[str, Any],
    judgments: list[CaseJudgment],
    policy_blocks: list[PolicyBlock],
) -> set[ExecutionKey]:
    keys: set[ExecutionKey] = set()
    for agent_results in results.values():
        for result in results_to_list(agent_results):
            keys.add(ExecutionKey(agent_label=result.agent_label, case_id=result.case_id))
    for judgment in judgments:
        keys.add(judgment.execution_key)
    for block in policy_blocks:
        keys.add(block.execution_key)
    return keys


def results_to_list(obj: object) -> list[Any]:
    if isinstance(obj, list):
        return obj
    return []
