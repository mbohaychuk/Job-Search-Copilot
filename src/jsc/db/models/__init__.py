"""ORM models — import all for Alembic autogenerate discovery."""

from jsc.db.models.candidate import (  # noqa: F401
    Candidate,
    CandidateRole,
    CandidateSkill,
    ResumeDocument,
)
from jsc.db.models.job import (  # noqa: F401
    JobPosting,
    JobPostingRaw,
    JobSkill,
    JobSource,
)
from jsc.db.models.match import MatchResult  # noqa: F401
