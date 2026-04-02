"""Skill coverage scorer — deterministic skill set overlap."""

from jsc.db.models.candidate import Candidate
from jsc.db.models.job import JobPosting
from jsc.ranking.base import ScorerResult


class SkillCoverageScorer:
    """Scores based on overlap between candidate skills and job-required skills."""

    name = "Skill Coverage"

    async def score(self, candidate: Candidate, job: JobPosting) -> ScorerResult:
        candidate_skills = {s.skill_name.lower() for s in candidate.skills}

        required = {s.skill_name.lower() for s in job.skills if s.is_required}
        optional = {s.skill_name.lower() for s in job.skills if not s.is_required}

        if not required and not optional:
            return ScorerResult(
                score=0.5,
                details={"reason": "no_skills_listed", "candidate_skills": sorted(candidate_skills)},
            )

        # Required skill coverage (70% weight)
        matched_required = candidate_skills & required
        missing_required = required - candidate_skills
        req_ratio = len(matched_required) / len(required) if required else 1.0

        # Optional skill coverage (30% weight)
        matched_optional = candidate_skills & optional
        opt_ratio = len(matched_optional) / len(optional) if optional else 1.0

        score = req_ratio * 0.7 + opt_ratio * 0.3

        return ScorerResult(
            score=round(score, 4),
            details={
                "matched_required": sorted(matched_required),
                "missing_required": sorted(missing_required),
                "matched_optional": sorted(matched_optional),
                "required_coverage": round(req_ratio, 2),
                "optional_coverage": round(opt_ratio, 2),
            },
        )
