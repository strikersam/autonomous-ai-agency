"""Quick notes must be judged on their linked source, never on its URL slug.

Quick notes #1569 (DeusData/codebase-memory-mcp) and #1570
(msitarzewski/agency-agents) were both *rejected* by the architect pass while
their draft PRs said "NOT FETCHED": fetch_url.py could not read a GitHub
repository page, and nothing stopped a verdict reached without the source.

Two fixes, tested here:
  * github_source.py reads repositories and files through the GitHub API and
    raw host instead of scraping the HTML page;
  * generate_context.apply_source_gate turns any verdict on an unread quick
    note into ``unverified`` — neither buried (reject) nor built from a guess.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".github" / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


gs = _load("github_source")


class _FakeGitHub:
    """Serves canned responses by URL and records what was requested."""

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.requested: list[str] = []

    def __call__(self, url: str) -> str | None:
        self.requested.append(url)
        return self.responses.get(url)


README = "# Codebase memory\n\n[![CI](https://x/b.svg)](https://x)\n\n" + "Real prose. " * 60


class TestParse:
    @pytest.mark.parametrize("url,owner,repo", [
        ("https://github.com/DeusData/codebase-memory-mcp", "DeusData", "codebase-memory-mcp"),
        ("https://github.com/msitarzewski/agency-agents/", "msitarzewski", "agency-agents"),
        ("https://github.com/a/b.git", "a", "b"),
        ("https://github.com/a/b/tree/dev", "a", "b"),
    ])
    def test_repository_urls(self, url: str, owner: str, repo: str) -> None:
        parts = gs.parse(url)
        assert parts is not None
        assert (parts["owner"], parts["repo"]) == (owner, repo)

    @pytest.mark.parametrize("url", [
        "https://github.com/strikersam/autonomous-ai-agency/issues/1565",
        "https://github.com/a/b/pull/3",
        "https://github.com/a/b/actions/runs/1",
        "https://github.com/orgs/foo/b",
        "https://example.com/a/b",
        "https://github.com/a/b/blob/main/../../etc/passwd",
    ])
    def test_everything_else_falls_through(self, url: str) -> None:
        assert gs.parse(url) is None


class TestFetch:
    def test_repository_reads_metadata_listing_and_readme(self) -> None:
        meta = {"full_name": "DeusData/codebase-memory-mcp", "description": "Code graph MCP",
                "topics": ["mcp"], "language": "C", "stargazers_count": 5,
                "license": {"spdx_id": "MIT"}, "default_branch": "main"}
        fake = _FakeGitHub({
            f"{gs.API}/repos/DeusData/codebase-memory-mcp": json.dumps(meta),
            f"{gs.API}/repos/DeusData/codebase-memory-mcp/contents/?ref=main": json.dumps(
                [{"name": "src", "type": "dir"}, {"name": "README.md", "type": "file"}]),
            f"{gs.RAW}/DeusData/codebase-memory-mcp/main/README.md": README,
        })
        text = gs.fetch_github_source("https://github.com/DeusData/codebase-memory-mcp", fake)
        assert "Description: Code graph MCP" in text
        assert "License: MIT" in text
        assert "Top-level files: README.md, src/" in text
        assert "Real prose." in text
        assert "[![CI]" not in text, "badge rows waste the context budget"
        assert all(u.startswith((gs.API, gs.RAW)) for u in fake.requested)

    def test_readme_is_found_without_the_api(self) -> None:
        """The API is rate-limited; the README alone still grounds a verdict."""
        fake = _FakeGitHub({f"{gs.RAW}/a/b/HEAD/README.md": README})
        text = gs.fetch_github_source("https://github.com/a/b", fake)
        assert "Real prose." in text

    def test_no_readme_is_a_failure(self) -> None:
        """Metadata alone is not the source — let other strategies try."""
        fake = _FakeGitHub({f"{gs.API}/repos/a/b": json.dumps({"full_name": "a/b"})})
        assert gs.fetch_github_source("https://github.com/a/b", fake) == ""

    def test_blob_reads_the_raw_file(self) -> None:
        fake = _FakeGitHub({f"{gs.RAW}/a/b/main/docs/x.md": "file body"})
        text = gs.fetch_github_source("https://github.com/a/b/blob/main/docs/x.md", fake)
        assert text.endswith("file body")
        assert fake.requested == [f"{gs.RAW}/a/b/main/docs/x.md"]


class TestSourceGate:
    @pytest.fixture(scope="class")
    @classmethod
    def gc(cls):
        return _load("generate_context")

    @pytest.mark.parametrize("verdict", ["reject", "adopt", "adapt", ""])
    def test_any_verdict_on_an_unread_quick_note_becomes_unverified(self, gc, verdict) -> None:
        result = gc.apply_source_gate(
            {"verdict": verdict, "verdict_reason": "guess"}, "https://github.com/a/b", False
        )
        assert result["verdict"] == "unverified"
        assert f"`{verdict or 'missing'}`" in result["verdict_reason"]

    def test_a_read_source_keeps_its_verdict(self, gc) -> None:
        result = gc.apply_source_gate({"verdict": "reject"}, "https://github.com/a/b", True)
        assert result["verdict"] == "reject"

    def test_no_url_keeps_its_verdict(self, gc) -> None:
        assert gc.apply_source_gate({"verdict": "adopt"}, None, False)["verdict"] == "adopt"

    @pytest.mark.parametrize("title,labels,body,expected", [
        ("quick-note:https://github.com/a/b", [], "", True),
        ("anything", ["quick-note"], "", True),
        ("anything", [], "URL: https://x\n\nTask: read it", True),
        ("Routine backlog — 2026-W39", ["routine-backlog"], "See https://x for context", False),
    ])
    def test_only_quick_notes_are_gated(self, gc, title, labels, body, expected) -> None:
        assert gc.is_quick_note(title, labels, body) is expected

    def test_unverified_renders_as_a_decision_not_a_plan(self, gc) -> None:
        result = gc.apply_source_gate({"verdict": "reject"}, "https://x", False)
        md = gc._build_pr_description(
            "1", "t", result, {"url": "https://x", "source_fetched": False}, ""
        )
        assert "UNVERIFIED" in md
        assert "## TODO List" not in md


class TestWorkflowWiring:
    @pytest.fixture(scope="class")
    @classmethod
    def steps(cls) -> list[dict]:
        wf = yaml.safe_load((REPO_ROOT / ".github/workflows/issue-context-generator.yml").read_text())
        return wf["jobs"]["generate-context"]["steps"]

    def test_unverified_never_dispatches_an_implementation(self, steps) -> None:
        dispatch = next(s for s in steps if "dispatch" in (s.get("name") or "").lower()
                        and "Comment +" in s.get("name", ""))
        assert "verdict != 'unverified'" in dispatch["if"]

    def test_unverified_is_labelled_needs_source(self, steps) -> None:
        step = next(s for s in steps if "verdict == 'unverified'" in (s.get("if") or ""))
        assert "quick-note:needs-source" in step["run"]
        assert "quick-note:rejected" not in step["run"]

    def test_the_sweep_skips_needs_source(self) -> None:
        text = (REPO_ROOT / ".github/workflows/process-quick-note.yml").read_text()
        assert '"quick-note:needs-source"' in text

    def test_bulk_workflow_carries_the_github_fetcher(self) -> None:
        text = (REPO_ROOT / ".github/workflows/bulk-issue-context.yml").read_text()
        assert "cp .github/scripts/github_source.py /tmp/github_source.py" in text
