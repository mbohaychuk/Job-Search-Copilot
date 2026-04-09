"""Adzuna job search provider.

API docs: https://developer.adzuna.com/overview
Free tier: 250 requests/day, 25/minute.
"""

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus, urlencode

import structlog

from jsc.ingestion.base import ParsedJob
from jsc.ingestion.fetcher import Fetcher
from jsc.search.base import Attribution, SearchPage, SearchQuery

logger = structlog.get_logger()

_BASE_URL = "https://api.adzuna.com/v1/api/jobs"
_ATTRIBUTION = Attribution(text="Jobs by Adzuna", url="https://www.adzuna.com")


class AdzunaProvider:
    name = "adzuna"

    def __init__(self, settings: Any) -> None:
        self._app_id = settings.adzuna_app_id
        self._app_key = settings.adzuna_app_key

    async def search(self, query: SearchQuery, fetcher: Fetcher) -> SearchPage:
        if not self._app_id or not self._app_key:
            raise ValueError(
                "Adzuna credentials not configured. "
                "Set ADZUNA_APP_ID and ADZUNA_APP_KEY in your environment."
            )

        url = self._build_url(query)
        result = await fetcher.fetch(url)

        if result.status != 200:
            logger.error("adzuna_search_failed", status=result.status, url=url)
            return SearchPage(
                results=[], total=0, page=query.page,
                page_size=query.page_size, provider=self.name,
                attribution=_ATTRIBUTION,
            )

        try:
            data = json.loads(result.content)
        except json.JSONDecodeError:
            logger.error("adzuna_invalid_json", url=url)
            return SearchPage(
                results=[], total=0, page=query.page,
                page_size=query.page_size, provider=self.name,
                attribution=_ATTRIBUTION,
            )

        results = [self._map_result(r) for r in data.get("results", [])]
        total = data.get("count", 0)

        logger.info("adzuna_search_ok", count=len(results), total=total)
        return SearchPage(
            results=results, total=total, page=query.page,
            page_size=query.page_size, provider=self.name,
            attribution=_ATTRIBUTION,
        )

    def _build_url(self, query: SearchQuery) -> str:
        path = f"{_BASE_URL}/{query.country}/search/{query.page}"
        params: dict[str, str] = {
            "app_id": self._app_id,
            "app_key": self._app_key,
            "what": query.keywords,
            "results_per_page": str(query.page_size),
        }
        if query.location:
            params["where"] = query.location
        return f"{path}?{urlencode(params, quote_via=quote_plus)}"

    @staticmethod
    def _map_result(r: dict) -> ParsedJob:
        posted_at = None
        if created := r.get("created"):
            try:
                posted_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        company_data = r.get("company", {})
        location_data = r.get("location", {})
        category_data = r.get("category", {})

        return ParsedJob(
            title=r.get("title", "Unknown"),
            company=company_data.get("display_name") if isinstance(company_data, dict) else None,
            location=location_data.get("display_name") if isinstance(location_data, dict) else None,
            description_text=r.get("description", ""),
            salary_min=_safe_int(r.get("salary_min")),
            salary_max=_safe_int(r.get("salary_max")),
            posted_at=posted_at,
            department=category_data.get("label") if isinstance(category_data, dict) else None,
            metadata={
                "url": r.get("redirect_url", ""),
                "provider": "adzuna",
                "adzuna_id": r.get("id"),
            },
        )


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
