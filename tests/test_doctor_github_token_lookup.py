"""The doctor must find a GitHub token wherever the connect flow stored it.

Production symptom: "Doctor says GitHub token doesn't work" for an account whose
GitHub connection is genuinely fine — repo listing, cloning and PR creation all
succeed.

Cause: a token reaches the backend by two routes that write to two different
places, and only ``PUT /api/github/token`` wrote to both.

* ``users.github_repo_token``  — PUT, and the ``/api/auth/github/repo`` redirect
* ``github_settings.token``    — the popup OAuth callback

The doctor read only the user document, so every popup-OAuth account reported
``missing_github_token`` while the rest of the app found the token via the
``github_settings`` fallback that those call sites already had.
"""
from __future__ import annotations

import pytest

from backend.server import _resolve_user_github_token


class _FakeCollection:
    def __init__(self, doc: dict | None = None) -> None:
        self._doc = doc
        self.queries: list[dict] = []

    async def find_one(self, query: dict) -> dict | None:
        self.queries.append(query)
        return self._doc


class _FakeDB:
    def __init__(self, github_settings: _FakeCollection) -> None:
        self.github_settings = github_settings


@pytest.fixture
def patch_db(monkeypatch):
    """Point backend.server.get_db() at a stub github_settings collection."""

    def _apply(doc: dict | None) -> _FakeCollection:
        collection = _FakeCollection(doc)
        monkeypatch.setattr(
            "backend.server.get_db", lambda: _FakeDB(collection)
        )
        return collection

    return _apply


@pytest.mark.asyncio
async def test_token_on_user_document_is_returned(patch_db) -> None:
    collection = patch_db(None)

    token = await _resolve_user_github_token(
        {"_id": "u1", "github_repo_token": "ghp_from_user_doc"}
    )

    assert token == "ghp_from_user_doc"
    # The user doc already had it — no need to hit the collection.
    assert collection.queries == []


@pytest.mark.asyncio
async def test_popup_oauth_token_is_found_in_github_settings(patch_db) -> None:
    """The regression: user doc empty, token lives in github_settings."""
    collection = patch_db({"user_id": "u1", "token": "gho_from_popup_oauth"})

    token = await _resolve_user_github_token({"_id": "u1"})

    assert token == "gho_from_popup_oauth"
    assert collection.queries == [{"user_id": "u1"}]


@pytest.mark.asyncio
async def test_no_token_anywhere_returns_none(patch_db) -> None:
    patch_db(None)

    assert await _resolve_user_github_token({"_id": "u1"}) is None


@pytest.mark.asyncio
async def test_empty_string_token_falls_through_to_github_settings(patch_db) -> None:
    """DELETE /api/github/token unsets by writing "" — that is not a token."""
    patch_db({"user_id": "u1", "token": "gho_still_connected"})

    token = await _resolve_user_github_token(
        {"_id": "u1", "github_repo_token": ""}
    )

    assert token == "gho_still_connected"


@pytest.mark.asyncio
async def test_missing_user_returns_none_without_querying(patch_db) -> None:
    collection = patch_db({"user_id": "u1", "token": "gho_x"})

    assert await _resolve_user_github_token(None) is None
    assert await _resolve_user_github_token({}) is None
    assert collection.queries == []


@pytest.mark.asyncio
async def test_db_failure_degrades_to_none_instead_of_raising(monkeypatch) -> None:
    """A diagnostics lookup must never turn into a 500."""

    class _Exploding:
        async def find_one(self, query: dict):
            raise RuntimeError("mongo is down")

    monkeypatch.setattr(
        "backend.server.get_db", lambda: _FakeDB(_Exploding())
    )

    assert await _resolve_user_github_token({"_id": "u1"}) is None
