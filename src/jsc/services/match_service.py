"""Match service — orchestrates ranking and match retrieval."""

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jsc.db.models.candidate import Candidate
from jsc.db.models.job import JobPosting
from jsc.db.models.match import MatchResult
from jsc.ranking.pipeline import RankingPipeline
from jsc.schemas.match import RankingSummary

logger = structlog.get_logger()


class MatchService:
    """Handles ranking and match result management."""

    def __init__(
        self,
        session: AsyncSession,
        ranking_pipeline: RankingPipeline,
    ) -> None:
        self._session = session
        self._pipeline = ranking_pipeline

    async def rank_jobs(
        self, candidate_id: UUID
    ) -> RankingSummary:
        """Rank all active jobs for a candidate and store results."""
        # Load candidate with skills and roles
        stmt = (
            select(Candidate)
            .options(selectinload(Candidate.skills), selectinload(Candidate.roles))
            .where(Candidate.id == candidate_id)
        )
        result = await self._session.execute(stmt)
        candidate = result.scalar_one_or_none()
        if candidate is None:
            raise ValueError(f"Candidate {candidate_id} not found")

        # Load active jobs with skills
        jobs_result = await self._session.execute(
            select(JobPosting)
            .options(selectinload(JobPosting.skills))
            .where(JobPosting.is_active.is_(True))
        )
        jobs = list(jobs_result.scalars().all())

        if not jobs:
            return RankingSummary(total_ranked=0)

        # Run ranking
        ranked = await self._pipeline.rank(candidate, jobs)

        # Store/update match results
        for match in ranked:
            existing = await self._session.execute(
                select(MatchResult).where(
                    MatchResult.candidate_id == candidate_id,
                    MatchResult.job_posting_id == match.job.id,
                )
            )
            existing_match = existing.scalar_one_or_none()

            explanation_dict = match.explanation.model_dump()

            if existing_match:
                existing_match.overall_score = match.overall_score
                existing_match.semantic_score = match.component_scores.get("Semantic Similarity", 0)
                existing_match.skill_coverage_score = match.component_scores.get("Skill Coverage", 0)
                existing_match.title_match_score = match.component_scores.get("Title/Role Match", 0)
                existing_match.seniority_score = match.component_scores.get("Seniority Match", 0)
                existing_match.location_score = match.component_scores.get("Location/Remote Fit", 0)
                existing_match.explanation = explanation_dict
            else:
                self._session.add(
                    MatchResult(
                        candidate_id=candidate_id,
                        job_posting_id=match.job.id,
                        overall_score=match.overall_score,
                        semantic_score=match.component_scores.get("Semantic Similarity", 0),
                        skill_coverage_score=match.component_scores.get("Skill Coverage", 0),
                        title_match_score=match.component_scores.get("Title/Role Match", 0),
                        seniority_score=match.component_scores.get("Seniority Match", 0),
                        location_score=match.component_scores.get("Location/Remote Fit", 0),
                        explanation=explanation_dict,
                    )
                )

        await self._session.commit()
        logger.info("ranking_complete", candidate_id=str(candidate_id), total=len(ranked))

        return RankingSummary(
            total_ranked=len(ranked),
            top_score=ranked[0].overall_score if ranked else None,
            top_grade=ranked[0].explanation.grade if ranked else None,
        )

    async def get_ranked_matches(
        self,
        candidate_id: UUID,
        min_score: float = 0.0,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MatchResult], int]:
        """Get ranked match results for a candidate."""
        from sqlalchemy import func

        base = (
            select(MatchResult)
            .options(selectinload(MatchResult.job_posting).selectinload(JobPosting.skills))
            .where(MatchResult.candidate_id == candidate_id)
            .where(MatchResult.overall_score >= min_score)
        )

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        stmt = base.order_by(MatchResult.overall_score.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(stmt)
        matches = list(result.scalars().all())

        return matches, total

    async def get_match_detail(
        self, candidate_id: UUID, job_id: UUID
    ) -> MatchResult | None:
        """Get a single match result with full explanation."""
        stmt = (
            select(MatchResult)
            .options(selectinload(MatchResult.job_posting).selectinload(JobPosting.skills))
            .where(
                MatchResult.candidate_id == candidate_id,
                MatchResult.job_posting_id == job_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
