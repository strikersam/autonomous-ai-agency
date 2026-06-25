from __future__ import annotations
from pathlib import Path
from fastapi.testclient import TestClient
import proxy
import direct_chat
from agent.state import AgentSessionStore
from agent.job_manager import AgentJobManager
from agent.doctor import PreflightReport, PreflightIssue


def _fake_user():
    return direct_chat.UserInfo(id="u1", email="refpath-tester@example.com")


def _make_fake_doctor(issue_code: str, message: str, fix_hint: str):
    """Return a FakeDoctor class that always reports a specific preflight issue."""
    class FakeDoctor:
        def __init__(self, **kwargs):
            pass

        async def check_all(self, **kwargs):
            return PreflightReport(
                ready=False,
                summary="Preflight checks failed",
                issues=[PreflightIssue(code=issue_code, message=message, fix_hint=fix_hint)],
            )
    return FakeDoctor


def test_repo_ref_preflight_fails(monkeypatch, tmp_path: Path):
    """412 with git_repo_ref when the specified branch/ref doesn't exist on the remote."""
    monkeypatch.setattr(direct_chat, "_direct_chat_store", AgentSessionStore(db_path=str(tmp_path / "chat_ref.db")))
    monkeypatch.setattr(direct_chat, "_agent_jobs", AgentJobManager())
    proxy.app.dependency_overrides[direct_chat._get_current_user] = _fake_user
    # Strict mode → preflight failures surface as 412, not softened to 200
    monkeypatch.setenv("DIRECT_CHAT_STRICT_PREFLIGHT", "true")
    monkeypatch.setattr(direct_chat, "_get_github_token_for_user", lambda email: "ghp_FAKE")

    # Inject a doctor that reports git_repo_ref failure (ref not found)
    monkeypatch.setattr(
        "direct_chat.DirectChatDoctor",
        _make_fake_doctor("git_repo_ref", "Branch 'nonexistent-branch' not found.", "Check the branch name."),
    )

    client = TestClient(proxy.app)
    # repo_url and repo_ref must be top-level fields so direct_chat.py reads them
    payload = {
        "content": "Please implement the feature and open a pull request with the changes",
        "agent_mode": True,
        "repo_url": "https://github.com/example/repo.git",
        "repo_ref": "nonexistent-branch",
    }
    resp = client.post("/api/chat/send", json=payload)
    assert resp.status_code == 412
    detail = resp.json().get("detail")
    assert detail and not detail.get("ready")
    codes = {i.get("code") for i in detail.get("issues", [])}
    assert "git_repo_ref" in codes

    proxy.app.dependency_overrides.clear()


def test_repo_path_preflight_fails(monkeypatch, tmp_path: Path):
    """412 with git_repo_path when the specified file path doesn't exist in the repo."""
    monkeypatch.setattr(direct_chat, "_direct_chat_store", AgentSessionStore(db_path=str(tmp_path / "chat_path.db")))
    monkeypatch.setattr(direct_chat, "_agent_jobs", AgentJobManager())
    proxy.app.dependency_overrides[direct_chat._get_current_user] = _fake_user
    monkeypatch.setenv("DIRECT_CHAT_STRICT_PREFLIGHT", "true")
    monkeypatch.setattr(direct_chat, "_get_github_token_for_user", lambda email: "ghp_FAKE")

    # Inject a doctor that reports git_repo_path failure (path not found)
    monkeypatch.setattr(
        "direct_chat.DirectChatDoctor",
        _make_fake_doctor("git_repo_path", "Path 'src/does/not/exist.py' not found.", "Check the file path."),
    )

    client = TestClient(proxy.app)
    payload = {
        "content": "Please implement the feature and open a pull request with the changes",
        "agent_mode": True,
        "repo_url": "https://github.com/example/repo.git",
        "repo_ref": "main",
        "repo_path": "src/does/not/exist.py",
    }
    resp = client.post("/api/chat/send", json=payload)
    assert resp.status_code == 412
    detail = resp.json().get("detail")
    assert detail and not detail.get("ready")
    codes = {i.get("code") for i in detail.get("issues", [])}
    assert "git_repo_path" in codes

    proxy.app.dependency_overrides.clear()
