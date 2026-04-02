"""Job-related ORM models."""

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jsc.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class JobSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "job_source"
    __table_args__ = (UniqueConstraint("base_url"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_crawled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    postings: Mapped[list["JobPosting"]] = relationship(back_populates="source")
    raw_postings: Mapped[list["JobPostingRaw"]] = relationship(back_populates="source")


class JobPosting(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "job_posting"

    source_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("job_source.id"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    is_remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remote_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_text: Mapped[str] = mapped_column(Text, nullable=False)
    description_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dedup_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Relationships
    source: Mapped["JobSource"] = relationship(back_populates="postings")
    skills: Mapped[list["JobSkill"]] = relationship(
        back_populates="job_posting", cascade="all, delete-orphan"
    )
    raw: Mapped["JobPostingRaw | None"] = relationship(back_populates="job_posting", uselist=False)
    matches: Mapped[list["MatchResult"]] = relationship(  # noqa: F821
        back_populates="job_posting", cascade="all, delete-orphan"
    )


class JobPostingRaw(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "job_posting_raw"

    job_posting_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("job_posting.id"), nullable=True
    )
    source_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("job_source.id"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    http_status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job_posting: Mapped["JobPosting | None"] = relationship(back_populates="raw")
    source: Mapped["JobSource"] = relationship(back_populates="raw_postings")


class JobSkill(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "job_skill"
    __table_args__ = (UniqueConstraint("job_posting_id", "skill_name"),)

    job_posting_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("job_posting.id", ondelete="CASCADE"), nullable=False
    )
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="extracted")

    job_posting: Mapped["JobPosting"] = relationship(back_populates="skills")
