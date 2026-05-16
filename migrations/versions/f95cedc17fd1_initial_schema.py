"""initial schema

Revision ID: f95cedc17fd1
Revises:
Create Date: 2026-05-16 14:14:49.154070

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "f95cedc17fd1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "candidate",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("years_experience", sa.SmallInteger(), nullable=True),
        sa.Column("preferred_locations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("preferred_seniority", sa.String(length=50), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "job_source",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("adapter_type", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("base_url"),
    )
    op.create_table(
        "candidate_role",
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "candidate_skill",
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("skill_name", sa.String(length=100), nullable=False),
        sa.Column("proficiency", sa.String(length=20), nullable=True),
        sa.Column("years_used", sa.SmallInteger(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "skill_name"),
    )
    op.create_table(
        "job_posting",
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("is_remote", sa.Boolean(), nullable=False),
        sa.Column("remote_type", sa.String(length=20), nullable=True),
        sa.Column("seniority", sa.String(length=50), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=False),
        sa.Column("description_html", sa.Text(), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("dedup_hash", sa.String(length=64), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["job_source.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url_hash"),
    )
    op.create_index(op.f("ix_job_posting_dedup_hash"), "job_posting", ["dedup_hash"], unique=False)
    op.create_table(
        "resume_document",
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "file_hash"),
    )
    op.create_table(
        "job_posting_raw",
        sa.Column("job_posting_id", sa.UUID(), nullable=True),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("http_status", sa.SmallInteger(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_posting.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["job_source.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "job_skill",
        sa.Column("job_posting_id", sa.UUID(), nullable=False),
        sa.Column("skill_name", sa.String(length=100), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_posting.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_posting_id", "skill_name"),
    )
    op.create_table(
        "match_result",
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("job_posting_id", sa.UUID(), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("semantic_score", sa.Float(), nullable=False),
        sa.Column("skill_coverage_score", sa.Float(), nullable=False),
        sa.Column("title_match_score", sa.Float(), nullable=False),
        sa.Column("seniority_score", sa.Float(), nullable=False),
        sa.Column("location_score", sa.Float(), nullable=False),
        sa.Column("explanation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_posting.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "job_posting_id"),
    )
    op.create_index(
        "ix_match_result_candidate_score",
        "match_result",
        ["candidate_id", "overall_score"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_match_result_candidate_score", table_name="match_result")
    op.drop_table("match_result")
    op.drop_table("job_skill")
    op.drop_table("job_posting_raw")
    op.drop_table("resume_document")
    op.drop_index(op.f("ix_job_posting_dedup_hash"), table_name="job_posting")
    op.drop_table("job_posting")
    op.drop_table("candidate_skill")
    op.drop_table("candidate_role")
    op.drop_table("job_source")
    op.drop_table("candidate")
