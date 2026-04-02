"""Match/ranking API endpoints."""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from jsc.dependencies import get_match_service
from jsc.schemas.common import Paginated
from jsc.schemas.match import MatchDetailRead, MatchExplanation, MatchResultRead, RankingSummary
from jsc.services.match_service import MatchService

router = APIRouter(prefix="/api/v1/matches", tags=["matches"])


def _grade_from_score(score: float) -> str:
    if score >= 0.90:
        return "A+"
    elif score >= 0.80:
        return "A"
    elif score >= 0.70:
        return "B+"
    elif score >= 0.60:
        return "B"
    elif score >= 0.50:
        return "C"
    elif score >= 0.35:
        return "D"
    return "F"


@router.post("/{candidate_id}/rank", response_model=RankingSummary)
async def rank_jobs(
    candidate_id: UUID,
    service: MatchService = Depends(get_match_service),
) -> RankingSummary:
    """Trigger ranking of all active jobs for a candidate."""
    try:
        return await service.rank_jobs(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{candidate_id}", response_model=Paginated[MatchResultRead])
async def list_matches(
    candidate_id: UUID,
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: MatchService = Depends(get_match_service),
) -> Paginated[MatchResultRead]:
    """Get ranked match results for a candidate."""
    matches, total = await service.get_ranked_matches(
        candidate_id, min_score, page, page_size
    )
    items = []
    for m in matches:
        explanation = m.explanation or {}
        items.append(
            MatchResultRead(
                id=m.id,
                job=m.job_posting,
                overall_score=m.overall_score,
                grade=_grade_from_score(m.overall_score),
                semantic_score=m.semantic_score,
                skill_coverage_score=m.skill_coverage_score,
                title_match_score=m.title_match_score,
                seniority_score=m.seniority_score,
                location_score=m.location_score,
                summary=explanation.get("summary", ""),
            )
        )
    return Paginated(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{candidate_id}/jobs/{job_id}", response_model=MatchDetailRead)
async def get_match_detail(
    candidate_id: UUID,
    job_id: UUID,
    service: MatchService = Depends(get_match_service),
) -> MatchDetailRead:
    """Get detailed match result with full explanation."""
    match = await service.get_match_detail(candidate_id, job_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")

    explanation_data = match.explanation or {}
    explanation = MatchExplanation.model_validate(explanation_data)

    return MatchDetailRead(
        id=match.id,
        job=match.job_posting,
        overall_score=match.overall_score,
        grade=explanation.grade,
        semantic_score=match.semantic_score,
        skill_coverage_score=match.skill_coverage_score,
        title_match_score=match.title_match_score,
        seniority_score=match.seniority_score,
        location_score=match.location_score,
        summary=explanation.summary,
        explanation=explanation,
    )
