"""Generic HTML adapter — fallback for unstructured job pages.

Uses heuristics to find job content: looks for common patterns like
ld+json structured data, og: meta tags, and common CSS class names.
"""

import json

import structlog
from bs4 import BeautifulSoup

from jsc.db.models.job import JobPostingRaw, JobSource
from jsc.ingestion.base import DiscoveredJob, ParsedJob
from jsc.ingestion.fetcher import Fetcher
from jsc.utils.text import clean_html, normalize_text

logger = structlog.get_logger()


class GenericHTMLAdapter:
    adapter_type = "generic_html"

    async def discover(self, source: JobSource, fetcher: Fetcher) -> list[DiscoveredJob]:
        """Discover job links by scanning for common job-listing patterns."""
        result = await fetcher.fetch(source.base_url)
        if result.status != 200:
            return []

        soup = BeautifulSoup(result.content, "html.parser")
        jobs: list[DiscoveredJob] = []
        seen: set[str] = set()

        # Strategy 1: Look for ld+json JobPosting structured data
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "JobPosting" and (url := item.get("url")):
                        if url not in seen:
                            seen.add(url)
                            jobs.append(DiscoveredJob(url=url, metadata={"ld_json": item}))
            except (json.JSONDecodeError, AttributeError):
                continue

        # Strategy 2: Links containing job-related path segments
        job_patterns = ["/job/", "/jobs/", "/career/", "/careers/", "/position/", "/opening/"]
        from urllib.parse import urljoin

        for a in soup.find_all("a", href=True):
            href = str(a["href"])
            if any(p in href.lower() for p in job_patterns):
                url = urljoin(source.base_url, href)
                if url not in seen:
                    seen.add(url)
                    jobs.append(
                        DiscoveredJob(url=url, metadata={"link_text": a.get_text(strip=True)})
                    )

        logger.info("generic_html_discovered", source=source.name, count=len(jobs))
        return jobs

    async def parse(self, raw: JobPostingRaw, source: JobSource) -> ParsedJob:
        """Parse a generic job page using heuristics."""
        soup = BeautifulSoup(raw.raw_content, "html.parser")

        # Try ld+json first
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    return self._parse_ld_json(data, source)
            except (json.JSONDecodeError, AttributeError):
                continue

        # Fallback: extract from page structure
        title_el = soup.find("h1") or soup.find("title")
        title = title_el.get_text(strip=True) if title_el else "Unknown"

        # Try common description containers
        desc_el = None
        for selector in ["article", ".job-description", "#job-description", ".posting-page"]:
            desc_el = soup.select_one(selector)
            if desc_el:
                break

        if desc_el is None:
            # Last resort: main content area
            desc_el = soup.find("main") or soup.find("body")

        description_html = str(desc_el) if desc_el else ""
        description_text = normalize_text(clean_html(description_html))

        return ParsedJob(
            title=title,
            company=source.config.get("company_name", source.name),
            description_html=description_html,
            description_text=description_text,
        )

    def _parse_ld_json(self, data: dict, source: JobSource) -> ParsedJob:
        """Parse from JSON-LD structured data."""
        title = data.get("title", "Unknown")
        company_data = data.get("hiringOrganization", {})
        company = company_data.get("name", source.name) if isinstance(company_data, dict) else source.name

        location_data = data.get("jobLocation", {})
        location = ""
        if isinstance(location_data, dict):
            address = location_data.get("address", {})
            if isinstance(address, dict):
                parts = [address.get("addressLocality", ""), address.get("addressRegion", "")]
                location = ", ".join(p for p in parts if p)

        description_html = data.get("description", "")
        description_text = normalize_text(clean_html(description_html))

        salary_min = None
        salary_max = None
        salary_currency = None
        if base_salary := data.get("baseSalary"):
            if isinstance(base_salary, dict):
                value = base_salary.get("value", {})
                if isinstance(value, dict):
                    salary_min = value.get("minValue")
                    salary_max = value.get("maxValue")
                salary_currency = base_salary.get("currency")

        return ParsedJob(
            title=title,
            company=company,
            location=location,
            description_html=description_html,
            description_text=description_text,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
        )
