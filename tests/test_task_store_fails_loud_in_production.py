"""Regression: prevent silent TaskStore in-memory fallback in production.

The 'phantom Telegram task' bug surfaced because tasks/store.py silently fell
back to an in-memory dict when no DB connection was supplied.  Telegram
notifications referenced task_ids with no persistent backing, leaving
end-users unable to find or act on them from the dashboard or from the bot
callback handler.

This test pins the contract: outside TESTING mode, TaskStore MUST fail loud
when no DB backend is wired in.  In TESTING mode (conftest.py sets
TESTING=true at import), the in-memory fallback remains so legacy tests
keep working.
"""
from __future__ import annotations

import importlib
import sys

import pytest


@pytest.fixture
def fresh_store_module(monkeypatch):
    """Force a fresh import of tasks.store so module-level state is clean."""
    for mod_name in [m for m in list(sys.modules) if m == "tasks.store" or m.startswith("tasks.store.")]:
        monkeypatch.delitem(sys.modules, mod_name, raising=False)
    return importlib.import_module("tasks.store")


def test_task_store_raises_in_production(monkeypatch, fresh_store_module):
    """With TESTING unset (production), TaskStore(db=None) MUST raise."""
    monkeypatch.delenv("TESTING", raising=False)
    cls = fresh_store_module.TaskStore
    assert cls is not None
    with pytest.raises(RuntimeError, match="TaskStore cannot start without a persistent backend"):
        cls(db=None)


def test_task_store_allows_inmemory_when_testing(monkeypatch, fresh_store_module):
    """With TESTING=true (CI), TaskStore(db=None) MUST allow in-memory fallback."""
    monkeypatch.setenv("TESTING", "true")
    cls = fresh_store_module.TaskStore
    cls(db=None)  # must not raise
