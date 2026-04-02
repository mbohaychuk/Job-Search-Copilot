"""Semantic similarity scorer — cosine similarity of pre-computed embeddings."""

import math

from jsc.db.models.candidate import Candidate
from jsc.db.models.job import JobPosting
from jsc.ranking.base import ScorerResult


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticScorer:
    """Computes semantic similarity between candidate and job embeddings."""

    name = "Semantic Similarity"

    async def score(self, candidate: Candidate, job: JobPosting) -> ScorerResult:
        if candidate.embedding is None or job.embedding is None:
            return ScorerResult(score=0.5, details={"reason": "missing_embeddings"})

        similarity = _cosine_similarity(
            list(candidate.embedding), list(job.embedding)
        )
        # Clamp to [0, 1] (cosine sim can be negative for very different vectors)
        similarity = max(0.0, min(1.0, similarity))

        return ScorerResult(
            score=similarity,
            details={"cosine_similarity": round(similarity, 4)},
        )
