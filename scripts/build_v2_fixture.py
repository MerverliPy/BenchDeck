"""Build a deterministic, schema-valid v2 benchmark fixture.

Usage:
    python scripts/build_v2_fixture.py

Produces: fixtures/original_run.zip

The fixture is a complete single-agent run with 8 cases, all judged
successfully, passing ``benchdeck inspect`` with zero warnings.
"""

from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from conftest import make_case, make_single_plan  # noqa: E402
from fakes import FakeGateway, json_response, text_response  # noqa: E402

from benchdeck.models import BenchmarkPlan  # noqa: E402
from benchdeck.runner import BenchmarkRunner  # noqa: E402


def _plan_json(cases):
    plan = BenchmarkPlan(
        mode="single",
        profile=make_single_plan(cases=cases).profile,
        cases=cases,
    )
    return plan.model_dump(mode="json")


def _judgment_json(case_id: int, rating: str = "Strong"):
    return {
        "case_verdict": "ok",
        "gate_check": {"status": "Pass", "reason": "meets requirements"},
        "rubric_dimensions": [
            {"dimension": "mission_fidelity", "rating": rating, "evidence": "ok"},
            {"dimension": "task_success", "rating": rating, "evidence": "ok"},
            {"dimension": "priority_adherence", "rating": rating, "evidence": "ok"},
            {"dimension": "ambiguity_handling", "rating": rating, "evidence": "ok"},
            {"dimension": "process_discipline", "rating": rating, "evidence": "ok"},
            {"dimension": "tool_discipline", "rating": rating, "evidence": "ok"},
            {"dimension": "robustness", "rating": rating, "evidence": "ok"},
            {"dimension": "regression_safety", "rating": rating, "evidence": "ok"},
        ],
        "overall_rating": rating,
        "why": "adequate response",
        "regression_notes": [],
    }


def build_fixture(target: Path) -> None:
    plan_cases = [
        make_case(1, "happy_path"),
        make_case(2, "happy_path"),
        make_case(3, "regression_protection"),
        make_case(4, "regression_protection"),
        make_case(5, "stress_adversarial"),
        make_case(6, "stress_adversarial"),
        make_case(7, "ambiguity"),
        make_case(8, "ambiguity"),
    ]
    plan = BenchmarkPlan(
        mode="single",
        profile=make_single_plan(cases=plan_cases).profile,
        cases=plan_cases,
    )
    plan_json = plan.model_dump(mode="json")

    planner = FakeGateway([json_response(plan_json)])
    agent = FakeGateway(
        [text_response(f"Deterministic answer for case {c.id}") for c in plan_cases]
    )
    judge = FakeGateway([json_response(_judgment_json(c.id, "Strong")) for c in plan_cases])

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmp = Path(tmpdir_str)
        agent_path = tmp / "agent.md"
        agent_path.write_text("# Test Agent\n\nYou are a helpful coding assistant.\n")
        out_dir = tmp / "run_out"

        runner = BenchmarkRunner(
            agent_a_path=agent_path,
            agent_b_path=None,
            output_dir=out_dir,
            model="fake-model",
            judge_model="fake-judge",
            planner_gateway=planner,
            agent_gateway=agent,
            judge_gateway=judge,
        )
        status = runner.run()
        assert status.value == "completed", f"Expected completed, got {status.value}"

        # Package all JSON artifacts into a ZIP.
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(out_dir.glob("*.json")):
                zf.write(p, p.name)

    print(f"Fixture written: {target}")


if __name__ == "__main__":
    build_fixture(REPO_ROOT / "fixtures" / "original_run.zip")
