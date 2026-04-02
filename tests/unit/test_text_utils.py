"""Tests for text utilities."""

from jsc.utils.text import extract_years_experience, normalize_whitespace


class TestNormalizeWhitespace:
    def test_collapses_spaces(self):
        assert normalize_whitespace("hello   world") == "hello world"

    def test_limits_newlines(self):
        assert normalize_whitespace("a\n\n\n\nb") == "a\n\nb"

    def test_strips(self):
        assert normalize_whitespace("  hello  ") == "hello"


class TestExtractYearsExperience:
    def test_plus_years(self):
        assert extract_years_experience("5+ years experience") == 5

    def test_range_years(self):
        assert extract_years_experience("3-5 years of experience required") == 3

    def test_no_match(self):
        assert extract_years_experience("looking for a great developer") is None

    def test_case_insensitive(self):
        assert extract_years_experience("7+ Years Experience") == 7
