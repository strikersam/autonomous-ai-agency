"""Retire models on evidence and move stored config onto live ones.

Providers retire models without notice. The runtime already skips an id that
answers 404/410 (``router._mark_model_dead``, ``model_discovery.mark_dead``),
but a *stored* choice (the brain config, a provider record's default model, a
deploy env var) kept naming the dead id until someone edited a list by hand.

This module closes that gap for every provider, with no list of dead ids:

* each real 404/410 on a model call records a *strike*;
* a model is retired when it has a strike and the provider's own ``/models``
  listing no longer includes it, or when it keeps striking while still listed;
* the replacement is the first live model in the probed catalogue, else a chat
  model the key actually serves;
* ``live_model()`` then resolves the retired id to its replacement wherever a
  stored value is read, and ``heal_brain_config()`` persists the change.

Nothing here raises: healing improves on the stored config and must never be
the reason a request fails.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

log = logging.getLogger("qwen-proxy")

STRIKE_WINDOW_SEC: float = 6 * 60 * 60
STRIKES_TO_RETIRE: int = 3
# Failed calls needed when the provider's listing also omits the model. Two, not
# one: a single 404 can be a blip, and dead-model cooldowns space them 30 min apart.
STRIKES_WHEN_UNLISTED: int = 2
HEAL_INTERVAL_SEC: float = 15 * 60
_ROLE_FIELDS = ("planner_model", "executor_model", "verifier_model", "judge_model")
_NVIDIA_IDS = frozenset({"nvidia", "nvidia-nim"})
# Families that cannot drive a chat/tool loop; never promoted as a replacement.
_NON_CHAT_MARKERS = (
    "embed", "rerank", "guard", "safety", "ocr", "whisper", "tts", "asr",
    "parakeet", "riva", "clip", "bge", "retriev", "detect", "translate",
    "diffusion", "image-gen", "audio", "reward", "moderation", "yolo", "sdxl",
    "cosmos", "usdcode",
)

# (provider, model) -> strike timestamps inside the window.
_STRIKES: dict[tuple[str, str], list[float]] = {}
# (provider, retired model) -> replacement.
_REPLACEMENTS: dict[tuple[str, str], str] = {}


def provider_key(provider_id: str) -> str:
    """Fold provider-record ids onto catalogue ids (``nvidia-nim`` is ``nvidia``)."""
    pid = (provider_id or "").strip().lower()
    return "nvidia" if pid in _NVIDIA_IDS else pid


def reset() -> None:
    """Forget every strike and replacement. For tests."""
    _STRIKES.clear()
    _REPLACEMENTS.clear()


def record_strike(provider_id: str, model: str, *, now: float | None = None) -> None:
    """Note that *model* just answered 404/410 on a real call to *provider_id*."""
    if not model:
        return
    ts = time.time() if now is None else now
    key = (provider_key(provider_id), model)
    kept = [t for t in _STRIKES.get(key, []) if ts - t <= STRIKE_WINDOW_SEC]
    kept.append(ts)
    _STRIKES[key] = kept[-STRIKES_TO_RETIRE * 2:]


def strikes(provider_id: str, model: str, *, now: float | None = None) -> int:
    """How many strikes *model* has inside the window."""
    ts = time.time() if now is None else now
    stamps = _STRIKES.get((provider_key(provider_id), model), [])
    return sum(1 for t in stamps if ts - t <= STRIKE_WINDOW_SEC)


def is_retired(
    provider_id: str, model: str, served: list[str] | None, *, now: float | None = None
) -> bool:
    """True when the evidence says *provider_id* no longer serves *model*.

    A listing alone is never enough, because a provider may spell ids
    differently in ``/models`` than it accepts on a call. A failed call is
    required; the listing, or repetition, only confirms it.
    """
    count = strikes(provider_id, model, now=now)
    if count == 0:
        return False
    if served is not None and not _is_listed(model, served):
        return count >= STRIKES_WHEN_UNLISTED
    return count >= STRIKES_TO_RETIRE


def _is_listed(model: str, served: list[str]) -> bool:
    """True if *served* contains *model*, allowing for an omitted vendor prefix.

    Some listings say ``gpt-oss-120b`` where calls take ``openai/gpt-oss-120b``;
    treating that as "not listed" would retire a model that works.
    """
    bare = model.rsplit("/", 1)[-1]
    return any(s == model or s.rsplit("/", 1)[-1] == bare for s in served)


def _allowed(models: list[str]) -> list[str]:
    """Drop ids on the operator's deny-list; a replacement must never be one."""
    try:
        from packages.ai.model_policy import drop_denied
        return list(drop_denied(models))
    except Exception:  # noqa: BLE001 - fail closed: offer nothing rather than a denied id
        log.warning("model_retirement: deny-list unreadable; no replacement offered")
        return []


def _catalogue(provider: str) -> list[str]:
    """The probed candidate list ``config/models.yaml`` holds for *provider*."""
    try:
        from packages.ai.brain_config import PROVIDER_CANDIDATES
        return list(PROVIDER_CANDIDATES.get(provider) or [])
    except Exception:  # noqa: BLE001 - the catalogue is optional input
        return []


def _is_chat_model(model: str) -> bool:
    lowered = model.lower()
    return not any(marker in lowered for marker in _NON_CHAT_MARKERS)


def pick_replacement(
    provider_id: str, served: list[str] | None, *, retired: set[str]
) -> str | None:
    """Best live model for *provider_id*, or ``None`` when none is known."""
    if served is None:
        return None  # no evidence of what is live; guessing is how configs got poisoned
    known = set(served)
    for model in _allowed(_catalogue(provider_key(provider_id))):
        if model not in retired and model in known:
            return model
    for model in _allowed(list(served)):
        if model not in retired and _is_chat_model(model):
            return model
    return None


def live_model(provider_id: str, model: str | None) -> str | None:
    """Resolve a stored model id to its replacement if it was retired."""
    if not model:
        return model
    return _REPLACEMENTS.get((provider_key(provider_id), model), model)


def replacements() -> dict[str, str]:
    """Snapshot of ``{"provider/retired": "replacement"}`` for diagnostics."""
    return {f"{p}/{m}": new for (p, m), new in _REPLACEMENTS.items()}


async def _discover(probe: Any) -> list[str] | None:
    from packages.ai.model_discovery import discover_models
    return await discover_models(probe)


async def heal_providers(probes: dict[str, Any]) -> dict[tuple[str, str], str]:
    """Map every newly retired model to a replacement. Returns what changed.

    *probes* maps a provider key to an object with ``id``, ``base_url`` and
    ``api_key``: what ``model_discovery.discover_models`` needs.
    """
    changed: dict[tuple[str, str], str] = {}
    for (provider, model) in list(_STRIKES):
        if (provider, model) in _REPLACEMENTS or provider not in probes:
            continue
        try:
            served = await _discover(probes[provider])
            if served is None or not is_retired(provider, model, served):
                continue
            retired = {m for (p, m) in _STRIKES if p == provider and is_retired(p, m, served)}
            replacement = pick_replacement(provider, served, retired=retired)
        except Exception as exc:  # noqa: BLE001 - healing must never raise
            log.warning("model_retirement: could not check %s/%s: %s", provider, model, exc)
            continue
        if not replacement:
            log.warning("model_retirement: %s/%s is retired and no live replacement is known",
                        provider, model)
            continue
        _REPLACEMENTS[(provider, model)] = replacement
        changed[(provider, model)] = replacement
        log.warning("model_retirement: %s retired %s; stored config now resolves to %s",
                    provider, model, replacement)
    return changed


def brain_patch_fields(cfg: Any) -> dict[str, str]:
    """Role fields of *cfg* that name a retired model, mapped to replacements."""
    provider = str(getattr(cfg, "primary_provider", "") or "")
    patch: dict[str, str] = {}
    for field in _ROLE_FIELDS:
        current = getattr(cfg, field, None)
        resolved = live_model(provider, current)
        if current and resolved and resolved != current:
            patch[field] = resolved
    return patch


async def heal_brain_config() -> dict[str, str]:
    """Persist replacements into the stored brain config. Returns the patch."""
    try:
        from packages.ai.brain_config import BrainConfigPatch, get_brain_config, set_brain_config
        fields = brain_patch_fields(await get_brain_config())
        if fields:
            await set_brain_config(BrainConfigPatch(**fields), actor="auto_model_retirement")
            log.warning("model_retirement: brain config moved off retired models: %s", fields)
        return fields
    except Exception as exc:  # noqa: BLE001 - healing must never raise
        log.warning("model_retirement: brain config heal failed (non-fatal): %s", exc)
        return {}


def auto_heal_enabled() -> bool:
    """Read the live ``MODEL_AUTO_HEAL_ENABLED`` control; default on."""
    try:
        from packages.config import settings
        return bool(settings.model_auto_heal_enabled)
    except Exception:  # noqa: BLE001 - an unreadable control must not stop healing
        return True


async def heal_once(probes: dict[str, Any]) -> dict[str, str]:
    """One pass: detect retirements, then persist them. Returns ``replacements()``."""
    if not auto_heal_enabled():
        return {}
    if await heal_providers(probes) or _REPLACEMENTS:
        await heal_brain_config()
    return replacements()


async def auto_heal_loop(get_probes: Any, *, interval_sec: float = HEAL_INTERVAL_SEC) -> None:
    """Run ``heal_once`` forever. *get_probes* is an async callable returning probes."""
    while True:
        await asyncio.sleep(interval_sec)
        try:
            await heal_once(await get_probes())
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the loop must survive any pass
            log.warning("model_retirement: heal pass failed (non-fatal): %s", exc)
