import asyncio
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    BenchmarkCase,
    BenchmarkSuite,
    CaseExecution,
    EvaluationRun,
    EvaluationStatus,
    RegressionAlert,
)
from repositories.benchmark_repository import BenchmarkRepository
from repositories.agent_repository import AgentRepository
from repositories.evaluation_repository import EvaluationRepository


class EvaluationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.benchmark_repo = BenchmarkRepository(session)
        self.agent_repo = AgentRepository(session)
        self.evaluation_repo = EvaluationRepository(session)

    async def create_evaluation_run(self, suite_id: str, agent_version_id: str, trigger: str) -> EvaluationRun:
        return await self.evaluation_repo.create_run(suite_id, agent_version_id, trigger)

    async def create_case_execution(
        self,
        evaluation_run_id: str,
        benchmark_case: BenchmarkCase,
    ) -> CaseExecution:
        return await self.evaluation_repo.create_case_execution(
            evaluation_run_id=evaluation_run_id,
            benchmark_case_id=str(benchmark_case.id),
            input_payload={
                "title": benchmark_case.title,
                "repository_state": benchmark_case.repository_state,
                "team_status": benchmark_case.team_status,
                "deadlines": benchmark_case.deadlines,
                "expected_actions": benchmark_case.expected_actions,
                "ground_truth": benchmark_case.ground_truth,
            },
        )

    async def execute_benchmark_case(
        self,
        agent_callable: Any,
        case: BenchmarkCase,
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        start = time.time()

        payload = {
            "case_id": str(case.id),
            "title": case.title,
            "description": case.description,
            "repository_state": case.repository_state,
            "team_status": case.team_status,
            "deadlines": case.deadlines,
            "expected_actions": case.expected_actions,
            "ground_truth": case.ground_truth,
        }

        output: dict[str, Any] = await agent_callable(payload)
        latency = time.time() - start

        metrics = {
            "latency_seconds": latency,
            "tokens_used": int(output.get("metrics", {}).get("tokens_used", 0)),
            "cost_usd": float(output.get("metrics", {}).get("cost_usd", 0.0)),
            "accuracy": self._score_accuracy(output.get("final_report", {}), case.ground_truth or {}),
            "completion_rate": 1.0 if output.get("final_report") else 0.0,
            "tool_success_rate": float(output.get("metrics", {}).get("tool_success_rate", 1.0)),
        }

        traces = output.get("execution_trace", [])
        return output, metrics, traces

    def _score_accuracy(self, output: dict[str, Any], ground_truth: dict[str, Any]) -> float:
        if not ground_truth or not output:
            return 0.0

        correct = 0
        total = 0
        for key, expected in ground_truth.items():
            total += 1
            actual = output.get(key)
            if actual == expected:
                correct += 1
            elif isinstance(expected, str) and isinstance(actual, str) and expected.lower().strip() == actual.lower().strip():
                correct += 1
        return correct / total if total else 0.0

    async def generate_regression_alerts(
        self,
        run: EvaluationRun,
        previous_run: EvaluationRun | None,
        case_executions: list[CaseExecution],
    ) -> list[RegressionAlert]:
        alerts: list[RegressionAlert] = []
        baseline_accuracy = previous_run.accuracy if previous_run else None
        baseline_latency = previous_run.average_latency_ms if previous_run else None

        if baseline_accuracy is not None and run.accuracy is not None and run.accuracy < baseline_accuracy - 0.05:
            alerts.append(
                await self.evaluation_repo.create_regression_alert(
                    evaluation_run_id=str(run.id),
                    agent_version_id=str(run.agent_version_id),
                    benchmark_case_id=None,
                    alert_type="accuracy_regression",
                    severity="high",
                    message=f"Accuracy dropped from {baseline_accuracy:.2f} to {run.accuracy:.2f}.",
                    indicators={"previous_accuracy": baseline_accuracy, "current_accuracy": run.accuracy},
                )
            )

        if baseline_latency is not None and run.average_latency_ms is not None and run.average_latency_ms > baseline_latency * 1.2:
            alerts.append(
                await self.evaluation_repo.create_regression_alert(
                    evaluation_run_id=str(run.id),
                    agent_version_id=str(run.agent_version_id),
                    benchmark_case_id=None,
                    alert_type="latency_regression",
                    severity="medium",
                    message=f"Average latency increased from {baseline_latency:.1f} ms to {run.average_latency_ms:.1f} ms.",
                    indicators={"previous_latency": baseline_latency, "current_latency": run.average_latency_ms},
                )
            )

        failed_cases = [execution for execution in case_executions if execution.status != "completed"]
        if failed_cases and len(failed_cases) / max(len(case_executions), 1) > 0.2:
            alerts.append(
                await self.evaluation_repo.create_regression_alert(
                    evaluation_run_id=str(run.id),
                    agent_version_id=str(run.agent_version_id),
                    benchmark_case_id=None,
                    alert_type="tool_failure_rate",
                    severity="critical",
                    message=f"{len(failed_cases)} of {len(case_executions)} benchmark cases failed during execution.",
                    indicators={"failed_cases": len(failed_cases), "total_cases": len(case_executions)},
                )
            )

        return alerts
