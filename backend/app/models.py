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

from core.config import settings

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


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clerk_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    github_token: Mapped[str | None] = mapped_column(Text)  # encrypted

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
    impact_score: Mapped[float | None] = mapped_column(Float)  # 0-10
    category: Mapped[str | None] = mapped_column(String(100))  # feature, bug, tech_debt, missing
    assignee: Mapped[str | None] = mapped_column(String(255))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    project: Mapped["Project"] = relationship("Project", back_populates="tasks")


class AgentRun(TimestampMixin, Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)  # supervisor, repo_analyst, etc.
    status: Mapped[AgentRunStatus] = mapped_column(String(50), default=AgentRunStatus.QUEUED)
    trigger: Mapped[str | None] = mapped_column(String(100))  # manual, scheduled, webhook
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
    pitch_type: Mapped[str] = mapped_column(String(100), nullable=False)  # devpost, elevator, demo_script, architecture
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


async def get_session() -> AsyncSession:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        