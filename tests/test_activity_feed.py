"""Alerts must be non-zero: log_activity always records to an in-memory feed so
the alerts bell works even when no Mongo DB is available (the prior behaviour was
to silently drop activity, so /api/activity always returned []).
"""

from __future__ import annotations

import os

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests-only")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("ADMIN_PASSWORD", "TestPassword1!")


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
