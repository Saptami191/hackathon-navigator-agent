import hashlib
import hmac
import json
import uuid

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from core.auth import CurrentUser, DBSession
from core.config import settings
from db.models import Project
from services.github_service import GitHubService

router = APIRouter(prefix="/github", tags=["github"])


class RepoInfoResponse(BaseModel):
    name: str
    full_name: str
    description: str | None
    languages: dict
    stars: int
    open_issues_count: int
    commit_frequency: float
    contributors: list[dict]
    inactive_contributors: list[str]
    last_commit_at: str | None


@router.get("/repo-info/{project_id}", response_model=RepoInfoResponse)
async def get_repo_info(project_id: uuid.UUID, user: CurrentUser, session: DBSession):
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project or not project.github_repo_url:
        raise HTTPException(status_code=404, detail="Project or repo not found")

    async with GitHubService(token=user.github_token or settings.github_token) as gh:
        analysis = await gh.analyze_repository(project.github_repo_url)

    return RepoInfoResponse(
        name=analysis.name,
        full_name=analysis.full_name,
        description=analysis.description,
        languages=analysis.languages,
        stars=analysis.stars,
        open_issues_count=analysis.open_issues_count,
        commit_frequency=analysis.commit_frequency,
        contributors=analysis.contributors,
        inactive_contributors=analysis.inactive_contributors,
        last_commit_at=analysis.last_commit_at.isoformat() if analysis.last_commit_at else None,
    )


@router.post("/webhook")
async def github_webhook(request: Request):
    """Handle GitHub webhook events for push/PR/issue triggers."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    # Verify webhook signature
    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    event_type = request.headers.get("X-GitHub-Event", "")
    payload = json.loads(body)
    repo_url = payload.get("repository", {}).get("html_url", "")

    if event_type in ("push", "pull_request", "issues") and repo_url:
        from workers.tasks import run_full_analysis_task
        # TODO: Look up project by repo URL and trigger analysis
        # For now, log the event
        pass

    return {"status": "received", "event": event_type}
    