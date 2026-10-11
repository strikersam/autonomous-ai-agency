"""Durable tool-output offload (agent/tool_output_store.py) + the operator control."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agent import tool_output_store as tos
from agent.capability_registry import ToolRegistry, _register_tool_output_tools
from packages.config import control_overrides, settings
from packages.config.control_registry import get_control
from packages.security.redact import redact_secrets
from tests._fake_state_db import FakeDB, drain, install

SECRET = "password=hunter2hunter2hunter2 token=ghp_abcdefghijklmnopqrstuvwxyz0123456789"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setattr(settings, "agency_state_persistence_enabled_raw", "true")
    tos.reset_store()
    yield
    tos.reset_store()


def _col(db: FakeDB):
    return db.tool_output_offload


async def test_offload_persists_with_owner_and_ttl(monkeypatch):
    db = install(monkeypatch)
    ref = tos.ToolOutputStore().offload("hello world", owner="run_a")
    await drain()
    doc = _col(db).docs[ref]
    assert doc["owner"] == "run_a" and doc["text"] == "hello world"
    remaining = (doc["expires_at"] - datetime.now(timezone.utc)).total_seconds()
    assert 3590 < remaining <= 3600  # matches the 1 h in-memory TTL
    assert ("expires_at", {"expireAfterSeconds": 0, "background": True}) in _col(db).indexes


async def test_secrets_are_redacted_before_the_db_write(monkeypatch):
    db = install(monkeypatch)
    assert redact_secrets(SECRET) != SECRET  # the fixture text really is redactable
    store = tos.ToolOutputStore()
    ref = store.offload(f"log: {SECRET}", owner="run_a")
    await drain()
    stored = _col(db).docs[ref]["text"]
    assert "hunter2hunter2hunter2" not in stored and "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in stored
    assert stored == redact_secrets(f"log: {SECRET}")
    assert "hunter2hunter2hunter2" in store.read(ref, owner="run_a")["content"]  # memory is untouched


async def test_second_worker_reads_from_db_with_owner_binding(monkeypatch):
    install(monkeypatch)
    text = "x" * 9000
    ref = tos.ToolOutputStore().offload(text, owner="run_a")
    await drain()
    worker_b = tos.ToolOutputStore()
    assert worker_b.read(ref, owner="run_a")["ok"] is False  # sync = memory only
    page = await worker_b.read_async(ref, offset=0, limit=4000, owner="run_a")
    assert page["ok"] and len(page["content"]) == 4000 and page["next_offset"] == 4000
    assert page["total_length"] == 9000
    tail = await worker_b.read_async(ref, offset=8000, limit=4000, owner="run_a")
    assert tail["next_offset"] is None and len(tail["content"]) == 1000
    assert (await worker_b.read_async(ref, owner="run_b"))["ok"] is False
    assert (await worker_b.read_async(ref))["ok"] is False
    assert (await worker_b.read_async("out_nope", owner="run_a"))["ok"] is False
    assert (await worker_b.read_async(ref, offset="x", owner="run_a"))["ok"] is False


async def test_expired_db_entry_is_not_served(monkeypatch):
    db = install(monkeypatch)
    ref = tos.ToolOutputStore().offload("old", owner="o")
    await drain()
    _col(db).docs[ref]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert (await tos.ToolOutputStore().read_async(ref, owner="o"))["ok"] is False


async def test_db_error_degrades_to_unknown_ref_and_memory_still_serves(monkeypatch):
    db = install(monkeypatch)
    _col(db).fail = True
    store = tos.ToolOutputStore()
    ref = store.offload("kept", owner="o")
    await drain()
    assert (await store.read_async(ref, owner="o"))["content"] == "kept"
    assert (await tos.ToolOutputStore().read_async(ref, owner="o"))["ok"] is False


async def test_index_failure_does_not_break_persistence(monkeypatch):
    db = install(monkeypatch)
    _col(db).index_fail = True
    ref = tos.ToolOutputStore().offload("data", owner="o")
    await drain()
    assert ref in _col(db).docs


async def test_oversized_entries_stay_memory_only_but_keep_size_caps(monkeypatch):
    db = install(monkeypatch)
    monkeypatch.setattr(tos, "MAX_PERSIST_CHARS", 10)
    store = tos.ToolOutputStore(max_total_chars=100)
    ref = store.offload("y" * 50, owner="o")
    assert store.offload("z" * 101, owner="o") is None  # total-size cap unchanged
    await drain()
    assert ref and _col(db).docs == {}
    assert store.read(ref, owner="o")["ok"]


async def test_flag_off_makes_no_db_calls(monkeypatch):
    db = install(monkeypatch)
    monkeypatch.setattr(settings, "agency_state_persistence_enabled_raw", "false")
    store = tos.ToolOutputStore()
    ref = store.offload("memory only", owner="o")
    assert (await store.read_async(ref, owner="o"))["ok"]
    assert (await tos.ToolOutputStore().read_async(ref, owner="o"))["ok"] is False
    await drain()
    assert db._cols == {}


def test_no_running_loop_is_memory_only(monkeypatch):
    db = install(monkeypatch)
    ref = tos.ToolOutputStore().offload("no loop", owner="o")  # no running loop: dropped
    assert ref and db._cols == {}


async def test_persist_false_store_never_writes(monkeypatch):
    db = install(monkeypatch)
    tos.ToolOutputStore(persist=False).offload("private", owner="o")
    await drain()
    assert db._cols == {}


async def test_registry_tool_falls_back_to_db(monkeypatch):
    install(monkeypatch)
    ref = tos.ToolOutputStore().offload("payload", owner="run_a")  # another worker
    await drain()
    reg = ToolRegistry()
    _register_tool_output_tools(reg)
    tool = reg.get("read_tool_output")
    assert (await tool.handler(ref, owner="run_a"))["content"] == "payload"
    assert (await tool.handler(ref, owner="run_b"))["ok"] is False


# ── Operator control ──────────────────────────────────────────────────────────


def test_persistence_control_registered_and_override_is_live():
    from packages.storage.state_persistence import persistence_enabled

    spec = get_control("AGENCY_STATE_PERSISTENCE_ENABLED")
    assert spec is not None and spec.live and spec.default == "true"
    applied = dict(control_overrides._applied)
    try:
        control_overrides.apply_overrides({"AGENCY_STATE_PERSISTENCE_ENABLED": "true"})
        assert persistence_enabled() is True  # conftest defaults it off; an override turns it on
        control_overrides.apply_overrides({"AGENCY_STATE_PERSISTENCE_ENABLED": "false"})
        assert persistence_enabled() is False
    finally:
        control_overrides.apply_overrides({})
        control_overrides._applied.clear()
        control_overrides._applied.update(applied)
