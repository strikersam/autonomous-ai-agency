"""scripts/check_model_catalog_consistency.py

CI guard against dead / drifted model IDs.

The platform declares model ids in more than one place, and they drift: a model
gets deprecated by a provider and the id lingers in a catalogue or a per-agent
``prefer_models`` list, so every call that prefers it fails over on a 404/410.
Production hit exactly this — the planner preferred ``z-ai/glm-5.2`` (410 on
NVIDIA) on every agency cycle. Nothing caught it because nothing checks that the
ids these files reference actually exist in the catalogue.

This guard closes that gap. It is intentionally conservative: it only fails on
drift it can prove from the files themselves, and reports the softer
cross-catalogue divergence as a warning rather than a hard failure (resolving
that needs the model→provider schema change tracked as the catalogue-unification
work). Run it in CI and before a commit that touches any model catalogue.

Checks
------
1. HARD — every ``prefer_models`` id in ``config/llm/routing.yaml`` is a declared
   model key in ``config/llm/models.yaml``. A preferred id that is not declared
   is routed first and can only fail.
2. HARD — in ``config/models.yaml`` every provider's ``role_presets`` model is in
   that provider's ``candidates`` list. A preset the failover chain never tries
   is a silent dead default.
3. WARN — a model id declared under provider X in ``config/llm/models.yaml`` but
   listed as a *different* provider's candidate in ``config/models.yaml``. This
   is catalogue divergence; it is reported, not failed, until the two catalogues
   are unified.

Exit codes: 0 clean (warnings allowed), 1 a HARD check failed, 2 a file is
missing or unparseable.

Usage::

    python scripts/check_model_catalog_consistency.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent.parent
_LLM_MODELS = _ROOT / "config" / "llm" / "models.yaml"
_LLM_ROUTING = _ROOT / "config" / "llm" / "routing.yaml"
_BRAIN_MODELS = _ROOT / "config" / "models.yaml"


def _load(path: Path) -> dict[str, Any]:
    """Parse a YAML file to a mapping, or exit 2 if it cannot be read."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"::error::cannot read {path.relative_to(_ROOT)}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    return data if isinstance(data, dict) else {}


def _llm_declared(models_doc: dict[str, Any]) -> dict[str, str]:
    """Map every declared model id (and alias) → its provider in the llm catalogue."""
    declared: dict[str, str] = {}
    for mid, cfg in (models_doc.get("models") or {}).items():
        provider = (cfg or {}).get("provider", "")
        declared[mid] = provider
        for alias in (cfg or {}).get("aliases") or []:
            declared[alias] = provider
    return declared


def _check_prefer_models(routing: dict[str, Any], declared: dict[str, str]) -> list[str]:
    """HARD check 1: every per-agent prefer_models id is declared in the catalogue."""
    errors: list[str] = []
    agents = ((routing.get("routing") or {}).get("agents")) or {}
    for agent, policy in agents.items():
        for mid in (policy or {}).get("prefer_models") or []:
            if mid not in declared:
                errors.append(
                    f"routing.yaml agent '{agent}' prefers '{mid}', which is not "
                    f"declared in config/llm/models.yaml — it can only fail over"
                )
    return errors


def _check_presets(brain_doc: dict[str, Any]) -> list[str]:
    """HARD check 2: every role_preset model is in that provider's candidate list."""
    errors: list[str] = []
    for pid, spec in (brain_doc.get("providers") or {}).items():
        candidates = set((spec or {}).get("candidates") or [])
        for role, mid in ((spec or {}).get("role_presets") or {}).items():
            if mid and mid not in candidates:
                errors.append(
                    f"config/models.yaml provider '{pid}' role '{role}' preset "
                    f"'{mid}' is absent from its candidates — the failover never tries it"
                )
    return errors


def _check_cross_catalogue(brain_doc: dict[str, Any], declared: dict[str, str]) -> list[str]:
    """WARN check 3: same id claimed by different providers across the two catalogues."""
    warnings: list[str] = []
    for pid, spec in (brain_doc.get("providers") or {}).items():
        for mid in (spec or {}).get("candidates") or []:
            other = declared.get(mid)
            if other and other != pid:
                warnings.append(
                    f"'{mid}' is provider '{pid}' in config/models.yaml but "
                    f"'{other}' in config/llm/models.yaml — catalogues disagree"
                )
    return warnings


def main() -> int:
    llm_models = _load(_LLM_MODELS)
    routing = _load(_LLM_ROUTING)
    brain = _load(_BRAIN_MODELS)
    declared = _llm_declared(llm_models)

    errors = _check_prefer_models(routing, declared) + _check_presets(brain)
    warnings = _check_cross_catalogue(brain, declared)

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"::error::{e}", file=sys.stderr)

    if errors:
        print(f"CATALOGUE DRIFT: {len(errors)} dead/undeclared id(s), "
              f"{len(warnings)} warning(s)", file=sys.stderr)
        return 1
    print(f"CATALOGUE OK: {len(declared)} declared ids, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
