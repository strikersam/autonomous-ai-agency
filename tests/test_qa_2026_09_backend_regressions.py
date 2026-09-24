"""Backend regressions found by the 2026-09-23 QA pass (route fuzzing on SQLite).

* ``/api/sources/*`` and ``/api/github/authorize-repos`` built ``ObjectId(id)``
  from ids that, on the SQLite backend, are plain UUID strings — so ingesting a
  source returned 500 and left it "pending" forever, and every per-source
  GET/DELETE and every repo authorisation 500'd.
* ``POST /v4/scheduler/trigger/{job_id}`` caught ``ValueError`` but the
  scheduler raises ``KeyError`` for an unknown job, so it answered 500.
* When every LLM provider failed, chat said "Internal server error".
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.server as server

UUID_ID = "a1b8fc08-ac62-4e59-a656-da3978dc16bb"
USER = {"_id": "32fe214f-3dc0-4ee3-9123-3768c67e5887", "email": "qa@example.com", "role": "admin"}


@pytest.fixture()
def signed_in(monkeypatch) -> TestClient:
    async def _user(request):
        return USER

    monkeypatch.setattr(server, "get_optional_user", _user)
    return TestClient(server.app, raise_server_exceptions=False)


def test_doc_id_filter_keeps_uuid_ids_as_strings() -> None:
    assert server._doc_id_filter(UUID_ID) == {"_id": UUID_ID}
    oid = "65f1c0ffee0000000000abcd"
    assert str(server._doc_id_filter(oid)["_id"]) == oid


def test_source_get_and_delete_accept_uuid_ids(signed_in, monkeypatch) -> None:
    db = MagicMock()
    db.sources.find_one = AsyncMock(return_value={"_id": UUID_ID, "title": "qa"})
    db.sources.delete_one = AsyncMock()
    monkeypatch.setattr(server, "get_db", lambda: db)

    got = signed_in.get(f"/api/sources/{UUID_ID}")
    assert got.status_code == 200, got.text
    db.sources.find_one.assert_awaited_with({"_id": UUID_ID})

    gone = signed_in.delete(f"/api/sources/{UUID_ID}")
    assert gone.status_code == 200, gone.text
    db.sources.delete_one.assert_awaited_with({"_id": UUID_ID})


def test_source_ingest_on_uuid_backend_marks_the_source(signed_in, monkeypatch) -> None:
    db = MagicMock()
    db.sources.insert_one = AsyncMock(return_value=MagicMock(inserted_id=UUID_ID))
    db.sources.update_one = AsyncMock()
    monkeypatch.setattr(server, "get_db", lambda: db)

    async def _llm_down(*args: Any, **kwargs: Any) -> str:
        raise HTTPException(status_code=503, detail="down")

    monkeypatch.setattr(server, "call_llm", _llm_down)
    resp = signed_in.post("/api/sources/ingest", data={"title": "qa", "content_text": "hello"})
    assert resp.status_code == 200, resp.text
    filt, update = db.sources.update_one.await_args.args
    assert filt == {"_id": UUID_ID}
    assert update["$set"]["status"] == "failed"


def test_authorize_repos_accepts_uuid_user_ids(signed_in, monkeypatch) -> None:
    db = MagicMock()
    db.users.update_one = AsyncMock()
    monkeypatch.setattr(server, "get_db", lambda: db)
    monkeypatch.setattr(server, "log_activity", AsyncMock())

    resp = signed_in.post("/api/github/authorize-repos", json={"repo_names": ["a/b"]})
    assert resp.status_code == 200, resp.text
    assert db.users.update_one.await_args.args[0] == {"_id": USER["_id"]}


def test_v4_trigger_unknown_job_is_404(signed_in) -> None:
    resp = signed_in.post("/v4/scheduler/trigger/qa-nonexistent-id")
    assert resp.status_code == 404, resp.text


def test_provider_outage_message_is_not_internal_server_error() -> None:
    assert "Internal server error" not in server._NO_LLM_PROVIDER_DETAIL
    assert "provider" in server._NO_LLM_PROVIDER_DETAIL
