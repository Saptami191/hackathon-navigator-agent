import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from db.models import engine, Base

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Hackathon Navigator API")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()
    logger.info("API shutdown complete")


app = FastAPI(
    title="Hackathon Navigator API",
    description="AI-powered hackathon teammate",
    version="1.0.0",
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.time()
    request_id = str(uuid.uuid4())[:8]
    logger.info("Request", method=request.method, path=request.url.path, id=request_id)
    response = await call_next(request)
    duration = time.time() - start
    logger.info("Response", status=response.status_code, duration=f"{duration:.3f}s", id=request_id)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", exc=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


# ─── Include routers ──────────────────────────────────────────────────────────

from api.routes import projects, analysis, tasks, pitches, github, health

app.include_router(health.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(pitches.router, prefix="/api/v1")
app.include_router(github.router, prefix="/api/v1")
