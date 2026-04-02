"""FastAPI application factory."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jsc.api.router import root_router
from jsc.config import Settings
from jsc.db.engine import build_engine

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — startup and shutdown."""
    settings = Settings()
    engine, _ = build_engine(settings)
    logger.info("app_started", database=settings.database_url.split("@")[-1])
    yield
    await engine.dispose()
    logger.info("app_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = Settings()

    app = FastAPI(
        title="Job Search Copilot",
        description="Resume-to-Job Match Analyzer API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include all routers
    app.include_router(root_router)

    return app
