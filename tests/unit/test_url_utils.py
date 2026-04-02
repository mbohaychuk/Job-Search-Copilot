"""Tests for URL normalization and hashing."""

from jsc.utils.url import dedup_hash, normalize_url, url_hash


class TestNormalizeUrl:
    def test_strips_tracking_params(self):
        url = "https://example.com/jobs/123?utm_source=linkedin&utm_medium=social"
        assert normalize_url(url) == "https://example.com/jobs/123"

    def test_strips_trailing_slash(self):
        assert normalize_url("https://example.com/jobs/") == "https://example.com/jobs"

    def test_lowercases_scheme_and_host(self):
        assert normalize_url("HTTPS://Example.COM/Jobs") == "https://example.com/Jobs"

    def test_preserves_meaningful_params(self):
        url = "https://example.com/search?q=python&page=2"
        normalized = normalize_url(url)
        assert "q=python" in normalized
        assert "page=2" in normalized

    def test_keeps_root_path(self):
        assert normalize_url("https://example.com/") == "https://example.com/"


class TestUrlHash:
    def test_same_url_same_hash(self):
        assert url_hash("https://example.com/jobs/1") == url_hash("https://example.com/jobs/1")

    def test_different_url_different_hash(self):
        assert url_hash("https://example.com/jobs/1") != url_hash("https://example.com/jobs/2")

    def test_ignores_tracking_params(self):
        assert url_hash("https://example.com/jobs/1") == url_hash(
            "https://example.com/jobs/1?utm_source=test"
        )


class TestDedupHash:
    def test_same_inputs_same_hash(self):
        h1 = dedup_hash("Backend Engineer", "ACME", "Edmonton")
        h2 = dedup_hash("Backend Engineer", "ACME", "Edmonton")
        assert h1 == h2

    def test_case_insensitive(self):
        h1 = dedup_hash("Backend Engineer", "ACME", "Edmonton")
        h2 = dedup_hash("backend engineer", "acme", "edmonton")
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        h1 = dedup_hash("Backend Engineer", "ACME", "Edmonton")
        h2 = dedup_hash("Frontend Engineer", "ACME", "Edmonton")
        assert h1 != h2
