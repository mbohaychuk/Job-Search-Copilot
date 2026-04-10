"""Tests for the Adzuna search provider."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from jsc.ingestion.fetcher import FetchResult
from jsc.search.base import SearchQuery
from jsc.search.providers.adzuna import AdzunaProvider


def _make_settings(**overrides):
    s = MagicMock()
    s.adzuna_app_id = overrides.get("app_id", "test-id")
    s.adzuna_app_key = overrides.get("app_key", "test-key")
    return s


def _adzuna_response(count: int = 2, total: int = 100) -> str:
    results = []
    for i in range(count):
        results.append({
            "id": str(1000 + i),
            "title": f"Python Developer {i}",
            "company": {"display_name": f"Company {i}"},
            "location": {"display_name": f"Calgary, AB"},
            "description": f"We need a Python developer to build things {i}.",
            "redirect_url": f"https://www.adzuna.ca/jobs/{1000 + i}",
            "salary_min": 80000 + i * 10000,
            "salary_max": 120000 + i * 10000,
            "created": "2026-04-01T12:00:00Z",
            "category": {"label": "IT Jobs", "tag": "it-jobs"},
        })
    return json.dumps({"results": results, "count": total})


class TestAdzunaSearch:
    async def test_search_returns_parsed_jobs(self):
        provider = AdzunaProvider(_make_settings())
        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchResult(
            url="https://api.adzuna.com/v1/api/jobs/ca/search/1",
            status=200,
            content=_adzuna_response(count=2, total=50),
            content_type="application/json",
        )
        query = SearchQuery(keywords="python developer", location="Calgary", country="ca")
        page = await provider.search(query, fetcher)
        assert len(page.results) == 2
        assert page.total == 50
        assert page.page == 1
        assert page.provider == "adzuna"
        assert page.attribution is not None
        assert "Adzuna" in page.attribution.text

    async def test_search_maps_fields_correctly(self):
        provider = AdzunaProvider(_make_settings())
        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchResult(
            url="https://api.adzuna.com/v1/api/jobs/ca/search/1",
            status=200,
            content=_adzuna_response(count=1),
            content_type="application/json",
        )
        query = SearchQuery(keywords="python", country="ca")
        page = await provider.search(query, fetcher)
        job = page.results[0]
        assert job.title == "Python Developer 0"
        assert job.company == "Company 0"
        assert job.location == "Calgary, AB"
        assert "Python developer" in job.description_text
        assert job.salary_min == 80000
        assert job.salary_max == 120000
        assert job.posted_at is not None
        assert job.department == "IT Jobs"
        assert job.metadata["url"] == "https://www.adzuna.ca/jobs/1000"
        assert job.metadata["provider"] == "adzuna"

    async def test_search_builds_correct_api_url(self):
        provider = AdzunaProvider(_make_settings(app_id="myid", app_key="mykey"))
        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchResult(
            url="", status=200,
            content=_adzuna_response(count=0, total=0),
            content_type="application/json",
        )
        query = SearchQuery(
            keywords="react developer", location="Toronto", country="ca", page=3, page_size=15,
        )
        await provider.search(query, fetcher)
        call_url = fetcher.fetch.call_args[0][0]
        assert "/jobs/ca/search/3" in call_url
        assert "app_id=myid" in call_url
        assert "app_key=mykey" in call_url
        assert "what=react+developer" in call_url or "what=react%20developer" in call_url
        assert "where=Toronto" in call_url
        assert "results_per_page=15" in call_url

    async def test_search_returns_empty_on_non_200(self):
        provider = AdzunaProvider(_make_settings())
        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchResult(
            url="", status=401, content="Unauthorized", content_type=""
        )
        query = SearchQuery(keywords="python")
        page = await provider.search(query, fetcher)
        assert page.results == []
        assert page.total == 0

    async def test_search_returns_empty_on_invalid_json(self):
        provider = AdzunaProvider(_make_settings())
        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchResult(
            url="", status=200, content="not json!", content_type=""
        )
        query = SearchQuery(keywords="python")
        page = await provider.search(query, fetcher)
        assert page.results == []
        assert page.total == 0

    async def test_search_raises_when_no_credentials(self):
        provider = AdzunaProvider(_make_settings(app_id="", app_key=""))
        fetcher = AsyncMock()
        query = SearchQuery(keywords="python")
        with pytest.raises(ValueError, match="Adzuna"):
            await provider.search(query, fetcher)

    async def test_search_handles_missing_optional_fields(self):
        provider = AdzunaProvider(_make_settings())
        result_json = json.dumps({
            "results": [{
                "id": "999",
                "title": "Mystery Job",
                "description": "Do things.",
                "redirect_url": "https://adzuna.ca/jobs/999",
                "created": "2026-04-01T12:00:00Z",
            }],
            "count": 1,
        })
        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchResult(
            url="", status=200, content=result_json, content_type="application/json"
        )
        query = SearchQuery(keywords="mystery")
        page = await provider.search(query, fetcher)
        job = page.results[0]
        assert job.title == "Mystery Job"
        assert job.company is None
        assert job.location is None
        assert job.salary_min is None
        assert job.salary_max is None
        assert job.department is None
