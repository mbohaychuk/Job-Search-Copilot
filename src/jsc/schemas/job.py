"""Job posting request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class JobSkillRead(BaseModel):
    skill_name: str
    is_required: bool

    model_config = {"from_attributes": True}


class JobSourceRead(BaseModel):
    id: UUID
    name: str
    adapter_type: str
    base_url: str
    is_active: bool
    last_crawled_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobSourceCreate(BaseModel):
    name: str
    adapter_type: str
    base_url: str
    config: dict = {}
    is_active: bool = True


class JobPostingRead(BaseModel):
    id: UUID
    title: str
    company: str
    location: str
    is_remote: bool
    remote_type: str | None = None
    seniority: str | None = None
    posted_at: datetime | None = None
    url: str
    skills: list[JobSkillRead] = []

    model_config = {"from_attributes": True}


class JobPostingDetailRead(JobPostingRead):
    description_html: str | None = None
    description_text: str
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    source: JobSourceRead

    model_config = {"from_attributes": True}


class JobFilter(BaseModel):
    location: str | None = None
    remote_type: str | None = None
    seniority: str | None = None
    search: str | None = None
    is_active: bool = True


class CollectRequest(BaseModel):
    source_ids: list[UUID] | None = None


class CollectionResult(BaseModel):
    jobs_found: int
    jobs_new: int
    jobs_duplicate: int
    sources_crawled: int
