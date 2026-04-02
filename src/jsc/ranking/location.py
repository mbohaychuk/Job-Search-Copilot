"""Location/remote fit scorer."""

from jsc.db.models.candidate import Candidate
from jsc.db.models.job import JobPosting
from jsc.ranking.base import ScorerResult


def _normalize_location(loc: str) -> str:
    """Normalize location for comparison."""
    return loc.lower().strip().replace(",", "").replace(".", "")


def _locations_match(candidate_locs: list[str], job_location: str) -> bool:
    """Check if any candidate preferred location matches the job location."""
    job_norm = _normalize_location(job_location)
    for c_loc in candidate_locs:
        c_norm = _normalize_location(c_loc)
        if c_norm in job_norm or job_norm in c_norm:
            return True
    return False


class LocationScorer:
    """Scores based on location and remote work compatibility."""

    name = "Location/Remote Fit"

    async def score(self, candidate: Candidate, job: JobPosting) -> ScorerResult:
        c_locs = candidate.preferred_locations or []
        j_remote = (job.remote_type or "").lower()
        j_location = job.location or ""
        c_wants_remote = any("remote" in loc.lower() for loc in c_locs)

        # Full remote job
        if j_remote == "full" or job.is_remote:
            if c_wants_remote:
                return ScorerResult(
                    score=1.0,
                    details={"match_type": "remote_match", "job_remote_type": j_remote},
                )
            # Remote job but candidate didn't mention remote preference — still good
            return ScorerResult(
                score=0.8,
                details={"match_type": "remote_available", "job_remote_type": j_remote},
            )

        loc_match = _locations_match(c_locs, j_location)

        # Hybrid job
        if j_remote == "hybrid":
            if loc_match:
                return ScorerResult(
                    score=0.9,
                    details={"match_type": "hybrid_location_match", "job_location": j_location},
                )
            return ScorerResult(
                score=0.3,
                details={"match_type": "hybrid_no_location_match", "job_location": j_location},
            )

        # Onsite job
        if loc_match:
            return ScorerResult(
                score=1.0,
                details={"match_type": "onsite_location_match", "job_location": j_location},
            )

        # No location data — neutral
        if not j_location and not j_remote:
            return ScorerResult(
                score=0.5,
                details={"match_type": "no_location_data"},
            )

        return ScorerResult(
            score=0.0,
            details={"match_type": "onsite_no_location_match", "job_location": j_location},
        )
