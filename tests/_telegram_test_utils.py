"""tests/_telegram_test_utils.py

Snapshot/restore helper for ``telegram_bot`` module-level globals + the
``TELEGRAM_POLLER_DISABLED`` environment variable.

Used by ``tests/test_telegram_diag.py``, ``tests/test_telegram_inbound.py``,
and ``tests/test_telegram_freebuff.py`` so each test starts from a known-clean
state and never leaks module-level state to the next test (no cascade damage
where a True flag set in test A survives into test B).

Exposes:

* ``isolated_telegram_config(...)`` — a ``@contextlib.contextmanager`` you
  drive explicitly from a ``setUp``/``tearDown`` pair via
  ``self._ctx.__enter__()`` / ``self._ctx.__exit__(None, None, None)``.
* ``isolated_telegram`` — a thin pytest fixture wrapping the same context
  manager for unittest-free test files.
"""
from __future__ import annotations

import contextlib
import os
from typing import Iterator

import pytest  # always available in this repo's dev/CI workflow

import telegram_bot as tb  # consumers also import this at module-top; the
#                           shared dep means a defensive local import is
#                           needless — declare it once at module scope.


_MISSING = object()


_TRACKED_GLOBALS: tuple[str, ...] = (
    "TELEGRAM_BOT_TOKEN",
    "ALLOWED_USER_IDS",
    "ADMIN_USER_IDS",
    "_send_message",
    "_send_message_with_id",
    "_EMPTY_ALLOWLIST_WARNED",
)


@contextlib.contextmanager
def isolated_telegram_config(
    *,
    token: object = _MISSING,
    allowed: object = _MISSING,
    admin: object = _MISSING,
    send_message: object = _MISSING,
    send_message_with_id: object = _MISSING,
    reset_throttle: bool = True,
    poller_disabled: object = _MISSING,
) -> Iterator[None]:
    """Snapshot+restore ``tb`` globals + ``TELEGRAM_POLLER_DISABLED``.

    Keyword args are *apply filters*: each kwarg name corresponds to a
    tracked global (see ``_TRACKED_GLOBALS``); passing a non-``_MISSING``
    value sets the module attribute at scope entry. Default ``_MISSING``
    leaves the existing value alone.

    ``reset_throttle=True`` (the default) explicitly sets
    ``tb._EMPTY_ALLOWLIST_WARNED = False`` at scope entry AND records
    ``False`` for restoration. This is the safe choice for any test that
    relies on the silent-drop throttle starting fresh — without this, a
    prior test that set the flag to ``True`` would carry it forward into
    the next test and silently change observable behaviour. Set
    ``reset_throttle=False`` only when the test specifically asserts state
    that depends on the throttle flag's prior value (e.g. a test that
    mutates ``tb._EMPTY_ALLOWLIST_WARNED`` mid-test and then verifies a
    restoration — the *lenient* choice).

    ``poller_disabled`` accepts three explicit semantics:

    * ``_MISSING`` (default) — leave the environment variable alone. Use
      this for tests that don't care about the poller's enabled/disabled
      state.
    * ``None`` — explicitly *pop* the environment variable. This matches
      ``os.environ.pop("TELEGRAM_POLLER_DISABLED", None)`` semantics.
      Use this for tests that need the poller ABSENT (active by default).
    * Any string (e.g. ``"true"``, ``"1"``) — set
      ``TELEGRAM_POLLER_DISABLED`` to that string. Use this for tests
      that need the poller DISABLED.

    Note this kwarg's ``None`` semantics (pop env var) are deliberately
    different from every other kwarg's ``None`` semantics (assign ``None``
    is treated as a literal value). The asymmetry exists to match the
    pre-refactor ``os.environ.pop(..., None)`` calls in the test suite.

    The snapshot is taken BEFORE the kwargs are applied, so save/restore
    round-trips the *pre-config* state — restore puts back whatever was
    there when the with-block started, NOT whatever the kwargs said.
    """
    # Snapshot FIRST so a failure between here and `yield` cannot leak
    # un-restored module state into the next test.
    snapshots: dict[str, object] = {}
    for attr in _TRACKED_GLOBALS:
        snapshots[attr] = getattr(tb, attr, _MISSING)
    snapshots["_poller_disabled_env"] = os.environ.get("TELEGRAM_POLLER_DISABLED", _MISSING)

    # Apply kwargs (None / set() / whatever the caller passed).
    if token is not _MISSING:
        tb.TELEGRAM_BOT_TOKEN = token  # type: ignore[assignment]
    if allowed is not _MISSING:
        tb.ALLOWED_USER_IDS = allowed  # type: ignore[assignment]
    if admin is not _MISSING:
        tb.ADMIN_USER_IDS = admin  # type: ignore[assignment]
    if send_message is not _MISSING:
        tb._send_message = send_message  # type: ignore[assignment]
    if send_message_with_id is not _MISSING:
        tb._send_message_with_id = send_message_with_id  # type: ignore[assignment]
    if reset_throttle:
        tb._EMPTY_ALLOWLIST_WARNED = False
        # Snapshot reflects the reset so __exit__ restores to False.
        snapshots["_EMPTY_ALLOWLIST_WARNED"] = False
    if poller_disabled is not _MISSING:
        if poller_disabled is None:
            os.environ.pop("TELEGRAM_POLLER_DISABLED", None)
        else:
            os.environ["TELEGRAM_POLLER_DISABLED"] = str(poller_disabled)

    try:
        yield
    finally:
        for attr, original in snapshots.items():
            if attr == "_poller_disabled_env":
                if original is _MISSING:
                    os.environ.pop("TELEGRAM_POLLER_DISABLED", None)
                else:
                    os.environ["TELEGRAM_POLLER_DISABLED"] = original  # type: ignore[assignment]
            elif original is _MISSING:
                if hasattr(tb, attr):
                    delattr(tb, attr)
            else:
                setattr(tb, attr, original)


@pytest.fixture
def isolated_telegram():
    """Pytest fixture alias for ``isolated_telegram_config``.

    Use this in tests that already prefer the pytest fixture style and
    don't need to apply per-test kwargs. For per-test overrides use
    ``with isolated_telegram_config(...)`` directly.
    """
    with isolated_telegram_config():
        yield


__all__ = ["isolated_telegram_config", "_MISSING"]
