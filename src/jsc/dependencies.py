"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from jsc.config import Settings
from jsc.ingestion.coordinator import IngestionCoordinator
from jsc.parsing.job_normalizer import JobNormalizer
from jsc.parsing.profile_extractor import ProfileExtractor
from jsc.parsing.resume_parser import ResumeParser
from jsc.parsing.skill_taxonomy import SkillTaxonomy
from jsc.providers import factory as provider_factory
from jsc.providers.base import EmbeddingProvider, LLMProvider
from jsc.ranking.pipeline import RankingPipeline
from jsc.search.cache import SearchCache
from jsc.search.service import SearchService
from jsc.services.dedup_service import DedupService
from jsc.services.job_service import JobService
from jsc.services.match_service import MatchService
from jsc.services.resume_service import ResumeService


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_skill_taxonomy() -> SkillTaxonomy:
    return SkillTaxonomy()


# --- API key authentication ---
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    """Verify API key if one is configured. Skip auth if api_key setting is empty."""
    if not settings.api_key:
        return  # No key configured — allow all (dev mode)
    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


# --- Database session from app.state ---

async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.session_factory() as session:
        yield session


# --- Providers ---

def get_embedding_provider(
    settings: Settings = Depends(get_settings),
) -> EmbeddingProvider:
    return provider_factory.create_embedding_provider(settings)


def get_llm_provider(
    settings: Settings = Depends(get_settings),
) -> LLMProvider:
    return provider_factory.create_llm_provider(settings)


# --- Parsers & extractors ---

def get_resume_parser() -> ResumeParser:
    return ResumeParser()


def get_profile_extractor(
    llm: LLMProvider = Depends(get_llm_provider),
    taxonomy: SkillTaxonomy = Depends(get_skill_taxonomy),
) -> ProfileExtractor:
    return ProfileExtractor(llm, taxonomy)


def get_resume_service(
    session: AsyncSession = Depends(get_db_session),
    parser: ResumeParser = Depends(get_resume_parser),
    extractor: ProfileExtractor = Depends(get_profile_extractor),
    embedder: EmbeddingProvider = Depends(get_embedding_provider),
) -> ResumeService:
    return ResumeService(session, parser, extractor, embedder)


def get_job_normalizer(
    taxonomy: SkillTaxonomy = Depends(get_skill_taxonomy),
) -> JobNormalizer:
    return JobNormalizer(taxonomy)


def get_dedup_service(
    session: AsyncSession = Depends(get_db_session),
) -> DedupService:
    return DedupService(session)


def get_ingestion_coordinator(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    normalizer: JobNormalizer = Depends(get_job_normalizer),
    embedder: EmbeddingProvider = Depends(get_embedding_provider),
    dedup: DedupService = Depends(get_dedup_service),
) -> IngestionCoordinator:
    return IngestionCoordinator(session, settings, normalizer, embedder, dedup)


def get_job_service(
    session: AsyncSession = Depends(get_db_session),
    coordinator: IngestionCoordinator = Depends(get_ingestion_coordinator),
) -> JobService:
    return JobService(session, coordinator)


def get_ranking_pipeline(
    settings: Settings = Depends(get_settings),
    taxonomy: SkillTaxonomy = Depends(get_skill_taxonomy),
) -> RankingPipeline:
    return RankingPipeline(settings, taxonomy)


def get_match_service(
    session: AsyncSession = Depends(get_db_session),
    pipeline: RankingPipeline = Depends(get_ranking_pipeline),
) -> MatchService:
    return MatchService(session, pipeline)


@lru_cache
def get_search_cache() -> SearchCache:
    return SearchCache(get_settings())


def get_search_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    cache: SearchCache = Depends(get_search_cache),
    normalizer: JobNormalizer = Depends(get_job_normalizer),
    embedder: EmbeddingProvider = Depends(get_embedding_provider),
    pipeline: RankingPipeline = Depends(get_ranking_pipeline),
) -> SearchService:
    return SearchService(session, settings, cache, normalizer, embedder, pipeline)
