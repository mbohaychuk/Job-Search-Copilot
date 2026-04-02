"""Job service — orchestrates job collection and listing."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jsc.db.models.job import JobPosting, JobSkill, JobSource
from jsc.ingestion.coordinator import IngestionCoordinator
from jsc.schemas.job import CollectionResult, JobFilter


class JobService:
    """Handles job collection, listing, and retrieval."""

    def __init__(
        self,
        session: AsyncSession,
        coordinator: IngestionCoordinator,
    ) -> None:
        self._session = session
        self._coordinator = coordinator

    async def trigger_collection(
        self, source_ids: list[UUID] | None = None
    ) -> CollectionResult:
        """Trigger job collection from configured sources."""
        counts = await self._coordinator.run(source_ids)
        return CollectionResult(
            jobs_found=counts["jobs_found"],
            jobs_new=counts["jobs_new"],
            jobs_duplicate=counts["jobs_duplicate"],
            sources_crawled=counts["sources_crawled"],
        )

    async def list_jobs(
        self,
        filters: JobFilter,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[JobPosting], int]:
        """List jobs with filtering and pagination."""
        stmt = (
            select(JobPosting)
            .options(selectinload(JobPosting.skills))
            .where(JobPosting.is_active == filters.is_active)
        )

        if filters.location:
            stmt = stmt.where(JobPosting.location.ilike(f"%{filters.location}%"))
        if filters.remote_type:
            stmt = stmt.where(JobPosting.remote_type == filters.remote_type)
        if filters.seniority:
            stmt = stmt.where(JobPosting.seniority == filters.seniority)
        if filters.search:
            search = f"%{filters.search}%"
            stmt = stmt.where(
                JobPosting.title.ilike(search) | JobPosting.description_text.ilike(search)
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        # Paginate
        stmt = stmt.order_by(JobPosting.posted_at.desc().nulls_last(), JobPosting.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self._session.execute(stmt)
        jobs = list(result.scalars().all())

        return jobs, total

    async def get_job(self, job_id: UUID) -> JobPosting | None:
        """Get a single job posting with all relations."""
        stmt = (
            select(JobPosting)
            .options(selectinload(JobPosting.skills), selectinload(JobPosting.source))
            .where(JobPosting.id == job_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_sources(self) -> list[JobSource]:
        """List all configured job sources."""
        result = await self._session.execute(
            select(JobSource).order_by(JobSource.name)
        )
        return list(result.scalars().all())

    async def create_source(
        self, name: str, adapter_type: str, base_url: str, config: dict, is_active: bool = True
    ) -> JobSource:
        """Create a new job source."""
        source = JobSource(
            name=name,
            adapter_type=adapter_type,
            base_url=base_url,
            config=config,
            is_active=is_active,
        )
        self._session.add(source)
        await self._session.commit()
        await self._session.refresh(source)
        return source
