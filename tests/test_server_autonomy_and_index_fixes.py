"""tests/test_server_autonomy_and_index_fixes.py — two production regressions.

1. ``_autonomy_bg_cycle`` crashed every cycle with ``name 'time' is not
   defined``: the module imports ``import time as _time``, so a bare
   ``time.time()`` inside the cycle is a ``LOAD_GLOBAL`` for a name the module
   namespace never binds. The warning "Autonomy background cycle error: name
   'time' is not defined" fired on every tick. The structural test below
   disassembles the function and asserts every global it loads actually
   resolves — catching this and any future same-shape typo.

2. ``tasks.source_id`` unique index could never build. It was declared
   ``sparse=True``, but a sparse unique index still indexes documents whose
   field is present-but-null, so the many tasks with ``source_id: null`` all
   collided (E11000 dup key {source_id: null}). The fix uses a
   ``partialFilterExpression`` restricting the index to string source_ids.
"""
from __future__ import annotations

import dis

import pytest


def _undefined_globals(func) -> list[str]:
    """Return the names ``func`` loads as globals that resolve to nothing.

    A ``LOAD_GLOBAL`` for a name that is neither in the module's namespace nor a
    builtin is a guaranteed ``NameError`` the moment that line runs.
    """
    import builtins

    module = __import__(func.__module__, fromlist=["_"])
    missing: list[str] = []
    for instr in dis.get_instructions(func):
        if instr.opname != "LOAD_GLOBAL":
            continue
        name = instr.argval
        if hasattr(module, name) or hasattr(builtins, name):
            continue
        missing.append(name)
    return missing


def test_autonomy_bg_cycle_has_no_undefined_globals():
    from backend.server import _autonomy_bg_cycle, _time

    # The module binds the stdlib time module under the private alias only.
    import time as _stdlib_time
    assert _time is _stdlib_time

    missing = _undefined_globals(_autonomy_bg_cycle)
    assert missing == [], (
        f"_autonomy_bg_cycle references undefined globals {missing} — a bare "
        f"time.time() (should be _time.time()) is the classic case."
    )


@pytest.mark.asyncio
async def test_source_id_index_is_partial_not_sparse(monkeypatch):
    """The unique index must be built with partialFilterExpression, never sparse.

    A sparse unique index cannot coexist with explicit null source_ids; only a
    partial index (restricted to string values) builds on real data.
    """
    import backend.server as server

    captured: dict[str, object] = {}

    class _FakeIndexes:
        async def create_index(self, keys, **kwargs):
            captured["keys"] = keys
            captured["kwargs"] = kwargs
            return "source_id_1"

    class _FakeDB:
        tasks = _FakeIndexes()

    async def _noop_dedup():
        return {"deleted": 0}

    # Dedup pass is exercised elsewhere; stub it so this test isolates the index.
    monkeypatch.setattr(
        "services.self_heal._heal_task_duplicates", _noop_dedup, raising=True
    )
    monkeypatch.setattr(server, "get_db", lambda: _FakeDB(), raising=True)

    await server._ensure_tasks_source_id_unique_index()

    assert captured["keys"] == "source_id"
    kwargs = captured["kwargs"]
    assert kwargs.get("unique") is True
    assert "sparse" not in kwargs, "sparse cannot exclude present-but-null keys"
    assert kwargs.get("partialFilterExpression") == {"source_id": {"$type": "string"}}
