from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import (
    BenchmarkCase,
    BenchmarkPlan,
    CaseJudgment,
    CaseRunResult,
    ClarificationExpectation,
    CoverageReport,
    ErrorCategory,
    ErrorRecord,
    ExecutionKey,
    GateStatus,
    GenerationResult,
    InfrastructureError,
    PolicyBlock,
    Rating,
    ResponseCapture,
    Rubric,
    RubricDimension,
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

                    # Accumulate usage from agent captures
                    _add_usage_from_capture(self.metadata, result.agent_capture)
                    if result.clarification_capture:
                        _add_usage_from_capture(self.metadata, result.clarification_capture)

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
                        _add_usage_from_capture(self.metadata, judgment.judge_capture)
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
        gen_result = planner.generate_json(
            instructions=PLANNER_INSTRUCTIONS,
            input_text=planner_input(agent_a, agent_b),
        )
        _add_usage_from_result(self.metadata, gen_result)
        self.store.write_json("planner_capture.json", gen_result.model_dump(mode="json"))
        if gen_result.value is None:
            raise RuntimeError(
                f"Planner failed: {gen_result.terminal_error or gen_result.parse_error}"
            )
        return BenchmarkPlan.model_validate(gen_result.value)

    def _run_case(self, case: BenchmarkCase, label: str, agent_text: str) -> CaseRunResult:
        first = self.agent_gateway.generate(instructions=agent_text, input_text=case.test_prompt)

        # Check for refusal or terminal error BEFORE generic completion check
        if first.has_refusal:
            return CaseRunResult(
                case_id=case.id,
                agent_label=label,
                agent_capture=_result_to_capture(first),
                infrastructure_error=False,
                final_output=first.last_attempt.output_text if first.last_attempt else "",
                first_output=first.last_attempt.output_text if first.last_attempt else "",
            )

        if first.terminal_error is not None:
            return CaseRunResult(
                case_id=case.id,
                agent_label=label,
                agent_capture=_result_to_capture(first),
                infrastructure_error=not _is_policy_error(first.terminal_error),
                final_output="",
                first_output="",
            )

        output_text = first.value or ""
        if not output_text:
            return CaseRunResult(
                case_id=case.id,
                agent_label=label,
                agent_capture=_result_to_capture(first),
                infrastructure_error=True,
            )

        # Use typed clarification expectation (replaces punctuation heuristic)
        clar_exp = case.clarification_expectation
        has_key = bool(case.clarification_answer_key)
        if clar_exp == ClarificationExpectation.REQUIRED.value and has_key:
            return self._clarify_and_return(case, label, agent_text, output_text, first)
        if clar_exp == ClarificationExpectation.OPTIONAL.value and has_key:
            return self._clarify_and_return(case, label, agent_text, output_text, first)
        # undesirable: no clarification regardless

        return CaseRunResult(
            case_id=case.id,
            agent_label=label,
            first_output=output_text,
            final_output=output_text,
            agent_capture=_result_to_capture(first),
        )

    def _clarify_and_return(
        self,
        case: BenchmarkCase,
        label: str,
        agent_text: str,
        first_output: str,
        first_result: GenerationResult[str],
    ) -> CaseRunResult:
        follow_up = (
            "Original task:\n"
            + case.test_prompt
            + "\n\nPrevious assistant response:\n"
            + first_output
            + "\n\nSimulated user clarification:\n"
            + str(case.clarification_answer_key)
            + "\n\nProvide the final response to the original task."
        )
        second = self.agent_gateway.generate(instructions=agent_text, input_text=follow_up)
        second_text = second.value or ""
        second_cap = _result_to_capture(second)
        return CaseRunResult(
            case_id=case.id,
            agent_label=label,
            clarification_used=True,
            clarification_question=first_output,
            first_output=first_output,
            final_output=second_text,
            agent_capture=_result_to_capture(first_result),
            clarification_capture=second_cap,
            infrastructure_error=(
                not bool(second_text) and second.terminal_error is None and not second.has_refusal
            ),
        )

    def _judge_case(self, case: BenchmarkCase, agent_label: str, output: str) -> CaseJudgment:
        gen_result = self.judge_gateway.generate_json(
            instructions=JUDGE_INSTRUCTIONS,
            input_text=judge_input(case, output),
        )
        if gen_result.value is None:
            raise RuntimeError(
                f"Judge failed for case {case.id} ({agent_label}): "
                f"{gen_result.terminal_error or gen_result.parse_error}"
            )
        payload: dict[str, Any] = dict(gen_result.value)
        payload["case_id"] = case.id
        payload["agent_label"] = agent_label

        # Build typed Rubric from judge's structured output
        raw_dims = payload.pop("rubric_dimensions", None)
        if isinstance(raw_dims, list):
            rubric = Rubric(
                dimensions=[
                    RubricDimension(
                        dimension=str(d.get("dimension", d.get("dim", ""))),
                        rating=Rating(str(d.get("rating", "Acceptable"))),
                        evidence=str(d.get("evidence", "")),
                        strengths=[str(s) for s in d.get("strengths", [])],
                        weaknesses=[str(w) for w in d.get("weaknesses", [])],
                    )
                    for d in raw_dims
                    if isinstance(d, dict)
                ]
            )
        else:
            rubric = Rubric(
                dimensions=[
                    RubricDimension(dimension=d, rating=Rating("Acceptable"))
                    for d in [
                        "mission_fidelity",
                        "task_success",
                        "priority_adherence",
                        "ambiguity_handling",
                        "process_discipline",
                        "tool_discipline",
                        "robustness",
                        "regression_safety",
                    ]
                ]
            )
        payload["rubric"] = rubric

        # Use deterministic Python rating if the model's overall_rating is missing
        if "overall_rating" not in payload or not payload["overall_rating"]:
            payload["overall_rating"] = rubric.overall_rating().value

        capture = _result_to_capture(gen_result)
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


# ── gateway result conversion ─────────────────────────────────────────────


def _result_to_capture(result: GenerationResult[Any]) -> ResponseCapture:
    """Convert a GenerationResult to a legacy ResponseCapture for storage."""
    last = result.last_attempt
    if last is not None:
        err_dict: dict[str, Any] | None = None
        if last.error is not None:
            error_raw = last.error.raw_error or {}
            err_dict = {
                "type": error_raw.get("type", "GenerationError"),
                "status_code": last.error.http_status,
                "message": last.error.message,
                "request_id": last.error.request_id,
                "body": error_raw.get("body")
                if isinstance(error_raw.get("body"), dict)
                else error_raw
                if isinstance(error_raw, dict)
                else None,
            }
        elif result.has_refusal:
            err_dict = {
                "type": "Refusal",
                "message": last.refusal or last.output_text or "Model refused",
                "request_id": last.request_id,
                "body": None,
            }
        return ResponseCapture(
            text=last.output_text,
            response_id=last.response_id,
            request_id=last.request_id,
            status=last.provider_status,
            finish_reason=last.finish_reason,
            input_tokens=last.usage.input_tokens,
            output_tokens=last.usage.output_tokens,
            raw_response=last.raw_response,
            error=err_dict,
            attempts=result.total_http_attempts,
        )
    # No attempts — synthesise from terminal_error
    err_dict_synth: dict[str, Any] | None = None
    if result.terminal_error is not None:
        err_dict_synth = {
            "type": "GenerationError",
            "message": result.terminal_error.message,
            "request_id": result.terminal_error.request_id,
            "body": result.terminal_error.raw_error,
            "category": result.terminal_error.category.value,
        }
    return ResponseCapture(error=err_dict_synth, attempts=result.total_http_attempts)


def _add_usage_from_result(metadata: RunMetadata, result: GenerationResult[Any]) -> None:
    metadata.token_usage.prompt_tokens += result.total_input_tokens
    metadata.token_usage.completion_tokens += result.total_output_tokens
    metadata.token_usage.total_tokens += result.total_input_tokens + result.total_output_tokens
    metadata.token_usage.requests += result.total_http_attempts


def _add_usage_from_capture(metadata: RunMetadata, capture: ResponseCapture) -> None:
    metadata.token_usage.prompt_tokens += capture.input_tokens
    metadata.token_usage.completion_tokens += capture.output_tokens
    metadata.token_usage.total_tokens += capture.input_tokens + capture.output_tokens
    metadata.token_usage.requests += capture.attempts


# ── failure classification ────────────────────────────────────────────────


def _is_policy_error(err: ErrorRecord) -> bool:
    return err.category == ErrorCategory.POLICY


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
    error_type = error.get("type", "")
    if error_type == "Refusal":
        return PolicyBlock(
            case_id=case.id,
            case_title=case.title,
            stage="agent",
            agent_label=label,
            operation=f"case {case.id} · {label}",
            message=f"Agent refused: {error.get('message', '')}",
            request_id=error.get("request_id"),
            error_code="refusal",
            error_type="Refusal",
            http_status=None,
        )
    body = error.get("body") or {}
    code = _extract_policy_code(body)
    if code is None:
        code = _extract_policy_code(error)
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


def _extract_policy_code(body: Any) -> str | None:
    """Recursively search for a policy code in nested provider error bodies."""
    if isinstance(body, dict):
        code = body.get("code")
        if code is not None and isinstance(code, str):
            return code
        nested = body.get("error")
        if isinstance(nested, dict):
            return _extract_policy_code(nested)
    return None


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
