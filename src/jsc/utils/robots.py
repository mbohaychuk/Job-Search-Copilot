"""robots.txt parser and cache."""

import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

# Cache TTL in seconds
_CACHE_TTL = 3600  # 1 hour


class RobotsChecker:
    """Checks robots.txt compliance with per-domain caching."""

    def __init__(self, user_agent: str = "JobSearchCopilot/1.0") -> None:
        self._user_agent = user_agent
        self._cache: dict[str, tuple[RobotFileParser, float]] = {}

    async def is_allowed(self, url: str, client: httpx.AsyncClient) -> bool:
        """Check if the URL is allowed by the domain's robots.txt."""
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        parser = await self._get_parser(domain, client)
        return parser.can_fetch(self._user_agent, url)

    async def _get_parser(self, domain: str, client: httpx.AsyncClient) -> RobotFileParser:
        """Get or fetch the robots.txt parser for a domain."""
        now = time.time()
        if domain in self._cache:
            parser, fetched_at = self._cache[domain]
            if now - fetched_at < _CACHE_TTL:
                return parser

        parser = RobotFileParser()
        robots_url = f"{domain}/robots.txt"
        try:
            resp = await client.get(robots_url, timeout=10)
            if resp.status_code == 200:
                parser.parse(resp.text.splitlines())
            else:
                # No robots.txt or error — allow everything
                parser.allow_all = True
        except httpx.HTTPError:
            parser.allow_all = True

        self._cache[domain] = (parser, now)
        return parser
