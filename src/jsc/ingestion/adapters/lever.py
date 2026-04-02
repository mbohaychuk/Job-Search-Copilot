"""Lever job board adapter.

Lever exposes a public JSON API at:
  https://api.lever.co/v0/postings/{company}?mode=json

No authentication required.
"""

import json
from datetime import datetime, timezone

import structlog

from jsc.db.models.job import JobPostingRaw, JobSource
from jsc.ingestion.base import DiscoveredJob, ParsedJob
from jsc.ingestion.fetcher import Fetcher
from jsc.utils.text import clean_html, normalize_text

logger = structlog.get_logger()


class LeverAdapter:
    adapter_type = "lever"

    async def discover(self, source: JobSource, fetcher: Fetcher) -> list[DiscoveredJob]:
        """Fetch all postings from a Lever company's JSON API."""
        # base_url should be like "https://api.lever.co/v0/postings/acmecorp"
        base = source.base_url.rstrip("/")
        api_url = f"{base}?mode=json"

        result = await fetcher.fetch(api_url)
        if result.status != 200:
            logger.error("lever_discover_failed", url=api_url, status=result.status)
            return []

        try:
            postings = json.loads(result.content)
        except json.JSONDecodeError:
            logger.error("lever_invalid_json", url=api_url)
            return []

        if not isinstance(postings, list):
            logger.error("lever_unexpected_format", url=api_url)
            return []

        jobs: list[DiscoveredJob] = []
        for posting in postings:
            posting_id = posting.get("id", "")
            # Lever posting detail — the list response already has full data
            jobs.append(
                DiscoveredJob(
                    url=posting.get("hostedUrl", f"{base}/{posting_id}"),
                    external_id=posting_id,
                    metadata={"list_data": posting},
                )
            )

        logger.info("lever_discovered", source=source.name, count=len(jobs))
        return jobs

    async def parse(self, raw: JobPostingRaw, source: JobSource) -> ParsedJob:
        """Parse a Lever posting JSON into structured data."""
        data = json.loads(raw.raw_content)

        title = data.get("text", "Unknown")
        company = source.config.get("company_name", source.name)

        # Location
        categories = data.get("categories", {})
        location = categories.get("location", "")

        # Description: Lever uses "descriptionPlain" and "description" (HTML)
        description_text = data.get("descriptionPlain", "")
        description_html = data.get("description", "")
        if not description_text and description_html:
            description_text = normalize_text(clean_html(description_html))

        # Additional content from "lists" (requirements, responsibilities, etc.)
        for section in data.get("lists", []):
            section_text = section.get("text", "")
            items = section.get("content", "")
            if section_text:
                description_text += f"\n\n{section_text}"
            if items:
                description_text += f"\n{normalize_text(clean_html(items))}"

        # Department and team
        department = categories.get("department", None)

        # Posted date
        posted_at = None
        if created_at := data.get("createdAt"):
            try:
                posted_at = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                pass

        return ParsedJob(
            title=title,
            company=company,
            location=location,
            description_html=description_html,
            description_text=normalize_text(description_text),
            posted_at=posted_at,
            department=department,
            metadata={"lever_id": data.get("id")},
        )
