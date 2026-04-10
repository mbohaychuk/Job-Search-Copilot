"""Search request/response schemas."""

from datetime import datetime

from pydantic import BaseModel

from jsc.schemas.job import JobSkillRead
from jsc.schemas.match import MatchExplanation


class SearchResultRead(BaseModel):
    """One ephemeral search result with ranking."""

    id: str
    title: str
    company: str
    location: str
    is_remote: bool
    remote_type: str | None = None
    seniority: str | None = None
    posted_at: datetime | None = None
    url: str
    skills: list[JobSkillRead] = []
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    provider: str
    match_score: float
    match_explanation: MatchExplanation


class SearchAttribution(BaseModel):
    """Provider attribution for ToS compliance."""

    text: str
    url: str


class SearchResponse(BaseModel):
    """Paginated search results with attribution."""

    items: list[SearchResultRead]
    total: int
    page: int
    page_size: int
    pages: int
    attribution: SearchAttribution | None = None
