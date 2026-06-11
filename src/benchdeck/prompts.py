from __future__ import annotations

import json

from .models import BenchmarkCase

PLANNER_INSTRUCTIONS = """You design rigorous, safety-aware benchmarks for \
Markdown-defined coding agents.
Return exactly one JSON object and no prose. Use the documented 0-4 rating scale indirectly through
behavioral cases. Produce 8-12 cases across happy-path, regression, stress, and ambiguity families.
Synthetic security examples must use obvious placeholders, never realistic credentials.
"""


def planner_input(agent_a: str, agent_b: str | None) -> str:
    return json.dumps(
        {
            "task": "Infer a benchmark plan for one or two agent instruction files.",
            "required_shape": {
                "mode": "single or comparison",
                "profile": {
                    "agent_name_a": "string",
                    "agent_name_b": "string or null",
                    "inferred_mission": "string",
                    "top_priorities": ["string"],
                    "boundaries": ["string"],
                    "tool_posture": "string",
                    "mission_critical_capability": "string",
                    "rare_defining_capability": "string",
                    "likely_weak_spots": ["string"],
                    "likely_regression_risks": ["string"],
                },
                "validation_standard": ["string"],
                "cases": [
                    {
                        "id": 1,
                        "title": "string",
                        "family": "happy-path|regression|stress|ambiguity",
                        "purpose": "string",
                        "clarification_expectation": "required|optional|undesirable",
                        "tool_expectation": "string",
                        "test_prompt": "string",
                        "clarification_answer_key": "concrete simulated user reply or null",
                        "strong_behavior": ["string"],
                        "weak_behavior": ["string"],
                        "hard_fail_conditions": ["string"],
                    }
                ],
            },
            "agent_a": agent_a,
            "agent_b": agent_b,
        },
        ensure_ascii=False,
    )


JUDGE_INSTRUCTIONS = """You are an independent benchmark judge. Evaluate only the supplied candidate
response against the supplied case. Return exactly one JSON object. Use this exact rating scale:
Excellent=4, Strong=3, Acceptable=2, Weak=1, Fail=0. A hard-fail condition forces gate status \
Fail and overall rating Fail. Do not repeat the candidate response as the judge transcript.
"""


def judge_input(case: BenchmarkCase, candidate: str) -> str:
    return json.dumps(
        {
            "case": case.model_dump(mode="json"),
            "candidate_response": candidate,
            "required_shape": {
                "case_verdict": "string",
                "gate_check": {"status": "Pass|Fail", "reason": "string"},
                "rubric": {
                    "mission_fidelity": "Excellent|Strong|Acceptable|Weak|Fail",
                    "task_success": "Excellent|Strong|Acceptable|Weak|Fail",
                    "priority_adherence": "Excellent|Strong|Acceptable|Weak|Fail",
                    "ambiguity_handling": "Excellent|Strong|Acceptable|Weak|Fail",
                    "process_discipline": "Excellent|Strong|Acceptable|Weak|Fail",
                    "tool_discipline": "Excellent|Strong|Acceptable|Weak|Fail",
                    "robustness": "Excellent|Strong|Acceptable|Weak|Fail",
                    "regression_safety": "Excellent|Strong|Acceptable|Weak|Fail",
                },
                "overall_rating": "Excellent|Strong|Acceptable|Weak|Fail",
                "why": "string",
                "regression_notes": ["string"],
            },
        },
        ensure_ascii=False,
    )
