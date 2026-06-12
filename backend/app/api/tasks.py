"""Tasks route"""
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update

from core.auth import CurrentUser, DBSession
from db.models import Project, Task, TaskPriority, TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskUpdate(BaseModel):
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee: str | None = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    status: str
    priority: str
    estimated_hours: float | None
    is_blocker: bool
    is_ai_generated: bool
    impact_score: float | None
    category: str | None
    assignee: str | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/{project_id}", response_model=list[TaskResponse])
async def get_project_tasks(
    project_id: uuid.UUID,
    user: CurrentUser,
    session: DBSession,
    status_filter: TaskStatus | None = None,
    priority_filter: TaskPriority | None = None,
):
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    query = select(Task).where(Task.project_id == project_id)
    if status_filter:
        query = query.where(Task.status == status_filter)
    if priority_filter:
        query = query.where(Task.priority == priority_filter)
    query = query.order_by(Task.impact_score.desc().nullslast(), Task.created_at.desc())

    tasks = await session.execute(query)
    return tasks.scalars().all()


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: uuid.UUID, data: TaskUpdate, user: CurrentUser, session: DBSession):
    result = await session.execute(
        select(Task).where(Task.id == task_id).join(Project).where(Project.owner_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(task, field, value)

    if data.status == TaskStatus.COMPLETED:
        task.completed_at = datetime.utcnow()

    await session.commit()
    await session.refresh(task)
    return task
    