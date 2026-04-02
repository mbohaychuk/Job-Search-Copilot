"""Shared schemas: pagination, error responses."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class ErrorResponse(BaseModel):
    detail: str


class HealthCheck(BaseModel):
    status: str


class ReadinessCheck(BaseModel):
    status: str
    db: bool
