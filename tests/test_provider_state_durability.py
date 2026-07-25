"""Operator provider state must survive a redeploy.

The per-provider kill switch and the paid-provider toggle were persisted only to
the local SQLite ``kv_store``. Render's disk is ephemeral, so every deploy wiped
that file: providers the operator had switched off silently rejoined the
rotation, and ``allow_paid`` reverted to false even though the UI had written it
to Mongo. These tests pin the durable path, the fallbacks, and — critically —
that a slow or dead Mongo can never stall or brick dispatch, because both
readers sit on the sync hot path inside the event loop.
"""
from __future__ import annotations

import os
import time
import uuid

import pytest

import services.brain_failover as bf


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Temp SQLite mirror + clean caches, so no test sees another's state."""
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "kv.db"))
    bf.reset_kv_state()
    yield
    bf.reset_kv_state()


# ── Fake Mongo ───────────────────────────────────────────────────────────────
# Exercises the read/write logic without a server. The real round trip against a
# live Mongo is covered separately below and skipped when none is reachable.

class _FakeCollection:
    def __init__(self, docs=None):
        self.docs: dict[str, dict] = dict(docs or {})
        self.raises: Exception | None = None

    def _check(self):
        if self.raises is not None:
            raise self.raises

    def find(self, query):
        self._check()
        kind = query.get("kind")
        return [
            dict(d, _id=k) for k, d in self.docs.items()
            if kind is None or d.get("kind") == kind
        ]

    def find_one(self, query):
        self._check()
        for k, d in self.docs.items():
            if query.get("_id") in (None, k) and all(
                d.get(f) == v for f, v in query.items() if f != "_id"
            ):
                return dict(d, _id=k)
        return None

    def update_one(self, query, update, upsert=False):
        self._check()
        key = query["_id"]
        self.docs.setdefault(key, {}).update(update["$set"])

    def delete_one(self, query):
        self._check()
        self.docs.pop(query["_id"], None)


class _FakeDb:
    def __init__(self):
        self.kv = _FakeCollection()
        self.providers = _FakeCollection()

    def __getitem__(self, name):
        if name == bf._KV_COLLECTION:
            return self.kv
        raise KeyError(name)


@pytest.fixture
def fake_mongo(monkeypatch):
    db = _FakeDb()
    monkeypatch.setattr(bf, "_mongo_db", lambda: db)
    return db


# ── The gate: when is the durable path used at all? ──────────────────────────

class TestMongoGate:
    @pytest.fixture(autouse=True)
    def _production_like(self, monkeypatch):
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.setenv("STORAGE_BACKEND", "mongo")
        monkeypatch.setenv("MONGO_URL", "mongodb://mongo.test:27017")

    def test_enabled_when_mongo_is_the_configured_backend(self) -> None:
        assert bf._mongo_enabled() is True

    def test_disabled_under_the_test_suite(self, monkeypatch) -> None:
        """Tests must never mutate a shared operational store."""
        monkeypatch.setenv("TESTING", "true")
        assert bf._mongo_enabled() is False

    def test_disabled_when_the_operator_chose_sqlite(self, monkeypatch) -> None:
        monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
        assert bf._mongo_enabled() is False

    def test_disabled_when_mongo_url_is_not_set(self, monkeypatch) -> None:
        """The storage layer's localhost default is a placeholder, not config.

        Treating it as configured would add a connection timeout to dispatch on
        every dev machine without a local Mongo.
        """
        monkeypatch.delenv("MONGO_URL", raising=False)
        assert bf._mongo_enabled() is False

    def test_disabled_during_the_error_backoff(self) -> None:
        bf._mongo_unavailable(OSError("connection refused"))
        assert bf._mongo_enabled() is False

    def test_backoff_expires(self, monkeypatch) -> None:
        bf._mongo_unavailable(OSError("connection refused"))
        monkeypatch.setattr(
            bf.time, "time", lambda: bf._mongo_retry_after + 1.0
        )
        assert bf._mongo_enabled() is True


# ── Kill switch ──────────────────────────────────────────────────────────────

class TestKillSwitchDurability:
    def test_disable_writes_to_mongo(self, fake_mongo) -> None:
        bf.set_provider_enabled("groq", False, "manual test")

        doc = fake_mongo.kv.docs[bf._DISABLED_KEY_PREFIX + "groq"]
        assert doc["value"] == "manual test"
        assert doc["kind"] == "provider_disabled"
        assert doc["provider_id"] == "groq"

    def test_disable_also_mirrors_to_sqlite(self, fake_mongo) -> None:
        """The local mirror is what keeps operator intent during a Mongo outage."""
        bf.set_provider_enabled("groq", False, "manual test")
        assert bf._disabled_from_sqlite() == {"groq": "manual test"}

    def test_read_prefers_mongo_over_a_stale_local_mirror(self, fake_mongo) -> None:
        bf._write_disabled_sqlite("zhipu", False, "stale local value")
        fake_mongo.kv.docs[bf._DISABLED_KEY_PREFIX + "groq"] = {
            "value": "auto: 401", "kind": "provider_disabled",
        }

        off = bf.disabled_providers(force=True)
        assert off == {"groq": "auto: 401"}, (
            "Mongo is the durable copy and must win — the local file is wiped on "
            "deploy and can lag behind another process"
        )

    def test_enable_removes_the_mongo_document(self, fake_mongo) -> None:
        bf.set_provider_enabled("groq", False, "manual test")
        bf.set_provider_enabled("groq", True)

        assert fake_mongo.kv.docs == {}
        assert bf.disabled_providers(force=True) == {}

    def test_round_trip_survives_a_process_restart(self, fake_mongo) -> None:
        """A restart clears every in-memory cache; the state must still be there."""
        bf.set_provider_enabled("zhipu", False, "auto: 401 invalid key")
        bf.reset_kv_state()

        assert bf.disabled_providers(force=True) == {"zhipu": "auto: 401 invalid key"}

    def test_mongo_read_failure_falls_back_to_the_local_mirror(
        self, fake_mongo
    ) -> None:
        bf._write_disabled_sqlite("groq", False, "local copy")
        fake_mongo.kv.raises = OSError("mongo down")

        assert bf.disabled_providers(force=True) == {"groq": "local copy"}
        assert bf._mongo_retry_after > time.time(), (
            "a failed read must open the backoff so an unreachable Mongo costs "
            "one stall, not one per dispatch attempt"
        )

    def test_both_stores_failing_never_raises(self, fake_mongo, monkeypatch) -> None:
        fake_mongo.kv.raises = OSError("mongo down")
        monkeypatch.setattr(bf, "_kv_connect", lambda: (_ for _ in ()).throw(
            OSError("disk gone")))

        assert bf.disabled_providers(force=True) == {}   # last known set
        bf.set_provider_enabled("groq", False, "x")      # no exception

    def test_a_switch_that_persisted_nowhere_is_reported_as_an_error(
        self, monkeypatch, caplog
    ) -> None:
        """Never claim a switch took effect when no store accepted it.

        Mongo off (``None``, not ``False``) plus a dead SQLite is the dev/CI
        shape of "nothing was written", and it must not log as a success.
        """
        monkeypatch.setattr(bf, "_mongo_db", lambda: None)
        monkeypatch.setattr(bf, "_kv_connect", lambda: (_ for _ in ()).throw(
            OSError("disk gone")))

        with caplog.at_level("INFO"):
            bf.set_provider_enabled("groq", False, "x")

        messages = [r.getMessage() for r in caplog.records]
        assert any("was not persisted anywhere" in m for m in messages)
        assert not any("DISABLED" in m for m in messages)

    def test_mongo_write_failure_still_persists_locally(
        self, fake_mongo, caplog
    ) -> None:
        fake_mongo.kv.raises = OSError("mongo down")

        with caplog.at_level("WARNING"):
            bf.set_provider_enabled("groq", False, "manual test")

        assert bf._disabled_from_sqlite() == {"groq": "manual test"}
        assert any("revert on the next deploy" in r.getMessage()
                   for r in caplog.records), (
            "an operator whose switch will not survive the next deploy must be told"
        )


# ── Paid-provider policy ─────────────────────────────────────────────────────

class TestPaidPolicyDurability:
    def test_reads_the_durable_providers_document(self, fake_mongo) -> None:
        """This is the document the UI toggle writes via _set_provider_policy."""
        fake_mongo.providers.docs["policy"] = {
            "provider_id": "provider_policy", "allow_paid": True,
        }
        assert bf._is_paid_allowed_db() is True

    def test_false_document_wins_over_a_stale_local_true(self, fake_mongo) -> None:
        bf._kv_connect().close()
        conn = bf._kv_connect()
        conn.execute("INSERT OR REPLACE INTO kv_store VALUES (?, ?)",
                     (bf._PAID_POLICY_KEY, "true"))
        conn.commit()
        conn.close()
        fake_mongo.providers.docs["policy"] = {
            "provider_id": "provider_policy", "allow_paid": False,
        }

        assert bf._is_paid_allowed_db() is False

    def test_falls_back_to_the_kv_mirror_when_no_document_exists(
        self, fake_mongo
    ) -> None:
        fake_mongo.kv.docs[bf._PAID_POLICY_KEY] = {"value": "true"}
        assert bf._is_paid_allowed_db() is True

    def test_defaults_to_false_when_nothing_is_stored(self, fake_mongo) -> None:
        """Never enable paid spend by accident."""
        assert bf._is_paid_allowed_db() is False

    def test_mongo_failure_falls_back_to_the_local_mirror(self, fake_mongo) -> None:
        conn = bf._kv_connect()
        conn.execute("INSERT OR REPLACE INTO kv_store VALUES (?, ?)",
                     (bf._PAID_POLICY_KEY, "true"))
        conn.commit()
        conn.close()
        fake_mongo.providers.raises = OSError("mongo down")

        assert bf._is_paid_allowed_db() is True

    def test_a_broken_mirror_does_not_enable_paid_spend(
        self, fake_mongo, monkeypatch
    ) -> None:
        fake_mongo.providers.raises = OSError("mongo down")
        monkeypatch.setattr(bf, "_kv_connect", lambda: (_ for _ in ()).throw(
            OSError("disk gone")))
        assert bf._is_paid_allowed_db() is False


# ── Durability signal shown in the UI ────────────────────────────────────────

class TestDurabilitySignal:
    def test_true_when_mongo_is_reachable(self, fake_mongo) -> None:
        assert bf.state_is_durable() is True

    def test_false_on_a_sqlite_only_deployment(self, monkeypatch) -> None:
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
        assert bf.state_is_durable() is False


# ── Real Mongo, no fakes ─────────────────────────────────────────────────────

def _live_mongo_url() -> str | None:
    """Return a reachable MONGO_URL, or None so the test skips."""
    import os
    url = (os.environ.get("MONGO_URL") or "").strip()
    if not url:
        return None
    try:
        from pymongo import MongoClient
        MongoClient(url, serverSelectionTimeoutMS=2000).admin.command("ping")
    except Exception:  # noqa: BLE001 — no server here; skip, don't fail
        return None
    return url


def test_real_mongo_round_trip(monkeypatch, tmp_path) -> None:
    """The pymongo path itself works — the fakes above cannot prove that.

    Skipped when no Mongo is reachable (local dev); runs in CI, which provides
    one. Uses a throwaway database so no operational state is touched.
    """
    url = _live_mongo_url()
    if url is None:
        pytest.skip("no reachable MONGO_URL")

    db_name = f"bf_durability_{uuid.uuid4().hex[:8]}"
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "mongo")
    monkeypatch.setenv("DB_NAME", db_name)
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "live.db"))
    bf.reset_kv_state()

    try:
        bf.set_provider_enabled("groq", False, "auto: 402 no credit")
        assert bf.state_is_durable() is True

        # Wipe the local mirror and every cache: only Mongo can answer now.
        (tmp_path / "live.db").unlink()
        bf.reset_kv_state()
        assert bf.disabled_providers(force=True) == {"groq": "auto: 402 no credit"}

        bf.set_provider_enabled("groq", True)
        bf.reset_kv_state()
        assert bf.disabled_providers(force=True) == {}
    finally:
        from pymongo import MongoClient
        MongoClient(url, serverSelectionTimeoutMS=2000).drop_database(db_name)
        bf.reset_kv_state()


# ── The suite must not touch the real operator database ──────────────────────

def test_conftest_isolates_operator_state_for_every_test() -> None:
    """Both halves matter, and the second one is easy to drop.

    Redirecting ``SQLITE_PATH`` alone is insufficient: both reads are cached for
    5-10 s, so one test that read the developer's real ``.data/agency.db`` left
    ``allow_paid=True`` in ``_PAID_CACHE`` and every test for the next ten
    seconds inherited it regardless of its own path. That is what made
    ``test_paid_providers_skipped_by_default`` fail only in a full run. The
    caches must be dropped per test as well as the path.
    """
    from pathlib import Path

    src = (Path(__file__).parent / "conftest.py").read_text()
    parts = src.split("_isolate_operator_provider_state", 1)
    assert len(parts) == 2, "the autouse operator-state isolation fixture is gone"
    body = parts[1]
    assert "SQLITE_PATH" in body, "the fixture must redirect the kv path"
    assert "reset_kv_state" in body, (
        "the fixture must also drop the read caches — the path alone leaks"
    )


def test_the_running_test_is_not_pointed_at_the_real_database() -> None:
    path = os.environ.get("SQLITE_PATH", "")
    assert path, "SQLITE_PATH must be redirected during tests"
    assert not path.endswith(".data/agency.db"), (
        f"tests would read and WRITE the real operator database ({path}) — the "
        f"kill switch persists there, so a test run would switch off providers "
        f"in a developer's actual configuration"
    )
