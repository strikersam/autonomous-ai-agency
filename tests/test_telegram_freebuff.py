"""Tests for the Telegram FreeBuff control flow (inline buttons, accept/reject)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import telegram_bot as tb


@pytest.fixture(autouse=True)
def _admin_user(monkeypatch):
    """Make user 42 an allowed admin and reset FreeBuff state between tests."""
    monkeypatch.setattr(tb, "ALLOWED_USER_IDS", {42})
    monkeypatch.setattr(tb, "ADMIN_USER_IDS", {42})
    tb._freebuff_state.clear()
    yield
    tb._freebuff_state.clear()


@pytest.fixture
def captured(monkeypatch):
    """Stub out all network helpers and capture their calls."""
    log: dict = {"sent": [], "keyboards": [], "edits": [], "answers": [], "posts": []}

    async def fake_send(token, chat_id, text, parse_mode="Markdown"):
        log["sent"].append(text)

    async def fake_keyboard(token, chat_id, text, keyboard, parse_mode="Markdown"):
        log["keyboards"].append((text, keyboard))

    async def fake_edit(token, chat_id, message_id, text, keyboard=None, parse_mode="Markdown"):
        log["edits"].append((text, keyboard))

    async def fake_answer(token, callback_id, text=""):
        log["answers"].append(text)

    async def fake_get(path, use_admin=True):
        return {"models": ["nvidia/llama-3.3-nemotron-super-49b-v1", "meta/llama-3.1-8b-instruct"]}

    async def fake_post(path, body, use_admin=True):
        log["posts"].append((path, body))
        if path == "/freebuff/plan":
            return {"model": body["model"], "plan": {"goal": "do it", "steps": [{"description": "step one"}]}}
        if path == "/freebuff/run":
            return {"result": {"summary": "Applied 1/1", "pr_url": "https://github.com/x/y/pull/1"}}
        return {}

    monkeypatch.setattr(tb, "_send_message", fake_send)
    monkeypatch.setattr(tb, "_send_keyboard", fake_keyboard)
    monkeypatch.setattr(tb, "_edit_message", fake_edit)
    monkeypatch.setattr(tb, "_answer_callback", fake_answer)
    monkeypatch.setattr(tb, "_proxy_get", fake_get)
    monkeypatch.setattr(tb, "_proxy_post", fake_post)
    return log


# ── pure helpers ─────────────────────────────────────────────────────────────


def test_parse_callback():
    assert tb._parse_callback("fb:model:2") == ("model", "2")
    assert tb._parse_callback("fb:accept") == ("accept", None)
    assert tb._parse_callback("fb:reject") == ("reject", None)
    assert tb._parse_callback("notfb:x") == ("", None)
    assert tb._parse_callback("") == ("", None)


def test_parse_user_ids_tolerant() -> None:
    # plain, spaced, quoted, bracketed, semicolons, negative (group chats)
    assert tb._parse_user_ids("8120976") == {8120976}
    assert tb._parse_user_ids("123, 456") == {123, 456}
    assert tb._parse_user_ids('"123"') == {123}
    assert tb._parse_user_ids("[123 456]") == {123, 456}
    assert tb._parse_user_ids("123;456") == {123, 456}
    assert tb._parse_user_ids("-1001234567890") == {-1001234567890}
    # usernames / empty → nothing
    assert tb._parse_user_ids("@strikersam") == set()
    assert tb._parse_user_ids("") == set()


def test_model_keyboard_uses_index_callbacks():
    kb = tb._model_keyboard(["a/b", "c/d"])
    assert kb == [
        [{"text": "a/b", "callback_data": "fb:model:0"}],
        [{"text": "c/d", "callback_data": "fb:model:1"}],
    ]


# ── command + callback flow ──────────────────────────────────────────────────


async def test_freebuff_command_requires_admin(captured, monkeypatch):
    monkeypatch.setattr(tb, "ADMIN_USER_IDS", set())  # 42 allowed but not admin
    await tb.cmd_freebuff(42, 100, "tok", "fix the bug")
    assert any("Admin only" in s for s in captured["sent"])
    assert 42 not in tb._freebuff_state


async def test_freebuff_command_presents_model_keyboard(captured):
    await tb.cmd_freebuff(42, 100, "tok", "fix the bug")
    assert tb._freebuff_state[42]["task"] == "fix the bug"
    assert captured["keyboards"], "expected a model picker keyboard"
    _, kb = captured["keyboards"][0]
    assert kb[0][0]["callback_data"] == "fb:model:0"


async def test_full_flow_select_model_then_accept(captured):
    # 1. start
    await tb.cmd_freebuff(42, 100, "tok", "fix the bug")

    def cb(data):
        return {
            "id": "cb1",
            "from": {"id": 42},
            "message": {"chat": {"id": 100}, "message_id": 7},
            "data": data,
        }

    # 2. pick the second model → triggers a plan
    await tb._process_callback("tok", cb("fb:model:1"))
    assert tb._freebuff_state[42]["model"] == "meta/llama-3.1-8b-instruct"
    plan_calls = [p for p in captured["posts"] if p[0] == "/freebuff/plan"]
    assert plan_calls and plan_calls[0][1]["model"] == "meta/llama-3.1-8b-instruct"
    # plan edit shows an Accept/Reject keyboard
    assert captured["edits"][-1][1] == tb._review_keyboard()

    # 3. accept → runs with commit + PR, state cleared
    await tb._process_callback("tok", cb("fb:accept"))
    run_calls = [p for p in captured["posts"] if p[0] == "/freebuff/run"]
    assert run_calls and run_calls[0][1]["auto_commit"] is True
    assert run_calls[0][1]["open_pr"] is True
    assert any("pull/1" in e[0] for e in captured["edits"])
    assert 42 not in tb._freebuff_state


async def test_reject_clears_state(captured):
    await tb.cmd_freebuff(42, 100, "tok", "fix the bug")
    cb = {
        "id": "cb1",
        "from": {"id": 42},
        "message": {"chat": {"id": 100}, "message_id": 7},
        "data": "fb:reject",
    }
    await tb._process_callback("tok", cb)
    assert 42 not in tb._freebuff_state
    assert any("rejected" in e[0].lower() for e in captured["edits"])


async def test_callback_from_non_admin_is_blocked(captured, monkeypatch):
    tb._freebuff_state[99] = {"task": "x", "models": ["a/b"], "model": None}
    cb = {
        "id": "cb1",
        "from": {"id": 99},  # not allowed/admin
        "message": {"chat": {"id": 100}, "message_id": 7},
        "data": "fb:accept",
    }
    await tb._process_callback("tok", cb)
    assert any("Not allowed" in a for a in captured["answers"])


# ── _resolve_bot_user_ids (TELEGRAM_CHAT_ID single-var fallback, G1) ─────────


def test_resolve_bot_user_ids_falls_back_to_chat_id():
    allowed, admin = tb._resolve_bot_user_ids("", "", "8120976")
    assert allowed == {8120976}
    assert admin == {8120976}


def test_resolve_bot_user_ids_explicit_vars_take_precedence():
    allowed, admin = tb._resolve_bot_user_ids("1, 2", "1", "999")
    assert allowed == {1, 2}
    assert admin == {1}


def test_resolve_bot_user_ids_admin_falls_back_independently():
    # ALLOWED explicitly set, ADMIN unset -> ADMIN falls back to TELEGRAM_CHAT_ID
    allowed, admin = tb._resolve_bot_user_ids("1,2", "", "2")
    assert allowed == {1, 2}
    assert admin == {2}


def test_resolve_bot_user_ids_all_empty():
    allowed, admin = tb._resolve_bot_user_ids("", "", "")
    assert allowed == set()
    assert admin == set()


# ── wfo: workflow-orchestrator approval gate callbacks (G1) ──────────────────


def test_parse_callback_wfo_approve_reject():
    assert tb._parse_callback("wfo:approve:wfo_a1b2c3") == ("wfo_approve", "wfo_a1b2c3")
    assert tb._parse_callback("wfo:reject:wfo_a1b2c3") == ("wfo_reject", "wfo_a1b2c3")
    # Unknown prefixes / empty still yield ("", None)
    assert tb._parse_callback("wfo:") == ("", None)
    assert tb._parse_callback("notwfo:x") == ("", None)


class _FakeWfoOrchestrator:
    """Minimal stand-in for WorkflowOrchestrator's approval-gate API."""

    def __init__(self, *, approve_exc: Exception | None = None, cancel_result: bool = True):
        self.approve_calls: list[tuple[str, str]] = []
        self.approve_async_calls: list[tuple[str, str]] = []
        self.cancel_calls: list[str] = []
        self._approve_exc = approve_exc
        self._cancel_result = cancel_result

    def approve(self, run_id: str, approved_by: str = "human"):
        self.approve_calls.append((run_id, approved_by))
        if self._approve_exc is not None:
            raise self._approve_exc
        return SimpleNamespace(run_id=run_id, status="awaiting_approval", approved=True)

    async def approve_async(self, run_id: str, approved_by: str = "human"):
        self.approve_async_calls.append((run_id, approved_by))
        return SimpleNamespace(run_id=run_id, status="queued")

    def cancel_run(self, run_id: str) -> bool:
        self.cancel_calls.append(run_id)
        return self._cancel_result


def _wfo_callback(data: str) -> dict:
    return {
        "id": "cb1",
        "from": {"id": 42},
        "message": {"chat": {"id": 100}, "message_id": 7},
        "data": data,
    }


async def test_wfo_approve_resumes_run(captured, monkeypatch):
    fake = _FakeWfoOrchestrator()
    monkeypatch.setattr(
        "services.workflow_orchestrator.get_workflow_orchestrator", lambda: fake
    )

    await tb._process_callback("tok", _wfo_callback("wfo:approve:wfo_abc123"))
    # Let the fire-and-forget approve_async task run.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert fake.approve_calls == [("wfo_abc123", "telegram:42")]
    assert fake.approve_async_calls == [("wfo_abc123", "telegram:42")]
    assert any("Approved" in a for a in captured["answers"])
    assert any("Approved" in e[0] and "wfo_abc123" in e[0] for e in captured["edits"])


async def test_wfo_reject_cancels_run(captured, monkeypatch):
    fake = _FakeWfoOrchestrator(cancel_result=True)
    monkeypatch.setattr(
        "services.workflow_orchestrator.get_workflow_orchestrator", lambda: fake
    )

    await tb._process_callback("tok", _wfo_callback("wfo:reject:wfo_abc123"))

    assert fake.cancel_calls == ["wfo_abc123"]
    assert any("Rejected" in a for a in captured["answers"])
    assert any("Rejected" in e[0] and "wfo_abc123" in e[0] for e in captured["edits"])


async def test_wfo_approve_run_not_found(captured, monkeypatch):
    fake = _FakeWfoOrchestrator(approve_exc=KeyError("WorkflowRun 'wfo_abc123' not found"))
    monkeypatch.setattr(
        "services.workflow_orchestrator.get_workflow_orchestrator", lambda: fake
    )

    await tb._process_callback("tok", _wfo_callback("wfo:approve:wfo_abc123"))

    assert fake.approve_async_calls == []
    assert any("not found" in a.lower() for a in captured["answers"])
    assert any("not found" in e[0].lower() for e in captured["edits"])


async def test_wfo_approve_already_resolved(captured, monkeypatch):
    fake = _FakeWfoOrchestrator(approve_exc=ValueError("Run wfo_abc123 is 'done', not awaiting_approval"))
    monkeypatch.setattr(
        "services.workflow_orchestrator.get_workflow_orchestrator", lambda: fake
    )

    await tb._process_callback("tok", _wfo_callback("wfo:approve:wfo_abc123"))

    assert fake.approve_async_calls == []
    assert any("resolved" in a.lower() for a in captured["answers"])
    assert any("wfo_abc123" in e[0] for e in captured["edits"])


async def test_wfo_reject_run_not_found(captured, monkeypatch):
    fake = _FakeWfoOrchestrator(cancel_result=False)
    monkeypatch.setattr(
        "services.workflow_orchestrator.get_workflow_orchestrator", lambda: fake
    )

    await tb._process_callback("tok", _wfo_callback("wfo:reject:wfo_abc123"))

    assert fake.cancel_calls == ["wfo_abc123"]
    assert any("not found" in a.lower() for a in captured["answers"])
    assert any("not found" in e[0].lower() for e in captured["edits"])


async def test_wfo_callback_from_non_admin_is_blocked(captured, monkeypatch):
    fake = _FakeWfoOrchestrator()
    monkeypatch.setattr(
        "services.workflow_orchestrator.get_workflow_orchestrator", lambda: fake
    )
    cb = _wfo_callback("wfo:approve:wfo_abc123")
    cb["from"]["id"] = 99  # not allowed/admin

    await tb._process_callback("tok", cb)

    assert any("Not allowed" in a for a in captured["answers"])
    assert fake.approve_calls == []


async def test_wfo_orchestrator_unavailable(captured, monkeypatch):
    def _boom():
        raise RuntimeError("orchestrator module not importable")

    monkeypatch.setattr("services.workflow_orchestrator.get_workflow_orchestrator", _boom)

    await tb._process_callback("tok", _wfo_callback("wfo:approve:wfo_abc123"))

    assert any("unavailable" in a.lower() for a in captured["answers"])


async def test_wfo_missing_run_id(captured):
    await tb._process_callback("tok", _wfo_callback("wfo:approve:"))
    assert any("Missing run id" in a for a in captured["answers"])
