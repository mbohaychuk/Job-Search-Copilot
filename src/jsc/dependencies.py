"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from jsc.config import Settings
from jsc.db.engine import build_engine
from jsc.ingestion.coordinator import IngestionCoordinator
from jsc.parsing.job_normalizer import JobNormalizer
from jsc.parsing.profile_extractor import ProfileExtractor
from jsc.parsing.resume_parser import ResumeParser
from jsc.parsing.skill_taxonomy import SkillTaxonomy
from jsc.providers import factory as provider_factory
from jsc.providers.base import EmbeddingProvider, LLMProvider
from jsc.ranking.pipeline import RankingPipeline
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


# Engine and session factory are module-level singletons, built lazily
_engine_session: tuple | None = None


def _get_engine_session(settings: Settings) -> tuple:
    global _engine_session
    if _engine_session is None:
        _engine_session = build_engine(settings)
    return _engine_session


async def get_db_session(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[AsyncSession, None]:
    _, session_factory = _get_engine_session(settings)
    async with session_factory() as session:
        yield session


def get_embedding_provider(
    settings: Settings = Depends(get_settings),
) -> EmbeddingProvider:
    return provider_factory.create_embedding_provider(settings)


def get_llm_provider(
    settings: Settings = Depends(get_settings),
) -> LLMProvider:
    return provider_factory.create_llm_provider(settings)


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
) -> RankingPipeline:
    return RankingPipeline(settings)


def get_match_service(
    session: AsyncSession = Depends(get_db_session),
    pipeline: RankingPipeline = Depends(get_ranking_pipeline),
) -> MatchService:
    return MatchService(session, pipeline)
