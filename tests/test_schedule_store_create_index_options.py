"""Regression tests for the MongoDB index creation in ScheduleStore.

Verifies the create_index call:
  1. Injects ``background=True`` so the build is off the request thread.
  2. Is skipped when the job_id index already exists (re-creating serialises
     writes against the collection for the duration of the build).

Both checks guard against a startup-time performance regression that
originally referred to the live collection and held the FastAPI lifespan.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock


def _install_pymongo_stub(fake_collection: MagicMock) -> None:
    """Stub pymongo so ``ScheduleStore.__init__`` resolves to ``fake_collection``.

    Implementation walks: ``client[db_name][_COLLECTION]`` \u2014 TWO ``__getitem__``
    hops. The first hop returns the database (modeled as fake_collection itself);
    the second hop subscript on the database returns the collection (also
    fake_collection). We wire the chain so both hops resolve to the same
    fake_collection with the create_index / index_information mocks in place.
    """
    pymongo_stub = MagicMock()
    pymongo_stub.MongoClient = MagicMock(
        return_value=MagicMock(
            admin=MagicMock(command=MagicMock(return_value={"ok": 1})),
            __getitem__=MagicMock(return_value=fake_collection),
        )
    )
    sys.modules["pymongo"] = pymongo_stub
    # The second hop on the database object must also resolve to fake_collection
    # so that ``self._collection`` carries our create_index / index_information
    # mocks. Without this wiring the auto-mock returns a fresh MagicMock that
    # silently no-ops create_index.
    fake_collection.__getitem__ = MagicMock(return_value=fake_collection)


def _restore_pymongo() -> None:
    sys.modules.pop("pymongo", None)


def test_schedule_store_creates_index_with_background_true(monkeypatch) -> None:
    # Force the Mongo path even when STORAGE_BACKEND=sqlite in the test env
    # (this test stubs pymongo and verifies Mongo index creation specifically).
    monkeypatch.setenv("STORAGE_BACKEND", "mongo")
    from agent.schedule_store import ScheduleStore

    fake_collection = MagicMock()
    fake_collection.index_information.return_value = {}  # no existing index

    captured_kwargs: dict = {}
    fake_collection.create_index = MagicMock(
        side_effect=lambda *a, **kw: (captured_kwargs.update(kw) or "job_id_1")
    )

    _install_pymongo_stub(fake_collection)
    try:
        ScheduleStore()
    finally:
        _restore_pymongo()

    assert "background" in captured_kwargs, "background kwarg MUST be passed (lazy build)"
    assert captured_kwargs["background"] is True, "background kwarg MUST be True"
    assert captured_kwargs.get("unique") is True, "unique constraint MUST be preserved"


def test_schedule_store_skips_index_already_present(monkeypatch) -> None:
    # Force the Mongo path even when STORAGE_BACKEND=sqlite in the test env.
    monkeypatch.setenv("STORAGE_BACKEND", "mongo")
    from agent.schedule_store import ScheduleStore

    fake_collection = MagicMock()
    # Pre-existing index with the exact (job_id, 1) key spec.
    fake_collection.index_information.return_value = {
        "job_id_1": {"key": [("job_id", 1)], "unique": True},
    }
    fake_collection.create_index = MagicMock()

    _install_pymongo_stub(fake_collection)
    try:
        ScheduleStore()
    finally:
        _restore_pymongo()

    assert fake_collection.create_index.call_count == 0, (
        "create_index MUST be skipped when an index on (job_id,1) already exists"
    )
