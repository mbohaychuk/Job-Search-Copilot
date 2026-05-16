"""Job posting normalization — enriches parsed job data with structured fields."""

import re

import structlog

from jsc.ingestion.base import ParsedJob
from jsc.parsing.skill_taxonomy import SkillTaxonomy

logger = structlog.get_logger()

_SENIORITY_PATTERNS: dict[str, list[str]] = {
    "junior": ["junior", "entry level", "entry-level", "new grad", "associate"],
    "mid": ["mid level", "mid-level", "intermediate"],
    "senior": ["senior", "sr."],
    "lead": ["lead", "team lead", "tech lead", "engineering lead"],
    "principal": ["principal", "staff", "distinguished", "fellow"],
}

_REMOTE_PATTERNS: dict[str, list[str]] = {
    "full": ["fully remote", "100% remote", "remote only", "work from anywhere"],
    "hybrid": ["hybrid", "partially remote", "flexible"],
    "onsite": ["on-site", "onsite", "in-office", "in office", "office-based"],
}


def _detect_seniority(title: str, description: str) -> str | None:
    """Detect seniority from job title (stronger signal) or description."""
    title_lower = title.lower()
    for level, patterns in _SENIORITY_PATTERNS.items():
        for p in patterns:
            if p in title_lower:
                return level

    combined = f"{title}\n{description}".lower()
    for level, patterns in _SENIORITY_PATTERNS.items():
        for p in patterns:
            if p in combined:
                return level
    return None


def _detect_remote_type(title: str, location: str, description: str) -> str | None:
    """Detect remote/hybrid/onsite status."""
    combined = f"{title}\n{location}\n{description}".lower()
    for remote_type, patterns in _REMOTE_PATTERNS.items():
        for p in patterns:
            if p in combined:
                return remote_type
    if re.search(r"\bremote\b", (location or "").lower()):
        return "full"
    return None


class JobNormalizer:
    """Normalizes parsed job data with skill extraction and field enrichment."""

    def __init__(self, skill_taxonomy: SkillTaxonomy) -> None:
        self._taxonomy = skill_taxonomy

    async def normalize(self, parsed: ParsedJob) -> ParsedJob:
        """Enrich a parsed job with seniority, remote type, and skills."""
        description = parsed.description_text or ""

        if not parsed.seniority:
            parsed.seniority = _detect_seniority(parsed.title, description)

        if not parsed.remote_type:
            parsed.remote_type = _detect_remote_type(
                parsed.title, parsed.location or "", description
            )

        if not parsed.skills:
            parsed.skills = self._taxonomy.find_skills_in_text(
                f"{parsed.title}\n{description}"
            )

        return parsed
