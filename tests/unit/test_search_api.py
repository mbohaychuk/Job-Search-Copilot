"""Tests for the GET /api/v1/search endpoint."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from jsc.dependencies import get_db_session, get_settings, verify_api_key
from jsc.main import create_app
from jsc.schemas.match import MatchExplanation
from jsc.schemas.search import SearchAttribution, SearchResponse, SearchResultRead
from jsc.search.service import SearchService


def _make_test_settings():
    s = MagicMock()
    s.database_url = "postgresql+asyncpg://test:test@localhost:5432/test"
    s.openai_api_key = "test-key"
    s.api_key = ""
    s.api_cors_origins = ["http://localhost:3000"]
    s.adzuna_app_id = "test-id"
    s.adzuna_app_key = "test-key"
    s.search_cache_query_ttl = 3600
    s.search_cache_job_ttl = 14400
    s.search_cache_max_queries = 100
    s.search_cache_max_jobs = 500
    s.weight_semantic = 0.40
    s.weight_skill_coverage = 0.25
    s.weight_title_match = 0.15
    s.weight_seniority = 0.10
    s.weight_location = 0.10
    s.ingestion_rate_limit_delay = 1.0
    s.ingestion_max_concurrent = 3
    s.ingestion_playwright_enabled = False
    return s


def _mock_search_response(n: int = 2) -> SearchResponse:
    items = []
    for i in range(n):
        items.append(SearchResultRead(
            id=f"hash{i}",
            title=f"Python Developer {i}",
            company=f"Company {i}",
            location="Calgary, AB",
            is_remote=False,
            remote_type=None,
            seniority="mid",
            posted_at=None,
            url=f"https://example.com/jobs/{i}",
            skills=[],
            salary_min=80000,
            salary_max=120000,
            salary_currency="CAD",
            provider="adzuna",
            match_score=0.85 - i * 0.1,
            match_explanation=MatchExplanation(
                overall_score=0.85, grade="A", summary="Good match",
                components=[], strengths=[], gaps=[],
            ),
        ))
    return SearchResponse(
        items=items, total=n, page=1, page_size=20,
        pages=1, attribution=SearchAttribution(text="Jobs by Adzuna", url="https://www.adzuna.com"),
    )


class TestSearchEndpoint:
    async def test_search_returns_200_with_results(self):
        app = create_app()
        app.dependency_overrides[verify_api_key] = lambda: None

        mock_service = AsyncMock(spec=SearchService)
        mock_service.search = AsyncMock(return_value=_mock_search_response(2))

        from jsc.dependencies import get_search_service
        app.dependency_overrides[get_search_service] = lambda: mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            candidate_id = str(uuid4())
            resp = await client.get(
                "/api/v1/search",
                params={"q": "python developer", "candidate_id": candidate_id},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert data["attribution"]["text"] == "Jobs by Adzuna"
        assert data["items"][0]["match_score"] == 0.85

    async def test_search_requires_q_param(self):
        app = create_app()
        app.dependency_overrides[verify_api_key] = lambda: None

        mock_service = AsyncMock(spec=SearchService)
        from jsc.dependencies import get_search_service
        app.dependency_overrides[get_search_service] = lambda: mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/search",
                params={"candidate_id": str(uuid4())},
            )

        assert resp.status_code == 422

    async def test_search_requires_candidate_id(self):
        app = create_app()
        app.dependency_overrides[verify_api_key] = lambda: None

        mock_service = AsyncMock(spec=SearchService)
        from jsc.dependencies import get_search_service
        app.dependency_overrides[get_search_service] = lambda: mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/search",
                params={"q": "python developer"},
            )

        assert resp.status_code == 422
