"""packages/lifecycle — every status field, declared once.

Import :mod:`packages.lifecycle.catalogue` (or this package) to populate the
registry; then ``get_machine("task")`` answers what a status may become next.

Adoption is deliberately narrow: the declaration describes a lifecycle, it does
not take over the writes.  ``TaskWorkflowService.transition`` is the first
enforced consumer; other machines are declared and documented so the drift in
them is visible before it is changed.
"""
from __future__ import annotations

from packages.lifecycle.machine import IllegalTransition, StateMachine
from packages.lifecycle.registry import (
    all_machines,
    describe,
    get_machine,
    machine_names,
    register,
)

# Importing the catalogue registers every declared lifecycle.
from packages.lifecycle import catalogue as catalogue  # noqa: E402  (registration side effect)

__all__ = [
    "IllegalTransition",
    "StateMachine",
    "all_machines",
    "catalogue",
    "describe",
    "get_machine",
    "machine_names",
    "register",
]
