"""packages/config/control_registry.py — the platform-control API.

The public surface every caller imports: the catalogue, the lookup helpers, and
the validation that keeps the override endpoint an allow-list rather than a
general ``os.environ`` write primitive.

Split three ways so the executable part stays small and reviewable:

* :mod:`packages.config.control_specs` — the types and builders
* :mod:`packages.config.control_catalogue` — the 109 declared controls
* this module — lookup, grouping, and coercion

Re-exports the types and the catalogue, so ``from
packages.config.control_registry import ControlSpec, GROUPS, all_controls`` keeps
working regardless of which file a given name physically lives in.
"""

from __future__ import annotations

from typing import Any

from packages.config.control_catalogue import CONTROLS, GROUPS
from packages.config.control_specs import (
    ControlGroup,
    ControlOption,
    ControlSpec,
    FALSEY,
    KIND_CHOICE,
    KIND_NUMBER,
    KIND_TOGGLE,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    TRUTHY,
)

__all__ = [
    "CONTROLS",
    "FALSEY",
    "GROUPS",
    "KIND_CHOICE",
    "KIND_NUMBER",
    "KIND_TOGGLE",
    "RISK_HIGH",
    "RISK_LOW",
    "RISK_MEDIUM",
    "TRUTHY",
    "ControlGroup",
    "ControlOption",
    "ControlSpec",
    "all_controls",
    "coerce",
    "controls_by_group",
    "get_control",
    "is_controllable",
]

_BY_KEY: dict[str, ControlSpec] = {c.key: c for c in CONTROLS}


# ── Lookup + validation ───────────────────────────────────────────────────────


def all_controls() -> tuple[ControlSpec, ...]:
    """Every control in the catalogue, in display order."""
    return CONTROLS


def get_control(key: str) -> ControlSpec | None:
    """The spec for *key*, or ``None`` when it is not operator-controllable."""
    return _BY_KEY.get(key)


def is_controllable(key: str) -> bool:
    """True when *key* may be overridden from the dashboard.

    The allow-list is what keeps the override endpoint from being a general
    ``os.environ`` write primitive: a secret is not in the catalogue, so it can
    never be set through this path.
    """
    return key in _BY_KEY


def controls_by_group() -> list[dict[str, Any]]:
    """The catalogue grouped for the dashboard, groups in display order."""
    out: list[dict[str, Any]] = []
    for group in GROUPS:
        members = [c for c in CONTROLS if c.group == group.id]
        if not members:
            continue
        out.append(group.as_dict() | {"controls": [c.as_dict() for c in members]})
    return out


def coerce(key: str, value: Any) -> str:
    """Normalise *value* into the env string this control stores.

    Raises ``ValueError`` when the value is not legal for the control, so a bad
    write is rejected before it reaches the process environment.
    """
    spec = _BY_KEY.get(key)
    if spec is None:
        raise ValueError(f"'{key}' is not an operator-controllable setting")
    if spec.kind == KIND_TOGGLE:
        return _coerce_toggle(value)
    if spec.kind == KIND_NUMBER:
        return _coerce_number(spec, value)
    return _coerce_choice(spec, value)


def _coerce_toggle(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    raw = str(value).strip().lower()
    if raw in TRUTHY:
        return "true"
    if raw in FALSEY:
        return "false"
    raise ValueError(f"expected a boolean, got {value!r}")


def _coerce_number(spec: ControlSpec, value: Any) -> str:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"expected a whole number, got {value!r}") from exc
    if spec.minimum is not None and number < spec.minimum:
        raise ValueError(f"{spec.key} must be at least {spec.minimum}")
    if spec.maximum is not None and number > spec.maximum:
        raise ValueError(f"{spec.key} must be at most {spec.maximum}")
    return str(number)


def _coerce_choice(spec: ControlSpec, value: Any) -> str:
    raw = "" if value is None else str(value).strip()
    allowed = {o.value for o in spec.options}
    if raw not in allowed:
        pretty = ", ".join(sorted(repr(a) for a in allowed))
        raise ValueError(f"{spec.key} must be one of {pretty}, got {raw!r}")
    return raw
