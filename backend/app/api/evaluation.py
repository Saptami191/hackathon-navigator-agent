import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from core.auth import CurrentUser, DBSession
from db.models import (
    BenchmarkCase,
    BenchmarkSuite,
    AgentVersion,
    EvaluationRun,
    CaseExecution,
    RegressionAlert,
)
from sqlalchemy import select
from services.benchmark_service import BenchmarkService
from services.agent_service import AgentService
from services.evaluation_service import EvaluationService

router = APIRouter(prefix="", tags=["evaluations"])


class BenchmarkSuiteCreate(BaseModel):
    name: str
    description: str | None = None
    version: str = "v1"
    tags: list[str] = []
    metadata: dict[str, Any] = {}


class BenchmarkSuiteResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    version: str
    tags: list[str] | None
    metadata: dict[str, Any] | None
    status: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BenchmarkCaseCreate(BaseModel):
    title: str
    description: str | None = None
    repository_state: dict[str, Any] = Field(default_factory=dict)
    team_status: dict[str, Any] = Field(default_factory=dict)
    deadlines: dict[str, Any] = Field(default_factory=dict)
    expected_actions: dict[str, Any] = Field(default_factory=dict)
    ground_truth: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = []
    case_version: str | None = None


class BenchmarkCaseResponse(BaseModel):
    id: uuid.UUID
    suite_id: uuid.UUID
    title: str
    description: str | None
    repository_state: dict[str, Any] | None
    team_status: dict[str, Any] | None
    deadlines: dict[str, Any] | None
    expected_actions: dict[str, Any] | None
    ground_truth: dict[str, Any] | None
    tags: list[str] | None
    case_version: str | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AgentVersionCreate(BaseModel):
    name: str
    version: str
    callable_path: str
    branch: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = {}
    status: str = "active"


class AgentVersionResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    branch: str | None
    description: str | None
    callable_path: str
    metadata: dict[str, Any] | None
    status: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class EvaluationRunCreate(BaseModel):
    suite_id: uuid.UUID
    agent_version_id: uuid.UUID
    trigger: str = "manual"


class EvaluationRunResponse(BaseModel):
    id: uuid.UUID
    suite_id: uuid.UUID
    agent_version_id: uuid.UUID
    trigger: str
    status: str
    total_cases: int | None
    completed_cases: int | None
    accuracy: float | None
    average_latency_ms: float | None
    token_usage_total: int | None
    average_cost_usd: float | None
    completion_rate: float | None
    tool_success_rate: float | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    class Config:
        from_attributes = True


class CaseExecutionResponse(BaseModel):
    id: uuid.UUID
    evaluation_run_id: uuid.UUID
    benchmark_case_id: uuid.UUID
    status: str
    input_payload: dict[str, Any] | None
    output_payload: dict[str, Any] | None
    metrics: dict[str, Any] | None
    latency_seconds: float | None
    tokens_used: int | None
    cost_usd: float | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class RegressionAlertResponse(BaseModel):
    id: uuid.UUID
    evaluation_run_id: uuid.UUID
    agent_version_id: uuid.UUID
    benchmark_case_id: uuid.UUID | None
    alert_type: str
    severity: str
    message: str | None
    indicators: dict[str, Any] | None
    is_resolved: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/suites", response_model=BenchmarkSuiteResponse, status_code=status.HTTP_201_CREATED)
async def create_benchmark_suite(data: BenchmarkSuiteCreate, user: CurrentUser, session: DBSession):
    service = BenchmarkService(session)
    suite = await service.create_suite(data.name, data.description, data.version, data.tags, data.metadata)
    return suite


@router.get("/suites", response_model=list[BenchmarkSuiteResponse])
async def list_benchmark_suites(user: CurrentUser, session: DBSession):
    service = BenchmarkService(session)
    return await service.list_suites()


@router.get("/suites/{suite_id}", response_model=BenchmarkSuiteResponse)
async def get_benchmark_suite(suite_id: uuid.UUID, user: CurrentUser, session: DBSession):
    service = BenchmarkService(session)
    suite = await service.get_suite(str(suite_id))
    if not suite:
        raise HTTPException(status_code=404, detail="Benchmark suite not found")
    return suite


@router.post("/suites/{suite_id}/cases", response_model=BenchmarkCaseResponse, status_code=status.HTTP_201_CREATED)
async def create_benchmark_case(suite_id: uuid.UUID, data: BenchmarkCaseCreate, user: CurrentUser, session: DBSession):
    service = BenchmarkService(session)
    suite = await service.get_suite(str(suite_id))
    if not suite:
        raise HTTPException(status_code=404, detail="Benchmark suite not found")
    case = await service.create_case(
        suite_id=str(suite_id),
        title=data.title,
        description=data.description,
        repository_state=data.repository_state,
        team_status=data.team_status,
        deadlines=data.deadlines,
        expected_actions=data.expected_actions,
        ground_truth=data.ground_truth,
        tags=data.tags,
        case_version=data.case_version,
    )
    return case


@router.get("/suites/{suite_id}/cases", response_model=list[BenchmarkCaseResponse])
async def list_benchmark_cases(suite_id: uuid.UUID, user: CurrentUser, session: DBSession):
    service = BenchmarkService(session)
    suite = await service.get_suite(str(suite_id))
    if not suite:
        raise HTTPException(status_code=404, detail="Benchmark suite not found")
    return await service.list_cases(str(suite_id))


@router.post("/agent-versions", response_model=AgentVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_version(data: AgentVersionCreate, user: CurrentUser, session: DBSession):
    service = AgentService(session)
    agent_version = await service.create_agent_version(
        data.name,
        data.version,
        data.callable_path,
        data.branch,
        data.description,
        data.metadata,
        data.status,
    )
    return agent_version


@router.get("/agent-versions", response_model=list[AgentVersionResponse])
async def list_agent_versions(user: CurrentUser, session: DBSession):
    service = AgentService(session)
    return await service.list_agent_versions()


@router.get("/agent-versions/{agent_version_id}", response_model=AgentVersionResponse)
async def get_agent_version(agent_version_id: uuid.UUID, user: CurrentUser, session: DBSession):
    service = AgentService(session)
    agent = await service.get_agent_version(str(agent_version_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent version not found")
    return agent


@router.post("/runs", response_model=EvaluationRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_evaluation_run(data: EvaluationRunCreate, user: CurrentUser, session: DBSession):
    benchmark_service = BenchmarkService(session)
    agent_service = AgentService(session)
    evaluation_service = EvaluationService(session)

    suite = await benchmark_service.get_suite(str(data.suite_id))
    if not suite:
        raise HTTPException(status_code=404, detail="Benchmark suite not found")

    agent_version = await agent_service.get_agent_version(str(data.agent_version_id))
    if not agent_version:
        raise HTTPException(status_code=404, detail="Agent version not found")

    run = await evaluation_service.create_evaluation_run(str(data.suite_id), str(data.agent_version_id), data.trigger)

    from workers.tasks import run_evaluation_suite_task

    run_evaluation_suite_task.delay(
        suite_id=str(data.suite_id),
        agent_version_id=str(data.agent_version_id),
        evaluation_run_id=str(run.id),
        trigger=data.trigger,
    )
    return run


@router.get("/runs/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation_run(run_id: uuid.UUID, user: CurrentUser, session: DBSession):
    service = EvaluationService(session)
    run = await service.evaluation_repo.get_run(str(run_id))
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return run


@router.get("/runs/{run_id}/cases", response_model=list[CaseExecutionResponse])
async def get_run_cases(run_id: uuid.UUID, user: CurrentUser, session: DBSession):
    service = EvaluationService(session)
    run = await service.evaluation_repo.get_run(str(run_id))
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return await service.evaluation_repo.list_run_cases(str(run_id))


@router.get("/alerts/{run_id}", response_model=list[RegressionAlertResponse])
async def get_regression_alerts(run_id: uuid.UUID, user: CurrentUser, session: DBSession):
    result = await session.execute(
        select(RegressionAlert).where(RegressionAlert.evaluation_run_id == str(run_id)).order_by(RegressionAlert.created_at.desc())
    )
    return result.scalars().all()
