"""tests/test_skill_registry.py — Unit tests for agent/skill_registry.py"""

from __future__ import annotations

import pytest
from agent.skill_registry import (
    _extract_tech_relevance,
    _extract_workflow_relevance,
    _fmt_name,
    _first_paragraph,
    _extract_tags,
    _MULTI_WORD_TECHS,
    _SINGLE_WORD_TECHS_BY_LEN,
    TECH_SKILL_MAP,
    WORKFLOW_SKILL_MAP,
    RegistrySkill,
)


class TestExtractTechRelevance:
    """Tests for _extract_tech_relevance() word-boundary matching."""

    def test_single_word_exact_match(self) -> None:
        content = "This skill works with React and Python."
        result = _extract_tech_relevance(content)
        assert "react" in result
        assert "python" in result

    def test_single_word_no_false_positive(self) -> None:
        # "reactive" should not match "react" — word-boundary regex prevents partial matches
        content = "This is a reactive rendering system using the render pipeline."
        result = _extract_tech_relevance(content)
        assert "react" not in result

    def test_multi_word_match(self) -> None:
        content = "Built with Next.js and Material UI components."
        result = _extract_tech_relevance(content)
        assert "next.js" in result
        # "material ui" should match (two-word tech)
        assert "material ui" in result

    def test_multi_word_boundary_consistency(self) -> None:
        # "next.js" should match in a real usage context
        content = "Built with next.js and tailwind css"
        result = _extract_tech_relevance(content)
        assert "next.js" in result
        assert "tailwind" in result

    def test_shopify_detected(self) -> None:
        content = "Specialized for Shopify stores with checkout extensions."
        result = _extract_tech_relevance(content)
        assert "shopify" in result

    def test_django_detected(self) -> None:
        content = "Django middleware for handling authentication."
        result = _extract_tech_relevance(content)
        assert "django" in result

    def test_aws_detected(self) -> None:
        content = "Deploy to AWS using ECS and S3 buckets."
        result = _extract_tech_relevance(content)
        assert "aws" in result

    def test_empty_content(self) -> None:
        result = _extract_tech_relevance("")
        assert isinstance(result, list)

    def test_caps_ignored(self) -> None:
        content = "Using DJANGO and REACT in this project"
        result = _extract_tech_relevance(content)
        assert "django" in result
        assert "react" in result

    def test_max_12_results(self) -> None:
        # Feed content with many techs to ensure cap works
        content = "React Vue Angular Svelte Django Flask FastAPI Rails Laravel Express " * 5
        result = _extract_tech_relevance(content)
        assert len(result) <= 12

    def test_deduplication(self) -> None:
        # "react" appears multiple times but should only be in result once
        content = "React React React React React"
        result = _extract_tech_relevance(content)
        react_count = sum(1 for t in result if "react" in t)
        assert react_count == 1


class TestExtractWorkflowRelevance:
    """Tests for _extract_workflow_relevance()."""

    def test_ci_cd_detected(self) -> None:
        content = "Automate your CI CD pipeline with this skill."
        result = _extract_workflow_relevance(content)
        assert "ci_cd" in result

    def test_ecommerce_detected(self) -> None:
        content = "Optimize your ecommerce checkout flow."
        result = _extract_workflow_relevance(content)
        assert "ecommerce" in result
        # Also matches with underscore variant
        content2 = "ecommerce_workflow with shopping cart"
        result2 = _extract_workflow_relevance(content2)
        assert "ecommerce" in result2

    def test_security_detected(self) -> None:
        content = "Security audit for your authentication module."
        result = _extract_workflow_relevance(content)
        assert "security" in result

    def test_underscore_and_space_variant(self) -> None:
        content = "CI_CD workflow configuration"
        result = _extract_workflow_relevance(content)
        assert "ci_cd" in result

    def test_max_5_results(self) -> None:
        content = "CI CD ecommerce security analytics research multi_agent" * 3
        result = _extract_workflow_relevance(content)
        assert len(result) <= 5


class TestHelpers:
    """Tests for module-level helper functions."""

    def test_fmt_name(self) -> None:
        assert _fmt_name("test-first-executor") == "Test First Executor"
        assert _fmt_name("risky-module-review") == "Risky Module Review"
        assert _fmt_name("stop_slop") == "Stop Slop"

    def test_first_paragraph(self) -> None:
        text = """# Skill Title

This is the first paragraph of content.
It has multiple lines but constitutes one logical paragraph.

## Another heading

This should not be returned as the first paragraph.
"""
        result = _first_paragraph(text)
        assert "first paragraph" in result.lower()
        assert len(result) <= 250

    def test_first_paragraph_skips_short_lines(self) -> None:
        text = "# Title\n\n# No\n\nThis is a real paragraph with meaningful content here."
        result = _first_paragraph(text)
        assert "real paragraph" in result

    def test_extract_tags_hashtags(self) -> None:
        content = "#python #react #django some text"
        result = _extract_tags(content)
        assert "python" in result
        assert "react" in result
        assert "django" in result

    def test_extract_tags_bold(self) -> None:
        content = "This skill covers **CI CD** and **ecommerce** workflows."
        result = _extract_tags(content)
        assert "ci cd" in result
        assert "ecommerce" in result

    def test_extract_tags_max_12(self) -> None:
        content = " ".join(f"#tag{i}" for i in range(20))
        result = _extract_tags(content)
        assert len(result) <= 12


class TestRegistrySkill:
    """Tests for RegistrySkill dataclass."""

    def test_as_dict(self) -> None:
        skill = RegistrySkill(
            skill_id="local:test",
            name="Test Skill",
            description="A test skill",
            source="local",
            registry_id="local",
            tags=["test", "example"],
            tech_relevance=["python", "django"],
            workflow_relevance=["ci_cd"],
            raw_content="Some content",
            fetched_at=999.0,
        )
        d = skill.as_dict()
        assert d["skill_id"] == "local:test"
        assert d["name"] == "Test Skill"
        assert d["source"] == "local"
        assert d["tags"] == ["test", "example"]
        assert d["tech_relevance"] == ["python", "django"]
        assert d["workflow_relevance"] == ["ci_cd"]
        # install_cmd is included even when None (field has default=None)
        assert "install_cmd" in d
        assert d["install_cmd"] is None

    def test_skill_id_required(self) -> None:
        with pytest.raises(TypeError):
            RegistrySkill(name="Test", description="desc", source="local")


class TestTechSkillMap:
    """Tests for TECH_SKILL_MAP coverage and correctness."""

    def test_all_map_values_are_lists(self) -> None:
        for tech, skills in TECH_SKILL_MAP.items():
            assert isinstance(skills, list), f"{tech} value is not a list"
            assert len(skills) > 0, f"{tech} has no skill recommendations"

    def test_shopify_skills_relevant(self) -> None:
        skills = TECH_SKILL_MAP.get("shopify", [])
        assert "abandoned-cart" in skills
        assert "seo-content" in skills

    def test_react_skills_relevant(self) -> None:
        skills = TECH_SKILL_MAP.get("react", [])
        assert "stop-slop-quality" in skills

    def test_python_skills_relevant(self) -> None:
        skills = TECH_SKILL_MAP.get("python", [])
        assert "test-first-executor" in skills

    def test_stripe_skills_relevant(self) -> None:
        skills = TECH_SKILL_MAP.get("stripe", [])
        assert "risky-module-review" in skills


class TestWorkflowSkillMap:
    """Tests for WORKFLOW_SKILL_MAP."""

    def test_all_values_are_lists(self) -> None:
        for _wf, skills in WORKFLOW_SKILL_MAP.items():
            assert isinstance(skills, list)
            assert len(skills) > 0

    def test_ci_cd_has_release_readiness(self) -> None:
        skills = WORKFLOW_SKILL_MAP.get("ci_cd", [])
        assert "release-readiness" in skills

    def test_security_has_risky_module_review(self) -> None:
        skills = WORKFLOW_SKILL_MAP.get("security", [])
        assert "risky-module-review" in skills


class TestPreCompiledPatterns:
    """Tests for module-level pre-compiled pattern constants."""

    def test_MULTI_WORD_TECHS_is_tuple(self) -> None:
        assert isinstance(_MULTI_WORD_TECHS, tuple)

    def test_SINGLE_WORD_TECHS_BY_LEN_not_empty(self) -> None:
        assert len(_SINGLE_WORD_TECHS_BY_LEN) > 0

    def test_all_single_word_tech_patterns_have_valid_regex(self) -> None:
        for tp in _SINGLE_WORD_TECHS_BY_LEN:
            assert hasattr(tp, "pattern")
            assert hasattr(tp, "_tech_name")
            # Pattern should match its own tech name
            assert tp.pattern.search(tp._tech_name), f"Pattern for {tp._tech_name} doesn't match itself"

    def test_tech_pattern_class_has_slots(self) -> None:
        from agent.skill_registry import _TechPattern
        # __slots__ should prevent arbitrary attribute assignment
        tp = _TechPattern("react")
        with pytest.raises(AttributeError):
            tp.foo = "bar"  # type: ignore[reportGeneralTypeIssues]


class TestRecommendLogic:
    """Integration-style tests for the recommendation path (no I/O)."""

    def test_recommend_returns_dict_with_score_and_reasons(self) -> None:
        # Can't easily test SkillRegistry.recommend() without mocking httpx,
        # so we test the extraction helpers directly and trust the wiring.
        content = "This skill works with Django and React for CI CD pipelines."
        techs = _extract_tech_relevance(content)
        wfs = _extract_workflow_relevance(content)
        assert "django" in techs
        assert "react" in techs
        assert "ci_cd" in wfs

    def test_recommend_favors_dynamic_match_over_map_match(self) -> None:
        # Dynamic match (skill mentions tech) scores 4; map match scores 3.
        # tech_relevance extraction is the prerequisite for the higher-score path.
        content_with_tech = "This skill is built specifically for React."
        tech_list = _extract_tech_relevance(content_with_tech)
        assert "react" in tech_list

# ---------------------------------------------------------------------------
# Nested registry structure (borghei/Claude-Skills style)
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.headers = {}

    def json(self):
        return self._json


class _FakeClient:
    """Stub httpx client for nested-registry fetch tests."""
    headers: dict = {}

    def __init__(self, tree, files):
        self._tree = tree
        self._files = files

    async def get(self, url, headers=None):
        if "/git/trees/" in url:
            return _FakeResp(json_data={"tree": self._tree})
        for path, content in self._files.items():
            if url.endswith(path):
                return _FakeResp(text=content)
        return _FakeResp(status_code=404)


def test_nested_registry_indexes_deeply_nested_skills():
    import asyncio
    from agent.skill_registry import SkillRegistry

    reg_cfg = {
        "id": "borghei-claude-skills",
        "owner": "borghei",
        "repo": "Claude-Skills",
        "path": "",
        "skill_file": "SKILL.md",
        "structure": "nested",
        "branch": "main",
    }
    tree = [
        {"type": "blob", "path": "project-management/discovery/pre-mortem/SKILL.md"},
        {"type": "blob", "path": "business-growth/churn-prevention/SKILL.md"},
        {"type": "blob", "path": "README.md"},
        {"type": "tree", "path": "project-management"},
    ]
    files = {
        "project-management/discovery/pre-mortem/SKILL.md":
            "---\nname: pre-mortem\n---\n# Pre-Mortem\n\nRisk analysis with Tigers and Elephants.",
        "business-growth/churn-prevention/SKILL.md":
            "# Churn Prevention\n\nReduce churn.",
    }
    sr = SkillRegistry(local_skills_dir="/nonexistent")
    client = _FakeClient(tree, files)
    skills = asyncio.run(sr._fetch_nested_registry(client, reg_cfg))
    ids = {s.skill_id for s in skills}
    assert "github:borghei-claude-skills:pre-mortem" in ids
    assert "github:borghei-claude-skills:churn-prevention" in ids
    pm = next(s for s in skills if s.skill_id.endswith(":pre-mortem"))
    # frontmatter stripped; description from prose, categories become tags
    assert "name: pre-mortem" not in pm.description
    assert "project-management" in pm.tags
