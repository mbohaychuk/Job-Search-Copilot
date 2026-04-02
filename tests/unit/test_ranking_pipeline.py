"""Tests for ranking scorers and pipeline."""

import pytest

from jsc.ranking.explainer import MatchExplainer, _grade
from jsc.ranking.location import LocationScorer
from jsc.ranking.semantic import SemanticScorer, _cosine_similarity
from jsc.ranking.seniority import SeniorityScorer
from jsc.ranking.skill_coverage import SkillCoverageScorer
from jsc.ranking.title_match import TitleMatchScorer, _normalize_title, _token_jaccard


class TestCosineSimlarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.5]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_zero_vector(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


class TestTitleNormalization:
    def test_removes_seniority(self):
        assert _normalize_title("Senior Backend Engineer") == "backend engineer"

    def test_removes_punctuation(self):
        assert _normalize_title("Full-Stack Developer (Sr.)") == "full stack developer"


class TestTokenJaccard:
    def test_identical(self):
        assert _token_jaccard("Backend Engineer", "Backend Engineer") == 1.0

    def test_partial_overlap(self):
        score = _token_jaccard("Backend Engineer", "Backend Developer")
        assert 0.3 < score < 0.7

    def test_no_overlap(self):
        score = _token_jaccard("Data Scientist", "Frontend Developer")
        assert score == 0.0


class TestGrade:
    def test_grade_a_plus(self):
        assert _grade(0.95) == "A+"

    def test_grade_c(self):
        assert _grade(0.55) == "C"

    def test_grade_f(self):
        assert _grade(0.2) == "F"


class TestMatchExplainer:
    def test_explain_produces_valid_output(self):
        explainer = MatchExplainer()
        components = [
            ("Semantic Similarity", 0.4, 0.85, {"cosine_similarity": 0.85}),
            ("Skill Coverage", 0.25, 0.7, {
                "matched_required": ["Python"], "missing_required": ["Go"],
                "matched_optional": [], "required_coverage": 0.5, "optional_coverage": 0.0,
            }),
            ("Title/Role Match", 0.15, 0.6, {
                "job_title": "Backend Engineer", "best_candidate_title": "Backend Dev",
                "role_family_match": False, "token_overlap": 0.6,
            }),
            ("Seniority Match", 0.1, 1.0, {
                "candidate_seniority": "senior", "job_seniority": "senior", "level_difference": 0,
            }),
            ("Location/Remote Fit", 0.1, 0.9, {
                "match_type": "hybrid_location_match", "job_location": "Edmonton",
            }),
        ]

        # overall = 0.4*0.85 + 0.25*0.7 + 0.15*0.6 + 0.1*1.0 + 0.1*0.9 = 0.795
        result = explainer.explain(0.795, components)

        assert result.grade == "B+"
        assert 0.79 <= result.overall_score <= 0.80
        assert len(result.components) == 5
        assert isinstance(result.strengths, list)
        assert isinstance(result.gaps, list)
        assert result.summary  # non-empty
