"""Tests for the skill taxonomy."""

from jsc.parsing.skill_taxonomy import SkillTaxonomy


class TestSkillTaxonomy:
    def setup_method(self):
        self.taxonomy = SkillTaxonomy()

    def test_canonicalize_exact(self):
        assert self.taxonomy.canonicalize("Python") == "Python"

    def test_canonicalize_alias(self):
        assert self.taxonomy.canonicalize("postgres") == "PostgreSQL"
        assert self.taxonomy.canonicalize("js") == "JavaScript"
        assert self.taxonomy.canonicalize("k8s") == "Kubernetes"

    def test_canonicalize_case_insensitive(self):
        assert self.taxonomy.canonicalize("PYTHON") == "Python"
        assert self.taxonomy.canonicalize("react.js") == "React"

    def test_canonicalize_unknown_returns_none(self):
        assert self.taxonomy.canonicalize("madeupskill123") is None

    def test_canonicalize_or_keep(self):
        assert self.taxonomy.canonicalize_or_keep("postgres") == "PostgreSQL"
        assert self.taxonomy.canonicalize_or_keep("UnknownTool") == "UnknownTool"

    def test_is_known(self):
        assert self.taxonomy.is_known("python")
        assert not self.taxonomy.is_known("madeupskill123")

    def test_find_skills_in_text(self):
        text = "We need someone with Python, PostgreSQL, and Docker experience"
        skills = self.taxonomy.find_skills_in_text(text)
        assert "Python" in skills
        assert "PostgreSQL" in skills
        assert "Docker" in skills

    def test_find_skills_avoids_short_false_positives(self):
        text = "We are looking for a good candidate with experience"
        skills = self.taxonomy.find_skills_in_text(text)
        # "Go" should not match "good"
        assert "Go" not in skills

    def test_all_canonical_returns_set(self):
        canonical = self.taxonomy.all_canonical
        assert isinstance(canonical, set)
        assert "Python" in canonical
        assert len(canonical) > 50
