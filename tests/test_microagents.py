"""Tests for agent/microagents.py — OpenHands-compatible microagents."""
from __future__ import annotations

import inspect
from pathlib import Path

from agent.microagents import (
    Microagent,
    load_microagents,
    match_microagents,
    microagents_block,
)


def _write_agent(root: Path, filename: str, body: str) -> Path:
    directory = root / ".openhands" / "microagents"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(body, encoding="utf-8")
    return path


_KNOWLEDGE_AGENT = """---
name: kubernetes
type: knowledge
triggers:
- kubernetes
- k8s
---

Use kubectl with the staging context only.
"""

_REPO_AGENT = """---
name: repo
type: repo
---

Always run pytest before committing.
"""


def test_load_parses_frontmatter_and_content(tmp_path: Path) -> None:
    _write_agent(tmp_path, "kubernetes.md", _KNOWLEDGE_AGENT)
    agents = load_microagents(tmp_path)
    assert len(agents) == 1
    agent = agents[0]
    assert agent.name == "kubernetes"
    assert agent.type == "knowledge"
    assert agent.triggers == ["kubernetes", "k8s"]
    assert "kubectl" in agent.content


def test_missing_directory_returns_empty(tmp_path: Path) -> None:
    assert load_microagents(tmp_path) == []
    assert microagents_block("anything", root=tmp_path) == ""


def test_knowledge_agent_triggers_case_insensitively(tmp_path: Path) -> None:
    _write_agent(tmp_path, "kubernetes.md", _KNOWLEDGE_AGENT)
    agents = load_microagents(tmp_path)
    assert match_microagents("Deploy to KUBERNETES please", agents)
    assert match_microagents("check the k8s cluster", agents)
    assert match_microagents("update the README", agents) == []


def test_short_trigger_requires_word_boundary(tmp_path: Path) -> None:
    agent = Microagent(name="gh", type="knowledge", triggers=["pr"])
    assert agent.matches("raise a PR for this")
    assert not agent.matches("sprint planning session")


def test_repo_agent_always_matches(tmp_path: Path) -> None:
    _write_agent(tmp_path, "repo.md", _REPO_AGENT)
    _write_agent(tmp_path, "kubernetes.md", _KNOWLEDGE_AGENT)
    matched = match_microagents("totally unrelated task", load_microagents(tmp_path))
    assert [a.name for a in matched] == ["repo"]


def test_repo_agents_sort_before_knowledge_agents(tmp_path: Path) -> None:
    _write_agent(tmp_path, "repo.md", _REPO_AGENT)
    _write_agent(tmp_path, "kubernetes.md", _KNOWLEDGE_AGENT)
    matched = match_microagents("fix k8s deploy", load_microagents(tmp_path))
    assert [a.name for a in matched] == ["repo", "kubernetes"]


def test_block_formats_matched_agents(tmp_path: Path) -> None:
    _write_agent(tmp_path, "repo.md", _REPO_AGENT)
    block = microagents_block("any task", root=tmp_path)
    assert "### repo" in block
    assert "pytest" in block


def test_block_caps_total_size(tmp_path: Path) -> None:
    for i in range(10):
        _write_agent(
            tmp_path,
            f"big{i}.md",
            f"---\nname: big{i}\ntype: repo\n---\n\n{'x' * 2000}\n",
        )
    block = microagents_block("task", root=tmp_path)
    assert 0 < len(block) <= 4200


def test_malformed_files_are_skipped(tmp_path: Path) -> None:
    _write_agent(tmp_path, "no_frontmatter.md", "just plain markdown")
    _write_agent(tmp_path, "bad_yaml.md", "---\n[unclosed\n---\n\nbody\n")
    _write_agent(tmp_path, "no_triggers.md", "---\nname: x\ntype: knowledge\n---\n\nbody\n")
    _write_agent(tmp_path, "good.md", _REPO_AGENT)
    agents = load_microagents(tmp_path)
    assert [a.name for a in agents] == ["repo"]


def test_committed_repo_microagents_parse() -> None:
    """The microagents shipped in this repo must always parse."""
    repo_root = Path(__file__).resolve().parents[1]
    agents = load_microagents(repo_root)
    names = {a.name for a in agents}
    assert {"repo", "github", "testing", "changelog"} <= names
    repo_agents = [a for a in agents if a.type == "repo"]
    assert len(repo_agents) == 1


def test_planner_wires_microagents_block() -> None:
    """_generate_plan injects the microagents block into the system prompt."""
    import agent.loop as loop_module

    source = inspect.getsource(loop_module.AgentRunner._generate_plan)
    assert "microagents_block" in source
    assert "self.tools.root" in source
