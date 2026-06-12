import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select

from core.auth import CurrentUser, DBSession
from db.models import Project

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    github_repo_url: str | None = None
    hackathon_theme: str | None = None
    submission_deadline: datetime | None = None
    judging_criteria: list[str] = []
    project_goals: list[str] = []
    devpost_url: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    github_repo_url: str | None = None
    hackathon_theme: str | None = None
    submission_deadline: datetime | None = None
    judging_criteria: list[str] | None = None
    project_goals: list[str] | None = None
    devpost_url: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    github_repo_url: str | None
    hackathon_theme: str | None
    submission_deadline: datetime | None
    judging_criteria: list[str]
    project_goals: list[str]
    tech_stack: list[str]
    devpost_url: str | None
    is_active: bool
    last_analyzed_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(user: CurrentUser, session: DBSession):
    result = await session.execute(
        select(Project).where(Project.owner_id == user.id, Project.is_active == True)
        .order_by(Project.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, user: CurrentUser, session: DBSession):
    project = Project(
        owner_id=user.id,
        name=data.name,
        description=data.description,
        github_repo_url=data.github_repo_url,
        hackathon_theme=data.hackathon_theme,
        submission_deadline=data.submission_deadline,
        judging_criteria=data.judging_criteria,
        project_goals=data.project_goals,
        devpost_url=data.devpost_url,
        tech_stack=[],
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, user: CurrentUser, session: DBSession):
    project = await _get_user_project(project_id, user.id, session)
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID, data: ProjectUpdate, user: CurrentUser, session: DBSession
):
    project = await _get_user_project(project_id, user.id, session)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await session.commit()
    await session.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: uuid.UUID, user: CurrentUser, session: DBSession):
    project = await _get_user_project(project_id, user.id, session)
    project.is_active = False
    await session.commit()


async def _get_user_project(project_id: uuid.UUID, user_id: uuid.UUID, session) -> Project:
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project
    