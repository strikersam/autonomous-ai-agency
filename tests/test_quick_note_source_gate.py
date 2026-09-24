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

import base64
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
            f"{gs.API}/repos/DeusData/codebase-memory-mcp/contents?ref=main": json.dumps(
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

    def test_readme_comes_from_the_api_whatever_its_name(self) -> None:
        """README.markdown etc. are not guessable on the raw host; the API
        readme endpoint resolves any spelling."""
        body = {"encoding": "base64", "content": base64.b64encode(README.encode()).decode()}
        fake = _FakeGitHub({f"{gs.API}/repos/a/b/readme?ref=HEAD": json.dumps(body)})
        text = gs.fetch_github_source("https://github.com/a/b", fake)
        assert "Real prose." in text
        assert not any(u.startswith(gs.RAW) for u in fake.requested)

    def test_tree_url_reads_that_directory(self) -> None:
        """A /tree/<ref>/<path> link is about that directory, not the repo root."""
        body = {"encoding": "base64", "content": base64.b64encode(b"Sub readme prose").decode()}
        fake = _FakeGitHub({
            f"{gs.API}/repos/a/b/contents/pkg/sub?ref=dev": json.dumps([{"name": "x.py"}]),
            f"{gs.API}/repos/a/b/readme/pkg/sub?ref=dev": json.dumps(body),
        })
        text = gs.fetch_github_source("https://github.com/a/b/tree/dev/pkg/sub", fake)
        assert "Files in pkg/sub: x.py" in text
        assert "Sub readme prose" in text

    def test_tree_readme_falls_back_to_the_raw_host_under_the_path(self) -> None:
        fake = _FakeGitHub({f"{gs.RAW}/a/b/dev/pkg/README.md": "Raw sub prose"})
        text = gs.fetch_github_source("https://github.com/a/b/tree/dev/pkg", fake)
        assert "Raw sub prose" in text

    def test_malformed_api_readme_falls_back(self) -> None:
        fake = _FakeGitHub({
            f"{gs.API}/repos/a/b/readme?ref=HEAD": "not json",
            f"{gs.RAW}/a/b/HEAD/README.md": README,
        })
        assert "Real prose." in gs.fetch_github_source("https://github.com/a/b", fake)

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

    def test_a_slug_written_summary_and_prompt_do_not_survive(self, gc) -> None:
        result = gc.apply_source_gate(
            {"verdict": "adopt", "source_summary": "A great tool that...",
             "prompt": "Build the thing"}, "https://github.com/a/b", False)
        assert "could not be read" in result["source_summary"]
        assert "great tool" not in result["source_summary"]
        assert result["prompt"] == ""

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


class TestImplementSideGate:
    """scripts/context_plan_gate.py is the second line: process-quick-note reads
    the plan before building. It must name `unverified` and must not label an
    unread note `quick-note:rejected` (which buried #1569 / #1570)."""

    def test_unverified_is_recognised_and_blocks_with_its_own_reason(self) -> None:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        gc = _load("generate_context")
        import context_plan_gate as gate

        doc = f"## Decision\n\n{gc.VERDICT_BADGES['unverified']}\n"
        decision = gate.evaluate(doc)
        assert decision.verdict == "unverified"
        assert decision.may_implement is False
        assert "could not be read" in decision.reason

    def test_block_step_uses_needs_source_for_an_unread_plan(self) -> None:
        wf = yaml.safe_load((REPO_ROOT / ".github/workflows/process-quick-note.yml").read_text())
        steps = next(iter(wf["jobs"].values()))["steps"]
        step = next(s for s in steps if s.get("id") == "plan_blocked")
        run = step["run"]
        assert 'LABEL="quick-note:needs-source"' in run
        assert '"$SOURCE_FETCHED" = "false"' in run
        assert step["env"]["SOURCE_FETCHED"] == "${{ steps.plan_gate.outputs.source_fetched }}"

    def test_block_step_needs_a_named_source_for_needs_source(self) -> None:
        """A reject on an issue with no URL is a plain reject, not needs-source."""
        wf = yaml.safe_load((REPO_ROOT / ".github/workflows/process-quick-note.yml").read_text())
        steps = next(iter(wf["jobs"].values()))["steps"]
        step = next(s for s in steps if s.get("id") == "plan_blocked")
        assert '"$HAS_SOURCE" != "false"' in step["run"]
        assert step["env"]["HAS_SOURCE"] == "${{ steps.plan_gate.outputs.has_source }}"

    @pytest.mark.parametrize("url,expected", [("https://github.com/a/b", True), (None, False)])
    def test_the_gate_reads_has_source_from_the_real_grounding_block(self, url, expected) -> None:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        gc = _load("generate_context")
        import context_plan_gate as gate

        block = gc._build_grounding_block({"url": url, "source_fetched": False})
        doc = f"{gc.VERDICT_BADGES['reject']}\n\n{block}"
        decision = gate.evaluate(doc)
        assert decision.source_fetched is False
        assert decision.has_source is expected
        assert f"has_source={'true' if expected else 'false'}" in decision.as_output_lines()
