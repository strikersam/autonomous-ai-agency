"""tests/test_telegram_mutating_commands.py — N5 acceptance: /setbrain + /merge.

Tests the Telegram bot's mutating commands (``cmd_setbrain``,
``cmd_merge``) with the HTTP layer mocked. The commands must:
  - reject non-admin callers
  - reject when SERVICE_TOKEN isn't set on the bot
  - call the backend with the X-Service-Token header
  - surface 503 (backend misconfigured), 401 (rejected), 422 (liveness/CI)
    as human-readable Telegram replies
  - echo the action back to Telegram for confirmation (the roadmap's audit
    requirement)
"""
from __future__ import annotations

import asyncio
import importlib
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import packages.notifications.bot
import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def telegram_bot(monkeypatch):
    """Load telegram_bot fresh in each test, with env vars reset."""
    # The telegram_bot module reads env at import time, so we set the env
    # first then force-reload.
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "11111")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "11111")
    monkeypatch.setenv("TELEGRAM_ADMIN_USER_IDS", "11111")
    monkeypatch.setenv("PROXY_BASE_URL", "http://test-backend.local")
    monkeypatch.setenv("SERVICE_TOKEN", "")  # default: not configured

    # Drop any cached version so reload picks up env changes.
    for mod_name in list(sys.modules):
        if mod_name == "telegram_bot" or mod_name.startswith("telegram_bot."):
            del sys.modules[mod_name]

    sys.path.insert(0, str(REPO_ROOT))
    import telegram_bot as tb  # noqa: F401
    importlib.reload(tb)
    yield tb

    if str(REPO_ROOT) in sys.path:
        sys.path.remove(str(REPO_ROOT))


# ── Permission gate ──────────────────────────────────────────────────────────

def test_setbrain_rejects_non_admin(telegram_bot, monkeypatch):
    """A non-admin user cannot even learn whether the command is wired —
    returns 'Permission denied' before any HTTP call."""
    monkeypatch.setenv("TELEGRAM_ADMIN_USER_IDS", "99999")  # user 11111 is not admin
    import importlib
    importlib.reload(telegram_bot)
    # Reload re-reads env, but ADMIN_USER_IDS is computed at import time — so we
    # need to monkeypatch the module-level attr directly too.
    packages.notifications.bot.ADMIN_USER_IDS = {99999}

    result = asyncio.run(telegram_bot.cmd_setbrain(11111, "cerebras"))
    assert "Permission denied" in result


def test_merge_rejects_non_admin(telegram_bot, monkeypatch):
    monkeypatch.setenv("TELEGRAM_ADMIN_USER_IDS", "99999")
    packages.notifications.bot.ADMIN_USER_IDS = {99999}
    result = asyncio.run(telegram_bot.cmd_merge(11111, "855"))
    assert "Permission denied" in result


# ── Misconfiguration paths ──────────────────────────────────────────────────

def test_setbrain_rejects_when_service_token_unset_on_bot(telegram_bot, monkeypatch):
    """When SERVICE_TOKEN is not set on the bot, the command refuses before
    calling the backend — surfaces a clear 'configure SERVICE_TOKEN' message."""
    # 11111 is admin
    packages.notifications.bot.ADMIN_USER_IDS = {11111}
    packages.notifications.bot.SERVICE_TOKEN = ""  # not configured
    result = asyncio.run(telegram_bot.cmd_setbrain(11111, "cerebras"))
    assert "SERVICE_TOKEN" in result
    assert "not configured" in result.lower() or "set SERVICE_TOKEN" in result


def test_merge_rejects_when_service_token_unset_on_bot(telegram_bot, monkeypatch):
    packages.notifications.bot.ADMIN_USER_IDS = {11111}
    packages.notifications.bot.SERVICE_TOKEN = ""
    result = asyncio.run(telegram_bot.cmd_merge(11111, "855"))
    assert "SERVICE_TOKEN" in result


# ── Argument validation ──────────────────────────────────────────────────────

def test_setbrain_rejects_invalid_provider(telegram_bot, monkeypatch):
    packages.notifications.bot.ADMIN_USER_IDS = {11111}
    packages.notifications.bot.SERVICE_TOKEN = "fake-token"
    result = asyncio.run(telegram_bot.cmd_setbrain(11111, "openai"))
    assert "Invalid provider" in result
    assert "cerebras" in result and "groq" in result and "nvidia" in result and "ollama" in result


def test_merge_rejects_non_numeric_pr(telegram_bot, monkeypatch):
    packages.notifications.bot.ADMIN_USER_IDS = {11111}
    packages.notifications.bot.SERVICE_TOKEN = "fake-token"
    result = asyncio.run(telegram_bot.cmd_merge(11111, "not-a-number"))
    assert "Usage:" in result


def test_merge_rejects_zero_or_negative_pr(telegram_bot, monkeypatch):
    packages.notifications.bot.ADMIN_USER_IDS = {11111}
    packages.notifications.bot.SERVICE_TOKEN = "fake-token"
    result = asyncio.run(telegram_bot.cmd_merge(11111, "0"))
    assert "positive integer" in result
    result = asyncio.run(telegram_bot.cmd_merge(11111, "-5"))
    assert "positive integer" in result or "Usage:" in result


# ── Backend response handling (HTTP layer mocked) ────────────────────────────

def _make_mock_response(status_code: int, json_data: dict | None = None):
    """Build a mock httpx.Response."""
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.raise_for_status = MagicMock()
    if status_code >= 400:
        r.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return r


def test_setbrain_sends_service_token_header_and_surfaces_success(telegram_bot, monkeypatch):
    """A successful /setbrain call must:
      1. send the X-Service-Token header
      2. PATCH /admin/api/policy/brain with the provider preset
      3. return a Telegram reply containing the new model ids + actor attribution
    """
    packages.notifications.bot.ADMIN_USER_IDS = {11111}
    packages.notifications.bot.SERVICE_TOKEN = "tok_fake"

    captured = {}

    async def _fake_patch(self, url, json=None, headers=None, **kw):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _make_mock_response(200, {
            "config": {
                "primary_provider": "cerebras",
                "planner_model": "qwen-3-coder-480b",
                "executor_model": "qwen-3-coder-480b",
                "verifier_model": "llama-3.3-70b",
                "judge_model": "llama-3.3-70b",
            },
            "probe_report": [],
        })

    monkeypatch.setattr("httpx.AsyncClient.patch", _fake_patch)
    result = asyncio.run(telegram_bot.cmd_setbrain(11111, "cerebras"))

    # Header sent
    assert captured["headers"]["X-Service-Token"] == "tok_fake"
    # URL is the brain policy endpoint
    assert "/admin/api/policy/brain" in captured["url"]
    # Body has the cerebras preset
    assert captured["json"]["primary_provider"] == "cerebras"
    assert captured["json"]["planner_model"] == "qwen-3-coder-480b"
    # Reply surfaces success + actor attribution
    assert "✅" in result
    assert "cerebras" in result
    assert "service:telegram" in result


def test_setbrain_surfaces_422_liveness_failure(telegram_bot, monkeypatch):
    """When the backend's liveness probe fails (HTTP 422), the bot reply must
    surface 'Refusing to switch' so the operator knows the brain wasn't changed."""
    packages.notifications.bot.ADMIN_USER_IDS = {11111}
    packages.notifications.bot.SERVICE_TOKEN = "tok_fake"

    async def _fake_patch(self, url, json=None, headers=None, **kw):
        return _make_mock_response(422, {
            "detail": {
                "message": "Refusing to persist a dead model",
                "failures": [
                    {"role": "executor", "model": "qwen-3-coder-480b", "reason": "HTTP 401"},
                ],
            },
        })

    monkeypatch.setattr("httpx.AsyncClient.patch", _fake_patch)
    result = asyncio.run(telegram_bot.cmd_setbrain(11111, "cerebras"))
    assert "Refusing to switch" in result
    assert "qwen-3-coder-480b" in result


def test_setbrain_surfaces_503_backend_misconfigured(telegram_bot, monkeypatch):
    """503 = backend doesn't have SERVICE_TOKEN set. The bot reply must tell
    the operator to set it on the backend (distinct from 'wrong token')."""
    packages.notifications.bot.ADMIN_USER_IDS = {11111}
    packages.notifications.bot.SERVICE_TOKEN = "tok_fake"

    async def _fake_patch(self, url, json=None, headers=None, **kw):
        return _make_mock_response(503, {"detail": "Service token not configured"})

    monkeypatch.setattr("httpx.AsyncClient.patch", _fake_patch)
    result = asyncio.run(telegram_bot.cmd_setbrain(11111, "cerebras"))
    assert "not configured on the backend" in result
    assert "SERVICE_TOKEN" in result


def test_merge_surfaces_success_with_sha_and_actor(telegram_bot, monkeypatch):
    """A successful /merge call returns the merge SHA + actor attribution so
    the operator can audit who merged what (the roadmap's audit requirement)."""
    packages.notifications.bot.ADMIN_USER_IDS = {11111}
    packages.notifications.bot.SERVICE_TOKEN = "tok_fake"

    captured = {}

    async def _fake_post(self, url, json=None, headers=None, **kw):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _make_mock_response(200, {
            "merged": True,
            "pr_number": 855,
            "merge_sha": "abc123def4567890abcdef",
            "method": "squash",
            "actor": "service:telegram",
        })

    monkeypatch.setattr("httpx.AsyncClient.post", _fake_post)
    result = asyncio.run(telegram_bot.cmd_merge(11111, "855"))

    # URL hits the merge endpoint with the PR number
    assert "/admin/api/prs/855/merge" in captured["url"]
    # Service token header sent
    assert captured["headers"]["X-Service-Token"] == "tok_fake"
    # squash merge method
    assert captured["json"]["merge_method"] == "squash"
    # Reply surfaces success + sha + actor
    assert "✅" in result
    assert "855" in result
    assert "abc123de" in result  # first 8 chars of the SHA
    assert "service:telegram" in result


def test_merge_surfaces_422_refusal(telegram_bot, monkeypatch):
    """When the backend refuses to merge (draft, failing CI, not mergeable),
    the bot reply must surface 'Refusing to merge' + the backend's reason."""
    packages.notifications.bot.ADMIN_USER_IDS = {11111}
    packages.notifications.bot.SERVICE_TOKEN = "tok_fake"

    async def _fake_post(self, url, json=None, headers=None, **kw):
        return _make_mock_response(422, {
            "detail": "PR #855 has 2 failed check(s): ['Test (Python 3.13)', 'Lint check']. Refusing to merge a red PR.",
        })

    monkeypatch.setattr("httpx.AsyncClient.post", _fake_post)
    result = asyncio.run(telegram_bot.cmd_merge(11111, "855"))
    assert "Refusing to merge" in result
    assert "Test (Python 3.13)" in result


def test_merge_surfaces_404_for_unknown_pr(telegram_bot, monkeypatch):
    packages.notifications.bot.ADMIN_USER_IDS = {11111}
    packages.notifications.bot.SERVICE_TOKEN = "tok_fake"

    async def _fake_post(self, url, json=None, headers=None, **kw):
        return _make_mock_response(404, {"detail": "PR #9999 not found."})

    monkeypatch.setattr("httpx.AsyncClient.post", _fake_post)
    result = asyncio.run(telegram_bot.cmd_merge(11111, "9999"))
    assert "not found" in result
