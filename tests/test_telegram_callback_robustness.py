"""Robustness tests for the Telegram inline-button callback flow."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import telegram_bot
import tasks.service as _tasks_service_mod


class _Captured:
    def __init__(self) -> None:
        self.answers: list = []
        self.edits: list = []

    async def _answer(self, *args, **kwargs):
        self.answers.append((args, kwargs))

    async def _edit(self, *args, **kwargs):
        self.edits.append((args, kwargs))


@pytest.fixture()
def captured(monkeypatch):
    cap = _Captured()
    monkeypatch.setattr(telegram_bot, "_answer_callback", cap._answer)
    monkeypatch.setattr(telegram_bot, "_edit_message", cap._edit)
    return cap


def _make_fake_task(task_id):
    task = MagicMock()
    task.task_id = task_id
    task.title = "Deploy hotfix"
    task.execution_approved = False
    return task


def _patch_workflow(monkeypatch, *, store, approve_side_effect=None):
    wf = MagicMock()
    wf.store = store
    if approve_side_effect:
        wf.approve_execution = approve_side_effect
    monkeypatch.setattr(_tasks_service_mod, "TaskWorkflowService", lambda **kw: wf)
    return wf


async def test_approve_success_clears_spinner_and_edits_message(captured, monkeypatch):
    fake_task = _make_fake_task("t1")
    fake_store = AsyncMock()
    fake_store.get.return_value = fake_task
    fake_store.update.return_value = None

    def _approve(task, **kwargs):
        task.execution_approved = kwargs.get("approved", True)
        return task

    _patch_workflow(monkeypatch, store=fake_store, approve_side_effect=_approve)
    await telegram_bot._process_task_callback(
        "test_token", "cb_approve", chat_id=1, message_id=2,
        action="task_approve", task_id=fake_task.task_id,
    )
    assert captured.answers
    assert captured.edits
    assert "Approved" in captured.edits[0][0][3]
    assert fake_task.execution_approved is True


async def test_reject_success_clears_spinner_and_edits_message(captured, monkeypatch):
    fake_task = _make_fake_task("t2")
    fake_store = AsyncMock()
    fake_store.get.return_value = fake_task
    fake_store.update.return_value = None

    def _approve(task, **kwargs):
        task.execution_approved = kwargs.get("approved", True)
        return task

    _patch_workflow(monkeypatch, store=fake_store, approve_side_effect=_approve)
    await telegram_bot._process_task_callback(
        "test_token", "cb_reject", chat_id=10, message_id=20,
        action="task_reject", task_id=fake_task.task_id,
    )
    assert captured.answers
    assert captured.edits
    assert "Rejected" in captured.edits[0][0][3]


async def test_task_not_found_clears_spinner_and_edits_message(captured, monkeypatch):
    fake_store = AsyncMock()
    fake_store.get.return_value = None
    _patch_workflow(monkeypatch, store=fake_store)
    await telegram_bot._process_task_callback(
        "test_token", "cb_null", chat_id=1, message_id=2,
        action="task_approve", task_id="t_missing",
    )
    assert captured.answers
    assert captured.edits
    edited = captured.edits[0][0][3].lower()
    assert ("not found" in edited or "not visible" in edited)


async def test_storage_init_failure_clears_spinner(captured, monkeypatch):
    def _boom(**kw):
        raise RuntimeError("mongo unreachable")
    monkeypatch.setattr(_tasks_service_mod, "TaskWorkflowService", _boom)
    await telegram_bot._process_task_callback(
        "test_token", "cb_init", chat_id=1, message_id=2,
        action="task_approve", task_id="t_init",
    )
    assert captured.answers
    assert captured.edits
    edited = captured.edits[0][0][3].lower()
    assert ("unavailable" in edited or "cannot approve" in edited or "reachable" in edited)


async def test_store_get_timeout_clears_spinner(captured, monkeypatch):
    fake_store = AsyncMock()
    async def _timeout_get(_):
        raise asyncio.TimeoutError()
    fake_store.get.side_effect = _timeout_get
    _patch_workflow(monkeypatch, store=fake_store)
    await telegram_bot._process_task_callback(
        "test_token", "cb_timeout", chat_id=1, message_id=2,
        action="task_approve", task_id="t_timeout",
    )
    assert captured.answers
    assert captured.edits
    edited = captured.edits[0][0][3].lower()
    assert ("timed out" in edited or "try the button" in edited)


async def test_store_update_exception_approve_clears_spinner(captured, monkeypatch):
    fake_task = _make_fake_task("t3")
    fake_store = AsyncMock()
    fake_store.get.return_value = fake_task
    fake_store.update.side_effect = ConnectionError("mongo down")
    def _approve(task, **kwargs):
        task.execution_approved = kwargs.get("approved", True)
        return task
    _patch_workflow(monkeypatch, store=fake_store, approve_side_effect=_approve)
    await telegram_bot._process_task_callback(
        "test_token", "cb_upd_err", chat_id=1, message_id=2,
        action="task_approve", task_id=fake_task.task_id,
    )
    assert captured.answers
    assert captured.edits
    edited = captured.edits[0][0][3].lower()
    assert ("approve failed" in edited or "approve error" in edited)


async def test_store_update_exception_reject_clears_spinner(captured, monkeypatch):
    fake_task = _make_fake_task("t4")
    fake_store = AsyncMock()
    fake_store.get.return_value = fake_task
    fake_store.update.side_effect = ConnectionError("mongo down")
    def _approve(task, **kwargs):
        task.execution_approved = kwargs.get("approved", True)
        return task
    _patch_workflow(monkeypatch, store=fake_store, approve_side_effect=_approve)
    await telegram_bot._process_task_callback(
        "test_token", "cb_rej_err", chat_id=1, message_id=2,
        action="task_reject", task_id=fake_task.task_id,
    )
    assert captured.answers
    assert captured.edits
    edited = captured.edits[0][0][3].lower()
    assert ("reject failed" in edited or "reject error" in edited)


async def test_unhandled_exception_still_clears_spinner(captured, monkeypatch):
    fake_store = AsyncMock()
    fake_store.get.side_effect = ZeroDivisionError("never-happens-in-prod")
    def _approve(task, **kw):
        return task
    _patch_workflow(monkeypatch, store=fake_store, approve_side_effect=_approve)
    await telegram_bot._process_task_callback(
        "test_token", "cb_crash", chat_id=1, message_id=2,
        action="task_approve", task_id="t_crash",
    )
    assert captured.answers, "failsafe: spinner must clear even when handler crashes"
