"""Text cleaning and normalization utilities."""

import re
import unicodedata


def clean_html(html: str) -> str:
    """Strip HTML tags and decode entities to get plain text."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace characters into single spaces."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_text(text: str) -> str:
    """Full normalization: unicode, whitespace, strip."""
    text = unicodedata.normalize("NFKC", text)
    return normalize_whitespace(text)


def extract_years_experience(text: str) -> int | None:
    """Try to extract years-of-experience requirement from text.

    Looks for patterns like "5+ years", "3-5 years experience", etc.
    Returns the minimum number found, or None.
    """
    patterns = [
        r"(\d+)\s*-\s*\d+\s*(?:years?|yrs?)[\s\w]*(?:experience|exp)",
        r"(\d+)\+?\s*(?:years?|yrs?)[\s\w]*(?:experience|exp)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None
