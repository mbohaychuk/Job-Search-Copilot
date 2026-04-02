"""Ingestion coordinator — orchestrates job discovery across sources."""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jsc.config import Settings
from jsc.db.models.job import JobPosting, JobPostingRaw, JobSource
from jsc.ingestion.base import DiscoveredJob
from jsc.ingestion.fetcher import Fetcher
from jsc.ingestion.registry import get_adapter
from jsc.parsing.job_normalizer import JobNormalizer
from jsc.providers.base import EmbeddingProvider
from jsc.services.dedup_service import DedupService
from jsc.utils.url import dedup_hash, url_hash

logger = structlog.get_logger()


class IngestionCoordinator:
    """Orchestrates the full job ingestion pipeline."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        normalizer: JobNormalizer,
        embedding_provider: EmbeddingProvider,
        dedup_service: DedupService,
    ) -> None:
        self._session = session
        self._settings = settings
        self._normalizer = normalizer
        self._embedding_provider = embedding_provider
        self._dedup = dedup_service

    async def run(
        self, source_ids: list[UUID] | None = None
    ) -> dict[str, int]:
        """Run ingestion for specified sources (or all active sources).

        Returns counts: jobs_found, jobs_new, jobs_duplicate, sources_crawled.
        """
        # Fetch sources
        stmt = select(JobSource).where(JobSource.is_active.is_(True))
        if source_ids:
            stmt = stmt.where(JobSource.id.in_(source_ids))
        result = await self._session.execute(stmt)
        sources = list(result.scalars().all())

        counts = {"jobs_found": 0, "jobs_new": 0, "jobs_duplicate": 0, "sources_crawled": 0}

        async with Fetcher(self._settings) as fetcher:
            for source in sources:
                source_counts = await self._process_source(source, fetcher)
                for k, v in source_counts.items():
                    counts[k] += v
                counts["sources_crawled"] += 1

                # Update last_crawled_at
                source.last_crawled_at = datetime.now(timezone.utc)

        await self._session.commit()
        logger.info("ingestion_complete", **counts)
        return counts

    async def _process_source(
        self, source: JobSource, fetcher: Fetcher
    ) -> dict[str, int]:
        """Process a single job source."""
        counts = {"jobs_found": 0, "jobs_new": 0, "jobs_duplicate": 0}

        try:
            adapter = get_adapter(source.adapter_type)
        except KeyError:
            logger.error("unknown_adapter", adapter_type=source.adapter_type, source=source.name)
            return counts

        # Discover jobs
        discovered = await adapter.discover(source, fetcher)
        counts["jobs_found"] = len(discovered)
        logger.info("source_discovered", source=source.name, count=len(discovered))

        # Process each discovered job
        for job_info in discovered:
            was_new = await self._process_job(source, adapter, fetcher, job_info)
            if was_new:
                counts["jobs_new"] += 1
            else:
                counts["jobs_duplicate"] += 1

        return counts

    async def _process_job(
        self,
        source: JobSource,
        adapter: object,
        fetcher: Fetcher,
        job_info: DiscoveredJob,
    ) -> bool:
        """Process a single discovered job. Returns True if it was new."""
        # Check URL dedup first
        u_hash = url_hash(job_info.url)
        existing = await self._session.execute(
            select(JobPosting.id).where(JobPosting.url_hash == u_hash)
        )
        if existing.scalar_one_or_none() is not None:
            return False

        # Fetch the job detail page (or use list data if available)
        if "list_data" in job_info.metadata:
            # Greenhouse/Lever already have full data from the list API
            import json

            raw_content = json.dumps(job_info.metadata["list_data"])
            content_type = "json"
            status = 200
        else:
            result = await fetcher.fetch(job_info.url)
            if result.status != 200:
                return False
            raw_content = result.content
            content_type = "html" if "html" in result.content_type else "text"
            status = result.status

        # Store raw content
        raw = JobPostingRaw(
            source_id=source.id,
            url=job_info.url,
            raw_content=raw_content,
            content_type=content_type,
            http_status=status,
        )
        self._session.add(raw)

        # Parse raw into structured data
        parsed = await adapter.parse(raw, source)

        # Normalize
        normalized = await self._normalizer.normalize(parsed)

        # Check fuzzy dedup
        d_hash = dedup_hash(
            normalized.title,
            normalized.company or "",
            normalized.location or "",
        )
        is_dup = await self._dedup.check_fuzzy_duplicate(d_hash, normalized.description_text or "")
        if is_dup:
            return False

        # Generate embedding
        embedding = None
        if normalized.description_text and self._settings.openai_api_key:
            try:
                vectors = await self._embedding_provider.embed([normalized.description_text])
                embedding = vectors[0] if vectors else None
            except Exception:
                logger.warning("embedding_failed", url=job_info.url)

        # Create the normalized job posting
        posting = JobPosting(
            source_id=source.id,
            external_id=job_info.external_id,
            url=job_info.url,
            url_hash=u_hash,
            title=normalized.title,
            company=normalized.company or source.name,
            location=normalized.location or "",
            is_remote="remote" in (normalized.remote_type or "").lower()
            or "remote" in (normalized.location or "").lower(),
            remote_type=normalized.remote_type,
            seniority=normalized.seniority,
            department=normalized.department,
            description_text=normalized.description_text or "",
            description_html=normalized.description_html,
            salary_min=normalized.salary_min,
            salary_max=normalized.salary_max,
            salary_currency=normalized.salary_currency,
            posted_at=normalized.posted_at,
            embedding=embedding,
            dedup_hash=d_hash,
        )
        self._session.add(posting)
        await self._session.flush()

        # Link raw to posting
        raw.job_posting_id = posting.id

        # Store skills
        from jsc.db.models.job import JobSkill

        for skill_name in normalized.skills:
            skill = JobSkill(
                job_posting_id=posting.id,
                skill_name=skill_name,
                is_required=True,
                source="extracted",
            )
            self._session.add(skill)

        return True
