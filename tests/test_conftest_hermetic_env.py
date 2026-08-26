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
    ("AGENCY_CEO_ENABLED", "false"),
    ("RUN_BACKGROUND_IN_WEB", "false"),
])
def test_hermetic_env_var_is_set(var: str, expected: str) -> None:
    """conftest must pin every hermeticity flag before backend import."""
    assert os.environ.get(var) == expected, (
        f"{var} must be {expected!r} in the test process — see tests/conftest.py"
    )


def test_admin_identity_matches_the_server_module() -> None:
    """The env admin address must be the one ``backend.server`` captured.

    ``backend/server.py`` resolves ``ADMIN_EMAIL`` once at import. If any test
    module mutates the env afterwards, ``seed_admin()`` seeds one address while
    tests authenticate as another — a 401 that reads like a password bug.
    """
    import backend.server

    assert backend.server.ADMIN_EMAIL == os.environ["ADMIN_EMAIL"], (
        "Admin identity split: the server seeds "
        f"{backend.server.ADMIN_EMAIL!r} but the env says "
        f"{os.environ['ADMIN_EMAIL']!r}"
    )


def test_no_test_module_reassigns_admin_email_at_import() -> None:
    """Guards the specific landmine: a module-level ADMIN_EMAIL setdefault.

    ``tests/test_activity_feed.py`` set ``ADMIN_EMAIL=admin@test.local`` at
    import time without ever using it, splitting the admin identity for every
    module imported after it.
    """
    from pathlib import Path

    this_file = Path(__file__).resolve()
    needle = 'setdefault("ADMIN_EMAIL"'
    offenders = [
        path.name
        for path in sorted(this_file.parent.glob("test_*.py"))
        if path != this_file and needle in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        "These test modules reassign ADMIN_EMAIL at import and will split the "
        f"admin identity for every module imported after them: {offenders}. "
        "conftest.py already pins it for the whole session."
    )


def test_conftest_does_not_pin_storage_backend() -> None:
    """conftest must NOT pin ``STORAGE_BACKEND=sqlite``.

    It looks like the obvious hermeticity fix and it is a trap. Routing the
    whole suite through SQLiteStore leaks an unclosed aiosqlite connection
    whose ``_connection_worker_thread`` is non-daemon and waits on its queue
    forever, with no atexit handler to reap it: every test passes, then the
    interpreter never exits. The CI test job declares no ``timeout-minutes``,
    so it runs toward GitHub's 360-minute ceiling — measured at 51+ minutes
    against master's 3m27s for the same step.

    The workflows carry a `mongo:7` service instead. A thread-inspection test
    cannot guard this (it would only see the threads alive at its own
    execution moment), so this asserts the decision itself, and
    ``pytest_sessionfinish`` in conftest reports any leak at the moment it
    would actually bite.
    """
    from pathlib import Path

    conftest = (Path(__file__).resolve().parent / "conftest.py").read_text(encoding="utf-8")
    assert 'setdefault("STORAGE_BACKEND"' not in conftest, (
        "conftest pins STORAGE_BACKEND — this hangs the suite at interpreter "
        "exit via a non-daemon aiosqlite worker thread. Read the note in "
        "conftest.py before re-adding it."
    )
