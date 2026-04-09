# Ephemeral Search Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an on-demand job search system that queries external aggregator APIs (Adzuna first), caches results in memory, and ranks them against a candidate profile — all without persisting to the database.

**Architecture:** A new `search/` module sits alongside the existing `ingestion/` module. Search providers implement a `SearchProvider` protocol. Results flow through the existing `JobNormalizer`, `EmbeddingProvider`, and `RankingPipeline` as transient (in-memory) `JobPosting` objects. A two-tier TTL cache (query-level + job-level) prevents redundant API calls and embedding recomputation.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx (via existing `Fetcher`), existing `RankingPipeline` + scorers, existing `EmbeddingProvider` (OpenAI).

**Spec:** `docs/superpowers/specs/2026-04-09-ephemeral-search-design.md`

---

## File Map

### New Files

| File | Responsibility |
|---|---|
| `src/jsc/search/__init__.py` | Module init |
| `src/jsc/search/base.py` | `SearchProvider` protocol, `SearchQuery`, `SearchPage`, `Attribution` dataclasses |
| `src/jsc/search/registry.py` | Maps provider name strings to `SearchProvider` instances |
| `src/jsc/search/cache.py` | `SearchCache` — two-tier in-memory TTL cache with LRU eviction |
| `src/jsc/search/service.py` | `SearchService` — orchestrates search → normalize → rank flow |
| `src/jsc/search/providers/__init__.py` | Providers subpackage init |
| `src/jsc/search/providers/adzuna.py` | `AdzunaProvider` — maps Adzuna API JSON to `ParsedJob` |
| `src/jsc/api/search.py` | `GET /api/v1/search` endpoint |
| `src/jsc/schemas/search.py` | `SearchResultRead`, `SearchAttribution`, `SearchResponse` schemas |
| `tests/unit/test_search_cache.py` | Cache unit tests |
| `tests/unit/test_adzuna_provider.py` | Adzuna provider unit tests |
| `tests/unit/test_search_service.py` | Search service unit tests |
| `tests/unit/test_search_api.py` | Search endpoint unit tests |

### Modified Files

| File | Change |
|---|---|
| `src/jsc/config.py` | Add Adzuna + cache settings fields |
| `src/jsc/dependencies.py` | Add `get_search_cache`, `get_search_service` |
| `src/jsc/api/router.py` | Include search router |

---

## Task 1: Search Base Types (`search/base.py`)

**Files:**
- Create: `src/jsc/search/__init__.py`
- Create: `src/jsc/search/base.py`
- Test: `tests/unit/test_search_base.py`

- [ ] **Step 1: Write failing test for SearchQuery**

Create `tests/unit/test_search_base.py`:

```python
"""Tests for search base types."""

from jsc.search.base import Attribution, SearchQuery


class TestSearchQuery:
    def test_defaults(self):
        q = SearchQuery(keywords="python developer")
        assert q.keywords == "python developer"
        assert q.location is None
        assert q.country == "ca"
        assert q.remote_only is False
        assert q.page == 1
        assert q.page_size == 20

    def test_cache_key_same_for_identical_queries(self):
        q1 = SearchQuery(keywords="python", location="Calgary", country="ca")
        q2 = SearchQuery(keywords="python", location="Calgary", country="ca")
        assert q1.cache_key() == q2.cache_key()

    def test_cache_key_differs_for_different_queries(self):
        q1 = SearchQuery(keywords="python", location="Calgary")
        q2 = SearchQuery(keywords="python", location="Edmonton")
        assert q1.cache_key() != q2.cache_key()

    def test_cache_key_differs_by_page(self):
        q1 = SearchQuery(keywords="python", page=1)
        q2 = SearchQuery(keywords="python", page=2)
        assert q1.cache_key() != q2.cache_key()


class TestAttribution:
    def test_fields(self):
        a = Attribution(text="Jobs by Adzuna", url="https://www.adzuna.com")
        assert a.text == "Jobs by Adzuna"
        assert a.url == "https://www.adzuna.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_search_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jsc.search'`

- [ ] **Step 3: Implement base types**

Create `src/jsc/search/__init__.py`:

```python
```

Create `src/jsc/search/base.py`:

```python
"""Search provider protocol and shared data types."""

import hashlib
from dataclasses import dataclass, field
from typing import Any, Protocol

from jsc.ingestion.base import ParsedJob
from jsc.ingestion.fetcher import Fetcher


@dataclass
class SearchQuery:
    """Parameters for an ephemeral job search."""

    keywords: str
    location: str | None = None
    country: str = "ca"
    remote_only: bool = False
    page: int = 1
    page_size: int = 20

    def cache_key(self) -> str:
        """Deterministic cache key for this query."""
        raw = (
            f"{self.keywords}|{self.location or ''}|{self.country}"
            f"|{self.remote_only}|{self.page}|{self.page_size}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class Attribution:
    """Provider attribution for ToS compliance."""

    text: str
    url: str


@dataclass
class SearchPage:
    """One page of search results from a provider."""

    results: list[ParsedJob]
    total: int
    page: int
    page_size: int
    provider: str
    attribution: Attribution | None = None


class SearchProvider(Protocol):
    """Protocol for ephemeral search providers."""

    name: str

    async def search(self, query: SearchQuery, fetcher: Fetcher) -> SearchPage:
        """Search for jobs. Returns one page of results."""
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_search_base.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/jsc/search/__init__.py src/jsc/search/base.py tests/unit/test_search_base.py
git commit -m "feat: add search base types (SearchQuery, SearchPage, SearchProvider protocol)"
```

---

## Task 2: Two-Tier Cache (`search/cache.py`)

**Files:**
- Create: `src/jsc/search/cache.py`
- Test: `tests/unit/test_search_cache.py`

- [ ] **Step 1: Write failing tests for SearchCache**

Create `tests/unit/test_search_cache.py`:

```python
"""Tests for the two-tier in-memory search cache."""

import time
from unittest.mock import MagicMock

import pytest

from jsc.search.cache import SearchCache
from jsc.search.base import Attribution, SearchPage
from jsc.ingestion.base import ParsedJob


def _make_settings(**overrides):
    s = MagicMock()
    s.search_cache_query_ttl = overrides.get("query_ttl", 3600)
    s.search_cache_job_ttl = overrides.get("job_ttl", 14400)
    s.search_cache_max_queries = overrides.get("max_queries", 1000)
    s.search_cache_max_jobs = overrides.get("max_jobs", 5000)
    return s


def _make_page(n_results: int = 1) -> SearchPage:
    results = [
        ParsedJob(title=f"Job {i}", company=f"Co {i}")
        for i in range(n_results)
    ]
    return SearchPage(
        results=results,
        total=n_results,
        page=1,
        page_size=20,
        provider="test",
        attribution=Attribution(text="Test", url="https://test.com"),
    )


def _make_job_posting():
    """Build a minimal mock transient JobPosting."""
    posting = MagicMock()
    posting.title = "Python Developer"
    posting.url = "https://example.com/jobs/1"
    return posting


class TestQueryCache:
    def test_put_and_get(self):
        cache = SearchCache(_make_settings())
        page = _make_page()
        cache.put_query("key1", page)
        assert cache.get_query("key1") is page

    def test_get_returns_none_for_missing_key(self):
        cache = SearchCache(_make_settings())
        assert cache.get_query("nonexistent") is None

    def test_expired_entry_returns_none(self):
        cache = SearchCache(_make_settings(query_ttl=0))
        cache.put_query("key1", _make_page())
        # TTL=0 means already expired
        assert cache.get_query("key1") is None

    def test_evicts_oldest_when_at_capacity(self):
        cache = SearchCache(_make_settings(max_queries=2))
        cache.put_query("old", _make_page())
        cache.put_query("mid", _make_page())
        cache.put_query("new", _make_page())
        # "old" should have been evicted
        assert cache.get_query("old") is None
        assert cache.get_query("mid") is not None
        assert cache.get_query("new") is not None


class TestJobCache:
    def test_put_and_get(self):
        cache = SearchCache(_make_settings())
        posting = _make_job_posting()
        cache.put_job("hash1", posting)
        assert cache.get_job("hash1") is posting

    def test_get_returns_none_for_missing_key(self):
        cache = SearchCache(_make_settings())
        assert cache.get_job("nonexistent") is None

    def test_expired_entry_returns_none(self):
        cache = SearchCache(_make_settings(job_ttl=0))
        cache.put_job("hash1", _make_job_posting())
        assert cache.get_job("hash1") is None

    def test_evicts_oldest_when_at_capacity(self):
        cache = SearchCache(_make_settings(max_jobs=2))
        cache.put_job("old", _make_job_posting())
        cache.put_job("mid", _make_job_posting())
        cache.put_job("new", _make_job_posting())
        assert cache.get_job("old") is None
        assert cache.get_job("mid") is not None
        assert cache.get_job("new") is not None


class TestPeriodicSweep:
    def test_sweep_clears_expired_entries(self):
        cache = SearchCache(_make_settings(query_ttl=0, job_ttl=0))
        cache.put_query("q1", _make_page())
        cache.put_job("j1", _make_job_posting())
        cache.sweep()
        assert cache.get_query("q1") is None
        assert cache.get_job("j1") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_search_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jsc.search.cache'`

- [ ] **Step 3: Implement SearchCache**

Create `src/jsc/search/cache.py`:

```python
"""Two-tier in-memory TTL cache for ephemeral search results."""

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from jsc.search.base import SearchPage


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class SearchCache:
    """Two-tier cache: query-level (SearchPage) and job-level (transient JobPosting).

    Both tiers use TTL-based expiration and LRU eviction when at capacity.
    """

    def __init__(self, settings: Any) -> None:
        self._query_ttl: float = settings.search_cache_query_ttl
        self._job_ttl: float = settings.search_cache_job_ttl
        self._max_queries: int = settings.search_cache_max_queries
        self._max_jobs: int = settings.search_cache_max_jobs

        self._queries: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._jobs: OrderedDict[str, _CacheEntry] = OrderedDict()

        self._put_count = 0

    # --- Query tier ---

    def get_query(self, key: str) -> SearchPage | None:
        entry = self._queries.get(key)
        if entry is None:
            return None
        if time.monotonic() >= entry.expires_at:
            del self._queries[key]
            return None
        self._queries.move_to_end(key)
        return entry.value

    def put_query(self, key: str, page: SearchPage) -> None:
        if key in self._queries:
            del self._queries[key]
        while len(self._queries) >= self._max_queries:
            self._queries.popitem(last=False)
        self._queries[key] = _CacheEntry(
            value=page,
            expires_at=time.monotonic() + self._query_ttl,
        )
        self._maybe_sweep()

    # --- Job tier ---

    def get_job(self, url_hash: str) -> Any | None:
        entry = self._jobs.get(url_hash)
        if entry is None:
            return None
        if time.monotonic() >= entry.expires_at:
            del self._jobs[url_hash]
            return None
        self._jobs.move_to_end(url_hash)
        return entry.value

    def put_job(self, url_hash: str, posting: Any) -> None:
        if url_hash in self._jobs:
            del self._jobs[url_hash]
        while len(self._jobs) >= self._max_jobs:
            self._jobs.popitem(last=False)
        self._jobs[url_hash] = _CacheEntry(
            value=posting,
            expires_at=time.monotonic() + self._job_ttl,
        )
        self._maybe_sweep()

    # --- Maintenance ---

    def sweep(self) -> None:
        """Remove all expired entries from both tiers."""
        now = time.monotonic()
        for store in (self._queries, self._jobs):
            expired = [k for k, v in store.items() if now >= v.expires_at]
            for k in expired:
                del store[k]

    def _maybe_sweep(self) -> None:
        self._put_count += 1
        if self._put_count >= 100:
            self._put_count = 0
            self.sweep()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_search_cache.py -v`
Expected: all 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/jsc/search/cache.py tests/unit/test_search_cache.py
git commit -m "feat: add two-tier in-memory TTL cache for ephemeral search"
```

---

## Task 3: Provider Registry (`search/registry.py`)

**Files:**
- Create: `src/jsc/search/registry.py`
- Create: `src/jsc/search/providers/__init__.py`
- (No separate test file — registry is trivial; tested via integration in Task 5)

- [ ] **Step 1: Create the registry**

Create `src/jsc/search/providers/__init__.py`:

```python
```

Create `src/jsc/search/registry.py`:

```python
"""Search provider registry — maps provider names to instances."""

from typing import Any

from jsc.search.base import SearchProvider

_PROVIDERS: dict[str, type] = {}


def get_provider(name: str, settings: Any) -> SearchProvider:
    """Get a provider instance by name. Raises KeyError if not registered."""
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise KeyError(
            f"Unknown search provider: {name!r}. "
            f"Available: {sorted(_PROVIDERS.keys())}"
        )
    return cls(settings)


def register_provider(name: str, cls: type) -> None:
    """Register a search provider."""
    _PROVIDERS[name] = cls


def available_providers() -> list[str]:
    """Return names of all registered providers."""
    return sorted(_PROVIDERS.keys())
```

- [ ] **Step 2: Commit**

```bash
git add src/jsc/search/providers/__init__.py src/jsc/search/registry.py
git commit -m "feat: add search provider registry"
```

---

## Task 4: Adzuna Provider (`search/providers/adzuna.py`)

**Files:**
- Create: `src/jsc/search/providers/adzuna.py`
- Modify: `src/jsc/config.py` (add Adzuna + cache settings)
- Modify: `src/jsc/search/registry.py` (register Adzuna)
- Test: `tests/unit/test_adzuna_provider.py`

- [ ] **Step 1: Add settings to config.py**

Add the following fields to the `Settings` class in `src/jsc/config.py`, after the existing `ingestion_playwright_enabled` field and before the ranking weights:

```python
    # Search providers
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    # Search cache
    search_cache_query_ttl: int = 3600
    search_cache_job_ttl: int = 14400
    search_cache_max_queries: int = 1000
    search_cache_max_jobs: int = 5000
```

- [ ] **Step 2: Write failing tests for AdzunaProvider**

Create `tests/unit/test_adzuna_provider.py`:

```python
"""Tests for the Adzuna search provider."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from jsc.ingestion.fetcher import FetchResult
from jsc.search.base import SearchQuery
from jsc.search.providers.adzuna import AdzunaProvider


def _make_settings(**overrides):
    s = MagicMock()
    s.adzuna_app_id = overrides.get("app_id", "test-id")
    s.adzuna_app_key = overrides.get("app_key", "test-key")
    return s


def _adzuna_response(count: int = 2, total: int = 100) -> str:
    """Build a realistic Adzuna API JSON response."""
    results = []
    for i in range(count):
        results.append({
            "id": str(1000 + i),
            "title": f"Python Developer {i}",
            "company": {"display_name": f"Company {i}"},
            "location": {"display_name": f"Calgary, AB"},
            "description": f"We need a Python developer to build things {i}.",
            "redirect_url": f"https://www.adzuna.ca/jobs/{1000 + i}",
            "salary_min": 80000 + i * 10000,
            "salary_max": 120000 + i * 10000,
            "created": "2026-04-01T12:00:00Z",
            "category": {"label": "IT Jobs", "tag": "it-jobs"},
        })
    return json.dumps({"results": results, "count": total})


class TestAdzunaSearch:
    async def test_search_returns_parsed_jobs(self):
        provider = AdzunaProvider(_make_settings())
        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchResult(
            url="https://api.adzuna.com/v1/api/jobs/ca/search/1",
            status=200,
            content=_adzuna_response(count=2, total=50),
            content_type="application/json",
        )
        query = SearchQuery(keywords="python developer", location="Calgary", country="ca")

        page = await provider.search(query, fetcher)

        assert len(page.results) == 2
        assert page.total == 50
        assert page.page == 1
        assert page.provider == "adzuna"
        assert page.attribution is not None
        assert "Adzuna" in page.attribution.text

    async def test_search_maps_fields_correctly(self):
        provider = AdzunaProvider(_make_settings())
        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchResult(
            url="https://api.adzuna.com/v1/api/jobs/ca/search/1",
            status=200,
            content=_adzuna_response(count=1),
            content_type="application/json",
        )
        query = SearchQuery(keywords="python", country="ca")

        page = await provider.search(query, fetcher)
        job = page.results[0]

        assert job.title == "Python Developer 0"
        assert job.company == "Company 0"
        assert job.location == "Calgary, AB"
        assert "Python developer" in job.description_text
        assert job.salary_min == 80000
        assert job.salary_max == 120000
        assert job.posted_at is not None
        assert job.department == "IT Jobs"
        assert job.metadata["url"] == "https://www.adzuna.ca/jobs/1000"
        assert job.metadata["provider"] == "adzuna"

    async def test_search_builds_correct_api_url(self):
        provider = AdzunaProvider(_make_settings(app_id="myid", app_key="mykey"))
        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchResult(
            url="", status=200,
            content=_adzuna_response(count=0, total=0),
            content_type="application/json",
        )
        query = SearchQuery(
            keywords="react developer",
            location="Toronto",
            country="ca",
            page=3,
            page_size=15,
        )

        await provider.search(query, fetcher)

        call_url = fetcher.fetch.call_args[0][0]
        assert "/jobs/ca/search/3" in call_url
        assert "app_id=myid" in call_url
        assert "app_key=mykey" in call_url
        assert "what=react+developer" in call_url or "what=react%20developer" in call_url
        assert "where=Toronto" in call_url
        assert "results_per_page=15" in call_url

    async def test_search_returns_empty_on_non_200(self):
        provider = AdzunaProvider(_make_settings())
        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchResult(
            url="", status=401, content="Unauthorized", content_type=""
        )
        query = SearchQuery(keywords="python")

        page = await provider.search(query, fetcher)

        assert page.results == []
        assert page.total == 0

    async def test_search_returns_empty_on_invalid_json(self):
        provider = AdzunaProvider(_make_settings())
        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchResult(
            url="", status=200, content="not json!", content_type=""
        )
        query = SearchQuery(keywords="python")

        page = await provider.search(query, fetcher)

        assert page.results == []
        assert page.total == 0

    async def test_search_raises_when_no_credentials(self):
        provider = AdzunaProvider(_make_settings(app_id="", app_key=""))
        fetcher = AsyncMock()
        query = SearchQuery(keywords="python")

        with pytest.raises(ValueError, match="Adzuna"):
            await provider.search(query, fetcher)

    async def test_search_handles_missing_optional_fields(self):
        """Adzuna results sometimes lack salary, category, or location."""
        provider = AdzunaProvider(_make_settings())
        result_json = json.dumps({
            "results": [{
                "id": "999",
                "title": "Mystery Job",
                "description": "Do things.",
                "redirect_url": "https://adzuna.ca/jobs/999",
                "created": "2026-04-01T12:00:00Z",
            }],
            "count": 1,
        })
        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchResult(
            url="", status=200, content=result_json, content_type="application/json"
        )
        query = SearchQuery(keywords="mystery")

        page = await provider.search(query, fetcher)
        job = page.results[0]

        assert job.title == "Mystery Job"
        assert job.company is None
        assert job.location is None
        assert job.salary_min is None
        assert job.salary_max is None
        assert job.department is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_adzuna_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jsc.search.providers.adzuna'`

- [ ] **Step 4: Implement AdzunaProvider**

Create `src/jsc/search/providers/adzuna.py`:

```python
"""Adzuna job search provider.

API docs: https://developer.adzuna.com/overview
Free tier: 250 requests/day, 25/minute.
"""

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus, urlencode

import structlog

from jsc.ingestion.base import ParsedJob
from jsc.ingestion.fetcher import Fetcher
from jsc.search.base import Attribution, SearchPage, SearchQuery

logger = structlog.get_logger()

_BASE_URL = "https://api.adzuna.com/v1/api/jobs"
_ATTRIBUTION = Attribution(text="Jobs by Adzuna", url="https://www.adzuna.com")


class AdzunaProvider:
    """Ephemeral search provider backed by the Adzuna API."""

    name = "adzuna"

    def __init__(self, settings: Any) -> None:
        self._app_id = settings.adzuna_app_id
        self._app_key = settings.adzuna_app_key

    async def search(self, query: SearchQuery, fetcher: Fetcher) -> SearchPage:
        if not self._app_id or not self._app_key:
            raise ValueError(
                "Adzuna credentials not configured. "
                "Set ADZUNA_APP_ID and ADZUNA_APP_KEY in your environment."
            )

        url = self._build_url(query)
        result = await fetcher.fetch(url)

        if result.status != 200:
            logger.error("adzuna_search_failed", status=result.status, url=url)
            return SearchPage(
                results=[], total=0, page=query.page,
                page_size=query.page_size, provider=self.name,
                attribution=_ATTRIBUTION,
            )

        try:
            data = json.loads(result.content)
        except json.JSONDecodeError:
            logger.error("adzuna_invalid_json", url=url)
            return SearchPage(
                results=[], total=0, page=query.page,
                page_size=query.page_size, provider=self.name,
                attribution=_ATTRIBUTION,
            )

        results = [self._map_result(r) for r in data.get("results", [])]
        total = data.get("count", 0)

        logger.info("adzuna_search_ok", count=len(results), total=total)
        return SearchPage(
            results=results,
            total=total,
            page=query.page,
            page_size=query.page_size,
            provider=self.name,
            attribution=_ATTRIBUTION,
        )

    def _build_url(self, query: SearchQuery) -> str:
        path = f"{_BASE_URL}/{query.country}/search/{query.page}"
        params: dict[str, str] = {
            "app_id": self._app_id,
            "app_key": self._app_key,
            "what": query.keywords,
            "results_per_page": str(query.page_size),
        }
        if query.location:
            params["where"] = query.location
        return f"{path}?{urlencode(params, quote_via=quote_plus)}"

    @staticmethod
    def _map_result(r: dict) -> ParsedJob:
        """Map a single Adzuna result dict to a ParsedJob."""
        posted_at = None
        if created := r.get("created"):
            try:
                posted_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        company_data = r.get("company", {})
        location_data = r.get("location", {})
        category_data = r.get("category", {})

        return ParsedJob(
            title=r.get("title", "Unknown"),
            company=company_data.get("display_name") if isinstance(company_data, dict) else None,
            location=location_data.get("display_name") if isinstance(location_data, dict) else None,
            description_text=r.get("description", ""),
            salary_min=_safe_int(r.get("salary_min")),
            salary_max=_safe_int(r.get("salary_max")),
            posted_at=posted_at,
            department=category_data.get("label") if isinstance(category_data, dict) else None,
            metadata={
                "url": r.get("redirect_url", ""),
                "provider": "adzuna",
                "adzuna_id": r.get("id"),
            },
        )


def _safe_int(value: Any) -> int | None:
    """Convert to int, returning None if not numeric."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 5: Register the Adzuna provider**

Update `src/jsc/search/registry.py` — replace the empty `_PROVIDERS` dict:

```python
"""Search provider registry — maps provider names to instances."""

from jsc.search.base import SearchProvider
from jsc.search.providers.adzuna import AdzunaProvider

_PROVIDERS: dict[str, type] = {
    "adzuna": AdzunaProvider,
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/unit/test_adzuna_provider.py -v`
Expected: all 7 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/jsc/config.py src/jsc/search/providers/adzuna.py src/jsc/search/registry.py tests/unit/test_adzuna_provider.py
git commit -m "feat: add Adzuna search provider with field mapping and error handling"
```

---

## Task 5: Search Schemas (`schemas/search.py`)

**Files:**
- Create: `src/jsc/schemas/search.py`

- [ ] **Step 1: Create search response schemas**

Create `src/jsc/schemas/search.py`:

```python
"""Search request/response schemas."""

from datetime import datetime

from pydantic import BaseModel

from jsc.schemas.job import JobSkillRead
from jsc.schemas.match import MatchExplanation


class SearchResultRead(BaseModel):
    """One ephemeral search result with ranking."""

    id: str
    title: str
    company: str
    location: str
    is_remote: bool
    remote_type: str | None = None
    seniority: str | None = None
    posted_at: datetime | None = None
    url: str
    skills: list[JobSkillRead] = []
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    provider: str
    match_score: float
    match_explanation: MatchExplanation


class SearchAttribution(BaseModel):
    """Provider attribution for ToS compliance."""

    text: str
    url: str


class SearchResponse(BaseModel):
    """Paginated search results with attribution."""

    items: list[SearchResultRead]
    total: int
    page: int
    page_size: int
    pages: int
    attribution: SearchAttribution | None = None
```

- [ ] **Step 2: Commit**

```bash
git add src/jsc/schemas/search.py
git commit -m "feat: add search response schemas"
```

---

## Task 6: Search Service (`search/service.py`)

**Files:**
- Create: `src/jsc/search/service.py`
- Test: `tests/unit/test_search_service.py`

- [ ] **Step 1: Write failing tests for SearchService**

Create `tests/unit/test_search_service.py`:

```python
"""Tests for the SearchService orchestrator."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from jsc.db.models.candidate import Candidate, CandidateRole, CandidateSkill
from jsc.db.models.job import JobPosting, JobSkill
from jsc.ingestion.base import ParsedJob
from jsc.search.base import Attribution, SearchPage, SearchQuery
from jsc.search.cache import SearchCache
from jsc.search.service import SearchService


def _make_candidate() -> Candidate:
    c = Candidate.__new__(Candidate)
    c.id = uuid4()
    c.name = "Test User"
    c.email = "test@example.com"
    c.summary = "Python developer"
    c.years_experience = 5
    c.preferred_locations = ["Calgary", "Remote"]
    c.preferred_seniority = "mid"
    c.embedding = [0.1] * 1536
    c.skills = [
        MagicMock(spec=CandidateSkill, skill_name="python"),
        MagicMock(spec=CandidateSkill, skill_name="fastapi"),
    ]
    c.roles = [MagicMock(spec=CandidateRole, title="Backend Developer")]
    return c


def _make_search_page(n: int = 2) -> SearchPage:
    results = []
    for i in range(n):
        results.append(ParsedJob(
            title=f"Python Developer {i}",
            company=f"Company {i}",
            location="Calgary, AB",
            description_text=f"Build Python services {i}",
            salary_min=80000,
            salary_max=120000,
            metadata={"url": f"https://example.com/jobs/{i}", "provider": "adzuna"},
        ))
    return SearchPage(
        results=results,
        total=n,
        page=1,
        page_size=20,
        provider="adzuna",
        attribution=Attribution(text="Jobs by Adzuna", url="https://www.adzuna.com"),
    )


class TestSearchService:
    async def test_search_returns_ranked_results(self):
        # Setup mocks
        settings = MagicMock()
        settings.adzuna_app_id = "id"
        settings.adzuna_app_key = "key"
        settings.search_cache_query_ttl = 3600
        settings.search_cache_job_ttl = 14400
        settings.search_cache_max_queries = 100
        settings.search_cache_max_jobs = 500
        settings.openai_api_key = "test"

        cache = SearchCache(settings)
        normalizer = AsyncMock()
        normalizer.normalize = AsyncMock(side_effect=lambda p: p)
        embedding_provider = AsyncMock()
        embedding_provider.embed = AsyncMock(return_value=[[0.1] * 1536, [0.1] * 1536])
        ranking_pipeline = AsyncMock()

        # Make ranking return a scored result
        from jsc.ranking.pipeline import RankedMatch
        from jsc.schemas.match import MatchExplanation
        mock_explanation = MatchExplanation(
            overall_score=0.85,
            grade="A",
            summary="Good match",
            components=[],
            strengths=["Python skills"],
            gaps=[],
        )

        def mock_rank(candidate, jobs):
            return [
                RankedMatch(
                    job=job,
                    overall_score=0.85,
                    component_scores={"Semantic Similarity": 0.9},
                    explanation=mock_explanation,
                )
                for job in jobs
            ]

        ranking_pipeline.rank = AsyncMock(side_effect=mock_rank)

        provider = AsyncMock()
        provider.name = "adzuna"
        provider.search = AsyncMock(return_value=_make_search_page(2))

        session = AsyncMock()
        candidate = _make_candidate()
        session.get = AsyncMock(return_value=candidate)

        service = SearchService(
            session=session,
            settings=settings,
            cache=cache,
            normalizer=normalizer,
            embedding_provider=embedding_provider,
            ranking_pipeline=ranking_pipeline,
        )

        query = SearchQuery(keywords="python developer", location="Calgary")
        result = await service.search(query, candidate.id, provider=provider)

        assert len(result.items) == 2
        assert result.total == 2
        assert result.attribution is not None
        assert result.items[0].match_score == 0.85
        assert result.items[0].provider == "adzuna"

    async def test_search_uses_query_cache_on_second_call(self):
        settings = MagicMock()
        settings.search_cache_query_ttl = 3600
        settings.search_cache_job_ttl = 14400
        settings.search_cache_max_queries = 100
        settings.search_cache_max_jobs = 500
        settings.openai_api_key = "test"

        cache = SearchCache(settings)
        normalizer = AsyncMock()
        normalizer.normalize = AsyncMock(side_effect=lambda p: p)
        embedding_provider = AsyncMock()
        embedding_provider.embed = AsyncMock(return_value=[[0.1] * 1536])
        ranking_pipeline = AsyncMock()

        from jsc.ranking.pipeline import RankedMatch
        from jsc.schemas.match import MatchExplanation

        mock_explanation = MatchExplanation(
            overall_score=0.8, grade="B+", summary="OK",
            components=[], strengths=[], gaps=[],
        )
        ranking_pipeline.rank = AsyncMock(return_value=[
            RankedMatch(
                job=MagicMock(spec=JobPosting),
                overall_score=0.8,
                component_scores={},
                explanation=mock_explanation,
            )
        ])

        provider = AsyncMock()
        provider.name = "adzuna"
        provider.search = AsyncMock(return_value=_make_search_page(1))

        session = AsyncMock()
        candidate = _make_candidate()
        session.get = AsyncMock(return_value=candidate)

        service = SearchService(
            session=session, settings=settings, cache=cache,
            normalizer=normalizer, embedding_provider=embedding_provider,
            ranking_pipeline=ranking_pipeline,
        )

        query = SearchQuery(keywords="python")

        # First call — provider.search called
        await service.search(query, candidate.id, provider=provider)
        assert provider.search.call_count == 1

        # Second call — should use cache, provider.search NOT called again
        await service.search(query, candidate.id, provider=provider)
        assert provider.search.call_count == 1

    async def test_search_raises_for_missing_candidate(self):
        settings = MagicMock()
        settings.search_cache_query_ttl = 3600
        settings.search_cache_job_ttl = 14400
        settings.search_cache_max_queries = 100
        settings.search_cache_max_jobs = 500

        cache = SearchCache(settings)
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        service = SearchService(
            session=session, settings=settings, cache=cache,
            normalizer=AsyncMock(), embedding_provider=AsyncMock(),
            ranking_pipeline=AsyncMock(),
        )

        query = SearchQuery(keywords="python")
        with pytest.raises(ValueError, match="[Cc]andidate"):
            await service.search(query, uuid4(), provider=AsyncMock())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_search_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jsc.search.service'`

- [ ] **Step 3: Implement SearchService**

Create `src/jsc/search/service.py`:

```python
"""Search service — orchestrates ephemeral search, normalization, and ranking."""

import math
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from jsc.db.models.candidate import Candidate
from jsc.db.models.job import JobPosting, JobSkill
from jsc.ingestion.base import ParsedJob
from jsc.ingestion.fetcher import Fetcher
from jsc.parsing.job_normalizer import JobNormalizer
from jsc.providers.base import EmbeddingProvider
from jsc.ranking.pipeline import RankingPipeline
from jsc.schemas.match import MatchExplanation
from jsc.schemas.search import SearchAttribution, SearchResponse, SearchResultRead
from jsc.search.base import SearchPage, SearchProvider, SearchQuery
from jsc.search.cache import SearchCache
from jsc.utils.url import url_hash

logger = structlog.get_logger()


class SearchService:
    """Orchestrates ephemeral search: provider → normalize → rank → respond."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Any,
        cache: SearchCache,
        normalizer: JobNormalizer,
        embedding_provider: EmbeddingProvider,
        ranking_pipeline: RankingPipeline,
    ) -> None:
        self._session = session
        self._settings = settings
        self._cache = cache
        self._normalizer = normalizer
        self._embedding_provider = embedding_provider
        self._ranking = ranking_pipeline

    async def search(
        self,
        query: SearchQuery,
        candidate_id: UUID,
        provider: SearchProvider,
    ) -> SearchResponse:
        """Execute an ephemeral search, returning ranked results."""
        # Load candidate
        candidate = await self._session.get(Candidate, candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate {candidate_id} not found")

        # Check query cache
        cache_key = f"{provider.name}:{query.cache_key()}"
        cached_page = self._cache.get_query(cache_key)

        if cached_page is not None:
            page = cached_page
        else:
            # Fetch from provider
            async with Fetcher(self._settings) as fetcher:
                page = await provider.search(query, fetcher)
            self._cache.put_query(cache_key, page)

        # Build transient JobPosting objects (check job cache first)
        postings: list[JobPosting] = []
        for parsed in page.results:
            job_url = parsed.metadata.get("url", "")
            j_hash = url_hash(job_url) if job_url else str(uuid4())

            cached_posting = self._cache.get_job(j_hash)
            if cached_posting is not None:
                postings.append(cached_posting)
                continue

            # Normalize
            normalized = await self._normalizer.normalize(parsed)
            posting = _build_transient_posting(normalized, j_hash)
            postings.append(posting)

        # Batch-embed any postings without embeddings
        to_embed = [(i, p) for i, p in enumerate(postings) if p.embedding is None]
        if to_embed and self._settings.openai_api_key:
            texts = [p.description_text for _, p in to_embed]
            try:
                vectors = await self._embedding_provider.embed(texts)
                for (i, posting), vec in zip(to_embed, vectors):
                    posting.embedding = vec
            except Exception:
                logger.warning("search_embedding_failed")

        # Cache processed postings
        for posting in postings:
            j_hash = posting.url_hash
            if self._cache.get_job(j_hash) is None:
                self._cache.put_job(j_hash, posting)

        # Rank
        ranked = await self._ranking.rank(candidate, postings)

        # Build response
        items = []
        for match in ranked:
            job = match.job
            items.append(SearchResultRead(
                id=job.url_hash,
                title=job.title,
                company=job.company,
                location=job.location,
                is_remote=job.is_remote,
                remote_type=job.remote_type,
                seniority=job.seniority,
                posted_at=job.posted_at,
                url=job.url,
                skills=[],
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_currency=job.salary_currency,
                provider=page.provider,
                match_score=match.overall_score,
                match_explanation=match.explanation,
            ))

        attribution = None
        if page.attribution:
            attribution = SearchAttribution(
                text=page.attribution.text,
                url=page.attribution.url,
            )

        total_pages = math.ceil(page.total / query.page_size) if page.total > 0 else 0

        return SearchResponse(
            items=items,
            total=page.total,
            page=query.page,
            page_size=query.page_size,
            pages=total_pages,
            attribution=attribution,
        )


def _build_transient_posting(parsed: ParsedJob, j_hash: str) -> JobPosting:
    """Build an in-memory JobPosting from a ParsedJob. Not attached to any DB session."""
    posting = JobPosting.__new__(JobPosting)
    posting.id = uuid4()
    posting.source_id = None
    posting.external_id = None
    posting.url = parsed.metadata.get("url", "")
    posting.url_hash = j_hash
    posting.title = parsed.title
    posting.company = parsed.company or "Unknown"
    posting.location = parsed.location or ""
    posting.is_remote = (
        "remote" in (parsed.remote_type or "").lower()
        or "remote" in (parsed.location or "").lower()
    )
    posting.remote_type = parsed.remote_type
    posting.seniority = parsed.seniority
    posting.department = parsed.department
    posting.description_text = parsed.description_text or ""
    posting.description_html = parsed.description_html
    posting.salary_min = parsed.salary_min
    posting.salary_max = parsed.salary_max
    posting.salary_currency = parsed.salary_currency
    posting.posted_at = parsed.posted_at
    posting.expires_at = None
    posting.embedding = None
    posting.is_active = True
    posting.dedup_hash = None

    # Build transient skill objects
    posting.skills = []
    for skill_name in parsed.skills:
        skill = JobSkill.__new__(JobSkill)
        skill.id = uuid4()
        skill.job_posting_id = posting.id
        skill.skill_name = skill_name
        skill.is_required = True
        skill.source = "extracted"
        posting.skills.append(skill)

    # Empty relationships the scorers don't use
    posting.source = None
    posting.raw = None
    posting.matches = []

    return posting
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_search_service.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/jsc/search/service.py tests/unit/test_search_service.py
git commit -m "feat: add SearchService orchestrator with caching and ranking"
```

---

## Task 7: API Endpoint + Dependency Injection + Router

**Files:**
- Create: `src/jsc/api/search.py`
- Modify: `src/jsc/dependencies.py`
- Modify: `src/jsc/api/router.py`
- Test: `tests/unit/test_search_api.py`

- [ ] **Step 1: Write failing tests for the search endpoint**

Create `tests/unit/test_search_api.py`:

```python
"""Tests for the GET /api/v1/search endpoint."""

import math
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from jsc.dependencies import get_db_session, get_settings, verify_api_key
from jsc.main import create_app
from jsc.schemas.match import MatchExplanation
from jsc.schemas.search import SearchAttribution, SearchResponse, SearchResultRead
from jsc.search.service import SearchService


def _make_test_settings():
    s = MagicMock()
    s.database_url = "postgresql+asyncpg://test:test@localhost:5432/test"
    s.openai_api_key = "test-key"
    s.api_key = ""
    s.api_cors_origins = ["http://localhost:3000"]
    s.adzuna_app_id = "test-id"
    s.adzuna_app_key = "test-key"
    s.search_cache_query_ttl = 3600
    s.search_cache_job_ttl = 14400
    s.search_cache_max_queries = 100
    s.search_cache_max_jobs = 500
    s.weight_semantic = 0.40
    s.weight_skill_coverage = 0.25
    s.weight_title_match = 0.15
    s.weight_seniority = 0.10
    s.weight_location = 0.10
    s.ingestion_rate_limit_delay = 1.0
    s.ingestion_max_concurrent = 3
    s.ingestion_playwright_enabled = False
    return s


def _mock_search_response(n: int = 2) -> SearchResponse:
    items = []
    for i in range(n):
        items.append(SearchResultRead(
            id=f"hash{i}",
            title=f"Python Developer {i}",
            company=f"Company {i}",
            location="Calgary, AB",
            is_remote=False,
            remote_type=None,
            seniority="mid",
            posted_at=None,
            url=f"https://example.com/jobs/{i}",
            skills=[],
            salary_min=80000,
            salary_max=120000,
            salary_currency="CAD",
            provider="adzuna",
            match_score=0.85 - i * 0.1,
            match_explanation=MatchExplanation(
                overall_score=0.85, grade="A", summary="Good match",
                components=[], strengths=[], gaps=[],
            ),
        ))
    return SearchResponse(
        items=items, total=n, page=1, page_size=20,
        pages=1, attribution=SearchAttribution(text="Jobs by Adzuna", url="https://www.adzuna.com"),
    )


class TestSearchEndpoint:
    async def test_search_returns_200_with_results(self):
        app = create_app()
        app.dependency_overrides[verify_api_key] = lambda: None

        mock_service = AsyncMock(spec=SearchService)
        mock_service.search = AsyncMock(return_value=_mock_search_response(2))

        from jsc.dependencies import get_search_service
        app.dependency_overrides[get_search_service] = lambda: mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            candidate_id = str(uuid4())
            resp = await client.get(
                "/api/v1/search",
                params={"q": "python developer", "candidate_id": candidate_id},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert data["attribution"]["text"] == "Jobs by Adzuna"
        assert data["items"][0]["match_score"] == 0.85

    async def test_search_requires_q_param(self):
        app = create_app()
        app.dependency_overrides[verify_api_key] = lambda: None

        mock_service = AsyncMock(spec=SearchService)
        from jsc.dependencies import get_search_service
        app.dependency_overrides[get_search_service] = lambda: mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/search",
                params={"candidate_id": str(uuid4())},
            )

        assert resp.status_code == 422

    async def test_search_requires_candidate_id(self):
        app = create_app()
        app.dependency_overrides[verify_api_key] = lambda: None

        mock_service = AsyncMock(spec=SearchService)
        from jsc.dependencies import get_search_service
        app.dependency_overrides[get_search_service] = lambda: mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/search",
                params={"q": "python developer"},
            )

        assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_search_api.py -v`
Expected: FAIL (either module import errors or 404 because route doesn't exist)

- [ ] **Step 3: Add dependencies to `dependencies.py`**

Add these imports to the top of `src/jsc/dependencies.py`:

```python
from jsc.search.cache import SearchCache
from jsc.search.service import SearchService
```

Add these functions at the bottom of `src/jsc/dependencies.py`:

```python
@lru_cache
def get_search_cache(
    settings: Settings = Depends(get_settings),
) -> SearchCache:
    return SearchCache(settings)


def get_search_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    cache: SearchCache = Depends(get_search_cache),
    normalizer: JobNormalizer = Depends(get_job_normalizer),
    embedder: EmbeddingProvider = Depends(get_embedding_provider),
    pipeline: RankingPipeline = Depends(get_ranking_pipeline),
) -> SearchService:
    return SearchService(session, settings, cache, normalizer, embedder, pipeline)
```

- [ ] **Step 4: Create the search API endpoint**

Create `src/jsc/api/search.py`:

```python
"""Ephemeral job search endpoint."""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from jsc.dependencies import get_search_service, get_settings, verify_api_key
from jsc.config import Settings
from jsc.schemas.search import SearchResponse
from jsc.search.base import SearchQuery
from jsc.search.registry import get_provider
from jsc.search.service import SearchService

router = APIRouter(
    prefix="/api/v1/search",
    tags=["search"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("", response_model=SearchResponse)
async def search_jobs(
    q: str = Query(..., min_length=1, description="Search keywords"),
    candidate_id: UUID = Query(..., description="Candidate profile ID"),
    location: str | None = Query(None, description="City or region"),
    country: str = Query("ca", description="Two-letter country code"),
    remote_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    service: SearchService = Depends(get_search_service),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    """Search for jobs across external aggregator APIs.

    Results are ranked against the candidate's profile and returned
    without being persisted to the database.
    """
    query = SearchQuery(
        keywords=q,
        location=location,
        country=country,
        remote_only=remote_only,
        page=page,
        page_size=page_size,
    )

    provider = get_provider("adzuna", settings)

    try:
        return await service.search(query, candidate_id, provider=provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
```

- [ ] **Step 5: Register the search router**

Update `src/jsc/api/router.py`:

```python
"""Root router — includes all sub-routers."""

from fastapi import APIRouter

from jsc.api.candidates import router as candidates_router
from jsc.api.jobs import router as jobs_router
from jsc.api.matches import router as matches_router
from jsc.api.search import router as search_router
from jsc.api.system import router as system_router

root_router = APIRouter()
root_router.include_router(system_router)
root_router.include_router(candidates_router)
root_router.include_router(jobs_router)
root_router.include_router(matches_router)
root_router.include_router(search_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/unit/test_search_api.py -v`
Expected: all 3 tests PASS

- [ ] **Step 7: Run the full test suite to check nothing is broken**

Run: `pytest tests/unit/ -v`
Expected: all existing tests still PASS, all new tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/jsc/api/search.py src/jsc/api/router.py src/jsc/dependencies.py tests/unit/test_search_api.py
git commit -m "feat: add GET /api/v1/search endpoint with dependency injection"
```

---

## Task 8: Final Integration Verification

**Files:**
- No new files — verification only.

- [ ] **Step 1: Run the complete test suite**

Run: `pytest tests/ -v`
Expected: all tests PASS, no import errors, no regressions.

- [ ] **Step 2: Verify the app starts**

Run: `python -c "from jsc.main import create_app; app = create_app(); print('OK')"`
Expected: prints `OK` with no import errors.

- [ ] **Step 3: Verify search endpoint appears in OpenAPI**

Run: `python -c "from jsc.main import create_app; app = create_app(); routes = [r.path for r in app.routes]; assert '/api/v1/search' in routes; print('Search route registered')"`
Expected: prints `Search route registered`.

- [ ] **Step 4: Final commit (if any fixes needed)**

Only commit if previous steps required fixes. No empty commits.
