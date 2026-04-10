"""Root router — includes all sub-routers."""

from fastapi import APIRouter

from jsc.api.candidates import router as candidates_router
from jsc.api.jobs import router as jobs_router
from jsc.api.matches import router as matches_router
from jsc.api.search import router as search_router
from jsc.api.system import router as system_router

root_router = APIRouter()
root_router.include_router(system_router)
root_router.include_router(candidates_router)
root_router.include_router(jobs_router)
root_router.include_router(matches_router)
root_router.include_router(search_router)
