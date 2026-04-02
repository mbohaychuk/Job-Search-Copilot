"""Job posting API endpoints."""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from jsc.dependencies import get_job_service
from jsc.schemas.common import Paginated
from jsc.schemas.job import (
    CollectRequest,
    CollectionResult,
    JobFilter,
    JobPostingDetailRead,
    JobPostingRead,
    JobSourceCreate,
    JobSourceRead,
)
from jsc.services.job_service import JobService

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("/collect", response_model=CollectionResult)
async def collect_jobs(
    request: CollectRequest | None = None,
    service: JobService = Depends(get_job_service),
) -> CollectionResult:
    """Trigger job collection from configured sources."""
    source_ids = request.source_ids if request else None
    return await service.trigger_collection(source_ids)


@router.get("", response_model=Paginated[JobPostingRead])
async def list_jobs(
    location: str | None = Query(None),
    remote_type: str | None = Query(None),
    seniority: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: JobService = Depends(get_job_service),
) -> Paginated[JobPostingRead]:
    """List job postings with optional filtering and pagination."""
    filters = JobFilter(
        location=location,
        remote_type=remote_type,
        seniority=seniority,
        search=search,
    )
    jobs, total = await service.list_jobs(filters, page, page_size)
    return Paginated(
        items=[JobPostingRead.model_validate(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/sources", response_model=list[JobSourceRead])
async def list_sources(
    service: JobService = Depends(get_job_service),
) -> list[JobSourceRead]:
    """List configured job sources."""
    sources = await service.list_sources()
    return [JobSourceRead.model_validate(s) for s in sources]


@router.post("/sources", response_model=JobSourceRead, status_code=201)
async def create_source(
    body: JobSourceCreate,
    service: JobService = Depends(get_job_service),
) -> JobSourceRead:
    """Add a new job source."""
    source = await service.create_source(
        name=body.name,
        adapter_type=body.adapter_type,
        base_url=body.base_url,
        config=body.config,
        is_active=body.is_active,
    )
    return JobSourceRead.model_validate(source)


@router.get("/{job_id}", response_model=JobPostingDetailRead)
async def get_job(
    job_id: UUID,
    service: JobService = Depends(get_job_service),
) -> JobPostingDetailRead:
    """Get a single job posting with full details."""
    job = await service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobPostingDetailRead.model_validate(job)
