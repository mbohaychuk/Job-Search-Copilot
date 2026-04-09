"""Tests for the SearchService orchestrator."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from jsc.db.models.candidate import Candidate, CandidateRole, CandidateSkill
from jsc.db.models.job import JobPosting, JobSkill
from jsc.ingestion.base import ParsedJob
from jsc.search.base import Attribution, SearchPage, SearchQuery
from jsc.search.cache import SearchCache
from jsc.search.service import SearchService


def _make_candidate() -> MagicMock:
    """Build a mock Candidate with realistic attributes.

    Uses MagicMock rather than Candidate.__new__ because SQLAlchemy's
    instrumented attributes require proper instance state initialization
    that __new__ alone doesn't provide.
    """
    c = MagicMock(spec=Candidate)
    c.id = uuid4()
    c.name = "Test User"
    c.email = "test@example.com"
    c.summary = "Python developer"
    c.years_experience = 5
    c.preferred_locations = ["Calgary", "Remote"]
    c.preferred_seniority = "mid"
    c.embedding = [0.1] * 1536
    c.skills = [
        MagicMock(spec=CandidateSkill, skill_name="python"),
        MagicMock(spec=CandidateSkill, skill_name="fastapi"),
    ]
    c.roles = [MagicMock(spec=CandidateRole, title="Backend Developer")]
    return c


def _make_search_page(n: int = 2) -> SearchPage:
    results = []
    for i in range(n):
        results.append(ParsedJob(
            title=f"Python Developer {i}",
            company=f"Company {i}",
            location="Calgary, AB",
            description_text=f"Build Python services {i}",
            salary_min=80000,
            salary_max=120000,
            metadata={"url": f"https://example.com/jobs/{i}", "provider": "adzuna"},
        ))
    return SearchPage(
        results=results,
        total=n,
        page=1,
        page_size=20,
        provider="adzuna",
        attribution=Attribution(text="Jobs by Adzuna", url="https://www.adzuna.com"),
    )


def _make_settings(**overrides) -> MagicMock:
    """Build a mock settings object with all required attributes."""
    settings = MagicMock()
    defaults = {
        "search_cache_query_ttl": 3600,
        "search_cache_job_ttl": 14400,
        "search_cache_max_queries": 100,
        "search_cache_max_jobs": 500,
        "openai_api_key": "test",
        "ingestion_rate_limit_delay": 1.0,
        "ingestion_max_concurrent": 5,
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(settings, k, v)
    return settings


class TestSearchService:
    async def test_search_returns_ranked_results(self):
        settings = _make_settings(adzuna_app_id="id", adzuna_app_key="key")

        cache = SearchCache(settings)
        normalizer = AsyncMock()
        normalizer.normalize = AsyncMock(side_effect=lambda p: p)
        embedding_provider = AsyncMock()
        embedding_provider.embed = AsyncMock(return_value=[[0.1] * 1536, [0.1] * 1536])
        ranking_pipeline = AsyncMock()

        from jsc.ranking.pipeline import RankedMatch
        from jsc.schemas.match import MatchExplanation
        mock_explanation = MatchExplanation(
            overall_score=0.85,
            grade="A",
            summary="Good match",
            components=[],
            strengths=["Python skills"],
            gaps=[],
        )

        def mock_rank(candidate, jobs):
            return [
                RankedMatch(
                    job=job,
                    overall_score=0.85,
                    component_scores={"Semantic Similarity": 0.9},
                    explanation=mock_explanation,
                )
                for job in jobs
            ]

        ranking_pipeline.rank = AsyncMock(side_effect=mock_rank)

        provider = AsyncMock()
        provider.name = "adzuna"
        provider.search = AsyncMock(return_value=_make_search_page(2))

        session = AsyncMock()
        candidate = _make_candidate()
        session.get = AsyncMock(return_value=candidate)

        service = SearchService(
            session=session,
            settings=settings,
            cache=cache,
            normalizer=normalizer,
            embedding_provider=embedding_provider,
            ranking_pipeline=ranking_pipeline,
        )

        query = SearchQuery(keywords="python developer", location="Calgary")
        result = await service.search(query, candidate.id, provider=provider)

        assert len(result.items) == 2
        assert result.total == 2
        assert result.attribution is not None
        assert result.items[0].match_score == 0.85
        assert result.items[0].provider == "adzuna"
        # Skills extracted by normalizer should appear in the response
        assert isinstance(result.items[0].skills, list)

    async def test_search_uses_query_cache_on_second_call(self):
        settings = _make_settings()

        cache = SearchCache(settings)
        normalizer = AsyncMock()
        normalizer.normalize = AsyncMock(side_effect=lambda p: p)
        embedding_provider = AsyncMock()
        embedding_provider.embed = AsyncMock(return_value=[[0.1] * 1536])
        ranking_pipeline = AsyncMock()

        from jsc.ranking.pipeline import RankedMatch
        from jsc.schemas.match import MatchExplanation

        mock_explanation = MatchExplanation(
            overall_score=0.8, grade="B+", summary="OK",
            components=[], strengths=[], gaps=[],
        )

        def mock_rank(candidate, jobs):
            return [
                RankedMatch(
                    job=job,
                    overall_score=0.8,
                    component_scores={},
                    explanation=mock_explanation,
                )
                for job in jobs
            ]

        ranking_pipeline.rank = AsyncMock(side_effect=mock_rank)

        provider = AsyncMock()
        provider.name = "adzuna"
        provider.search = AsyncMock(return_value=_make_search_page(1))

        session = AsyncMock()
        candidate = _make_candidate()
        session.get = AsyncMock(return_value=candidate)

        service = SearchService(
            session=session, settings=settings, cache=cache,
            normalizer=normalizer, embedding_provider=embedding_provider,
            ranking_pipeline=ranking_pipeline,
        )

        query = SearchQuery(keywords="python")

        await service.search(query, candidate.id, provider=provider)
        assert provider.search.call_count == 1

        await service.search(query, candidate.id, provider=provider)
        assert provider.search.call_count == 1

    async def test_search_raises_for_missing_candidate(self):
        settings = _make_settings(openai_api_key=None)

        cache = SearchCache(settings)
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        service = SearchService(
            session=session, settings=settings, cache=cache,
            normalizer=AsyncMock(), embedding_provider=AsyncMock(),
            ranking_pipeline=AsyncMock(),
        )

        query = SearchQuery(keywords="python")
        with pytest.raises(ValueError, match="[Cc]andidate"):
            await service.search(query, uuid4(), provider=AsyncMock())
