"""Anonymous GET /api/doctor must not probe GitHub with the server's GH_PAT."""
from __future__ import annotations

from fastapi.testclient import TestClient

import agent.doctor as doctor_mod
import backend.server as server


def test_anonymous_doctor_runs_without_the_server_token(monkeypatch) -> None:
    monkeypatch.setenv("GH_PAT", "ghp_server_owned_token")
    seen: list = []
    real = doctor_mod.DirectChatDoctor

    class _Spy(real):
        def __init__(self, github_token=None):
            seen.append(github_token)
            super().__init__(github_token=github_token)

    monkeypatch.setattr(doctor_mod, "DirectChatDoctor", _Spy)
    resp = TestClient(server.app, raise_server_exceptions=False).get("/api/doctor")
    assert resp.status_code == 200, resp.text
    assert seen and seen[0] is None
