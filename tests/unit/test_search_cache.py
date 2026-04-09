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
