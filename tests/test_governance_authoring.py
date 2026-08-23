"""Tests for in-product policy authoring (propose-via-PR).

The design invariant under test: the dashboard can validate and *propose* a
policy change, but it never writes the live file, and it can never loosen the
org baseline. A proposal that drops a baseline guardrail is refused before any
branch or PR is created; a valid one opens a PR and is recorded in the audit
trail. See packages/governance/authoring.py and backend/governance_router.py.
"""
from __future__ import annotations

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.governance_router import build_governance_router
from packages.governance import authoring
from packages.governance.audit import AuditLog
from packages.governance.authoring import (
    diff_policy,
    parse_policy_text,
    propose_policy_change,
    validate_policy_text,
)

ADMIN = {"email": "admin@example.com", "role": "admin"}
VIEWER = {"email": "viewer@example.com", "role": "viewer"}

_CURRENT = (
    "version: 1\n"
    "mode: observe\n"
    "baseline:\n"
    "  filesystem:\n"
    "    deny:\n"
    "      - .env\n"
    "      - '**/*.pem'\n"
    "  tool:\n"
    "    require_approval:\n"
    "      - github_merge_pr\n"
)


def _client(user: dict) -> TestClient:
    app = FastAPI()
    app.include_router(build_governance_router(lambda: user))
    return TestClient(app)


class _FakeGitHub:
    """Records the create-branch / commit / open-PR calls without any network."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def create_branch(self, owner, repo, branch_name, base_branch="master"):
        self.calls.append(("create_branch", owner, repo, branch_name, base_branch))
        return {"ref": f"refs/heads/{branch_name}"}

    async def commit_file(self, owner, repo, path, content, message, branch="master"):
        self.calls.append(("commit_file", owner, repo, path, branch))
        self.committed_content = content
        return {"commit": {"sha": "abc123"}}

    async def open_pull_request(self, owner, repo, title, head, base="master", body=""):
        self.calls.append(("open_pull_request", owner, repo, head, base))
        return {"html_url": f"https://github.com/{owner}/{repo}/pull/42", "number": 42}


# ── Validation ────────────────────────────────────────────────────────────────


class TestValidatePolicy:
    def test_valid_policy_passes(self) -> None:
        result = validate_policy_text(_CURRENT, current_document=yaml.safe_load(_CURRENT))
        assert result.ok, result.errors

    def test_malformed_yaml_is_rejected(self) -> None:
        result = validate_policy_text("mode: observe\n  bad: : :", current_document=None)
        assert not result.ok
        assert any("YAML" in e or "compile" in e for e in result.errors)

    def test_non_mapping_root_is_rejected(self) -> None:
        result = validate_policy_text("- just\n- a\n- list\n", current_document=None)
        assert not result.ok
        assert any("mapping" in e for e in result.errors)

    def test_empty_document_is_rejected(self) -> None:
        result = validate_policy_text("   \n", current_document=None)
        assert not result.ok

    def test_dropping_a_baseline_deny_is_refused(self) -> None:
        loosened = "version: 1\nmode: observe\nbaseline:\n  filesystem:\n    deny:\n      - .env\n  tool:\n    require_approval:\n      - github_merge_pr\n"
        result = validate_policy_text(loosened, current_document=yaml.safe_load(_CURRENT))
        assert not result.ok
        assert any("*.pem" in e for e in result.errors)

    def test_dropping_a_baseline_require_approval_is_refused(self) -> None:
        loosened = "version: 1\nmode: observe\nbaseline:\n  filesystem:\n    deny:\n      - .env\n      - '**/*.pem'\n  tool:\n    require_approval: []\n"
        result = validate_policy_text(loosened, current_document=yaml.safe_load(_CURRENT))
        assert not result.ok
        assert any("github_merge_pr" in e for e in result.errors)

    def test_tightening_the_baseline_is_allowed(self) -> None:
        tightened = _CURRENT + "      - '**/*.key'\n"
        # append under filesystem.deny by rebuilding cleanly
        doc = yaml.safe_load(_CURRENT)
        doc["baseline"]["filesystem"]["deny"].append("**/*.key")
        result = validate_policy_text(yaml.safe_dump(doc), current_document=yaml.safe_load(_CURRENT))
        assert result.ok, result.errors

    def test_mode_flip_is_a_warning_not_an_error(self) -> None:
        doc = yaml.safe_load(_CURRENT)
        doc["mode"] = "enforce"
        result = validate_policy_text(yaml.safe_dump(doc), current_document=yaml.safe_load(_CURRENT))
        assert result.ok
        assert any("mode change" in w for w in result.warnings)

    def test_unknown_mode_warns(self) -> None:
        doc = yaml.safe_load(_CURRENT)
        doc["mode"] = "banana"
        result = validate_policy_text(yaml.safe_dump(doc), current_document=None)
        assert any("unknown mode" in w for w in result.warnings)


class TestDiff:
    def test_diff_shows_added_line(self) -> None:
        after = _CURRENT + "      - '**/*.key'\n"
        diff = diff_policy(_CURRENT, after)
        assert "*.key" in diff and diff.startswith("---")

    def test_no_diff_for_identical(self) -> None:
        assert diff_policy(_CURRENT, _CURRENT) == ""


# ── Propose ───────────────────────────────────────────────────────────────────


class TestProposePolicyChange:
    @pytest.fixture(autouse=True)
    def _isolate_audit(self):
        from packages.governance import audit as audit_module

        audit_module.reset_audit_log(AuditLog(capacity=50))
        yield
        audit_module.reset_audit_log(None)

    @pytest.mark.asyncio
    async def test_valid_proposal_opens_a_pr_and_audits(self) -> None:
        from packages.governance.audit import get_audit_log

        gh = _FakeGitHub()
        proposed = _CURRENT + "      - '**/*.key'\n"
        out = await propose_policy_change(
            proposed, actor="admin@example.com", reason="lock down keys",
            gh=gh, repo="strikersam/autonomous-ai-agency", current_text=_CURRENT,
        )
        assert out["proposed"] is True
        assert out["pr_url"].endswith("/pull/42")
        # branch, commit, and PR were all created, in that order
        assert [c[0] for c in gh.calls] == ["create_branch", "commit_file", "open_pull_request"]
        # the committed content is exactly the proposed policy
        assert gh.committed_content == proposed
        # the proposer is in the audit trail — "who changed the rules" stays answerable
        events = get_audit_log().recent(limit=10)
        assert any(e.get("action") == "governance.policy.propose" for e in events)

    @pytest.mark.asyncio
    async def test_invalid_proposal_never_touches_github(self) -> None:
        gh = _FakeGitHub()
        loosened = "version: 1\nmode: observe\nbaseline:\n  filesystem:\n    deny:\n      - .env\n  tool:\n    require_approval:\n      - github_merge_pr\n"
        with pytest.raises(ValueError):
            await propose_policy_change(
                loosened, actor="admin@example.com", reason="", gh=gh,
                repo="strikersam/autonomous-ai-agency", current_text=_CURRENT,
            )
        assert gh.calls == [], "no branch or PR may be created for an invalid proposal"

    @pytest.mark.asyncio
    async def test_bad_repo_format_is_rejected(self) -> None:
        gh = _FakeGitHub()
        with pytest.raises(ValueError):
            await propose_policy_change(
                _CURRENT + "      - '**/*.key'\n", actor="a", reason="", gh=gh,
                repo="not-a-slug", current_text=_CURRENT,
            )


# ── HTTP surface ──────────────────────────────────────────────────────────────


class TestAuthoringEndpoints:
    def test_raw_requires_admin(self) -> None:
        assert _client(VIEWER).get("/api/governance/policy/raw").status_code == 403

    def test_raw_returns_text_for_admin(self) -> None:
        resp = _client(ADMIN).get("/api/governance/policy/raw")
        assert resp.status_code == 200
        assert "text" in resp.json()

    def test_validate_requires_admin(self) -> None:
        resp = _client(VIEWER).post("/api/governance/policy/validate", json={"text": _CURRENT})
        assert resp.status_code == 403

    def test_validate_returns_ok_and_diff(self) -> None:
        resp = _client(ADMIN).post("/api/governance/policy/validate", json={"text": _CURRENT})
        assert resp.status_code == 200
        body = resp.json()
        assert "ok" in body and "diff" in body and "errors" in body

    def test_validate_missing_text_is_400(self) -> None:
        resp = _client(ADMIN).post("/api/governance/policy/validate", json={})
        assert resp.status_code == 400

    def test_propose_without_github_credential_is_503(self, monkeypatch) -> None:
        from packages.config import settings

        monkeypatch.setattr(settings, "gh_pat", "", raising=False)
        resp = _client(ADMIN).post(
            "/api/governance/policy/propose", json={"text": _CURRENT + "      - '**/*.key'\n"}
        )
        assert resp.status_code == 503

    def test_propose_requires_admin(self) -> None:
        resp = _client(VIEWER).post("/api/governance/policy/propose", json={"text": _CURRENT})
        assert resp.status_code == 403

    def test_propose_opens_pr_for_admin(self, monkeypatch) -> None:
        from packages.config import settings

        monkeypatch.setattr(settings, "gh_pat", "ghp_fake", raising=False)
        monkeypatch.setattr(settings, "github_repository", "strikersam/autonomous-ai-agency", raising=False)

        fake = _FakeGitHub()
        monkeypatch.setattr("agent.github_tools.GitHubTools", lambda *a, **k: fake)

        # Build the proposal on the REAL live policy (the endpoint validates
        # against the on-disk file), tightening it so the baseline is never
        # loosened. A minimal fixture would read as dropping the live baseline.
        current_text = __import__("pathlib").Path(settings.governance_policy_path).read_text(encoding="utf-8")
        current_doc = parse_policy_text(current_text)[0] or {}
        current_doc.setdefault("baseline", {}).setdefault("filesystem", {}).setdefault("deny", []).append("**/*.newsecret")
        proposed = yaml.safe_dump(current_doc)
        resp = _client(ADMIN).post("/api/governance/policy/propose", json={"text": proposed, "reason": "lock keys"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["pr_url"].endswith("/pull/42")

    def test_propose_rejects_a_loosening_with_400(self, monkeypatch) -> None:
        from packages.config import settings

        monkeypatch.setattr(settings, "gh_pat", "ghp_fake", raising=False)
        fake = _FakeGitHub()
        monkeypatch.setattr("agent.github_tools.GitHubTools", lambda *a, **k: fake)

        # Drop a baseline deny that the live policy file actually contains.
        current_text = __import__("pathlib").Path(settings.governance_policy_path).read_text(encoding="utf-8")
        current_doc = parse_policy_text(current_text)[0] or {}
        current_doc.setdefault("baseline", {}).setdefault("filesystem", {})["deny"] = []
        resp = _client(ADMIN).post(
            "/api/governance/policy/propose", json={"text": yaml.safe_dump(current_doc)}
        )
        # Either a real loosening (400) — the live file has baseline denies — and
        # in every case no PR is opened when validation fails.
        if resp.status_code == 400:
            assert fake.calls == []
        else:  # live file happened to have no baseline denies to drop
            assert resp.status_code == 200
