"""Match result and ranking schemas."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from jsc.schemas.job import JobPostingRead


class ComponentExplanation(BaseModel):
    name: str
    weight: float
    score: float
    weighted_score: float
    details: dict[str, Any]


class MatchExplanation(BaseModel):
    overall_score: float
    grade: str
    summary: str
    components: list[ComponentExplanation]
    strengths: list[str]
    gaps: list[str]


class MatchResultRead(BaseModel):
    id: UUID
    job: JobPostingRead
    overall_score: float
    grade: str
    semantic_score: float
    skill_coverage_score: float
    title_match_score: float
    seniority_score: float
    location_score: float
    summary: str

    model_config = {"from_attributes": True}


class MatchDetailRead(MatchResultRead):
    explanation: MatchExplanation


class RankingSummary(BaseModel):
    total_ranked: int
    top_score: float | None = None
    top_grade: str | None = None
