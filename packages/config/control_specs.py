"""packages/config/control_specs.py — the vocabulary of a platform control.

The types, kinds, and builders that :mod:`packages.config.control_catalogue`
uses to declare each control, split out so neither the catalogue data nor the
lookup API has to carry them. Import the public surface from
:mod:`packages.config.control_registry`, not from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Kinds ─────────────────────────────────────────────────────────────────────

KIND_TOGGLE = "toggle"
KIND_CHOICE = "choice"
KIND_NUMBER = "number"

TRUTHY = ("1", "true", "yes", "on")
FALSEY = ("0", "false", "no", "off")

# ── Risk tiers (drive the confirm-before-save affordance in the UI) ───────────

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"


@dataclass(frozen=True)
class ControlOption:
    """One selectable value for a ``choice`` control."""

    value: str
    label: str
    help: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.value, "label": self.label, "help": self.help}


@dataclass(frozen=True)
class ControlSpec:
    """One operator-controllable setting."""

    key: str
    label: str
    group: str
    kind: str
    default: str
    help: str = ""
    options: tuple[ControlOption, ...] = ()
    live: bool = False
    risk: str = RISK_LOW
    requires: tuple[str, ...] = field(default_factory=tuple)
    minimum: int | None = None
    maximum: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "group": self.group,
            "kind": self.kind,
            "default": self.default,
            "help": self.help,
            "options": [o.as_dict() for o in self.options],
            "live": self.live,
            "risk": self.risk,
            "requires": list(self.requires),
            "minimum": self.minimum,
            "maximum": self.maximum,
        }


@dataclass(frozen=True)
class ControlGroup:
    """A UI section of related controls."""

    id: str
    label: str
    help: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "help": self.help}


def _toggle(
    key: str,
    label: str,
    group: str,
    default: str,
    help_text: str,
    *,
    live: bool = False,
    risk: str = RISK_LOW,
    requires: tuple[str, ...] = (),
) -> ControlSpec:
    """Build a boolean control. Keeps the catalogue below readable."""
    return ControlSpec(
        key=key,
        label=label,
        group=group,
        kind=KIND_TOGGLE,
        default=default,
        help=help_text,
        live=live,
        risk=risk,
        requires=requires,
    )


def _number(
    key: str,
    label: str,
    group: str,
    default: str,
    help_text: str,
    *,
    live: bool = False,
    minimum: int | None = 0,
    maximum: int | None = None,
    risk: str = RISK_LOW,
) -> ControlSpec:
    """Build an integer control."""
    return ControlSpec(
        key=key,
        label=label,
        group=group,
        kind=KIND_NUMBER,
        default=default,
        help=help_text,
        live=live,
        minimum=minimum,
        maximum=maximum,
        risk=risk,
    )
