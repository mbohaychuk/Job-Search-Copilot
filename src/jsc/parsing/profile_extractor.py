"""LLM-based structured profile extraction from resume text."""

import json

import structlog
from pydantic import BaseModel

from jsc.parsing.skill_taxonomy import SkillTaxonomy
from jsc.providers.base import LLMProvider

logger = structlog.get_logger()

_SYSTEM_PROMPT = """You are a resume parser. Extract structured information from the resume text.
Return valid JSON matching the requested schema. Be precise and factual.
Only include information explicitly stated in the resume."""

_EXTRACTION_PROMPT = """Extract the following from this resume text:

1. name: Full name
2. email: Email address (null if not found)
3. summary: A 1-2 sentence professional summary
4. years_experience: Total years of professional experience (integer, estimate from work history dates)
5. skills: List of technical skills with optional proficiency ("beginner", "intermediate", "advanced", "expert") and years_used
6. roles: List of work experience entries with title, company, start_date (YYYY-MM-DD or null), end_date (YYYY-MM-DD or null for current), description
7. preferred_seniority: Estimated seniority level ("junior", "mid", "senior", "lead", "principal")

Resume text:
---
{resume_text}
---

Return JSON with this structure:
{{
  "name": "string",
  "email": "string or null",
  "summary": "string",
  "years_experience": integer or null,
  "preferred_seniority": "string",
  "skills": [
    {{"name": "string", "proficiency": "string or null", "years_used": integer or null}}
  ],
  "roles": [
    {{"title": "string", "company": "string", "start_date": "string or null", "end_date": "string or null", "description": "string"}}
  ]
}}"""


class ExtractedSkill(BaseModel):
    name: str
    proficiency: str | None = None
    years_used: int | None = None


class ExtractedRole(BaseModel):
    title: str
    company: str
    start_date: str | None = None
    end_date: str | None = None
    description: str = ""


class ExtractedProfile(BaseModel):
    name: str
    email: str | None = None
    summary: str = ""
    years_experience: int | None = None
    preferred_seniority: str | None = None
    skills: list[ExtractedSkill] = []
    roles: list[ExtractedRole] = []


class ProfileExtractor:
    """Extracts structured candidate profiles from resume text using an LLM."""

    def __init__(self, llm_provider: LLMProvider, skill_taxonomy: SkillTaxonomy) -> None:
        self._llm = llm_provider
        self._taxonomy = skill_taxonomy

    async def extract(self, raw_text: str) -> ExtractedProfile:
        """Extract a structured profile from resume text."""
        prompt = _EXTRACTION_PROMPT.format(resume_text=raw_text[:8000])

        response = await self._llm.complete(
            prompt,
            system=_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=3000,
        )

        try:
            data = json.loads(response)
            profile = ExtractedProfile.model_validate(data)
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("profile_extraction_failed", error=str(exc))
            # Return a minimal profile with skill taxonomy keyword extraction
            skills_found = self._taxonomy.find_skills_in_text(raw_text)
            return ExtractedProfile(
                name="Unknown",
                skills=[ExtractedSkill(name=s) for s in skills_found],
            )

        # Canonicalize skill names
        for skill in profile.skills:
            skill.name = self._taxonomy.canonicalize_or_keep(skill.name)

        return profile
