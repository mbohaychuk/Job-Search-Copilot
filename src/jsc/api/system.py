"""System endpoints: health and readiness checks."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from jsc.dependencies import get_db_session
from jsc.schemas.common import HealthCheck, ReadinessCheck

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthCheck)
async def health() -> HealthCheck:
    return HealthCheck(status="ok")


@router.get("/ready", response_model=ReadinessCheck)
async def ready(session: AsyncSession = Depends(get_db_session)) -> ReadinessCheck:
    try:
        await session.execute(text("SELECT 1"))
        return ReadinessCheck(status="ready", db=True)
    except Exception:
        return ReadinessCheck(status="degraded", db=False)
