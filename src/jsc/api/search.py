"""Ephemeral job search endpoint."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from jsc.dependencies import get_search_service, get_settings, verify_api_key
from jsc.config import Settings
from jsc.schemas.search import SearchResponse
from jsc.search.base import SearchQuery
from jsc.search.registry import get_provider
from jsc.search.service import SearchService

router = APIRouter(
    prefix="/api/v1/search",
    tags=["search"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("", response_model=SearchResponse)
async def search_jobs(
    q: str = Query(..., min_length=1, description="Search keywords"),
    candidate_id: UUID = Query(..., description="Candidate profile ID"),
    location: str | None = Query(None, description="City or region"),
    country: str = Query("ca", description="Two-letter country code"),
    remote_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    service: SearchService = Depends(get_search_service),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    """Search for jobs across external aggregator APIs.

    Results are ranked against the candidate's profile and returned
    without being persisted to the database.
    """
    query = SearchQuery(
        keywords=q,
        location=location,
        country=country,
        remote_only=remote_only,
        page=page,
        page_size=page_size,
    )

    provider = get_provider("adzuna", settings)

    try:
        return await service.search(query, candidate_id, provider=provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
