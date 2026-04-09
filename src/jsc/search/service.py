"""Search service — orchestrates ephemeral search, normalization, and ranking."""

import math
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from jsc.db.models.candidate import Candidate
from jsc.db.models.job import JobPosting, JobSkill
from jsc.ingestion.base import ParsedJob
from jsc.ingestion.fetcher import Fetcher
from jsc.parsing.job_normalizer import JobNormalizer
from jsc.providers.base import EmbeddingProvider
from jsc.ranking.pipeline import RankingPipeline
from jsc.schemas.search import SearchAttribution, SearchResponse, SearchResultRead
from jsc.search.base import SearchPage, SearchProvider, SearchQuery
from jsc.search.cache import SearchCache
from jsc.utils.url import url_hash

logger = structlog.get_logger()


class SearchService:
    """Orchestrates ephemeral search: provider -> normalize -> rank -> respond."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Any,
        cache: SearchCache,
        normalizer: JobNormalizer,
        embedding_provider: EmbeddingProvider,
        ranking_pipeline: RankingPipeline,
    ) -> None:
        self._session = session
        self._settings = settings
        self._cache = cache
        self._normalizer = normalizer
        self._embedding_provider = embedding_provider
        self._ranking = ranking_pipeline

    async def search(
        self,
        query: SearchQuery,
        candidate_id: UUID,
        provider: SearchProvider,
    ) -> SearchResponse:
        """Execute an ephemeral search, returning ranked results.

        The flow is: load candidate -> check query cache -> fetch from provider
        (on miss) -> normalize each job -> build transient JobPosting objects ->
        embed descriptions -> cache processed postings -> rank -> build response.
        """
        # Load candidate
        candidate = await self._session.get(Candidate, candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate {candidate_id} not found")

        # Check query cache
        cache_key = f"{provider.name}:{query.cache_key()}"
        cached_page = self._cache.get_query(cache_key)

        if cached_page is not None:
            page = cached_page
        else:
            # Fetch from provider — Fetcher manages HTTP rate-limiting
            async with Fetcher(self._settings) as fetcher:
                page = await provider.search(query, fetcher)
            self._cache.put_query(cache_key, page)

        # Build transient JobPosting objects (check job cache first)
        postings: list[JobPosting] = []
        for parsed in page.results:
            job_url = parsed.metadata.get("url", "")
            j_hash = url_hash(job_url) if job_url else str(uuid4())

            cached_posting = self._cache.get_job(j_hash)
            if cached_posting is not None:
                postings.append(cached_posting)
                continue

            # Normalize parsed job (enrich seniority, remote type, skills)
            normalized = await self._normalizer.normalize(parsed)
            posting = _build_transient_posting(normalized, j_hash)
            postings.append(posting)

        # Batch-embed any postings that lack an embedding vector
        to_embed = [(i, p) for i, p in enumerate(postings) if p.embedding is None]
        if to_embed and getattr(self._settings, "openai_api_key", None):
            texts = [p.description_text for _, p in to_embed]
            try:
                vectors = await self._embedding_provider.embed(texts)
                for (i, posting), vec in zip(to_embed, vectors):
                    posting.embedding = vec
            except Exception:
                logger.warning("search_embedding_failed")

        # Cache processed postings for reuse across queries
        for posting in postings:
            j_hash = posting.url_hash
            if self._cache.get_job(j_hash) is None:
                self._cache.put_job(j_hash, posting)

        # Rank all postings against the candidate
        ranked = await self._ranking.rank(candidate, postings)

        # Build response
        items = []
        for match in ranked:
            job = match.job
            items.append(SearchResultRead(
                id=job.url_hash,
                title=job.title,
                company=job.company,
                location=job.location,
                is_remote=job.is_remote,
                remote_type=job.remote_type,
                seniority=job.seniority,
                posted_at=job.posted_at,
                url=job.url,
                skills=[],
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_currency=job.salary_currency,
                provider=page.provider,
                match_score=match.overall_score,
                match_explanation=match.explanation,
            ))

        attribution = None
        if page.attribution:
            attribution = SearchAttribution(
                text=page.attribution.text,
                url=page.attribution.url,
            )

        total_pages = math.ceil(page.total / query.page_size) if page.total > 0 else 0

        return SearchResponse(
            items=items,
            total=page.total,
            page=query.page,
            page_size=query.page_size,
            pages=total_pages,
            attribution=attribution,
        )


def _build_transient_posting(parsed: ParsedJob, j_hash: str) -> JobPosting:
    """Build an in-memory JobPosting from a ParsedJob.

    Creates a transient ORM instance using the regular constructor. The
    instance is never added to a DB session — it exists purely in memory
    for the ranking pipeline to score against. This works because all
    scorers only read attributes; they never flush or query the session.

    We use the normal constructor rather than __new__ because SQLAlchemy's
    instrumented attributes require the instance state that __init__
    initializes (the mapper, attribute tracking, etc.).
    """
    posting_id = uuid4()

    # Build transient skill objects first
    skills = []
    for skill_name in parsed.skills:
        skill = JobSkill(
            id=uuid4(),
            job_posting_id=posting_id,
            skill_name=skill_name,
            is_required=True,
            source="extracted",
        )
        skills.append(skill)

    posting = JobPosting(
        id=posting_id,
        source_id=None,
        external_id=None,
        url=parsed.metadata.get("url", ""),
        url_hash=j_hash,
        title=parsed.title,
        company=parsed.company or "Unknown",
        location=parsed.location or "",
        is_remote=(
            "remote" in (parsed.remote_type or "").lower()
            or "remote" in (parsed.location or "").lower()
        ),
        remote_type=parsed.remote_type,
        seniority=parsed.seniority,
        department=parsed.department,
        description_text=parsed.description_text or "",
        description_html=parsed.description_html,
        salary_min=parsed.salary_min,
        salary_max=parsed.salary_max,
        salary_currency=parsed.salary_currency,
        posted_at=parsed.posted_at,
        expires_at=None,
        embedding=None,
        is_active=True,
        dedup_hash=None,
    )

    # Assign skills after construction to avoid relationship issues
    posting.skills = skills

    return posting
