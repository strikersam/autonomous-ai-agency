"""Regression test pinning the actor NameError fix in backend/local_brain_router.py.

Both buggy lines were:
  * line 102:  log.info("local_brain: GET /state (actor=%s)", actor)
               -> name 'actor' is not defined (def get_local_brain_state(request) only takes `request`)
  * line 119:  actor_str = (payload.actor or actor or "service:local_daemon")[:200]
               -> second `actor` is not in scope

Tests verify that the FIXED handlers do NOT raise NameError when invoked with
a stubbed store + stubbed Request. Any future re-introduction of a bare `actor`
reference in either body will re-raise NameError and FAIL this test.
"""
from __future__ import annotations

import asyncio
import os
import sys
import types
from typing import Any

import pytest

os.environ.setdefault("ADMIN_PASSWORD", "ci-test")


def _make_stub_request(path: str = "/api/local-brain/state") -> Any:
    rf = types.SimpleNamespace()
    rf.headers = {"X-Service-Token": "test-token"}
    rf.url = types.SimpleNamespace(path=path)
    return rf


def _patch_store(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = []

    class _StateObj:
        desired = "off"
        last_heartbeat = None
        lease = {"owner": "stub", "expires_at": None}

    class _StubStore:
        def get_state(self) -> _StateObj:
            calls.append(("get_state", {}))
            return _StateObj()

        def set_desired(
            self,
            *,
            desired_state: str,
            provider: str | None = None,
            actor: str | None = None,
        ) -> dict[str, Any]:
            calls.append(("set_desired", {"desired_state": desired_state, "provider": provider, "actor": actor}))
            return {"accepted": True, "desired_state": desired_state, "provider": provider, "actor": actor}

    monkeypatch.setattr("backend.local_brain_router._store", lambda: _StubStore())
    return calls


class TestGethandlerDoesNotNameError:
    @pytest.mark.asyncio
    async def test_get_state_invocation_does_not_raise_name_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.local_brain_router import get_local_brain_state
        _patch_store(monkeypatch)
        handler = get_local_brain_state
        out = await handler(_make_stub_request())
        assert out is not None
        accepted = out.get("accepted") if isinstance(out, dict) else getattr(out, "accepted", None)
        assert accepted is None or accepted in (True, False)
        if isinstance(out, dict):
            assert "desired" in out or "last_heartbeat" in out


class TestPosthandlerDoesNotNameError:
    @pytest.mark.asyncio
    async def test_post_toggle_with_actor_in_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.local_brain_router import post_local_brain_toggle, ToggleBody
        _patch_store(monkeypatch)
        payload = ToggleBody(desired_state="on", desired_provider="colibri", actor="test-actor")
        out = await post_local_brain_toggle(payload)
        assert out is not None
        accepted = out.get("accepted") if isinstance(out, dict) else getattr(out, "accepted", None)
        assert accepted is True

    @pytest.mark.asyncio
    async def test_post_toggle_without_actor_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.local_brain_router import post_local_brain_toggle, ToggleBody
        _patch_store(monkeypatch)
        payload = ToggleBody(desired_state="off", desired_provider=None, actor=None)
        out = await post_local_brain_toggle(payload)
        assert out is not None
        actor_val = out.get("actor") if isinstance(out, dict) else getattr(out, "actor", None)
        # Pin the FIX: default actor string when payload.actor is None and the
        # legacy in-scope `actor` fallback has been DROPPED.
        assert actor_val == "service:local_daemon"
