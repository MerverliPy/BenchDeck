from __future__ import annotations

import contextlib
import logging
import os
import signal
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .budget import BudgetLimits, BudgetTracker, preflight_check
from .manifest import Manifest
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
from .openai_gateway import GatewayConfig, GatewayProtocol, OpenAIGateway
from .prompts import JUDGE_INSTRUCTIONS, PLANNER_INSTRUCTIONS, judge_input, planner_input
from .reporting import (
    build_per_agent_verdict,
    build_run_verdict,
    case_judgments_markdown,
    run_verdict_markdown,
)
from .scoring import (
    build_tally,
    collect_terminal_keys,
    validate_execution_coverage,
)
from .storage import ArtifactStore

logger = logging.getLogger("benchdeck.runner")


class BenchmarkRunner:
    def __init__(
        self,
        *,
        agent_a_path: Path,
        agent_b_path: Path | None,
        output_dir: Path,
        model: str,
        planner_model: str | None = None,
        judge_model: str,
        plan_path: Path | None = None,
        planner_gateway: GatewayProtocol | None = None,
        agent_gateway: GatewayProtocol | None = None,
        judge_gateway: GatewayProtocol | None = None,
        overwrite: bool = False,
        timeout: float | None = None,
        max_retries: int | None = None,
        budget: BudgetLimits | None = None,
        resume_from: Path | None = None,
        num_judges: int = 1,
    ) -> None:
        self.agent_a_path = agent_a_path
        self.agent_b_path = agent_b_path
        self.output_root = output_dir
        self.plan_path = plan_path
        _planner_model = planner_model or model
        _gw_timeout = timeout if timeout is not None else 90.0
        _gw_retries = max_retries if max_retries is not None else 3
        self._planner_gateway_user = planner_gateway
        self._planner_model = _planner_model
        self._gw_timeout = _gw_timeout
        self._gw_retries = _gw_retries
        self.agent_gateway = agent_gateway or OpenAIGateway(
            GatewayConfig(model=model, timeout_s=_gw_timeout, max_retries=_gw_retries)
        )
        self.judge_gateway = judge_gateway or OpenAIGateway(
            GatewayConfig(
                model=judge_model, timeout_s=_gw_timeout, max_retries=_gw_retries,
                use_structured_output=True,
            )
        )
        self._shutdown = False
        self.num_judges = max(1, num_judges)
        self.budget = BudgetTracker(limits=budget or BudgetLimits())
        self.metadata = RunMetadata(
            config={
                "agent_a": str(agent_a_path),
                "agent_b": str(agent_b_path) if agent_b_path else None,
                "model": model,
                "planner_model": _planner_model,
                "judge_model": judge_model,
                "output_dir": str(output_dir),
                "timeout": _gw_timeout,
                "max_retries": _gw_retries,
            }
        )
        self._resume_from = resume_from
        if resume_from is not None and resume_from.is_dir():
            self.output_dir = resume_from
            self.metadata.run_id = resume_from.name
        else:
            self.output_dir = output_dir / self.metadata.run_id
        if _dir_has_artifacts(output_dir) and not overwrite and resume_from is None:
            raise RuntimeError(
                f"Output directory {output_dir} already contains run artifacts. "
                f"Use --overwrite to replace, or point to a parent directory."
            )
        self.manifest = Manifest(self.output_dir)
        self.store = ArtifactStore(self.output_dir, manifest=self.manifest)
        self._acquire_lock()

    @property
    def agent_labels(self) -> list[str]:
        labels = ["agent_a"]
        if self.agent_b_path is not None:
            labels.append("agent_b")
        return labels

    def _acquire_lock(self) -> None:
        lock_path = self.output_dir / "run.lock"
        if lock_path.exists():
            try:
                stale_ms = (datetime.now(UTC) - datetime.fromtimestamp(
                    lock_path.stat().st_mtime, tz=UTC
                )).total_seconds() * 1000
                if stale_ms < 600_000:
                    pid = lock_path.read_text().strip()
                    raise RuntimeError(
                        f"Run lock held by PID {pid} — another run may be in progress. "
                        "Remove run.lock manually if stale."
                    )
                lock_path.unlink()
            except RuntimeError:
                raise
            except Exception:
                pass
        lock_path.write_text(str(os.getpid()))
        self._lock_path = lock_path

    def _release_lock(self) -> None:
        if getattr(self, "_lock_path", None) is not None:
            with contextlib.suppress(FileNotFoundError):
                self._lock_path.unlink()

    def _load_existing_judgments(self) -> list[CaseJudgment]:
        raw = self.store.read_json("case_judgments.json") or []
        if not isinstance(raw, list):
            return []
        loaded: list[CaseJudgment] = []
        for item in raw:
            if isinstance(item, dict):
                try:
                    loaded.append(CaseJudgment.model_validate(item))
                except Exception:
                    continue
        return loaded

    def _on_signal(self, signum: int, frame: object) -> None:
        self._shutdown = True

    def run(self) -> RunStatus:
        self.store.write_json("run_metadata.json", self.metadata)
        logger.info(
            "Run %s starting — model=%s judge_model=%s agents=%d",
            self.metadata.run_id,
            self.metadata.config.get("model", "?"),
            self.metadata.config.get("judge_model", "?"),
            len(self.agent_labels),
        )
        prev_sigterm = signal.signal(signal.SIGTERM, self._on_signal)
        try:
            agent_a_text = self.agent_a_path.read_text(encoding="utf-8")
            agent_b_text = (
                self.agent_b_path.read_text(encoding="utf-8") if self.agent_b_path else None
            )
            existing_judgments: list[CaseJudgment] = []
            completed_keys: set[ExecutionKey] = set()
            all_runs: dict[str, list[CaseRunResult]] = {}
            blocks: list[PolicyBlock] = []
            infra_errors: list[InfrastructureError] = []

            if self._resume_from is not None:
                plan_data = self.store.read_json("benchmark_plan.json")
                if plan_data is None:
                    raise RuntimeError(
                        f"Cannot resume: no benchmark_plan.json in {self._resume_from}"
                    )
                plan = BenchmarkPlan.model_validate(plan_data)
                existing_judgments = self._load_existing_judgments()
                completed_keys = {j.execution_key for j in existing_judgments}
                existing_results = self.store.read_json("run_results.json") or {}
                for label, models_list in existing_results.items():
                    if isinstance(models_list, list):
                        loaded = [
                            CaseRunResult.model_validate(r)
                            for r in models_list
                            if isinstance(r, dict)
                        ]
                    else:
                        loaded = []
                    all_runs.setdefault(label, []).extend(loaded)
                existing_blocks = self.store.read_json("policy_blocks.json") or []
                blocks = [
                    PolicyBlock.model_validate(b) for b in existing_blocks if isinstance(b, dict)
                ]
                existing_infra = self.store.read_json("infrastructure_errors.json") or []
                infra_errors = [
                    InfrastructureError.model_validate(e)
                    for e in existing_infra
                    if isinstance(e, dict)
                ]
                logger.info(
                    "Resumed run %s: %d cases already judged",
                    self.metadata.run_id,
                    len(existing_judgments),
                )
            else:
                plan = self._load_or_generate_plan(agent_a_text, agent_b_text)
                self.store.write_json("benchmark_plan.json", plan)

            labels = self.agent_labels
            self.metadata.cases_in_plan = len(plan.cases)
            self.metadata.agents_in_run = len(labels)
            self.metadata.executions_planned = len(plan.cases) * len(labels)
            self.metadata.executions_attempted = len(completed_keys)
            self.metadata.executions_model_completed = len(completed_keys)
            self.metadata.executions_judged = len(existing_judgments)
            expected_keys = plan.all_execution_keys(labels)

            if self._resume_from is None:
                self.store.write_json("benchmark_plan.json", plan)
            logger.info("Plan loaded: %d cases across %d agents", len(plan.cases), len(labels))

            # Preflight budget check
            budget_warnings = preflight_check(
                self.budget.limits, len(plan.cases), len(labels)
            )
            for w in budget_warnings:
                logger.warning("Budget preflight: %s", w)

            judgments: list[CaseJudgment] = existing_judgments

            label_texts: list[tuple[str, str | None]] = [
                ("agent_a", agent_a_text),
                ("agent_b", agent_b_text),
            ]

            for label, agent_text in label_texts:
                if agent_text is None:
                    continue
                all_runs.setdefault(label, [])
                for case in plan.cases:
                    if ExecutionKey(agent_label=label, case_id=case.id) in completed_keys:
                        continue
                    if self._shutdown:
                        self.metadata.stop_reason = "Shutdown requested (SIGTERM)"
                        logger.warning("Run %s shutdown requested — aborting", self.metadata.run_id)
                        break
                    self.metadata.executions_attempted += 1
                    logger.debug("Case %d (%s) — executing", case.id, label)
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
                            logger.info("Case %d (%s) — policy blocked", case.id, label)
                        else:
                            self.metadata.infrastructure_failures += 1
                            infra_errors.append(_infra_error(case, label, "agent", failed_cap))
                            logger.warning("Case %d (%s) — infrastructure failure", case.id, label)
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
                        logger.warning(
                            "Case %d (%s) — infrastructure error (empty output)", case.id, label
                        )
                        self._checkpoint(all_runs, judgments, blocks, infra_errors, plan)
                        continue

                    self.metadata.executions_model_completed += 1
                    for judge_idx in range(self.num_judges):
                        if self._shutdown or self.budget.exhausted:
                            break
                        judgment, judge_err = self._judge_case(
                            case, label, result.final_output, judge_idx
                        )
                        if judgment is None:
                            self.metadata.infrastructure_failures += 1
                            if judge_err is not None:
                                infra_errors.append(judge_err)
                            continue
                        judgments.append(judgment)
                        if judgment.judge_capture:
                            _add_usage_from_capture(self.metadata, judgment.judge_capture)
                        self.metadata.executions_judged += 1
                        logger.info(
                            "Case %d (%s) judge %d — %s",
                            case.id,
                            label,
                            judge_idx,
                            judgment.overall_rating.value,
                        )
                    self._checkpoint(all_runs, judgments, blocks, infra_errors, plan)

                if self._shutdown:
                    break

            if self._shutdown:
                self.metadata.completed_at = datetime.now(UTC).isoformat()
                self.metadata.status = RunStatus.ABORTED
                self.store.write_json("run_metadata.json", self.metadata)
                return self.metadata.status

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
            logger.info(
                "Run %s finished — status=%s judged=%d/%d blocks=%d infra=%d",
                self.metadata.run_id,
                run_status.value,
                self.metadata.executions_judged,
                self.metadata.executions_planned,
                self.metadata.policy_blocks,
                self.metadata.infrastructure_failures,
            )

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
            self.store.write_json(
                "budget_tracker.json",
                {
                    "limits": {
                        k: v
                        for k, v in self.budget.limits.__dict__.items()
                        if v is not None
                    },
                    "logical_calls": self.budget.logical_calls,
                    "http_attempts": self.budget.http_attempts,
                    "total_input_tokens": self.budget.total_input_tokens,
                    "total_output_tokens": self.budget.total_output_tokens,
                    "input_tokens_planner": self.budget.input_tokens_planner,
                    "output_tokens_planner": self.budget.output_tokens_planner,
                    "input_tokens_agent": self.budget.input_tokens_agent,
                    "output_tokens_agent": self.budget.output_tokens_agent,
                    "input_tokens_judge": self.budget.input_tokens_judge,
                    "output_tokens_judge": self.budget.output_tokens_judge,
                    "exhausted": self.budget.exhausted,
                    "exhausted_reason": self.budget.exhausted_reason,
                },
            )
            self.store.write_text(
                "final_verdict.md",
                run_verdict_markdown(run_verdict, plan),
            )
            self.store.write_text("case_judgments.md", case_judgments_markdown(judgments))
            self.store.write_json("run_metadata.json", self.metadata)
            return self.metadata.status
        except KeyboardInterrupt:
            self.metadata.completed_at = datetime.now(UTC).isoformat()
            self.metadata.status = RunStatus.ABORTED
            self.metadata.stop_reason = "Interrupted by user"
            logger.warning("Run %s aborted by user", self.metadata.run_id)
            self.store.write_json("run_metadata.json", self.metadata)
            return self.metadata.status
        except Exception as exc:
            self.metadata.completed_at = datetime.now(UTC).isoformat()
            self.metadata.status = RunStatus.INFRASTRUCTURE_FAILED
            self.metadata.stop_reason = f"{type(exc).__name__}: {exc}"
            logger.error("Run %s failed: %s", self.metadata.run_id, exc, exc_info=True)
            self.store.write_json("run_metadata.json", self.metadata)
            return self.metadata.status
        finally:
            self._release_lock()
            signal.signal(signal.SIGTERM, prev_sigterm)

    def _load_or_generate_plan(self, agent_a: str, agent_b: str | None) -> BenchmarkPlan:
        if self.plan_path:
            return BenchmarkPlan.model_validate_json(self.plan_path.read_text(encoding="utf-8"))
        if self.budget.exhausted:
            raise RuntimeError(
                f"Budget exhausted before planner: {self.budget.exhausted_reason}"
            )
        if self._planner_gateway_user is not None:
            planner = self._planner_gateway_user
        else:
            planner = OpenAIGateway(
                GatewayConfig(
                    model=self._planner_model,
                    timeout_s=self._gw_timeout,
                    max_retries=self._gw_retries,
                    use_structured_output=True,
                )
            )
        gen_result = planner.generate_json(
            instructions=PLANNER_INSTRUCTIONS,
            input_text=planner_input(agent_a, agent_b),
        )
        self.budget.record_call(
            stage="planner",
            input_tokens=gen_result.total_input_tokens,
            output_tokens=gen_result.total_output_tokens,
            http_attempts=gen_result.total_http_attempts,
        )
        _add_usage_from_result(self.metadata, gen_result)
        self.store.write_json("planner_capture.json", gen_result.model_dump(mode="json"))
        if gen_result.value is None:
            raise RuntimeError(
                f"Planner failed: {gen_result.terminal_error or gen_result.parse_error}"
            )
        return BenchmarkPlan.model_validate(gen_result.value)

    def _run_case(self, case: BenchmarkCase, label: str, agent_text: str) -> CaseRunResult:
        if self.budget.exhausted:
            return CaseRunResult(
                case_id=case.id,
                agent_label=label,
                agent_capture=ResponseCapture(
                    error={"type": "BudgetExhausted", "message": self.budget.exhausted_reason},
                ),
                infrastructure_error=True,
            )
        first = self.agent_gateway.generate(instructions=agent_text, input_text=case.test_prompt)
        self.budget.record_call(
            stage="agent",
            input_tokens=first.total_input_tokens,
            output_tokens=first.total_output_tokens,
            http_attempts=first.total_http_attempts,
        )

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
        self.budget.record_call(
            stage="agent",
            input_tokens=second.total_input_tokens,
            output_tokens=second.total_output_tokens,
            http_attempts=second.total_http_attempts,
        )
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

    def _judge_case(
        self, case: BenchmarkCase, agent_label: str, output: str, judge_idx: int = 0
    ) -> tuple[CaseJudgment | None, InfrastructureError | None]:
        if self.budget.exhausted:
            logger.warning(
                "Case %d (%s) — skipped judge %d: budget exhausted",
                case.id, agent_label, judge_idx,
            )
            return None, InfrastructureError(
                case_id=case.id,
                agent_label=agent_label,
                case_title=case.title,
                stage=f"judge_{judge_idx}",
                error_type="BudgetExhausted",
                message=self.budget.exhausted_reason,
            )
        gen_result = self.judge_gateway.generate_json(
            instructions=JUDGE_INSTRUCTIONS,
            input_text=judge_input(case, output),
        )
        self.budget.record_call(
            stage="judge",
            input_tokens=gen_result.total_input_tokens,
            output_tokens=gen_result.total_output_tokens,
            http_attempts=gen_result.total_http_attempts,
        )
        _add_usage_from_result(self.metadata, gen_result)
        capture = _result_to_capture(gen_result)
        if gen_result.value is None:
            err_msg = gen_result.terminal_error.message if gen_result.terminal_error else (
                gen_result.parse_error or "Unknown judge failure"
            )
            logger.error(
                "Case %d (%s) judge %d — failed: %s",
                case.id, agent_label, judge_idx, err_msg,
            )
            return None, InfrastructureError(
                case_id=case.id,
                agent_label=agent_label,
                case_title=case.title,
                stage=f"judge_{judge_idx}",
                error_type="JudgeGenerationError",
                message=err_msg,
                response_id=capture.response_id,
                request_id=capture.request_id,
                status=capture.status,
                finish_reason=capture.finish_reason,
                attempts=capture.attempts,
                error=capture.error,
                raw_response=capture.raw_response,
            )
        payload: dict[str, Any] = dict(gen_result.value)
        payload["case_id"] = case.id
        payload["agent_label"] = agent_label
        payload["judge_index"] = judge_idx

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
        return judgment, None

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


def _dir_has_artifacts(directory: Path) -> bool:
    if not directory.is_dir():
        return False
    if (directory / "run_metadata.json").exists():
        return True
    return any(
        (d / "run_metadata.json").exists()
        for d in directory.iterdir()
        if d.is_dir()
    )


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
