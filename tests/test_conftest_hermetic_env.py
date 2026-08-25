"""Guards the hermeticity contract that ``tests/conftest.py`` establishes.

Rule 32 requires tests to be hermetic. Most of that contract is enforced by
env vars conftest sets before any backend import; if one is dropped the suite
does not fail loudly, it fails *slowly and confusingly* somewhere unrelated.

``STORAGE_BACKEND`` is the case that actually bit us. ``db/__init__.py``
resolves it with a ``"mongo"`` default (right for production), so with the var
unset any test reaching the real store dialled ``localhost:27017``, burned the
server-selection timeout and raised ``ServerSelectionTimeoutError`` — one red
error in an otherwise green 6235-test run, for weeks (issues #1352 / #1354).
"""
from __future__ import annotations

import os

import pytest


@pytest.mark.parametrize("var,expected", [
    ("TESTING", "true"),
    ("STORAGE_BACKEND", "sqlite"),
    ("AGENCY_CEO_ENABLED", "false"),
    ("RUN_BACKGROUND_IN_WEB", "false"),
])
def test_hermetic_env_var_is_set(var: str, expected: str) -> None:
    """conftest must pin every hermeticity flag before backend import."""
    assert os.environ.get(var) == expected, (
        f"{var} must be {expected!r} in the test process — see tests/conftest.py"
    )


def test_store_is_not_mongo_backed() -> None:
    """The resolved store must never be the Mongo one under test.

    Asserting on the concrete class (not just the env var) catches a
    resolution-order regression in ``db/__init__.py`` that leaves the env var
    correct but still hands back a Mongo store.
    """
    from db import get_store

    store = get_store()
    assert type(store).__name__ != "MongoStore", (
        "Tests resolved a MongoStore — the suite would dial a real MongoDB"
    )
