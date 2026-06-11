from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import (
    BenchmarkCase,
    BenchmarkPlan,
    CaseJudgment,
    CaseRunResult,
    GateStatus,
    PolicyBlock,
    Rating,
    ResponseCapture,
    RunMetadata,
    RunStatus,
)
from .openai_gateway import GatewayConfig, OpenAIGateway
from .prompts import JUDGE_INSTRUCTIONS, PLANNER_INSTRUCTIONS, judge_input, planner_input
from .reporting import build_final_verdict, case_judgments_markdown, final_verdict_markdown
from .scoring import build_tally
from .storage import ArtifactStore


class BenchmarkRunner:
    def __init__(
        self,
        *,
        agent_a_path: Path,
        agent_b_path: Path | None,
        output_dir: Path,
        model: str,
        judge_model: str,
        plan_path: Path | None = None,
    ) -> None:
        self.agent_a_path = agent_a_path
        self.agent_b_path = agent_b_path
        self.output_dir = output_dir
        self.plan_path = plan_path
        self.agent_gateway = OpenAIGateway(GatewayConfig(model=model))
        self.judge_gateway = OpenAIGateway(GatewayConfig(model=judge_model))
        self.store = ArtifactStore(output_dir)
        self.metadata = RunMetadata(
            config={
                "agent_a": str(agent_a_path),
                "agent_b": str(agent_b_path) if agent_b_path else None,
                "model": model,
                "judge_model": judge_model,
                "output_dir": str(output_dir),
            }
        )

    def run(self) -> RunStatus:
        self.store.write_json("run_metadata.json", self.metadata)
        try:
            agent_a = self.agent_a_path.read_text(encoding="utf-8")
            agent_b = self.agent_b_path.read_text(encoding="utf-8") if self.agent_b_path else None
            plan = self._load_or_generate_plan(agent_a, agent_b)
            self.metadata.planned_cases = len(plan.cases)
            self.store.write_json("benchmark_plan.json", plan)

            all_runs: dict[str, list[CaseRunResult]] = {"agent_a": []}
            if agent_b is not None:
                all_runs["agent_b"] = []
            judgments: list[CaseJudgment] = []
            blocks: list[PolicyBlock] = []
            infrastructure_errors: list[dict[str, Any]] = []

            for label, agent_text in (("agent_a", agent_a), ("agent_b", agent_b)):
                if agent_text is None:
                    continue
                for case in plan.cases:
                    self.metadata.attempted_cases += 1
                    result = self._run_case(case, label, agent_text)
                    all_runs[label].append(result)
                    self._add_usage(result.agent_capture)
                    if result.clarification_capture:
                        self._add_usage(result.clarification_capture)

                    failed_capture = _failed_capture(result)
                    if failed_capture is not None:
                        block = self._policy_block_from_capture(case, label, failed_capture)
                        if block:
                            blocks.append(block)
                            self.metadata.policy_blocks += 1
                        else:
                            self.metadata.infrastructure_failures += 1
                            infrastructure_errors.append(
                                _infrastructure_record(case, label, "agent", failed_capture)
                            )
                        self._checkpoint(
                            all_runs, judgments, blocks, infrastructure_errors, plan
                        )
                        continue
                    if result.infrastructure_error:
                        self.metadata.infrastructure_failures += 1
                        infrastructure_errors.append(
                            _infrastructure_record(
                                case,
                                label,
                                "agent",
                                result.clarification_capture or result.agent_capture,
                            )
                        )
                        self._checkpoint(
                            all_runs, judgments, blocks, infrastructure_errors, plan
                        )
                        continue

                    self.metadata.model_completed_cases += 1
                    try:
                        judgment = self._judge_case(case, result.final_output)
                    except Exception as exc:
                        self.metadata.infrastructure_failures += 1
                        infrastructure_errors.append(
                            {
                                "case_id": case.id,
                                "agent": label,
                                "stage": "judge",
                                "type": type(exc).__name__,
                                "message": str(exc),
                            }
                        )
                        self._checkpoint(
                            all_runs, judgments, blocks, infrastructure_errors, plan
                        )
                        continue
                    judgments.append(judgment)
                    if judgment.judge_capture:
                        self._add_usage(judgment.judge_capture)
                    self.metadata.judged_cases += 1
                    self._checkpoint(all_runs, judgments, blocks, infrastructure_errors, plan)

            tally = build_tally(
                plan.cases,
                judgments,
                policy_blocks=len(blocks),
                infrastructure_failures=self.metadata.infrastructure_failures,
            )
            self.metadata.completed_at = datetime.now(UTC).isoformat()
            self.metadata.status = self._final_status(plan, judgments, blocks)
            verdict = build_final_verdict(plan, judgments, tally, self.metadata.status)
            self.store.write_json("summary_tally.json", tally)
            self.store.write_json("final_verdict.json", verdict)
            self.store.write_text("final_verdict.md", final_verdict_markdown(verdict))
            self.store.write_text("case_judgments.md", case_judgments_markdown(judgments))
            self.store.write_json("run_metadata.json", self.metadata)
            return self.metadata.status
        except KeyboardInterrupt:
            self.metadata.completed_at = datetime.now(UTC).isoformat()
            self.metadata.status = RunStatus.ABORTED
            self.metadata.stop_reason = "Interrupted by user"
            self.store.write_json("run_metadata.json", self.metadata)
            return self.metadata.status
        except Exception as exc:
            self.metadata.completed_at = datetime.now(UTC).isoformat()
            self.metadata.status = RunStatus.INFRASTRUCTURE_FAILED
            self.metadata.stop_reason = f"{type(exc).__name__}: {exc}"
            self.store.write_json("run_metadata.json", self.metadata)
            raise

    def _load_or_generate_plan(self, agent_a: str, agent_b: str | None) -> BenchmarkPlan:
        if self.plan_path:
            return BenchmarkPlan.model_validate_json(self.plan_path.read_text(encoding="utf-8"))
        payload, capture = self.agent_gateway.generate_json(
            instructions=PLANNER_INSTRUCTIONS,
            input_text=planner_input(agent_a, agent_b),
        )
        self._add_usage(capture)
        self.store.write_json("planner_capture.json", capture)
        return BenchmarkPlan.model_validate(payload)

    def _run_case(self, case: BenchmarkCase, label: str, agent_text: str) -> CaseRunResult:
        first = self.agent_gateway.generate(instructions=agent_text, input_text=case.test_prompt)
        if not first.text:
            return CaseRunResult(
                case_id=case.id,
                agent_label=label,
                agent_capture=first,
                infrastructure_error=first.error is None,
            )

        needs_clarification = bool(case.clarification_answer_key) and _looks_like_question(
            first.text
        )
        if needs_clarification:
            follow_up = (
                "Original task:\n"
                + case.test_prompt
                + "\n\nPrevious assistant response:\n"
                + first.text
                + "\n\nSimulated user clarification:\n"
                + str(case.clarification_answer_key)
                + "\n\nProvide the final response to the original task."
            )
            second = self.agent_gateway.generate(instructions=agent_text, input_text=follow_up)
            return CaseRunResult(
                case_id=case.id,
                agent_label=label,
                clarification_used=True,
                clarification_question=first.text,
                first_output=first.text,
                final_output=second.text,
                agent_capture=first,
                clarification_capture=second,
                infrastructure_error=not bool(second.text) and second.error is None,
            )
        return CaseRunResult(
            case_id=case.id,
            agent_label=label,
            first_output=first.text,
            final_output=first.text,
            agent_capture=first,
        )

    def _judge_case(self, case: BenchmarkCase, output: str) -> CaseJudgment:
        payload, capture = self.judge_gateway.generate_json(
            instructions=JUDGE_INSTRUCTIONS,
            input_text=judge_input(case, output),
        )
        payload["case_id"] = case.id
        payload["judge_capture"] = capture.model_dump(mode="json")
        judgment = CaseJudgment.model_validate(payload)
        if judgment.gate_check.status == GateStatus.FAIL:
            judgment.overall_rating = Rating.FAIL
        return judgment

    def _checkpoint(
        self,
        runs: dict[str, list[CaseRunResult]],
        judgments: list[CaseJudgment],
        blocks: list[PolicyBlock],
        infrastructure_errors: list[dict[str, Any]],
        plan: BenchmarkPlan,
    ) -> None:
        self.store.write_json("run_results.json", runs)
        self.store.write_json("case_judgments.json", judgments)
        self.store.write_json("policy_blocks.json", blocks)
        self.store.write_json("infrastructure_errors.json", infrastructure_errors)
        self.store.write_json(
            "summary_tally.json",
            build_tally(
                plan.cases,
                judgments,
                policy_blocks=len(blocks),
                infrastructure_failures=self.metadata.infrastructure_failures,
            ),
        )
        self.store.write_json("run_metadata.json", self.metadata)

    def _add_usage(self, capture: ResponseCapture) -> None:
        self.metadata.token_usage.prompt_tokens += capture.input_tokens
        self.metadata.token_usage.completion_tokens += capture.output_tokens
        self.metadata.token_usage.total_tokens += capture.input_tokens + capture.output_tokens
        self.metadata.token_usage.requests += capture.attempts

    def _policy_block_from_capture(
        self, case: BenchmarkCase, label: str, capture: ResponseCapture
    ) -> PolicyBlock | None:
        error = capture.error or {}
        body = error.get("body") or {}
        code = body.get("code") if isinstance(body, dict) else None
        if code not in {"cyber_policy", "content_policy"}:
            return None
        return PolicyBlock(
            case_id=case.id,
            case_title=case.title,
            stage="agent",
            agent=label,
            operation=f"case {case.id} · {label}",
            http_status=error.get("status_code"),
            error_type=body.get("type") if isinstance(body, dict) else error.get("type"),
            error_code=code,
            message=error.get("message", "Policy blocked"),
            request_id=error.get("request_id"),
        )

    def _final_status(
        self, plan: BenchmarkPlan, judgments: list[CaseJudgment], blocks: list[PolicyBlock]
    ) -> RunStatus:
        expected = len(plan.cases) * (2 if self.agent_b_path else 1)
        if self.metadata.infrastructure_failures or blocks or len(judgments) < expected:
            return RunStatus.INCONCLUSIVE
        if any(j.gate_check.status == GateStatus.FAIL for j in judgments):
            return RunStatus.COMPLETED_WITH_FAILURES
        return RunStatus.COMPLETED


def _failed_capture(result: CaseRunResult) -> ResponseCapture | None:
    if result.agent_capture.error:
        return result.agent_capture
    if result.clarification_capture and result.clarification_capture.error:
        return result.clarification_capture
    return None


def _infrastructure_record(
    case: BenchmarkCase, label: str, stage: str, capture: ResponseCapture
) -> dict[str, Any]:
    return {
        "case_id": case.id,
        "case_title": case.title,
        "agent": label,
        "stage": stage,
        "response_id": capture.response_id,
        "request_id": capture.request_id,
        "status": capture.status,
        "finish_reason": capture.finish_reason,
        "attempts": capture.attempts,
        "error": capture.error,
        "raw_response": capture.raw_response,
    }


def _looks_like_question(text: str) -> bool:
    return "?" in text.strip()[-500:]
