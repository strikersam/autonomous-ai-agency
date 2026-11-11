"""packages/lifecycle/machine.py — a lifecycle declared as data.

A state machine here is data, not a framework: the states, the legal moves and
the resting states of one status field, declared once.  Domain code keeps
owning the writes; this module only answers whether a move is legal and, when
it is not, what *is* legal.

Why it exists: status fields in this codebase are written from HTTP handlers,
background workers, supervisors and schedulers.  Each writer used to carry its
own idea of what could follow what, so an illegal move surfaced as an opaque
400 or, worse, as a state no reader expected.  One declaration makes a
lifecycle readable by a person, by a CLI (``scripts/lifecycles.py --json``) and
by an agent, and makes drift checkable in a test.

Resting (``terminal``) states are resting points, not prisons: ``task``
deliberately declares DONE -> IN_PROGRESS so a person can re-open completed
work, and a machine may declare an edge out of a resting state.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping


class IllegalTransition(ValueError):
    """A move the lifecycle does not declare, carrying the legal alternatives."""

    def __init__(
        self, machine: str, source: str, target: str, allowed: Iterable[str]
    ) -> None:
        self.machine = machine
        self.source = source
        self.target = target
        self.allowed = tuple(sorted(allowed))
        if self.allowed:
            alternatives = ", ".join(self.allowed)
        else:
            alternatives = "none (resting state)"
        super().__init__(
            f"{machine}: cannot go from {source!r} to {target!r}; "
            f"allowed from {source!r}: {alternatives}"
        )


@dataclass(frozen=True, slots=True)
class StateMachine:
    """One status field: its states, its initial state, and its legal moves.

    ``transitions`` must have an entry for *every* state, including resting
    ones (an empty entry), so that "no declared exit" is distinguishable from
    "nobody wrote it down".  Construction validates that, so a typo in a
    transition target fails at import time rather than at 3 a.m.

    ``status_type`` is an optional ``"module:Name"`` reference to the enum or
    ``Literal`` alias that types the same field.  It stays a string here so the
    catalogue never imports domain modules; ``packages.lifecycle.status_types``
    resolves and compares it for whoever asks.
    """

    name: str
    states: frozenset[str]
    initial: str
    transitions: Mapping[str, frozenset[str]]
    owner: str
    description: str
    terminal: frozenset[str] = frozenset()
    notes: tuple[str, ...] = ()
    status_type: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "states", frozenset(self.states))
        object.__setattr__(self, "terminal", frozenset(self.terminal))
        object.__setattr__(
            self,
            "transitions",
            MappingProxyType(
                {str(src): frozenset(dsts) for src, dsts in self.transitions.items()}
            ),
        )
        object.__setattr__(self, "notes", tuple(self.notes))
        self.validate()

    # ── Construction checks ──────────────────────────────────────────────────

    def validate(self) -> None:
        """Raise ``ValueError`` when the declaration is internally inconsistent."""
        problems: list[str] = []
        if not self.name:
            problems.append("name is empty")
        if not self.states:
            problems.append("states is empty")
        if self.initial not in self.states:
            problems.append(f"initial state {self.initial!r} is not declared")
        missing = self.states - set(self.transitions)
        extra = set(self.transitions) - self.states
        if missing:
            problems.append(f"no transition entry for {sorted(missing)}")
        if extra:
            problems.append(f"transition entry for undeclared states {sorted(extra)}")
        unknown_targets = {
            target
            for targets in self.transitions.values()
            for target in targets
            if target not in self.states
        }
        if unknown_targets:
            problems.append(f"undeclared transition targets {sorted(unknown_targets)}")
        unknown_terminal = self.terminal - self.states
        if unknown_terminal:
            problems.append(f"undeclared resting states {sorted(unknown_terminal)}")
        if not self.owner:
            problems.append("owner is empty")
        if not self.description:
            problems.append("description is empty")
        if self.status_type is not None:
            module, separator, attribute = str(self.status_type).partition(":")
            if not separator or not module or not attribute:
                problems.append(
                    f"status_type {self.status_type!r} must look like 'module:Name'"
                )
        if problems:
            raise ValueError(f"lifecycle {self.name!r}: " + "; ".join(problems))

    # ── Queries ──────────────────────────────────────────────────────────────

    def can(self, source: str, target: str) -> bool:
        """True when ``source -> target`` is declared."""
        return target in self.transitions.get(source, frozenset())

    def require(self, source: str, target: str) -> None:
        """Raise :class:`IllegalTransition` unless ``source -> target`` is declared."""
        if not self.can(source, target):
            raise IllegalTransition(self.name, source, target, self.allowed(source))

    def allowed(self, source: str) -> tuple[str, ...]:
        """Sorted states reachable in one move from ``source``."""
        return tuple(sorted(self.transitions.get(source, frozenset())))

    def is_terminal(self, state: str) -> bool:
        """True for a declared resting state (it may still have a re-open edge)."""
        return state in self.terminal

    def unreachable(self) -> tuple[str, ...]:
        """States with no incoming edge from the initial state.

        Such a state is still legal data — a legacy row, or a field written by
        a dedicated API path (a "clarify" action) rather than a transition —
        but its existence is worth seeing.
        """
        reachable = {self.initial}
        frontier = [self.initial]
        while frontier:
            current = frontier.pop()
            for target in self.transitions.get(current, frozenset()):
                if target not in reachable:
                    reachable.add(target)
                    frontier.append(target)
        return tuple(sorted(self.states - reachable))

    def as_dict(self) -> dict[str, Any]:
        """JSON-safe description, used by the CLI and ``--json`` consumers."""
        return {
            "name": self.name,
            "description": self.description,
            "owner": self.owner,
            "initial": self.initial,
            "terminal": sorted(self.terminal),
            "states": sorted(self.states),
            "transitions": {
                source: sorted(targets)
                for source, targets in sorted(self.transitions.items())
            },
            "notes": list(self.notes),
            "status_type": self.status_type,
            "unreachable": list(self.unreachable()),
        }
