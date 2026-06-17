import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.config import settings


engine = create_async_engine(
    str(settings.database_url),
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=settings.debug,
)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DatasetStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class EvaluationStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentVersionStatus(str, Enum):
    ACTIVE = "active"
    EXPERIMENTAL = "experimental"
    RETIRED = "retired"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clerk_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    github_token: Mapped[str | None] = mapped_column(Text)

    projects: Mapped[list["Project"]] = relationship("Project", back_populates="owner")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    github_repo_url: Mapped[str | None] = mapped_column(Text)
    github_repo_name: Mapped[str | None] = mapped_column(String(255))
    hackathon_theme: Mapped[str | None] = mapped_column(Text)
    submission_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    judging_criteria: Mapped[list[str] | None] = mapped_column(JSON)
    project_goals: Mapped[list[str] | None] = mapped_column(JSON)
    tech_stack: Mapped[list[str] | None] = mapped_column(JSON)
    devpost_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped["User"] = relationship("User", back_populates="projects")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship("AgentRun", back_populates="project", cascade="all, delete-orphan")
    pitches: Mapped[list["Pitch"]] = relationship("Pitch", back_populates="project", cascade="all, delete-orphan")
    analysis_snapshots: Mapped[list["AnalysisSnapshot"]] = relationship("AnalysisSnapshot", back_populates="project", cascade="all, delete-orphan")


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(String(50), default=TaskStatus.PENDING)
    priority: Mapped[TaskPriority] = mapped_column(String(50), default=TaskPriority.MEDIUM)
    estimated_hours: Mapped[float | None] = mapped_column(Float)
    is_blocker: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    github_issue_url: Mapped[str | None] = mapped_column(Text)
    impact_score: Mapped[float | None] = mapped_column(Float)
    category: Mapped[str | None] = mapped_column(String(100))
    assignee: Mapped[str | None] = mapped_column(String(255))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    project: Mapped["Project"] = relationship("Project", back_populates="tasks")


class AgentRun(TimestampMixin, Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[AgentRunStatus] = mapped_column(String(50), default=AgentRunStatus.QUEUED)
    trigger: Mapped[str | None] = mapped_column(String(100))
    input_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))

    project: Mapped["Project"] = relationship("Project", back_populates="agent_runs")


class Pitch(TimestampMixin, Base):
    __tablename__ = "pitches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    pitch_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    project: Mapped["Project"] = relationship("Project", back_populates="pitches")


class AnalysisSnapshot(TimestampMixin, Base):
    __tablename__ = "analysis_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String(40))
    repo_structure: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    architecture_summary: Mapped[str | None] = mapped_column(Text)
    tech_stack_detected: Mapped[list[str] | None] = mapped_column(JSON)
    open_issues_count: Mapped[int | None] = mapped_column(Integer)
    open_prs_count: Mapped[int | None] = mapped_column(Integer)
    contributor_activity: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    completion_percentage: Mapped[float | None] = mapped_column(Float)
    risk_level: Mapped[str | None] = mapped_column(String(50))
    estimated_hours_remaining: Mapped[float | None] = mapped_column(Float)
    recommendations: Mapped[list[str] | None] = mapped_column(JSON)
    raw_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    project: Mapped["Project"] = relationship("Project", back_populates="analysis_snapshots")


class BenchmarkSuite(TimestampMixin, Base):
    __tablename__ = "benchmark_suites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")
    tags: Mapped[list[str] | None] = mapped_column(JSON)
    metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[DatasetStatus] = mapped_column(String(50), default=DatasetStatus.ACTIVE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    benchmark_cases: Mapped[list["BenchmarkCase"]] = relationship(
        "BenchmarkCase", back_populates="suite", cascade="all, delete-orphan"
    )
    evaluation_runs: Mapped[list["EvaluationRun"]] = relationship(
        "EvaluationRun", back_populates="suite", cascade="all, delete-orphan"
    )


class BenchmarkCase(TimestampMixin, Base):
    __tablename__ = "benchmark_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suite_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("benchmark_suites.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    repository_state: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    team_status: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    deadlines: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    expected_actions: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ground_truth: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    tags: Mapped[list[str] | None] = mapped_column(JSON)
    case_version: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    suite: Mapped["BenchmarkSuite"] = relationship("BenchmarkSuite", back_populates="benchmark_cases")
    executions: Mapped[list["CaseExecution"]] = relationship(
        "CaseExecution", back_populates="benchmark_case", cascade="all, delete-orphan"
    )


class AgentVersion(TimestampMixin, Base):
    __tablename__ = "agent_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    branch: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    callable_path: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[AgentVersionStatus] = mapped_column(String(50), default=AgentVersionStatus.ACTIVE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    evaluation_runs: Mapped[list["EvaluationRun"]] = relationship(
        "EvaluationRun", back_populates="agent_version", cascade="all, delete-orphan"
    )


class EvaluationRun(TimestampMixin, Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suite_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("benchmark_suites.id"), nullable=False)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_versions.id"), nullable=False)
    trigger: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[EvaluationStatus] = mapped_column(String(50), default=EvaluationStatus.QUEUED)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_cases: Mapped[int | None] = mapped_column(Integer)
    completed_cases: Mapped[int | None] = mapped_column(Integer)
    accuracy: Mapped[float | None] = mapped_column(Float)
    average_latency_ms: Mapped[float | None] = mapped_column(Float)
    token_usage_total: Mapped[int | None] = mapped_column(Integer)
    average_cost_usd: Mapped[float | None] = mapped_column(Float)
    completion_rate: Mapped[float | None] = mapped_column(Float)
    tool_success_rate: Mapped[float | None] = mapped_column(Float)
    metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    suite: Mapped["BenchmarkSuite"] = relationship("BenchmarkSuite", back_populates="evaluation_runs")
    agent_version: Mapped["AgentVersion"] = relationship("AgentVersion", back_populates="evaluation_runs")
    case_executions: Mapped[list["CaseExecution"]] = relationship(
        "CaseExecution", back_populates="evaluation_run", cascade="all, delete-orphan"
    )
    regression_alerts: Mapped[list["RegressionAlert"]] = relationship(
        "RegressionAlert", back_populates="evaluation_run", cascade="all, delete-orphan"
    )


class CaseExecution(TimestampMixin, Base):
    __tablename__ = "case_executions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluation_runs.id"), nullable=False)
    benchmark_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("benchmark_cases.id"), nullable=False)
    status: Mapped[EvaluationStatus] = mapped_column(String(50), default=EvaluationStatus.QUEUED)
    input_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    output_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    latency_seconds: Mapped[float | None] = mapped_column(Float)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    evaluation_run: Mapped["EvaluationRun"] = relationship("EvaluationRun", back_populates="case_executions")
    benchmark_case: Mapped["BenchmarkCase"] = relationship("BenchmarkCase", back_populates="executions")
    traces: Mapped[list["ExecutionTrace"]] = relationship(
        "ExecutionTrace", back_populates="case_execution", cascade="all, delete-orphan"
    )


class ExecutionTrace(TimestampMixin, Base):
    __tablename__ = "execution_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("case_executions.id"), nullable=False)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text)
    retrieved_context: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    intermediate_reasoning: Mapped[str | None] = mapped_column(Text)
    model_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    output: Mapped[str | None] = mapped_column(Text)

    case_execution: Mapped["CaseExecution"] = relationship("CaseExecution", back_populates="traces")


class RegressionAlert(TimestampMixin, Base):
    __tablename__ = "regression_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluation_runs.id"), nullable=False)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_versions.id"), nullable=False)
    benchmark_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("benchmark_cases.id"), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    indicators: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    evaluation_run: Mapped["EvaluationRun"] = relationship("EvaluationRun", back_populates="regression_alerts")
    agent_version: Mapped["AgentVersion"] = relationship("AgentVersion")
    benchmark_case: Mapped["BenchmarkCase"] = relationship("BenchmarkCase")


async def get_session() -> AsyncSession:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
