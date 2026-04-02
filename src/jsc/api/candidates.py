"""Candidate API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from jsc.db.models.candidate import Candidate
from jsc.dependencies import get_db_session, get_resume_service
from jsc.schemas.candidate import CandidateRead, CandidateUpdate, ResumeUploadResponse
from jsc.services.resume_service import ResumeService

router = APIRouter(prefix="/api/v1/candidates", tags=["candidates"])


@router.post("/upload-resume", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    candidate_id: UUID | None = Query(None),
    service: ResumeService = Depends(get_resume_service),
) -> ResumeUploadResponse:
    """Upload a resume PDF or DOCX to create or update a candidate profile."""
    if file.content_type not in (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        candidate = await service.ingest_resume(
            file_bytes=file_bytes,
            filename=file.filename or "resume",
            content_type=file.content_type,
            candidate_id=candidate_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return ResumeUploadResponse(
        candidate=CandidateRead.model_validate(candidate),
        message="Resume processed successfully",
    )


@router.get("/{candidate_id}", response_model=CandidateRead)
async def get_candidate(
    candidate_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateRead:
    """Get a candidate profile."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Candidate)
        .options(selectinload(Candidate.skills), selectinload(Candidate.roles))
        .where(Candidate.id == candidate_id)
    )
    result = await session.execute(stmt)
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return CandidateRead.model_validate(candidate)


@router.put("/{candidate_id}", response_model=CandidateRead)
async def update_candidate(
    candidate_id: UUID,
    update: CandidateUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateRead:
    """Update candidate preferences."""
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if update.name is not None:
        candidate.name = update.name
    if update.preferred_locations is not None:
        candidate.preferred_locations = update.preferred_locations
    if update.preferred_seniority is not None:
        candidate.preferred_seniority = update.preferred_seniority

    await session.commit()
    await session.refresh(candidate, ["skills", "roles"])
    return CandidateRead.model_validate(candidate)
