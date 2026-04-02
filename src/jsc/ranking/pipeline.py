"""Ranking pipeline — orchestrates all scorers and computes weighted final score."""

from dataclasses import dataclass

from jsc.config import Settings
from jsc.db.models.candidate import Candidate
from jsc.db.models.job import JobPosting
from jsc.ranking.base import Scorer, ScorerResult
from jsc.ranking.explainer import MatchExplainer
from jsc.ranking.location import LocationScorer
from jsc.ranking.semantic import SemanticScorer
from jsc.ranking.seniority import SeniorityScorer
from jsc.ranking.skill_coverage import SkillCoverageScorer
from jsc.ranking.title_match import TitleMatchScorer
from jsc.schemas.match import MatchExplanation


@dataclass
class WeightedScorer:
    scorer: Scorer
    weight: float


@dataclass
class RankedMatch:
    job: JobPosting
    overall_score: float
    component_scores: dict[str, float]
    explanation: MatchExplanation


class RankingPipeline:
    """Orchestrates scoring and ranking of jobs against a candidate."""

    def __init__(self, settings: Settings) -> None:
        self._scorers = [
            WeightedScorer(SemanticScorer(), settings.weight_semantic),
            WeightedScorer(SkillCoverageScorer(), settings.weight_skill_coverage),
            WeightedScorer(TitleMatchScorer(), settings.weight_title_match),
            WeightedScorer(SeniorityScorer(), settings.weight_seniority),
            WeightedScorer(LocationScorer(), settings.weight_location),
        ]
        self._explainer = MatchExplainer()

    async def rank(
        self, candidate: Candidate, jobs: list[JobPosting]
    ) -> list[RankedMatch]:
        """Score and rank all jobs for a candidate. Returns sorted descending."""
        results: list[RankedMatch] = []

        for job in jobs:
            match = await self._score_one(candidate, job)
            results.append(match)

        results.sort(key=lambda m: m.overall_score, reverse=True)
        return results

    async def _score_one(
        self, candidate: Candidate, job: JobPosting
    ) -> RankedMatch:
        """Score a single candidate-job pair."""
        component_results: list[tuple[str, float, ScorerResult]] = []

        for ws in self._scorers:
            result = await ws.scorer.score(candidate, job)
            component_results.append((ws.scorer.name, ws.weight, result))

        # Compute weighted sum
        overall = sum(weight * r.score for _, weight, r in component_results)

        # Build component scores dict
        component_scores = {name: r.score for name, _, r in component_results}

        # Build explanation
        explanation_input = [
            (name, weight, r.score, r.details) for name, weight, r in component_results
        ]
        explanation = self._explainer.explain(overall, explanation_input)

        return RankedMatch(
            job=job,
            overall_score=round(overall, 4),
            component_scores=component_scores,
            explanation=explanation,
        )
