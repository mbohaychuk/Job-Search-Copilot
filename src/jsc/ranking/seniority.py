"""Seniority match scorer — compares candidate and job seniority levels."""

from jsc.db.models.candidate import Candidate
from jsc.db.models.job import JobPosting
from jsc.ranking.base import ScorerResult

_LEVEL_MAP: dict[str, int] = {
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "lead": 4,
    "principal": 5,
    "staff": 5,
}


class SeniorityScorer:
    """Scores based on seniority level alignment."""

    name = "Seniority Match"

    async def score(self, candidate: Candidate, job: JobPosting) -> ScorerResult:
        c_level = _LEVEL_MAP.get((candidate.preferred_seniority or "").lower())
        j_level = _LEVEL_MAP.get((job.seniority or "").lower())

        if c_level is None or j_level is None:
            return ScorerResult(
                score=0.5,
                details={
                    "reason": "missing_seniority_data",
                    "candidate_seniority": candidate.preferred_seniority,
                    "job_seniority": job.seniority,
                },
            )

        diff = abs(c_level - j_level)
        # Perfect match = 1.0, one level off = 0.7, two off = 0.4, three+ = 0.1
        score = max(0.1, 1.0 - diff * 0.3)

        return ScorerResult(
            score=round(score, 4),
            details={
                "candidate_seniority": candidate.preferred_seniority,
                "job_seniority": job.seniority,
                "level_difference": diff,
            },
        )
