"""Tests for agent/skills.py — Skill Library."""
from pathlib import Path

from agent.skills import Skill, SkillLibrary


def test_empty_library():
    lib = SkillLibrary(skills_dir="/nonexistent_dir_xyz")
    assert lib.list() == []


def test_index_local_skills():
    # Uses the real .claude/skills directory if it exists
    lib = SkillLibrary()
    skills = lib.list(source="local")
    # The repo has at least a few skills; if dir missing, just assert empty list is ok
    assert isinstance(skills, list)


def test_search_by_name():
    lib = SkillLibrary()
    lib.register_mcp(name="test-runner", description="Runs tests and reports", content="")
    results = lib.search("runner")
    assert any(s.skill_id == "mcp:test-runner" for s in results)


def test_search_by_description():
    lib = SkillLibrary()
    lib.register_mcp(name="foo", description="Unique keyword xyzzy123", content="")
    results = lib.search("xyzzy123")
    assert len(results) == 1


def test_extract_description_skips_yaml_frontmatter():
    """Regression: frontmatter (--- ... ---) must not surface as '---'."""
    markdown = (
        "---\nname: some-skill\ndescription: A real description here.\n---\n"
        "# Some Skill\n\nA real description here.\n"
    )
    result = SkillLibrary._extract_description(markdown)
    assert result != "---"
    assert "real description" in result.lower()


def test_search_no_results():
    lib = SkillLibrary()
    results = lib.search("zzz_no_match_zzz")
    assert results == []


def test_register_mcp():
    lib = SkillLibrary()
    skill = lib.register_mcp(name="deploy", description="Deploy to cloud", tags=["ops"])
    assert skill.skill_id == "mcp:deploy"
    assert skill.source == "mcp"


def test_get_skill():
    lib = SkillLibrary()
    lib.register_mcp(name="lint", description="Linting skill")
    skill = lib.get("mcp:lint")
    assert skill is not None
    assert skill.name == "lint"


def test_get_missing_returns_none():
    lib = SkillLibrary()
    assert lib.get("local:nope") is None


def test_list_by_source():
    lib = SkillLibrary(skills_dir="/nonexistent_xyz")
    lib.register_mcp(name="m1", description="")
    lib.register_mcp(name="m2", description="")
    mcp_skills = lib.list(source="mcp")
    assert len(mcp_skills) == 2
    assert all(s.source == "mcp" for s in mcp_skills)


def test_as_dict():
    lib = SkillLibrary()
    s = lib.register_mcp(name="x", description="X skill", tags=["t1"])
    d = s.as_dict()
    assert "skill_id" in d
    assert "source" in d
    assert d["tags"] == ["t1"]


def test_index_follows_symlinked_skill_dirs(tmp_path):
    """Regression: generic skills live in harness/skills/ and are symlinked into
    .claude/skills/. Path.rglob skips symlinked dirs, which hid them all."""
    real = tmp_path / "harness" / "skills" / "linked-skill"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("---\nname: linked-skill\ndescription: Linked.\n---\nBody\n")
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "linked-skill").symlink_to(real, target_is_directory=True)
    lib = SkillLibrary(skills_dir=skills_dir)
    assert lib.get("local:linked-skill") is not None


def test_repo_harness_skills_are_indexed():
    """Every harness skill is reachable through the default .claude/skills dir."""
    repo = Path(__file__).resolve().parent.parent
    lib = SkillLibrary(skills_dir=repo / ".claude" / "skills")
    for skill_md in (repo / "harness" / "skills").glob("*/SKILL.md"):
        assert lib.get(f"local:{skill_md.parent.name}") is not None, skill_md.parent.name


def test_harness_skill_index_is_current():
    """harness/skills/README.md is generated; a new or edited skill must refresh it."""
    import importlib.util

    repo = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "index_skills", repo / "harness" / "scripts" / "index_skills.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    current = (repo / "harness" / "skills" / "README.md").read_text(encoding="utf-8")
    assert current == module.render(), "run: python harness/scripts/index_skills.py"
