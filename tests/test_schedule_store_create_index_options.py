"""Regression tests for the MongoDB index creation in ScheduleStore.

Verifies the create_index call:
  1. Injects ``background=True`` so the build is off the request thread.
  2. Is skipped when the job_id index already exists (re-creating serialises
     writes against the collection for the duration of the build).

Both checks guard against a startup-time performance regression that
originally referred to the live collection and held the FastAPI lifespan.
"""
from __future__ import annotations

from unittest.mock import MagicMock


def _make_index_info(existing_key: list[tuple] | None = None) -> dict:
    """Build a stub index_information() return value for the job_id index.

    Each entry's 'key' tuple is preserved verbatim so the implementation
    can compare it to (('job_id', 1),).
    """
    if existing_key is None:
        return {}
    return {"job_id_1": {"key": existing_key}}


def test_schedule_store_creates_index_with_background_true() -> None:
    """On a fresh collection, create_index is called with the right kwargs."""
    from agent.schedule_store import ScheduleStore
    fakemodule = MagicMock()

    # When background=True is passed to Motor/MongoDB, the call site returns None.
    captured_kwargs: dict = {}

    def fake_create_index(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return "job_id_1"

    fake_collection = MagicMock()
    fake_collection.create_index = fake_create_index
    fake_collection.index_information.return_value = _make_index_info()  # no existing index

    fakemodule.MongoClient.return_value = MagicMock(
        admin=MagicMock(command=MagicMock(return_value={"ok": 1})),
        **{"_db_path": MagicMock(__getitem__=MagicMock(return_value=fake_collection))},
    )

    # Direct path on the constructor: we exercise the implementation via
    # monkeypatching pymongo at import time.
    import sys
    saved = sys.modules.get("pymongo")
    pymongo_stub = MagicMock()
    pymongo_stub.MongoClient = MagicMock(
        return_value=MagicMock(
            admin=MagicMock(command=MagicMock(return_value={"ok": 1})),
            __getitem__=MagicMock(return_value=fake_collection),
        )
    )
    sys.modules["pymongo"] = pymongo_stub

    try:
        ScheduleStore()
    finally:
        if saved is None:
            sys.modules.pop("pymongo", None)
        else:
            sys.modules["pymongo"] = saved

    assert "background" in captured_kwargs, "background kwarg MUST be passed (lazy build)"
    assert captured_kwargs["background"] is True, "background kwarg MUST be True"
    assert captured_kwargs.get("unique") is True, "unique constraint MUST be preserved"


def test_schedule_store_skips_index_already_present() -> None:
    """If the job_id index exists, create_index MUST NOT be called again."""
    from agent.schedule_store import ScheduleStore
    import sys

    fake_collection = MagicMock()
    fake_collection.index_information.return_value = _make_index_info([("job_id", 1)])
    create_calls: list[dict] = []
    fake_collection.create_index = MagicMock(
        side_effect=lambda *a, **kw: create_calls.append(kw) or "job_id_1"
    )

    saved = sys.modules.get("pymongo")
    pymongo_stub = MagicMock()
    pymongo_stub.MongoClient = MagicMock(
        return_value=MagicMock(
            admin=MagicMock(command=MagicMock(return_value={"ok": 1})),
            __getitem__=MagicMock(return_value=fake_collection),
        )
    )
    sys.modules["pymongo"] = pymongo_stub

    try:
        ScheduleStore()
    finally:
        if saved is None:
            sys.modules.pop("pymongo", None)
        else:
            sys.modules["pymongo"] = saved

    assert fake_collection.create_index.call_count == 0, "create_index MUST be skipped when index exists"
