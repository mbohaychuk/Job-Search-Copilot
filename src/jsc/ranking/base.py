"""Scorer protocol and shared types for the ranking pipeline."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from jsc.db.models.candidate import Candidate
from jsc.db.models.job import JobPosting


@dataclass
class ScorerResult:
    """Result from an individual scorer."""

    score: float  # 0.0 to 1.0
    details: dict[str, Any] = field(default_factory=dict)


class Scorer(Protocol):
    """Protocol for ranking scorers."""

    name: str

    async def score(self, candidate: Candidate, job: JobPosting) -> ScorerResult:
        """Score a candidate-job pair. Returns 0.0-1.0 with explanation details."""
        ...
