"""Alerts must be non-zero: log_activity always records to an in-memory feed so
the alerts bell works even when no Mongo DB is available (the prior behaviour was
to silently drop activity, so /api/activity always returned []).
"""

from __future__ import annotations

import os

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests-only")
# NOTE: do not set ADMIN_EMAIL here. This module never used it, but the
# assignment ran at *import* time and mutated the shared environment for every
# test module imported after it. `backend/server.py` reads ADMIN_EMAIL once at
# its own import (already done via conftest), so seed_admin() kept seeding
# admin@llmrelay.local while later modules re-read the env and authenticated as
# admin@test.local — a 401 that looked like a password bug. conftest pins
# ADMIN_EMAIL for the whole session instead.


async def test_log_activity_records_to_in_memory_feed():
    import backend.server as server

    server._ACTIVITY_BUFFER.clear()
    await server.log_activity("test", "something happened", user_id="u1")
    assert len(server._ACTIVITY_BUFFER) == 1
    entry = server._ACTIVITY_BUFFER[0]
    assert entry["category"] == "test"
    assert entry["message"] == "something happened"


async def test_activity_buffer_survives_db_outage(monkeypatch):
    import backend.server as server

    server._ACTIVITY_BUFFER.clear()

    # Simulate a DB outage: get_db() raises. The in-memory feed must still capture it.
    def _boom():
        raise RuntimeError("no db")

    monkeypatch.setattr(server, "get_db", _boom)
    await server.log_activity("alert", "task failed", user_id="u2")
    assert any(e["message"] == "task failed" for e in server._ACTIVITY_BUFFER)
