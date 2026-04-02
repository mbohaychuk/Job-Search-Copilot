"""Candidate request/response schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class CandidateSkillRead(BaseModel):
    id: UUID
    skill_name: str
    proficiency: str | None = None
    years_used: int | None = None
    source: str

    model_config = {"from_attributes": True}


class CandidateRoleRead(BaseModel):
    id: UUID
    title: str
    company: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None

    model_config = {"from_attributes": True}


class CandidateRead(BaseModel):
    id: UUID
    name: str
    email: str | None = None
    summary: str | None = None
    years_experience: int | None = None
    preferred_locations: list[str]
    preferred_seniority: str | None = None
    skills: list[CandidateSkillRead] = []
    roles: list[CandidateRoleRead] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateUpdate(BaseModel):
    name: str | None = None
    preferred_locations: list[str] | None = None
    preferred_seniority: str | None = None


class ResumeUploadResponse(BaseModel):
    candidate: CandidateRead
    message: str
