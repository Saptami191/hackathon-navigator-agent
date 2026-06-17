from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    CaseExecution,
    ExecutionTrace,
    EvaluationRun,
    RegressionAlert,
)


class EvaluationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_run(
        self,
        suite_id: str,
        agent_version_id: str,
        trigger: str,
    ) -> EvaluationRun:
        run = EvaluationRun(
            suite_id=suite_id,
            agent_version_id=agent_version_id,
            trigger=trigger,
            status="queued",
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def update_run(self, run: EvaluationRun, **fields) -> EvaluationRun:
        for key, value in fields.items():
            setattr(run, key, value)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def create_case_execution(
        self,
        evaluation_run_id: str,
        benchmark_case_id: str,
        input_payload: dict | None = None,
    ) -> CaseExecution:
        case_execution = CaseExecution(
            evaluation_run_id=evaluation_run_id,
            benchmark_case_id=benchmark_case_id,
            status="queued",
            input_payload=input_payload or {},
        )
        self.session.add(case_execution)
        await self.session.commit()
        await self.session.refresh(case_execution)
        return case_execution

    async def update_case_execution(self, case_execution: CaseExecution, **fields) -> CaseExecution:
        for key, value in fields.items():
            setattr(case_execution, key, value)
        await self.session.commit()
        await self.session.refresh(case_execution)
        return case_execution

    async def create_trace(
        self,
        case_execution_id: str,
        step_name: str,
        prompt: str | None = None,
        retrieved_context: dict | None = None,
        tool_calls: list[dict] | None = None,
        intermediate_reasoning: str | None = None,
        model_response: dict | None = None,
        output: str | None = None,
    ) -> ExecutionTrace:
        trace = ExecutionTrace(
            case_execution_id=case_execution_id,
            step_name=step_name,
            prompt=prompt,
            retrieved_context=retrieved_context or {},
            tool_calls=tool_calls or [],
            intermediate_reasoning=intermediate_reasoning,
            model_response=model_response or {},
            output=output,
        )
        self.session.add(trace)
        await self.session.commit()
        await self.session.refresh(trace)
        return trace

    async def create_regression_alert(
        self,
        evaluation_run_id: str,
        agent_version_id: str,
        benchmark_case_id: str | None,
        alert_type: str,
        severity: str,
        message: str,
        indicators: dict | None = None,
    ) -> RegressionAlert:
        alert = RegressionAlert(
            evaluation_run_id=evaluation_run_id,
            agent_version_id=agent_version_id,
            benchmark_case_id=benchmark_case_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            indicators=indicators or {},
        )
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        return alert

    async def list_run_cases(self, run_id: str) -> list[CaseExecution]:
        result = await self.session.execute(
            select(CaseExecution).where(CaseExecution.evaluation_run_id == run_id).order_by(CaseExecution.created_at)
        )
        return result.scalars().all()

    async def get_run(self, run_id: str) -> EvaluationRun | None:
        result = await self.session.execute(select(EvaluationRun).where(EvaluationRun.id == run_id))
        return result.scalar_one_or_none()
