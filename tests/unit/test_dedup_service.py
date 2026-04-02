"""Tests for dedup service logic."""

from jsc.services.dedup_service import _jaccard_bigrams


class TestJaccardBigrams:
    def test_identical_texts(self):
        text = "the quick brown fox jumps over the lazy dog"
        assert _jaccard_bigrams(text, text) == 1.0

    def test_completely_different(self):
        a = "python backend engineer needed"
        b = "marketing manager required immediately"
        score = _jaccard_bigrams(a, b)
        assert score < 0.1

    def test_similar_texts(self):
        a = "senior backend engineer python postgresql docker"
        b = "senior backend engineer python postgresql kubernetes"
        score = _jaccard_bigrams(a, b)
        assert score > 0.5

    def test_short_text(self):
        assert _jaccard_bigrams("hello", "world") == 0.0
