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
