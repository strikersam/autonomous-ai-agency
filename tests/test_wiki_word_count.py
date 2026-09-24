"""Wiki pages store word_count: the list endpoint projects `content` out, so the
Knowledge screen could never count words and showed "—" for every page."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

import backend.server as server


def _client(monkeypatch) -> tuple[TestClient, MagicMock]:
    async def _user(request):
        return {"_id": "u1", "email": "qa@example.com", "role": "admin"}

    db = MagicMock()
    db.wiki_pages.find_one = AsyncMock(side_effect=[None, {"_id": "p", "slug": "notes"}])
    db.wiki_pages.insert_one = AsyncMock(return_value=MagicMock(inserted_id="p"))
    db.wiki_pages.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
    monkeypatch.setattr(server, "get_optional_user", _user)
    monkeypatch.setattr(server, "get_db", lambda: db)
    monkeypatch.setattr(server, "log_activity", AsyncMock())
    return TestClient(server.app, raise_server_exceptions=False), db


def test_create_and_update_store_word_count(monkeypatch) -> None:
    client, db = _client(monkeypatch)
    assert client.post("/api/wiki/pages", json={"title": "Notes", "content": "one two  three"}).status_code == 200
    assert db.wiki_pages.insert_one.await_args.args[0]["word_count"] == 3

    assert client.put("/api/wiki/pages/notes", json={"content": "just two"}).status_code == 200
    assert db.wiki_pages.update_one.await_args.args[1]["$set"]["word_count"] == 2
