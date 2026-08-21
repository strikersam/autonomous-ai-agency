"""tests/test_refresh_agent_built_proof.py

Root-cause fix for the "agent-built proof" numbers going stale for five
weeks: they were hand-typed prose in three files. These tests lock down
`scripts/refresh_agent_built_proof.py`'s table-rewrite/extraction functions
(the CLI's fetch step hits the live GitHub API and is intentionally not
exercised here) plus an end-to-end drift-vs-no-drift run of `main()` against
tmp-path copies of the real docs.
"""
from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "scripts" / "refresh_agent_built_proof.py"

_spec = importlib.util.spec_from_file_location("refresh_agent_built_proof", _SCRIPT)
rabp = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = rabp  # dataclass field resolution needs this registered
_spec.loader.exec_module(rabp)  # type: ignore[union-attr]


AGENT_BUILT_SAMPLE = """# This repository is maintained by its own agents

## The numbers (verifiable via the GitHub API)

As of 2026-07-10:

| Metric | Count | Verify it yourself |
|---|---|---|
| Merged pull requests, total | **642** | [`is:pr is:merged`](x) |
| Merged PRs opened by agent sessions (`claude/*` head branches) | **176** | [`is:pr is:merged head:claude/`](x) |
| Merged PRs opened by agent sessions (`codex/*` head branches) | **8** | [`is:pr is:merged head:codex/`](x) |

**184 of 642 merged PRs (29%) were opened by AI agent sessions**, identifiable by their head branch prefix alone. The true share is higher.
"""

PROOF_README_SAMPLE = (
    "| [`agent-built.md`](agent-built.md) | This repository is maintained by "
    "its own agents: **184 of the 642 merged pull requests** were opened by "
    "AI agent sessions (verifiable from the PR head branches). |\n"
)

ROOT_README_SAMPLE = (
    "| [**This repo is maintained by its own agents**](proof/agent-built.md) "
    "| **184 of the 642 merged pull requests** in this repository were "
    "opened by the agent fleet. |\n"
)


def test_extract_counts_reads_table_values():
    counts = rabp.extract_counts(AGENT_BUILT_SAMPLE)
    assert counts == rabp.ProofCounts(total_merged=642, claude_merged=176, codex_merged=8)


def test_extract_counts_raises_on_missing_field():
    with pytest.raises(ValueError):
        rabp.extract_counts("no table here")


def test_proof_counts_agent_merged_and_pct():
    counts = rabp.ProofCounts(total_merged=829, claude_merged=271, codex_merged=8)
    assert counts.agent_merged == 279
    assert counts.agent_pct == 34  # 279/829 = 33.65% -> rounds to 34


def test_proof_counts_pct_matches_historical_rounding():
    counts = rabp.ProofCounts(total_merged=642, claude_merged=176, codex_merged=8)
    assert counts.agent_merged == 184
    assert counts.agent_pct == 29  # 184/642 = 28.66% -> rounds to 29, as committed historically


def test_rewrite_agent_built_updates_date_table_and_summary():
    fresh = rabp.ProofCounts(total_merged=829, claude_merged=271, codex_merged=8)
    out = rabp.rewrite_agent_built(AGENT_BUILT_SAMPLE, fresh, datetime.date(2026, 8, 16))

    assert "As of 2026-08-16:" in out
    assert "As of 2026-07-10:" not in out
    assert "Merged pull requests, total | **829**" in out
    assert "`claude/*` head branches) | **271**" in out
    assert "`codex/*` head branches) | **8**" in out
    assert "**279 of 829 merged PRs (34%) were opened by AI agent sessions**" in out
    # Caveats and methodology text must survive untouched.
    assert "The true share is higher." in out


def test_rewrite_agent_built_is_noop_when_counts_already_match():
    current = rabp.extract_counts(AGENT_BUILT_SAMPLE)
    out = rabp.rewrite_agent_built(AGENT_BUILT_SAMPLE, current, datetime.date(2026, 7, 10))
    assert out == AGENT_BUILT_SAMPLE


def test_rewrite_n_of_m_updates_proof_readme():
    fresh = rabp.ProofCounts(total_merged=829, claude_merged=271, codex_merged=8)
    out = rabp.rewrite_n_of_m(PROOF_README_SAMPLE, fresh)
    assert "**279 of the 829 merged pull requests**" in out
    assert "184" not in out
    assert "642" not in out


def test_rewrite_n_of_m_updates_root_readme():
    fresh = rabp.ProofCounts(total_merged=829, claude_merged=271, codex_merged=8)
    out = rabp.rewrite_n_of_m(ROOT_README_SAMPLE, fresh)
    assert "**279 of the 829 merged pull requests**" in out


def test_rewrite_functions_are_idempotent_on_live_docs():
    """The real committed docs, run through the rewriter with their own
    current numbers, must come back byte-identical — this is what --check
    relies on to detect 'no drift' correctly."""
    agent_built_text = (_ROOT / "proof" / "agent-built.md").read_text(encoding="utf-8")
    current = rabp.extract_counts(agent_built_text)
    as_of_match = rabp._AS_OF_RE.search(agent_built_text)
    as_of = datetime.date.fromisoformat(as_of_match.group(0))

    assert rabp.rewrite_agent_built(agent_built_text, current, as_of) == agent_built_text

    for path in (_ROOT / "proof" / "README.md", _ROOT / "README.md"):
        text = path.read_text(encoding="utf-8")
        assert rabp.rewrite_n_of_m(text, current) == text


@pytest.fixture
def doc_paths(tmp_path, monkeypatch):
    agent_built = tmp_path / "agent-built.md"
    proof_readme = tmp_path / "proof-README.md"
    root_readme = tmp_path / "README.md"
    agent_built.write_text(AGENT_BUILT_SAMPLE, encoding="utf-8")
    proof_readme.write_text(PROOF_README_SAMPLE, encoding="utf-8")
    root_readme.write_text(ROOT_README_SAMPLE, encoding="utf-8")

    monkeypatch.setattr(rabp, "AGENT_BUILT_PATH", agent_built)
    monkeypatch.setattr(rabp, "PROOF_README_PATH", proof_readme)
    monkeypatch.setattr(rabp, "ROOT_README_PATH", root_readme)
    return agent_built, proof_readme, root_readme


def test_main_check_exits_1_and_does_not_write_when_drifted(doc_paths, monkeypatch):
    agent_built, proof_readme, root_readme = doc_paths
    fresh = rabp.ProofCounts(total_merged=829, claude_merged=271, codex_merged=8)
    monkeypatch.setattr(rabp, "fetch_counts", lambda repo, token: fresh)

    before = agent_built.read_text(encoding="utf-8")
    rc = rabp.main(["--check"])
    assert rc == 1
    assert agent_built.read_text(encoding="utf-8") == before  # unchanged


def test_main_exits_0_and_writes_all_three_files_when_drifted(doc_paths, monkeypatch):
    agent_built, proof_readme, root_readme = doc_paths
    fresh = rabp.ProofCounts(total_merged=829, claude_merged=271, codex_merged=8)
    monkeypatch.setattr(rabp, "fetch_counts", lambda repo, token: fresh)

    rc = rabp.main([])
    assert rc == 0

    new_agent_built = agent_built.read_text(encoding="utf-8")
    assert "**829**" in new_agent_built
    assert "**279 of 829 merged PRs (34%)" in new_agent_built
    assert "**279 of the 829 merged pull requests**" in proof_readme.read_text(encoding="utf-8")
    assert "**279 of the 829 merged pull requests**" in root_readme.read_text(encoding="utf-8")


def test_main_no_drift_exits_0_and_does_not_write(doc_paths, monkeypatch):
    agent_built, proof_readme, root_readme = doc_paths
    current = rabp.extract_counts(agent_built.read_text(encoding="utf-8"))
    monkeypatch.setattr(rabp, "fetch_counts", lambda repo, token: current)

    before = agent_built.read_text(encoding="utf-8")
    rc = rabp.main(["--check"])
    assert rc == 0
    assert agent_built.read_text(encoding="utf-8") == before
