"""Greenhouse job board adapter.

Greenhouse exposes a public JSON API at:
  https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs

No authentication required. Returns all active job listings.
"""

import json

import structlog

from jsc.db.models.job import JobPostingRaw, JobSource
from jsc.ingestion.base import DiscoveredJob, ParsedJob
from jsc.ingestion.fetcher import Fetcher
from jsc.utils.text import clean_html, normalize_text

logger = structlog.get_logger()


class GreenhouseAdapter:
    adapter_type = "greenhouse"

    async def discover(self, source: JobSource, fetcher: Fetcher) -> list[DiscoveredJob]:
        """Fetch all jobs from a Greenhouse board's JSON API."""
        # base_url should be like "https://boards-api.greenhouse.io/v1/boards/acmecorp"
        # or just the board token stored in config
        base = source.base_url.rstrip("/")
        api_url = f"{base}/jobs"

        result = await fetcher.fetch(api_url)
        if result.status != 200:
            logger.error("greenhouse_discover_failed", url=api_url, status=result.status)
            return []

        try:
            data = json.loads(result.content)
        except json.JSONDecodeError:
            logger.error("greenhouse_invalid_json", url=api_url)
            return []

        jobs: list[DiscoveredJob] = []
        for job in data.get("jobs", []):
            job_id = str(job.get("id", ""))
            # Individual job detail URL
            detail_url = f"{base}/jobs/{job_id}"
            jobs.append(
                DiscoveredJob(
                    url=detail_url,
                    external_id=job_id,
                    metadata={"list_data": job},
                )
            )

        logger.info("greenhouse_discovered", source=source.name, count=len(jobs))
        return jobs

    async def parse(self, raw: JobPostingRaw, source: JobSource) -> ParsedJob:
        """Parse a Greenhouse job JSON response into structured data."""
        data = json.loads(raw.raw_content)

        title = data.get("title", "Unknown")
        company = source.config.get("company_name", source.name)

        # Location from the first location object
        location_data = data.get("location", {})
        location = location_data.get("name", "") if isinstance(location_data, dict) else ""

        # Description HTML
        description_html = data.get("content", "")
        description_text = normalize_text(clean_html(description_html)) if description_html else ""

        # Departments
        departments = data.get("departments", [])
        department = departments[0].get("name", "") if departments else None

        # Posted date
        posted_at = None
        if updated_at := data.get("updated_at"):
            from datetime import datetime

            try:
                posted_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return ParsedJob(
            title=title,
            company=company,
            location=location,
            description_html=description_html,
            description_text=description_text,
            posted_at=posted_at,
            department=department,
            metadata={"greenhouse_id": data.get("id")},
        )
