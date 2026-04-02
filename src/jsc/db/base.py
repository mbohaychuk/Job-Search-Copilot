"""Declarative base with common mixins for all models."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Use uuid_extensions.uuid7 if available, fall back to uuid4
try:
    from uuid_extensions import uuid7 as _generate_uuid
except ImportError:
    _generate_uuid = uuid4


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class TimestampMixin:
    """Adds created_at / updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key (v7 when available, v4 fallback)."""

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=_generate_uuid,
    )
