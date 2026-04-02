"""HTTP fetcher with rate limiting and robots.txt compliance."""

import asyncio
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import structlog

from jsc.config import Settings
from jsc.utils.robots import RobotsChecker

logger = structlog.get_logger()


@dataclass
class FetchResult:
    """Result of an HTTP fetch."""

    url: str
    status: int
    content: str
    content_type: str


class Fetcher:
    """HTTP fetcher with per-domain rate limiting and robots.txt checking."""

    def __init__(self, settings: Settings) -> None:
        self._rate_delay = settings.ingestion_rate_limit_delay
        self._max_concurrent = settings.ingestion_max_concurrent
        self._robots = RobotsChecker()
        self._domain_locks: dict[str, asyncio.Lock] = {}
        self._domain_last_fetch: dict[str, float] = {}
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "Fetcher":
        self._client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "JobSearchCopilot/1.0"},
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client:
            await self._client.aclose()

    def _get_domain(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a URL respecting robots.txt and rate limits."""
        assert self._client is not None, "Use Fetcher as an async context manager"

        # Check robots.txt
        if not await self._robots.is_allowed(url, self._client):
            logger.warning("robots_txt_disallowed", url=url)
            return FetchResult(url=url, status=403, content="", content_type="")

        domain = self._get_domain(url)

        # Per-domain lock for rate limiting
        if domain not in self._domain_locks:
            self._domain_locks[domain] = asyncio.Lock()

        async with self._semaphore:
            async with self._domain_locks[domain]:
                # Enforce minimum delay between requests to same domain
                last = self._domain_last_fetch.get(domain, 0)
                elapsed = time.monotonic() - last
                if elapsed < self._rate_delay:
                    await asyncio.sleep(self._rate_delay - elapsed)

                try:
                    resp = await self._client.get(url)
                    self._domain_last_fetch[domain] = time.monotonic()

                    content_type = resp.headers.get("content-type", "")
                    return FetchResult(
                        url=str(resp.url),
                        status=resp.status_code,
                        content=resp.text,
                        content_type=content_type,
                    )
                except httpx.HTTPError as exc:
                    logger.error("fetch_error", url=url, error=str(exc))
                    return FetchResult(url=url, status=0, content="", content_type="")
