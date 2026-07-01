"""tests/test_agency_fix.py — N3 acceptance tests for scripts/agency_fix.py.

The previous incarnation of the agency-fix script produced placeholder slop
(closed PR #852 was a ``assertTrue(True)`` fake test against issue #398).
These tests pin the new behaviour so that can't happen again:

  1. The slop-gate rejects an edit round that only touches doc files
     (``is_doc_only_boilerplate``).
  2. The slop-gate rejects an edit that would commit a secrets-shaped file
     (``looks_like_secret_file``).
  3. The slop-gate rejects an edit that produces unparseable Python
     (``python_parses``).
  4. The slop-gate rejects a destructive overwrite (truncating a real file).
  5. ``decline_cleanly`` posts a comment on the linked issue when given an
     issue number + a valid token; declines silently (exit 0, no comment)
     when no issue is linked; returns False only when the API call itself
     fails.
  6. End-to-end: a deliberately-broken fixture test gets fixed by a stubbed
     LLM and the verify-before-PR step confirms pytest goes green.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
GITHUB_SCRIPTS_DIR = REPO_ROOT / ".github" / "scripts"


@pytest.fixture(scope="module")
def agency_fix():
    """Load scripts/agency_fix.py as a module (it's not on sys.path by default).

    The script adds .github/scripts to sys.path at import time so it can
    import slop_gate; we mirror that for the test by inserting both dirs.
    """
    sys.path.insert(0, str(GITHUB_SCRIPTS_DIR))
    sys.path.insert(0, str(SCRIPTS_DIR))
    if "agency_fix" in sys.modules:
        del sys.modules["agency_fix"]
    mod = importlib.import_module("agency_fix")
    yield mod
    # Cleanup
    sys.path.remove(str(SCRIPTS_DIR))
    if str(GITHUB_SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(GITHUB_SCRIPTS_DIR))


# ── 1. Slop-gate: doc-only boilerplate rejected ──────────────────────────────

def test_apply_edits_rejects_doc_only_boilerplate(agency_fix, tmp_path, monkeypatch):
    """An edit round that only touches doc files must be rejected — the model
    produced boilerplate, not a real test fix (the original #398 failure mode)."""
    # Set REPO_ROOT to the tmp dir so the script doesn't touch the real repo.
    monkeypatch.setattr(agency_fix, "REPO_ROOT", tmp_path)

    # Create a doc file the model would try to "edit"
    doc_file = tmp_path / "NOTES.md"
    doc_file.write_text("# Old\nSome content here.\n")

    edits = [
        {
            "file": "NOTES.md",
            "old": "Some content here.",
            "new": "Some replaced content.",
        }
    ]
    applied = agency_fix.apply_edits(edits)
    assert applied == [], "doc-only edit round must be rejected by slop-gate"
    # And the file must be unchanged (edit wasn't persisted)
    assert "Some content here." in doc_file.read_text()


# ── 2. Slop-gate: secrets-shaped file rejected ───────────────────────────────

def test_apply_edits_rejects_secrets_shaped_file(agency_fix, tmp_path, monkeypatch):
    """An edit that produces a secrets-shaped file content must be rejected
    (CLAUDE.md rule #2 — no secrets in source).

    The ``looks_like_secret_file`` gate parses the new content as JSON or a
    Python dict-literal and rejects when the top-level keys name credentials
    (api_key, secret, token, etc.). We exercise this by editing a Python file
    whose NEW content is a bare dict literal with credential keys — exactly
    the shape PR #842 auto-merged (``{'ANTHROPIC_API_KEY': ...}``)."""
    monkeypatch.setattr(agency_fix, "REPO_ROOT", tmp_path)

    # Start with a Python file whose body is a bare dict literal (the gate
    # uses ast.literal_eval on the whole content, so we need the new content
    # to be a literal — not an assignment statement).
    py_file = tmp_path / "config_data.py"
    py_file.write_text("{'version': '1.0'}\n")  # bare dict literal, valid Python

    edits = [
        {
            "file": "config_data.py",
            "old": "{'version': '1.0'}",
            "new": "{'api_key': 'sk-1234567890abcdef', 'token': 'tok_abc'}",
        }
    ]
    applied = agency_fix.apply_edits(edits)
    assert applied == [], "secret-shaped dict-literal content must be rejected by slop-gate"
    assert "api_key" not in py_file.read_text()  # file unchanged


# ── 3. Slop-gate: unparseable Python rejected ────────────────────────────────

def test_apply_edits_rejects_unparseable_python(agency_fix, tmp_path, monkeypatch):
    """An edit that produces a syntactically-broken Python file must be rejected
    — this is the gate that would have caught the original N3 slop."""
    monkeypatch.setattr(agency_fix, "REPO_ROOT", tmp_path)
    code_file = tmp_path / "module.py"
    code_file.write_text("def foo():\n    return 1\n")

    edits = [
        {
            "file": "module.py",
            "old": "def foo():\n    return 1",
            "new": "def foo(  # broken syntax\n    return 1",  # missing closing paren
        }
    ]
    applied = agency_fix.apply_edits(edits)
    assert applied == [], "unparseable Python must be rejected by python_parses gate"
    assert "def foo():\n    return 1" in code_file.read_text()  # unchanged


# ── 4. Slop-gate: destructive overwrite rejected ─────────────────────────────

def test_apply_edits_rejects_destructive_overwrite(agency_fix, tmp_path, monkeypatch):
    """An edit that truncates a real code file to a trivial body must be rejected
    — this is the gate that would have caught PR #833 (892-line file → '{}')."""
    monkeypatch.setattr(agency_fix, "REPO_ROOT", tmp_path)
    # Build a >30-line file so the truncation rule fires
    code_file = tmp_path / "big_module.py"
    original = "\n".join(f"line_{i} = {i}" for i in range(40)) + "\n"
    code_file.write_text(original)

    edits = [
        {
            "file": "big_module.py",
            "old": original.rstrip(),  # exact match
            "new": "{}",  # trivial replacement
        }
    ]
    applied = agency_fix.apply_edits(edits)
    assert applied == [], "destructive overwrite must be rejected"
    assert code_file.read_text() == original  # unchanged


# ── 5. decline_cleanly behavior ───────────────────────────────────────────────

def test_decline_cleanly_no_issue_returns_true(agency_fix):
    """With no issue linked, decline is just an exit-code signal — no API call."""
    result = agency_fix.decline_cleanly(None, "owner/repo", ["test_x"], "reason")
    assert result is True


def test_decline_cleanly_no_token_returns_false(agency_fix, monkeypatch):
    """When an issue is linked but no GH_PAT/GH_TOKEN is set, the decline fails
    loudly so the workflow can surface it (return False → exit 1)."""
    monkeypatch.delenv("GH_PAT", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = agency_fix.decline_cleanly(42, "owner/repo", ["test_x"], "reason")
    assert result is False


def test_decline_cleanly_posts_comment_on_success(agency_fix, monkeypatch):
    """When an issue is linked and the API call succeeds, decline_cleanly returns
    True and posts a Markdown comment with the failing-test list."""
    monkeypatch.setenv("GH_PAT", "fake-token")
    captured = {}

    import contextlib

    class _FakeResponse:
        status = 201
        def read(self): return b'{"id": 1}'
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _fake_urlopen(req, timeout=30):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.headers)
        captured["body"] = req.data.decode()
        return _FakeResponse()

    monkeypatch.setattr(agency_fix.urllib.request, "urlopen", _fake_urlopen)
    failing = ["tests/test_a.py::test_one", "tests/test_b.py::test_two"]
    result = agency_fix.decline_cleanly(42, "owner/repo", failing, "exhausted iterations")

    assert result is True
    assert captured["url"] == "https://api.github.com/repos/owner/repo/issues/42/comments"
    assert "token fake-token" in captured["headers"]["Authorization"]
    # Body must include the failing tests + the no-PR declaration
    assert "tests/test_a.py::test_one" in captured["body"]
    assert "tests/test_b.py::test_two" in captured["body"]
    assert "No PR opened" in captured["body"]


def test_decline_cleanly_returns_false_on_api_failure(agency_fix, monkeypatch):
    """When the API call itself fails (network error), decline_cleanly returns
    False so the workflow surfaces the malfunction via exit 1."""
    import urllib.error
    monkeypatch.setenv("GH_PAT", "fake-token")
    monkeypatch.setattr(
        agency_fix.urllib.request,
        "urlopen",
        MagicMock(side_effect=urllib.error.URLError("network down")),
    )
    result = agency_fix.decline_cleanly(42, "owner/repo", ["t"], "reason")
    assert result is False


# ── 6. End-to-end: stubbed LLM fixes a broken fixture test ────────────────────

def test_agency_fix_loop_fixes_broken_test_via_stub_llm(agency_fix, tmp_path, monkeypatch):
    """End-to-end N3 acceptance: a deliberately-broken fixture test is fixed
    by a stubbed LLM, and the verify-before-PR step confirms pytest goes green.

    This is the roadmap acceptance criterion: 'a deliberately-broken test in
    a sandbox is fixed and verified green by the loop.' We stub the LLM (no
    API keys in CI for this test) and stub run_pytest so the test doesn't
    depend on a real pytest invocation against the fixture.
    """
    monkeypatch.setattr(agency_fix, "REPO_ROOT", tmp_path)
    # Pretend at least one LLM key is set so main() doesn't exit 2.
    monkeypatch.setattr(agency_fix, "NVIDIA_KEY", "fake-nvidia-key")
    monkeypatch.setattr(agency_fix, "ANTHROPIC_KEY", "")

    # Simulate the first pytest run finding one failure, and the verify run green.
    call_count = {"pytest": 0}
    def _fake_run_pytest(extra_args=None):
        call_count["pytest"] += 1
        if call_count["pytest"] == 1:
            return 1, "FAILED tests/test_fixture.py::test_broken\nassert 1 == 2\n"
        return 0, "1 passed in 0.01s\n"
    monkeypatch.setattr(agency_fix, "run_pytest", _fake_run_pytest)

    # Stub the LLM to propose a real code fix (touches a .py file → passes doc-only gate).
    code_file = tmp_path / "module.py"
    code_file.write_text("VALUE = 1\n")
    def _fake_call_llm(messages):
        return (
            '{"explanation": "fix the value", '
            '"edits": [{"file": "module.py", "old": "VALUE = 1", "new": "VALUE = 2"}]}'
        )
    monkeypatch.setattr(agency_fix, "call_llm", _fake_call_llm)

    # Stub update_changelog so the test doesn't touch a real changelog file.
    monkeypatch.setattr(agency_fix, "update_changelog", lambda *a, **kw: None)

    # Build a fake pytest-output file so main() doesn't try to run pytest itself
    # for the initial scan.
    pytest_out = tmp_path / "pytest_output.txt"
    pytest_out.write_text("FAILED tests/test_fixture.py::test_broken\n")

    # Run main() — should return 0 (green after one iteration).
    monkeypatch.setattr(sys, "argv", ["agency_fix.py", str(pytest_out)])
    exit_code = agency_fix.main()
    assert exit_code == 0, "loop must return 0 when the verify step goes green"
    # And the file must actually be modified
    assert "VALUE = 2" in code_file.read_text()


def test_agency_fix_loop_declines_when_llm_returns_no_edits(agency_fix, tmp_path, monkeypatch):
    """When the LLM offers no edits, the loop declines cleanly (exit 0) and
    posts an issue comment — never opens a placeholder PR. This is the second
    N3 acceptance criterion."""
    monkeypatch.setattr(agency_fix, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(agency_fix, "NVIDIA_KEY", "fake")
    monkeypatch.setattr(agency_fix, "ANTHROPIC_KEY", "")

    # Stub run_pytest to always report a failure (the loop can't fix it).
    monkeypatch.setattr(agency_fix, "run_pytest", lambda extra_args=None: (1, "FAILED tests/x.py::test_y\n"))
    # Stub the LLM to return zero edits.
    monkeypatch.setattr(agency_fix, "call_llm", lambda m: '{"explanation": "no fix possible", "edits": []}')

    # Stub decline_cleanly so we can assert it was called with the right issue.
    decline_calls = []
    def _fake_decline(issue, repo, failing, reason):
        decline_calls.append({"issue": issue, "reason": reason, "failing": failing})
        return True
    monkeypatch.setattr(agency_fix, "decline_cleanly", _fake_decline)

    pytest_out = tmp_path / "pytest_output.txt"
    pytest_out.write_text("FAILED tests/x.py::test_y\n")

    monkeypatch.setattr(sys, "argv", ["agency_fix.py", str(pytest_out), "--issue", "398", "--repo", "owner/repo"])
    exit_code = agency_fix.main()
    assert exit_code == 0, "decline-cleanly must exit 0 (no PR opened)"
    assert len(decline_calls) == 1
    assert decline_calls[0]["issue"] == 398
    assert "no edits" in decline_calls[0]["reason"].lower() or "no fix" in decline_calls[0]["reason"].lower()
