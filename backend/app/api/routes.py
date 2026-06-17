from fastapi import APIRouter

from .analysis import router as analysis_router
from .github import router as github_router
from .health import router as health_router
from .projects import router as projects_router
from .pitches import router as pitches_router
from .tasks import router as tasks_router
from .evaluation import router as evaluation_router

router = APIRouter()
router.include_router(health_router, prefix="/health")
router.include_router(projects_router, prefix="/projects")
router.include_router(analysis_router, prefix="/analysis")
router.include_router(tasks_router, prefix="/tasks")
router.include_router(pitches_router, prefix="/pitches")
router.include_router(github_router, prefix="/github")
router.include_router(evaluation_router, prefix="/evaluations")
