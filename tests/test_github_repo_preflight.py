from __future__ import annotations
import subprocess
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
import proxy
import direct_chat
from agent.state import AgentSessionStore
from agent.job_manager import AgentJobManager


def _fake_user():
    """Return a fixed test UserInfo for a fake user."""
    return direct_chat.UserInfo(id="u1", email="repo-tester@example.com")


def test_repo_access_preflight_fails_when_git_ls_remote_fails(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(direct_chat, "_direct_chat_store", AgentSessionStore(db_path=str(tmp_path / "chat_repo.db")))
    monkeypatch.setattr(direct_chat, "_agent_jobs", AgentJobManager())
    proxy.app.dependency_overrides[direct_chat._get_current_user] = _fake_user
    # Strict mode makes preflight failures return 412 rather than the soft 200+preflight_failed path
    monkeypatch.setenv("DIRECT_CHAT_STRICT_PREFLIGHT", "true")

    # Ensure git binary appears present in the doctor's shutil.which check
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/git")

    # Return a fake token so the doctor proceeds to the git ls-remote check
    monkeypatch.setattr(direct_chat, "_get_github_token_for_user", lambda email: "ghp_FAKE")

    # Simulate git ls-remote failing (authentication refused) by patching subprocess.run.
    # The doctor calls subprocess.run for the git ls-remote repo-access check.
    def fake_run(cmd, stdout, stderr, env, timeout):
        class P:
            returncode = 128
            stderr = b"fatal: Authentication failed"
            stdout = b""
        return P()

    monkeypatch.setattr("subprocess.run", fake_run)
    # Also patch inside agent.doctor so the import-time reference is intercepted
    import agent.doctor as _doctor_mod
    monkeypatch.setattr(_doctor_mod, "subprocess", type("M", (), {"run": staticmethod(fake_run)})())

    client = TestClient(proxy.app)
    # repo_url must be a top-level field (not nested in metadata) so direct_chat reads it
    # and passes it to the doctor's check_all for the git ls-remote preflight.
    payload = {
        "content": "Please clone this repo and create PR",
        "agent_mode": True,
        "repo_url": "https://github.com/example/notfound.git",
    }
    resp = client.post("/api/chat/send", json=payload)
    assert resp.status_code == 412
    detail = resp.json().get("detail")
    assert detail and not detail.get("ready")
    codes = {i.get("code") for i in detail.get("issues", [])}
    assert "git_repo_access" in codes

    proxy.app.dependency_overrides.clear()
