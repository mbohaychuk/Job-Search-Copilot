"""Match result ORM model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jsc.db.base import Base, UUIDPrimaryKeyMixin


class MatchResult(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "match_result"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_posting_id"),
        Index("ix_match_result_candidate_score", "candidate_id", "overall_score"),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False
    )
    job_posting_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("job_posting.id", ondelete="CASCADE"), nullable=False
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    semantic_score: Mapped[float] = mapped_column(Float, nullable=False)
    skill_coverage_score: Mapped[float] = mapped_column(Float, nullable=False)
    title_match_score: Mapped[float] = mapped_column(Float, nullable=False)
    seniority_score: Mapped[float] = mapped_column(Float, nullable=False)
    location_score: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    candidate: Mapped["Candidate"] = relationship(back_populates="matches")  # noqa: F821
    job_posting: Mapped["JobPosting"] = relationship(back_populates="matches")  # noqa: F821
