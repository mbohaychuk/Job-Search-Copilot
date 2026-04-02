"""Title/role match scorer — fuzzy matching of job title to candidate history."""

import re

from jsc.db.models.candidate import Candidate
from jsc.db.models.job import JobPosting
from jsc.ranking.base import ScorerResult

# Role families — titles that should be considered equivalent
_ROLE_FAMILIES: dict[str, set[str]] = {
    "backend": {
        "backend engineer", "backend developer", "server engineer",
        "api engineer", "api developer", "platform engineer",
    },
    "frontend": {
        "frontend engineer", "frontend developer", "ui engineer",
        "ui developer", "web developer",
    },
    "fullstack": {
        "full stack engineer", "full stack developer", "fullstack engineer",
        "fullstack developer", "software engineer", "software developer",
        "web engineer",
    },
    "devops": {
        "devops engineer", "site reliability engineer", "sre",
        "infrastructure engineer", "platform engineer", "cloud engineer",
    },
    "data": {
        "data engineer", "data scientist", "data analyst",
        "ml engineer", "machine learning engineer", "analytics engineer",
    },
    "mobile": {
        "mobile engineer", "mobile developer", "ios engineer",
        "ios developer", "android engineer", "android developer",
    },
    "qa": {
        "qa engineer", "test engineer", "sdet",
        "quality assurance engineer", "automation engineer",
    },
}

# Invert: title -> family
_TITLE_TO_FAMILY: dict[str, str] = {}
for family, titles in _ROLE_FAMILIES.items():
    for t in titles:
        _TITLE_TO_FAMILY[t] = family

# Stop words to remove from titles for token comparison
_STOP_WORDS = {
    "senior", "junior", "lead", "principal", "staff", "distinguished",
    "i", "ii", "iii", "iv", "v", "sr", "jr", "intern",
}


def _normalize_title(title: str) -> str:
    """Lowercase, remove punctuation and seniority modifiers."""
    title = title.lower().strip()
    title = re.sub(r"[^\w\s]", " ", title)
    tokens = [t for t in title.split() if t not in _STOP_WORDS]
    return " ".join(tokens)


def _get_family(title: str) -> str | None:
    """Map a title to its role family."""
    normalized = _normalize_title(title)
    return _TITLE_TO_FAMILY.get(normalized)


def _token_jaccard(a: str, b: str) -> float:
    """Jaccard similarity on word tokens."""
    tokens_a = set(_normalize_title(a).split())
    tokens_b = set(_normalize_title(b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


class TitleMatchScorer:
    """Scores based on how well the job title matches the candidate's role history."""

    name = "Title/Role Match"

    async def score(self, candidate: Candidate, job: JobPosting) -> ScorerResult:
        if not candidate.roles:
            return ScorerResult(score=0.5, details={"reason": "no_candidate_roles"})

        job_family = _get_family(job.title)
        candidate_titles = [r.title for r in candidate.roles]

        best_score = 0.0
        best_title = ""
        family_matched = False

        for c_title in candidate_titles:
            # Check family match
            c_family = _get_family(c_title)
            if job_family and c_family and job_family == c_family:
                score = 1.0
                family_matched = True
            else:
                # Token overlap
                score = _token_jaccard(c_title, job.title)

            if score > best_score:
                best_score = score
                best_title = c_title

        return ScorerResult(
            score=round(best_score, 4),
            details={
                "job_title": job.title,
                "best_candidate_title": best_title,
                "role_family_match": family_matched,
                "token_overlap": round(best_score, 2),
            },
        )
