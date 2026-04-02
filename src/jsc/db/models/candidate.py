"""Candidate-related ORM models."""

from datetime import date, datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jsc.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Candidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "candidate"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    years_experience: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    preferred_locations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    preferred_seniority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)

    # Relationships
    skills: Mapped[list["CandidateSkill"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    roles: Mapped[list["CandidateRole"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    resumes: Mapped[list["ResumeDocument"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    matches: Mapped[list["MatchResult"]] = relationship(  # noqa: F821
        back_populates="candidate", cascade="all, delete-orphan"
    )


class CandidateSkill(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "candidate_skill"
    __table_args__ = (UniqueConstraint("candidate_id", "skill_name"),)

    candidate_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False
    )
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    proficiency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    years_used: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="extracted")

    candidate: Mapped["Candidate"] = relationship(back_populates="skills")


class CandidateRole(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "candidate_role"

    candidate_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="roles")


class ResumeDocument(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "resume_document"
    __table_args__ = (UniqueConstraint("candidate_id", "file_hash"),)

    candidate_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    candidate: Mapped["Candidate"] = relationship(back_populates="resumes")
