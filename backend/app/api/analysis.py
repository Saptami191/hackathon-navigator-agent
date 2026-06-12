import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from core.auth import CurrentUser, DBSession
from db.models import AgentRun, AgentRunStatus, AnalysisSnapshot, Project

router = APIRouter(prefix="/analysis", tags=["analysis"])


class TriggerAnalysisRequest(BaseModel):
    project_id: uuid.UUID
    force_refresh: bool = False


class AgentRunResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    agent_type: str
    status: str
    trigger: str | None
    output_data: dict[str, Any] | None
    error_message: str | None
    duration_seconds: float | None
    tokens_used: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisSnapshotResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    architecture_summary: str | None
    tech_stack_detected: list[str] | None
    open_issues_count: int | None
    open_prs_count: int | None
    completion_percentage: float | None
    risk_level: str | None
    estimated_hours_remaining: float | None
    recommendations: list[str] | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/trigger", response_model=AgentRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(
    data: TriggerAnalysisRequest,
    user: CurrentUser,
    session: DBSession,
    background_tasks: BackgroundTasks,
):
    """Trigger a full multi-agent analysis for a project."""
    result = await session.execute(
        select(Project).where(Project.id == data.project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Create agent run record
    agent_run = AgentRun(
        project_id=project.id,
        agent_type="supervisor",
        status=AgentRunStatus.QUEUED,
        trigger="manual",
        input_data={
            "github_repo_url": project.github_repo_url,
            "hackathon_theme": project.hackathon_theme,
            "project_goals": project.project_goals,
            "judging_criteria": project.judging_criteria,
        },
    )
    session.add(agent_run)
    await session.commit()
    await session.refresh(agent_run)

    # Queue Celery task
    from workers.tasks import run_full_analysis_task
    run_full_analysis_task.delay(
        project_id=str(project.id),
        project_name=project.name,
        github_repo_url=project.github_repo_url,
        hackathon_theme=project.hackathon_theme,
        submission_deadline=project.submission_deadline.isoformat() if project.submission_deadline else None,
        judging_criteria=project.judging_criteria,
        project_goals=project.project_goals,
        agent_run_id=str(agent_run.id),
    )

    return agent_run


@router.get("/runs/{project_id}", response_model=list[AgentRunResponse])
async def get_agent_runs(project_id: uuid.UUID, user: CurrentUser, session: DBSession):
    """Get all agent run history for a project."""
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    runs_result = await session.execute(
        select(AgentRun)
        .where(AgentRun.project_id == project_id)
        .order_by(AgentRun.created_at.desc())
        .limit(20)
    )
    return runs_result.scalars().all()


@router.get("/runs/status/{run_id}", response_model=AgentRunResponse)
async def get_run_status(run_id: uuid.UUID, user: CurrentUser, session: DBSession):
    """Poll the status of a specific agent run."""
    result = await session.execute(select(AgentRun).where(AgentRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


@router.get("/snapshots/{project_id}", response_model=list[AnalysisSnapshotResponse])
async def get_snapshots(project_id: uuid.UUID, user: CurrentUser, session: DBSession):
    """Get all analysis snapshots for a project."""
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    snapshots = await session.execute(
        select(AnalysisSnapshot)
        .where(AnalysisSnapshot.project_id == project_id)
        .order_by(AnalysisSnapshot.created_at.desc())
        .limit(10)
    )
    return snapshots.scalars().all()


@router.get("/latest/{project_id}", response_model=AnalysisSnapshotResponse)
async def get_latest_snapshot(project_id: uuid.UUID, user: CurrentUser, session: DBSession):
    """Get the most recent analysis snapshot."""
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    snapshot = await session.execute(
        select(AnalysisSnapshot)
        .where(AnalysisSnapshot.project_id == project_id)
        .order_by(AnalysisSnapshot.created_at.desc())
        .limit(1)
    )
    snap = snapshot.scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=404, detail="No analysis available yet")
    return snap
    