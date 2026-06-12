import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from core.auth import CurrentUser, DBSession
from db.models import Pitch, Project

router = APIRouter(prefix="/pitches", tags=["pitches"])


class GeneratePitchRequest(BaseModel):
    project_id: uuid.UUID
    pitch_type: str  # devpost, elevator, demo_script, architecture


class PitchResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    pitch_type: str
    content: str
    version: int
    is_latest: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/{project_id}", response_model=list[PitchResponse])
async def get_pitches(project_id: uuid.UUID, user: CurrentUser, session: DBSession):
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    pitches = await session.execute(
        select(Pitch)
        .where(Pitch.project_id == project_id, Pitch.is_latest == True)
        .order_by(Pitch.created_at.desc())
    )
    return pitches.scalars().all()


@router.post("/generate", response_model=dict)
async def generate_pitch(data: GeneratePitchRequest, user: CurrentUser, session: DBSession):
    result = await session.execute(
        select(Project).where(Project.id == data.project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    from workers.tasks import generate_pitch_task
    task = generate_pitch_task.delay(
        project_id=str(data.project_id),
        pitch_type=data.pitch_type,
    )
    return {"task_id": task.id, "status": "queued", "pitch_type": data.pitch_type}
    