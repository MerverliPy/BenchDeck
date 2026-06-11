from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import (
    BenchmarkCase,
    BenchmarkPlan,
    CaseJudgment,
    CaseRunResult,
    CoverageReport,
    ExecutionKey,
    GateStatus,
    InfrastructureError,
    PolicyBlock,
    Rating,
    ResponseCapture,
    RunMetadata,
    RunStatus,
)
from .openai_gateway import GatewayConfig, OpenAIGateway
from .prompts import JUDGE_INSTRUCTIONS, PLANNER_INSTRUCTIONS, judge_input, planner_input
from .reporting import (
    build_per_agent_verdict,
    build_run_verdict,
    case_judgments_markdown,
    final_verdict_markdown,
)
from .scoring import (
    build_tally,
    collect_terminal_keys,
    validate_execution_coverage,
)
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
        planner_gateway: Any = None,
        agent_gateway: Any = None,
        judge_gateway: Any = None,
    ) -> None:
        self.agent_a_path = agent_a_path
        self.agent_b_path = agent_b_path
        self.output_dir = output_dir
        self.plan_path = plan_path
        self._planner_gateway = planner_gateway
        self._external_agent_gateway = agent_gateway
        self._external_judge_gateway = judge_gateway
        self.agent_gateway = agent_gateway or OpenAIGateway(GatewayConfig(model=model))
        self.judge_gateway = judge_gateway or OpenAIGateway(GatewayConfig(model=judge_model))
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

    @property
    def agent_labels(self) -> list[str]:
        labels = ["agent_a"]
        if self.agent_b_path is not None:
            labels.append("agent_b")
        return labels

    def run(self) -> RunStatus:
        self.store.write_json("run_metadata.json", self.metadata)
        try:
            agent_a_text = self.agent_a_path.read_text(encoding="utf-8")
            agent_b_text = (
                self.agent_b_path.read_text(encoding="utf-8") if self.agent_b_path else None
            )
            plan = self._load_or_generate_plan(agent_a_text, agent_b_text)

            labels = self.agent_labels
            self.metadata.cases_in_plan = len(plan.cases)
            self.metadata.agents_in_run = len(labels)
            self.metadata.executions_planned = len(plan.cases) * len(labels)
            expected_keys = plan.all_execution_keys(labels)

            self.store.write_json("benchmark_plan.json", plan)

            all_runs: dict[str, list[CaseRunResult]] = {}
            judgments: list[CaseJudgment] = []
            blocks: list[PolicyBlock] = []
            infra_errors: list[InfrastructureError] = []

            label_texts: list[tuple[str, str | None]] = [
                ("agent_a", agent_a_text),
                ("agent_b", agent_b_text),
            ]

            for label, agent_text in label_texts:
                if agent_text is None:
                    continue
                all_runs.setdefault(label, [])
                for case in plan.cases:
                    self.metadata.executions_attempted += 1
                    result = self._run_case(case, label, agent_text)
                    all_runs[label].append(result)
                    _add_usage(self.metadata, result.agent_capture)
                    if result.clarification_capture:
                        _add_usage(self.metadata, result.clarification_capture)

                    failed_cap = _failed_capture(result)
                    if failed_cap is not None:
                        block = _policy_block_from_capture(case, label, failed_cap)
                        if block:
                            blocks.append(block)
                            self.metadata.policy_blocks += 1
                        else:
                            self.metadata.infrastructure_failures += 1
                            infra_errors.append(_infra_error(case, label, "agent", failed_cap))
                        self._checkpoint(all_runs, judgments, blocks, infra_errors, plan)
                        continue
                    if result.infrastructure_error:
                        self.metadata.infrastructure_failures += 1
                        infra_errors.append(
                            _infra_error(
                                case,
                                label,
                                "agent",
                                result.clarification_capture or result.agent_capture,
                            )
                        )
                        self._checkpoint(all_runs, judgments, blocks, infra_errors, plan)
                        continue

                    self.metadata.executions_model_completed += 1
                    try:
                        judgment = self._judge_case(case, label, result.final_output)
                    except Exception as exc:
                        self.metadata.infrastructure_failures += 1
                        infra_errors.append(
                            InfrastructureError(
                                case_id=case.id,
                                agent_label=label,
                                case_title=case.title,
                                stage="judge",
                                error_type=type(exc).__name__,
                                message=str(exc),
                            )
                        )
                        self._checkpoint(all_runs, judgments, blocks, infra_errors, plan)
                        continue
                    judgments.append(judgment)
                    if judgment.judge_capture:
                        _add_usage(self.metadata, judgment.judge_capture)
                    self.metadata.executions_judged += 1
                    self._checkpoint(all_runs, judgments, blocks, infra_errors, plan)

            # collect terminal keys and validate coverage
            terminal_keys = collect_terminal_keys(all_runs, judgments, blocks)
            for ie in infra_errors:
                terminal_keys.add(ie.execution_key)
            coverage = validate_execution_coverage(expected_keys, terminal_keys)

            # per-agent tallies
            per_agent_tallies: dict[str, Any] = {}
            for label in labels:
                per_agent_tallies[label] = build_tally(
                    plan.cases,
                    judgments,
                    agent_label=label,
                    policy_blocks=sum(1 for b in blocks if b.agent_label == label),
                    infrastructure_failures=sum(
                        1 for ie in infra_errors if ie.agent_label == label
                    ),
                )

            self.metadata.completed_at = datetime.now(UTC).isoformat()
            self.metadata.status = _final_status(plan, judgments, blocks, coverage)
            run_status = self.metadata.status

            # per-agent verdicts
            agent_verdicts: dict[str, Any] = {}
            for label in labels:
                agent_cov = _coverage_for_agent(expected_keys, terminal_keys, label)
                agent_verdicts[label] = build_per_agent_verdict(
                    label, plan, judgments, per_agent_tallies[label], agent_cov, run_status
                )

            run_verdict = build_run_verdict(run_status, agent_verdicts, plan, judgments)

            self.store.write_json("summary_tally.json", per_agent_tallies)
            self.store.write_json("final_verdict.json", run_verdict)
            self.store.write_text(
                "final_verdict.md",
                final_verdict_markdown(
                    _legacy_verdict(plan, judgments, run_status, per_agent_tallies)
                ),
            )
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
        planner = self._planner_gateway or self.agent_gateway
        payload, capture = planner.generate_json(
            instructions=PLANNER_INSTRUCTIONS,
            input_text=planner_input(agent_a, agent_b),
        )
        _add_usage(self.metadata, capture)
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

    def _judge_case(self, case: BenchmarkCase, agent_label: str, output: str) -> CaseJudgment:
        payload, capture = self.judge_gateway.generate_json(
            instructions=JUDGE_INSTRUCTIONS,
            input_text=judge_input(case, output),
        )
        payload["case_id"] = case.id
        payload["agent_label"] = agent_label
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
        infra_errors: list[InfrastructureError],
        plan: BenchmarkPlan,
    ) -> None:
        self.store.write_json("run_results.json", runs)
        self.store.write_json("case_judgments.json", judgments)
        self.store.write_json("policy_blocks.json", blocks)
        self.store.write_json("infrastructure_errors.json", infra_errors)
        self.store.write_json("run_metadata.json", self.metadata)


# ── helpers ───────────────────────────────────────────────────────────────


def _add_usage(metadata: RunMetadata, capture: ResponseCapture) -> None:
    metadata.token_usage.prompt_tokens += capture.input_tokens
    metadata.token_usage.completion_tokens += capture.output_tokens
    metadata.token_usage.total_tokens += capture.input_tokens + capture.output_tokens
    metadata.token_usage.requests += capture.attempts


def _failed_capture(result: CaseRunResult) -> ResponseCapture | None:
    if result.agent_capture.error:
        return result.agent_capture
    if result.clarification_capture and result.clarification_capture.error:
        return result.clarification_capture
    return None


def _policy_block_from_capture(
    case: BenchmarkCase, label: str, capture: ResponseCapture
) -> PolicyBlock | None:
    error = capture.error or {}
    body = error.get("body") or {}
    code = None
    if isinstance(body, dict):
        code = body.get("code")
        if code is None:
            nested = body.get("error")
            if isinstance(nested, dict):
                code = nested.get("code")
    if code not in {"cyber_policy", "content_policy"}:
        return None
    return PolicyBlock(
        case_id=case.id,
        case_title=case.title,
        stage="agent",
        agent_label=label,
        operation=f"case {case.id} · {label}",
        http_status=error.get("status_code"),
        error_type=body.get("type") if isinstance(body, dict) else error.get("type"),
        error_code=code,
        message=error.get("message", "Policy blocked"),
        request_id=error.get("request_id"),
    )


def _infra_error(
    case: BenchmarkCase, label: str, stage: str, capture: ResponseCapture
) -> InfrastructureError:
    return InfrastructureError(
        case_id=case.id,
        case_title=case.title,
        agent_label=label,
        stage=stage,
        response_id=capture.response_id,
        request_id=capture.request_id,
        status=capture.status,
        finish_reason=capture.finish_reason,
        attempts=capture.attempts,
        error=capture.error,
        raw_response=capture.raw_response,
    )


def _looks_like_question(text: str) -> bool:
    return "?" in text.strip()[-500:]


def _final_status(
    plan: BenchmarkPlan,
    judgments: list[CaseJudgment],
    blocks: list[PolicyBlock],
    coverage: object,
) -> RunStatus:
    cov_ok = getattr(coverage, "is_complete", True)
    if not cov_ok or blocks:
        return RunStatus.INCONCLUSIVE
    if any(j.gate_check.status == GateStatus.FAIL for j in judgments):
        return RunStatus.COMPLETED_WITH_FAILURES
    return RunStatus.COMPLETED


def _coverage_for_agent(
    expected: set[ExecutionKey],
    terminal: set[ExecutionKey],
    agent_label: str,
) -> CoverageReport:
    expected_agent = {k for k in expected if k.agent_label == agent_label}
    terminal_agent = {k for k in terminal if k.agent_label == agent_label}
    return validate_execution_coverage(expected_agent, terminal_agent)


def _legacy_verdict(
    plan: BenchmarkPlan,
    judgments: list[CaseJudgment],
    status: RunStatus,
    tallies: dict[str, Any],
) -> dict[str, Any]:
    from collections import Counter

    first_tally: Any = next(iter(tallies.values()), {}) if tallies else {}
    ratings = Counter(j.overall_rating.value for j in judgments)
    family_scores = getattr(first_tally, "family_scores", {})
    gate_failures = getattr(first_tally, "gate_failures", 0)
    validated = status == RunStatus.COMPLETED and gate_failures == 0
    return {
        "overall_verdict": "Validated" if validated else "Not Validated",
        "run_status": status.value,
        "decision": "Ready for use" if validated else "Revise or rerun before use",
        "cases_planned": len(plan.cases),
        "cases_judged": len(judgments),
        "rating_counts": dict(ratings),
        "gate_failures": int(gate_failures),
        "family_scores": family_scores,
        "strongest_capabilities": [],
        "remaining_weak_spots": [],
        "confidence_notes": "",
    }
