"""packages/lifecycle/registry.py — one index of every declared lifecycle.

The registry is populated when ``packages.lifecycle.catalogue`` is imported.
Lookups fail with the known names (and a spelling suggestion), because the two
common errors here are a typo and a name that was renamed — both of which are
cheaper to fix from an error message than from a grep.
"""
from __future__ import annotations

import difflib
import threading
from typing import Iterable

from packages.lifecycle.machine import StateMachine

_MACHINES: dict[str, StateMachine] = {}
_LOCK = threading.RLock()


def register(machine: StateMachine, *, replace: bool = False) -> StateMachine:
    """Add ``machine`` to the registry, returning it for module-level binding."""
    key = machine.name.strip().lower()
    if not key:
        raise ValueError("lifecycle name must not be empty")
    with _LOCK:
        if key in _MACHINES and not replace:
            raise ValueError(
                f"lifecycle {key!r} is already registered by "
                f"{_MACHINES[key].owner!r}; pass replace=True to override"
            )
        _MACHINES[key] = machine
    return machine


def machine_names() -> tuple[str, ...]:
    """Every registered lifecycle name, sorted."""
    with _LOCK:
        return tuple(sorted(_MACHINES))


def all_machines() -> tuple[StateMachine, ...]:
    """Every registered lifecycle, sorted by name."""
    with _LOCK:
        return tuple(_MACHINES[name] for name in sorted(_MACHINES))


def get_machine(name: str) -> StateMachine:
    """Return the lifecycle called ``name``.

    Raises ``KeyError`` naming the available lifecycles and, when the name is a
    near miss, the closest one.  A reviewer or agent that guessed the name gets
    the answer without a second search.
    """
    key = str(name or "").strip().lower()
    with _LOCK:
        machine = _MACHINES.get(key)
        known = sorted(_MACHINES)
    if machine is not None:
        return machine
    close = difflib.get_close_matches(key, known, n=1)
    hint = f" Did you mean {close[0]!r}?" if close else ""
    raise KeyError(
        f"unknown lifecycle {name!r}.{hint} Known lifecycles: {', '.join(known) or '(none)'}"
    )


def describe(name: str) -> dict:
    """JSON-safe description of one lifecycle (see :meth:`StateMachine.as_dict`)."""
    return get_machine(name).as_dict()


def register_many(machines: Iterable[StateMachine]) -> tuple[StateMachine, ...]:
    """Register several machines in order, returning them."""
    return tuple(register(machine) for machine in machines)
