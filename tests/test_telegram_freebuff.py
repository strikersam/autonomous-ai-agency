"""Tests for the Telegram FreeBuff control flow (inline buttons, accept/reject)."""

from __future__ import annotations

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
        return {"models": ["nvidia/nemotron-3-super-120b-a12b", "meta/llama-3.1-8b-instruct"]}

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
