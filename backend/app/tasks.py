
import asyncio
from typing import Any

import structlog
from celery import Celery
from celery.utils.log import get_task_logger

from core.config import settings

logger = get_task_logger(__name__)

celery_app = Celery(
    "hackathon_navigator",
    broker=str(settings.redis_url).replace("/0", f"/{settings.redis_celery_db}"),
    backend=str(settings.redis_url).replace("/0", f"/{settings.redis_celery_db}"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "workers.tasks.run_full_analysis": {"queue": "analysis"},
        "workers.tasks.run_quick_check": {"queue": "quick"},
        "workers.tasks.generate_pitch": {"queue": "pitch"},
        "workers.tasks.ingest_repository": {"queue": "ingest"},
    },
    beat_schedule={
        "scheduled-analysis": {
            "task": "workers.tasks.scheduled_project_check",
            "schedule": 3600.0,  # Every hour
        },
    },
)


def run_async(coro):
    """Helper to run async code in Celery's sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="workers.tasks.run_full_analysis",
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=300,
    time_limit=360,
)
def run_full_analysis_task(
    self,
    project_id: str,
    project_name: str,
    github_repo_url: str | None = None,
    hackathon_theme: str | None = None,
    submission_deadline: str | None = None,
    judging_criteria: list[str] | None = None,
    project_goals: list[str] | None = None,
    agent_run_id: str | None = None,
) -> dict[str, Any]:
    from agents.supervisor import run_analysis
    from db.models import AgentRun, AgentRunStatus
    import uuid

    logger.info(f"Starting full analysis for project {project_id}")

    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
        from core.config import settings

        engine = create_async_engine(str(settings.database_url))
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        if agent_run_id:
            async with async_session() as session:
                run = await session.get(AgentRun, uuid.UUID(agent_run_id))
                if run:
                    run.status = AgentRunStatus.RUNNING
                    run.celery_task_id = self.request.id
                    await session.commit()

        import time
        start = time.time()

        result = await run_analysis(
            project_id=project_id,
            project_name=project_name,
            github_repo_url=github_repo_url,
            hackathon_theme=hackathon_theme,
            submission_deadline=submission_deadline,
            judging_criteria=judging_criteria,
            project_goals=project_goals,
        )

        duration = time.time() - start

        if agent_run_id:
            async with async_session() as session:
                run = await session.get(AgentRun, uuid.UUID(agent_run_id))
                if run:
                    run.status = AgentRunStatus.COMPLETED
                    run.output_data = result
                    run.duration_seconds = duration
                    await session.commit()

        # Store tasks in DB
        async with async_session() as session:
            from db.models import Task, Project, AnalysisSnapshot
            from datetime import datetime, timezone

            # Update project
            project = await session.get(Project, uuid.UUID(project_id))
            if project:
                project.last_analyzed_at = datetime.now(timezone.utc)
                if result.get("tech_stack"):
                    project.tech_stack = result["tech_stack"]

            # Create snapshot
            snapshot = AnalysisSnapshot(
                project_id=uuid.UUID(project_id),
                architecture_summary=result.get("architecture_summary"),
                tech_stack_detected=result.get("tech_stack", []),
                open_issues_count=result.get("repo_analysis", {}).get("open_issues_count"),
                open_prs_count=len(result.get("repo_analysis", {}).get("open_prs", [])),
                completion_percentage=result.get("completion_percentage"),
                risk_level=result.get("risk_level"),
                estimated_hours_remaining=result.get("estimated_hours_remaining"),
                recommendations=result.get("recommendations", []),
                raw_analysis=result,
            )
            session.add(snapshot)

            # Create tasks
            for task_data in result.get("tasks", []):
                from db.models import TaskStatus, TaskPriority
                task = Task(
                    project_id=uuid.UUID(project_id),
                    title=task_data.get("title", ""),
                    description=task_data.get("description"),
                    priority=task_data.get("priority", TaskPriority.MEDIUM),
                    category=task_data.get("category"),
                    estimated_hours=task_data.get("estimated_hours"),
                    is_blocker=task_data.get("is_blocker", False),
                    impact_score=task_data.get("impact_score"),
                    is_ai_generated=True,
                )
                session.add(task)

            await session.commit()

        await engine.dispose()
        return result

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error(f"Analysis task failed: {exc}")
        self.retry(exc=exc)


@celery_app.task(
    name="workers.tasks.generate_pitch",
    soft_time_limit=120,
    time_limit=150,
)
def generate_pitch_task(project_id: str, pitch_type: str) -> dict[str, str]:
    """Generate a specific pitch type for a project."""
    async def _run():
        from agents.supervisor import get_claude
        from langchain_core.messages import HumanMessage
        import uuid
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from db.models import Project, Pitch
        from core.config import settings

        engine = create_async_engine(str(settings.database_url))
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            project = await session.get(Project, uuid.UUID(project_id))
            if not project:
                return {"error": "Project not found"}

            llm = get_claude()
            prompt = f"Generate a {pitch_type} for: {project.name}. Theme: {project.hackathon_theme}. Goals: {project.project_goals}"
            response = await llm.ainvoke([HumanMessage(content=prompt)])

            pitch = Pitch(
                project_id=uuid.UUID(project_id),
                pitch_type=pitch_type,
                content=response.content,
            )
            session.add(pitch)
            await session.commit()

        await engine.dispose()
        return {"content": response.content, "pitch_type": pitch_type}

    return run_async(_run())


@celery_app.task(name="workers.tasks.scheduled_project_check")
def scheduled_project_check():
    """Periodic task to re-analyze active projects near deadline."""
    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy import select
        from db.models import Project
        from core.config import settings
        from datetime import datetime, timezone, timedelta

        engine = create_async_engine(str(settings.database_url))
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            now = datetime.now(timezone.utc)
            soon = now + timedelta(hours=48)
            stmt = select(Project).where(
                Project.is_active == True,
                Project.submission_deadline <= soon,
                Project.submission_deadline >= now,
            )
            result = await session.execute(stmt)
            projects = result.scalars().all()

            for p in projects:
                run_full_analysis_task.delay(
                    project_id=str(p.id),
                    project_name=p.name,
                    github_repo_url=p.github_repo_url,
                    hackathon_theme=p.hackathon_theme,
                    submission_deadline=p.submission_deadline.isoformat() if p.submission_deadline else None,
                    judging_criteria=p.judging_criteria,
                    project_goals=p.project_goals,
                    trigger="scheduled",
                )

        await engine.dispose()

    run_async(_run())
    