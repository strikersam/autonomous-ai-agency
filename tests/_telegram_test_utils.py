"""tests/_telegram_test_utils.py

Snapshot + restore context manager for ``telegram_bot`` module-global config.

Individual telegram-slice tests use :func:`isolated_telegram_config` to apply an
isolated configuration (bot token / allowlist / admin set / send hooks / the
empty-allowlist throttle flag / the poller env var) for the duration of a
``with`` block, and have the previous state deterministically restored on exit —
even if the body raises.

This is a *test-only* helper. The leading underscore keeps pytest from
collecting it as a test module; its own contract is locked by the self-test in
``tests/test_telegram_test_utils.py``.

Semantics worth calling out:

* ``reset_throttle`` (default ``True``) is applied *before* the snapshot, so the
  throttle flag is restored to its post-reset value on exit (a fresh-warning
  default), not the caller's pre-config value.
* ``poller_disabled`` is asymmetric: the ``_MISSING`` default leaves the env var
  untouched, ``None`` pops it, and a string sets it.
* On restore, a tracked attribute that was *absent* at snapshot time
  (``_MISSING``) is ``delattr``'d rather than re-created as ``None``.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

import telegram_bot as tb


class _Missing:
    """Sentinel: argument not supplied / attribute absent at snapshot time.

    Distinct from ``None``, which is a meaningful value for ``poller_disabled``.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return "_MISSING"


_MISSING: Any = _Missing()

_POLLER_ENV = "TELEGRAM_POLLER_DISABLED"

# Module-global attrs on telegram_bot that the helper snapshots and restores.
# MUST stay in sync with tests/test_telegram_test_utils._TRACKED.
_TRACKED_GLOBALS: tuple[str, ...] = (
    "TELEGRAM_BOT_TOKEN",
    "ALLOWED_USER_IDS",
    "ADMIN_USER_IDS",
    "_send_message",
    "_send_message_with_id",
    "_EMPTY_ALLOWLIST_WARNED",
)

# kwarg name -> telegram_bot attribute it maps onto.
_KWARG_TO_ATTR: dict[str, str] = {
    "token": "TELEGRAM_BOT_TOKEN",
    "allowed": "ALLOWED_USER_IDS",
    "admin": "ADMIN_USER_IDS",
    "send_message": "_send_message",
    "send_message_with_id": "_send_message_with_id",
}


@contextmanager
def isolated_telegram_config(
    *,
    token: Any = _MISSING,
    allowed: Any = _MISSING,
    admin: Any = _MISSING,
    send_message: Any = _MISSING,
    send_message_with_id: Any = _MISSING,
    reset_throttle: bool = True,
    poller_disabled: Any = _MISSING,
) -> Iterator[None]:
    """Apply an isolated ``telegram_bot`` config, restoring prior state on exit.

    Only kwargs that are explicitly supplied (i.e. not ``_MISSING``) are applied;
    everything else is left exactly as it was.
    """
    # 1. Apply reset_throttle FIRST so it is captured by the snapshot below — the
    #    flag is intentionally restored to its *post-reset* value on exit.
    if reset_throttle:
        tb._EMPTY_ALLOWLIST_WARNED = False

    # 2. Snapshot tracked globals + the poller env var.
    attr_snapshot: dict[str, Any] = {
        name: getattr(tb, name, _MISSING) for name in _TRACKED_GLOBALS
    }
    env_snapshot: Any = os.environ.get(_POLLER_ENV, _MISSING)

    # 3. Apply supplied kwargs onto their mapped telegram_bot attributes.
    supplied = {
        "token": token,
        "allowed": allowed,
        "admin": admin,
        "send_message": send_message,
        "send_message_with_id": send_message_with_id,
    }
    for kw, value in supplied.items():
        if value is _MISSING:
            continue
        setattr(tb, _KWARG_TO_ATTR[kw], value)

    # poller_disabled: _MISSING leaves env alone; None pops it; str sets it.
    if poller_disabled is not _MISSING:
        if poller_disabled is None:
            os.environ.pop(_POLLER_ENV, None)
        else:
            os.environ[_POLLER_ENV] = poller_disabled

    try:
        yield
    finally:
        # 4. Restore tracked globals: delattr if the attr was absent at snapshot
        #    time, else set it back to the snapshot value.
        for name, original in attr_snapshot.items():
            if original is _MISSING:
                if hasattr(tb, name):
                    delattr(tb, name)
            else:
                setattr(tb, name, original)
        # Restore the poller env var with the same delattr-vs-set asymmetry.
        if env_snapshot is _MISSING:
            os.environ.pop(_POLLER_ENV, None)
        else:
            os.environ[_POLLER_ENV] = env_snapshot
