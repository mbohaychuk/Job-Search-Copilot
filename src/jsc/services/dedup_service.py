"""Job deduplication service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jsc.db.models.job import JobPosting


def _jaccard_bigrams(a: str, b: str) -> float:
    """Word-level bigram Jaccard similarity."""
    words_a = a.lower().split()
    words_b = b.lower().split()

    if len(words_a) < 2 or len(words_b) < 2:
        return 0.0

    bigrams_a = {(words_a[i], words_a[i + 1]) for i in range(len(words_a) - 1)}
    bigrams_b = {(words_b[i], words_b[i + 1]) for i in range(len(words_b) - 1)}

    if not bigrams_a or not bigrams_b:
        return 0.0

    intersection = bigrams_a & bigrams_b
    union = bigrams_a | bigrams_b
    return len(intersection) / len(union)


class DedupService:
    """Detects duplicate job postings."""

    SIMILARITY_THRESHOLD = 0.85

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def check_fuzzy_duplicate(
        self, dedup_hash_value: str, description_text: str
    ) -> bool:
        """Check if a job with the same dedup_hash exists and text is similar.

        Returns True if a duplicate is found.
        """
        result = await self._session.execute(
            select(JobPosting.description_text)
            .where(JobPosting.dedup_hash == dedup_hash_value)
            .where(JobPosting.is_active.is_(True))
            .limit(5)
        )
        existing_texts = result.scalars().all()

        for existing in existing_texts:
            similarity = _jaccard_bigrams(existing, description_text)
            if similarity >= self.SIMILARITY_THRESHOLD:
                return True

        return False
