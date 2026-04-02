"""Tests for job normalizer."""

import pytest

from jsc.parsing.job_normalizer import _detect_remote_type, _detect_seniority


class TestDetectSeniority:
    def test_senior_in_title(self):
        assert _detect_seniority("Senior Backend Engineer", "") == "senior"

    def test_lead_in_title(self):
        assert _detect_seniority("Tech Lead", "") == "lead"

    def test_junior_in_description(self):
        assert _detect_seniority("Software Engineer", "entry level position") == "junior"

    def test_no_seniority(self):
        assert _detect_seniority("Software Engineer", "great opportunity") is None


class TestDetectRemoteType:
    def test_fully_remote(self):
        assert _detect_remote_type("", "Remote", "fully remote position") == "full"

    def test_hybrid(self):
        assert _detect_remote_type("", "Edmonton (Hybrid)", "hybrid work") == "hybrid"

    def test_onsite(self):
        assert _detect_remote_type("", "Edmonton", "this is an on-site role") == "onsite"

    def test_remote_in_location(self):
        assert _detect_remote_type("", "Remote", "") == "full"

    def test_no_info(self):
        assert _detect_remote_type("Engineer", "Edmonton", "great company") is None
