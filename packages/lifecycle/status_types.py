"""packages/lifecycle/status_types.py — bind a lifecycle to the type of its field.

A lifecycle says which strings a status field may hold; the enum (or ``Literal``
alias) that types the same field says it again.  Two declarations of one
vocabulary drift the moment somebody adds a member on one side, and the failure
is quiet: a new state is legal to write but missing from the map, or the map
promises a state no writer can produce.

The catalogue keeps the binding as data (``status_type="module:Name"``) and this
module resolves it on demand, so importing the catalogue stays free of domain
imports and only the commands that check the binding pay for them.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Literal, get_args, get_origin

from packages.lifecycle.machine import StateMachine

__all__ = [
    "StatusTypeReport",
    "inspect",
    "problems",
    "reports",
    "resolve",
    "values_of",
]


def resolve(spec: str) -> Any:
    """Return the object named by ``"module:Name"``.

    Raises ``LookupError`` naming the spec: a typo in a declaration should read
    as a broken binding, not as a stack trace from a checkout command.
    """
    module_name, separator, attribute = str(spec).partition(":")
    if not separator or not module_name or not attribute:
        raise LookupError(f"status type {spec!r} must look like 'module:Name'")
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # reported to the caller as a binding error
        raise LookupError(
            f"status type {spec!r}: cannot import {module_name!r}: {exc}"
        ) from exc
    try:
        return getattr(module, attribute)
    except AttributeError as exc:
        raise LookupError(
            f"status type {spec!r}: {module_name!r} has no {attribute!r}"
        ) from exc


def values_of(spec: str) -> tuple[str, ...]:
    """Every value the bound type allows, as strings, in declaration order."""
    bound = resolve(spec)
    if isinstance(bound, type) and issubclass(bound, Enum):
        return tuple(str(member.value) for member in bound)
    if get_origin(bound) is Literal:
        return tuple(str(value) for value in get_args(bound))
    raise TypeError(
        f"status type {spec!r} is {type(bound).__name__}; "
        "expected an Enum subclass or a Literal alias"
    )


@dataclass(frozen=True)
class StatusTypeReport:
    """The comparison of one lifecycle with the type that types its field.

    ``missing`` is a state the map promises but the type cannot express;
    ``undeclared`` is a member the type allows but the map does not declare.
    Both are drift, and both are named so the fix is a one-line edit.
    """

    lifecycle: str
    status_type: str
    values: tuple[str, ...] = ()
    undeclared: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and not self.undeclared and not self.missing

    def describe(self) -> str:
        if self.error is not None:
            return f"{self.lifecycle}: {self.error}"
        if self.ok:
            return f"{self.lifecycle} ({self.status_type}): matches"
        details = []
        if self.missing:
            details.append("declared but not in the type: " + ", ".join(self.missing))
        if self.undeclared:
            details.append("in the type but not declared: " + ", ".join(self.undeclared))
        return f"{self.lifecycle} ({self.status_type}): " + "; ".join(details)


def inspect(machine: StateMachine) -> StatusTypeReport | None:
    """Compare ``machine`` with its bound type; ``None`` when nothing is bound."""
    if not machine.status_type:
        return None
    spec = machine.status_type
    try:
        values = values_of(spec)
    except (LookupError, TypeError) as exc:
        return StatusTypeReport(lifecycle=machine.name, status_type=spec, error=str(exc))
    return StatusTypeReport(
        lifecycle=machine.name,
        status_type=spec,
        values=values,
        undeclared=tuple(sorted(set(values) - set(machine.states))),
        missing=tuple(sorted(set(machine.states) - set(values))),
    )


def reports(machines: Iterable[StateMachine]) -> tuple[StatusTypeReport, ...]:
    """One report per lifecycle that binds a type, in input order."""
    return tuple(
        report for report in (inspect(machine) for machine in machines) if report is not None
    )


def problems(machines: Iterable[StateMachine]) -> tuple[str, ...]:
    """One readable problem per drifted binding; empty when everything matches."""
    return tuple(report.describe() for report in reports(machines) if not report.ok)
