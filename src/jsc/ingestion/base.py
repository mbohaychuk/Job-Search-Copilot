"""Source adapter protocol and shared data types."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from jsc.db.models.job import JobPostingRaw, JobSource


@dataclass
class DiscoveredJob:
    """A job listing discovered during source crawling."""

    url: str
    external_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedJob:
    """Structured job data extracted from raw content."""

    title: str
    company: str | None = None
    location: str | None = None
    description_html: str | None = None
    description_text: str | None = None
    posted_at: datetime | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    remote_type: str | None = None
    seniority: str | None = None
    department: str | None = None
    skills: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SourceAdapter(Protocol):
    """Protocol for job source adapters.

    Each adapter knows how to discover job listings from a specific
    source type and parse raw content into structured data.
    """

    adapter_type: str

    async def discover(
        self, source: JobSource, fetcher: "Fetcher"  # noqa: F821
    ) -> list[DiscoveredJob]:
        """Discover job listing URLs/IDs from the source."""
        ...

    async def parse(self, raw: JobPostingRaw, source: JobSource) -> ParsedJob:
        """Parse raw fetched content into structured job data."""
        ...
