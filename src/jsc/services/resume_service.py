"""Resume ingestion service — orchestrates upload, parsing, and storage."""

from datetime import date
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from jsc.db.models.candidate import Candidate, CandidateRole, CandidateSkill, ResumeDocument
from jsc.parsing.profile_extractor import ProfileExtractor
from jsc.parsing.resume_parser import ResumeParser
from jsc.providers.base import EmbeddingProvider

logger = structlog.get_logger()


class ResumeService:
    """Handles resume upload, text extraction, profile building, and storage."""

    def __init__(
        self,
        session: AsyncSession,
        resume_parser: ResumeParser,
        profile_extractor: ProfileExtractor,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._session = session
        self._parser = resume_parser
        self._extractor = profile_extractor
        self._embedder = embedding_provider

    async def ingest_resume(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        candidate_id: UUID | None = None,
    ) -> Candidate:
        """Process a resume file and create/update a candidate.

        1. Extract text from PDF/DOCX
        2. Check for duplicate file
        3. Extract structured profile via LLM
        4. Generate embedding
        5. Store candidate + skills + roles + document
        """
        # Extract text
        raw_text = self._parser.extract_text(file_bytes, content_type)
        file_hash = self._parser.file_hash(file_bytes)

        # Create or fetch candidate
        if candidate_id:
            candidate = await self._session.get(Candidate, candidate_id)
            if candidate is None:
                raise ValueError(f"Candidate {candidate_id} not found")
        else:
            candidate = Candidate(name="Unknown", preferred_locations=[])
            self._session.add(candidate)
            await self._session.flush()

        # Extract structured profile
        profile = await self._extractor.extract(raw_text)

        # Update candidate fields
        candidate.name = profile.name
        candidate.email = profile.email
        candidate.summary = profile.summary
        candidate.years_experience = profile.years_experience
        candidate.preferred_seniority = profile.preferred_seniority

        # Generate embedding from full resume text
        try:
            vectors = await self._embedder.embed([raw_text[:8000]])
            if vectors:
                candidate.embedding = vectors[0]
        except Exception:
            logger.warning("resume_embedding_failed", candidate_id=str(candidate.id))

        # Clear and rebuild skills
        candidate.skills.clear()
        for skill in profile.skills:
            candidate.skills.append(
                CandidateSkill(
                    candidate_id=candidate.id,
                    skill_name=skill.name,
                    proficiency=skill.proficiency,
                    years_used=skill.years_used,
                    source="extracted",
                )
            )

        # Clear and rebuild roles
        candidate.roles.clear()
        for role in profile.roles:
            candidate.roles.append(
                CandidateRole(
                    candidate_id=candidate.id,
                    title=role.title,
                    company=role.company,
                    start_date=_parse_date(role.start_date),
                    end_date=_parse_date(role.end_date),
                    description=role.description,
                )
            )

        # Store resume document
        resume_doc = ResumeDocument(
            candidate_id=candidate.id,
            filename=filename,
            content_type=content_type,
            raw_text=raw_text,
            file_hash=file_hash,
        )
        self._session.add(resume_doc)

        await self._session.commit()
        await self._session.refresh(candidate, ["skills", "roles", "resumes"])

        logger.info(
            "resume_ingested",
            candidate_id=str(candidate.id),
            skills_count=len(candidate.skills),
            roles_count=len(candidate.roles),
        )
        return candidate


def _parse_date(date_str: str | None) -> date | None:
    """Parse a date string in YYYY-MM-DD format."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return None
