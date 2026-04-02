"""Career page adapter for structured company career pages.

Uses CSS selectors (stored in job_source.config) to extract job links
from a company's career page.

Expected config keys:
  - job_link_selector: CSS selector for job listing links (e.g. "a.job-title")
  - title_selector: CSS selector for job title on detail page
  - description_selector: CSS selector for job description on detail page
  - company_name: company name override
"""

from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup

from jsc.db.models.job import JobPostingRaw, JobSource
from jsc.ingestion.base import DiscoveredJob, ParsedJob
from jsc.ingestion.fetcher import Fetcher
from jsc.utils.text import clean_html, normalize_text

logger = structlog.get_logger()


class CareerPageAdapter:
    adapter_type = "career_page"

    async def discover(self, source: JobSource, fetcher: Fetcher) -> list[DiscoveredJob]:
        """Find job links on a career page using configured CSS selectors."""
        result = await fetcher.fetch(source.base_url)
        if result.status != 200:
            logger.error("career_page_fetch_failed", url=source.base_url, status=result.status)
            return []

        soup = BeautifulSoup(result.content, "html.parser")
        selector = source.config.get("job_link_selector", "a[href*='job'], a[href*='career']")

        links = soup.select(selector)
        jobs: list[DiscoveredJob] = []
        seen_urls: set[str] = set()

        for link in links:
            href = link.get("href", "")
            if not href:
                continue
            url = urljoin(source.base_url, str(href))
            if url in seen_urls:
                continue
            seen_urls.add(url)
            jobs.append(DiscoveredJob(url=url, metadata={"link_text": link.get_text(strip=True)}))

        logger.info("career_page_discovered", source=source.name, count=len(jobs))
        return jobs

    async def parse(self, raw: JobPostingRaw, source: JobSource) -> ParsedJob:
        """Parse a career page job detail using configured selectors."""
        soup = BeautifulSoup(raw.raw_content, "html.parser")
        config = source.config

        # Title
        title_el = soup.select_one(config.get("title_selector", "h1"))
        title = title_el.get_text(strip=True) if title_el else "Unknown"

        # Description
        desc_el = soup.select_one(config.get("description_selector", "article, .job-description"))
        description_html = str(desc_el) if desc_el else ""
        description_text = normalize_text(clean_html(description_html)) if desc_el else ""

        company = config.get("company_name", source.name)

        return ParsedJob(
            title=title,
            company=company,
            description_html=description_html,
            description_text=description_text,
        )
