"""URL normalization for deduplication."""

import hashlib
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Tracking params to strip for canonical URLs
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "source", "fbclid", "gclid", "mc_cid", "mc_eid",
}


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication.

    Lowercases scheme/host, strips tracking params and trailing slashes.
    """
    parsed = urlparse(url)
    # Lowercase scheme and netloc
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    # Strip trailing slash from path
    path = parsed.path.rstrip("/") or "/"
    # Remove tracking query params
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {k: v for k, v in query_params.items() if k.lower() not in _TRACKING_PARAMS}
    query = urlencode(filtered, doseq=True) if filtered else ""
    return urlunparse((scheme, netloc, path, "", query, ""))


def url_hash(url: str) -> str:
    """SHA-256 hash of a normalized URL."""
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode()).hexdigest()


def dedup_hash(title: str, company: str, location: str) -> str:
    """Hash of normalized title + company + location for fuzzy dedup."""
    key = f"{title.lower().strip()}|{company.lower().strip()}|{location.lower().strip()}"
    return hashlib.sha256(key.encode()).hexdigest()
