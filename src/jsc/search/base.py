"""Search provider protocol and shared data types."""

import hashlib
from dataclasses import dataclass
from typing import Protocol

from jsc.ingestion.base import ParsedJob
from jsc.ingestion.fetcher import Fetcher


@dataclass
class SearchQuery:
    """Parameters for an ephemeral job search."""

    keywords: str
    location: str | None = None
    country: str = "ca"
    remote_only: bool = False
    page: int = 1
    page_size: int = 20

    def cache_key(self) -> str:
        """Deterministic cache key for this query."""
        raw = (
            f"{self.keywords}|{self.location or ''}|{self.country}"
            f"|{self.remote_only}|{self.page}|{self.page_size}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class Attribution:
    """Provider attribution for ToS compliance."""

    text: str
    url: str


@dataclass
class SearchPage:
    """One page of search results from a provider."""

    results: list[ParsedJob]
    total: int
    page: int
    page_size: int
    provider: str
    attribution: Attribution | None = None


class SearchProvider(Protocol):
    """Protocol for ephemeral search providers."""

    name: str

    async def search(self, query: SearchQuery, fetcher: Fetcher) -> SearchPage:
        """Search for jobs. Returns one page of results."""
        ...
