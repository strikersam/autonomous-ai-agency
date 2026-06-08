import asyncio
import shutil
import pytest

from agent.doctor import DirectChatDoctor


@pytest.mark.asyncio
async def test_missing_git_and_token(monkeypatch):
    """When git is missing and no GitHub token is present, the doctor should report both issues."""
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    doctor = DirectChatDoctor(github_token=None)
    report = await doctor.check_all()
    assert not report.ready
    codes = {issue.code for issue in report.issues}
    assert "missing_git_binary" in codes
    assert "missing_github_token" in codes
