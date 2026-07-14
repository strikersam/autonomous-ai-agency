"""Shared free-brain policy helpers (issue #656).

Single source of truth for "is the agent allowed to use a paid brain?" and
"what free NVIDIA brain should we route to instead?". Imported by both
``services/workflow_orchestrator.py`` (orchestrator brain resolver) and
``agent/loop.py`` (the ``internal_agent`` runtime) so neither can silently call
paid Anthropic when the operator has not opted in.

Design invariants:
  - Free-first by default. ``ALLOW_PAID_BRAIN`` must be explicitly truthy for any
    paid (Anthropic / Bedrock) call path to run.
  - No heavy imports here (only ``os``) so this module is safe to import from
    anywhere, including risky low-level modules, without circular-import risk.
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("brain_policy")

# Default free NVIDIA NIM brain. The operator points this at the most capable
# free cloud model via NVIDIA_DEFAULT_MODEL; this fallback is the documented
# default (see .env.example / render.yaml).
#
# PR #984: default changed to z-ai/glm-5.2 — the operator's preferred brain
# model (https://build.nvidia.com/z-ai/glm-5.2). Free, high-quality, fast.
# The old default (meta/llama-3.3-70b-instruct) is kept as the fallback in
# the model registry.
DEFAULT_FREE_NVIDIA_MODEL = "z-ai/glm-5.2"

_TRUTHY = {"1", "true", "yes", "on"}


def allow_paid_brain() -> bool:
    """True only when the operator explicitly opted into a paid (Anthropic) brain.

    Default ``False``: the free-brain policy (Autonomy Charter / issue #656)
    means no runtime silently calls a paid API. Set ``ALLOW_PAID_BRAIN=true`` to
    permit paid Anthropic / Bedrock as a last resort.
    """
    return os.environ.get("ALLOW_PAID_BRAIN", "").strip().lower() in _TRUTHY


def get_brain_preference() -> str:
    """Return the operator's brain provider preference.

    Values:
      - ``"nvidia"``  — prefer NVIDIA NIM cloud (default)
      - ``"ollama"``  — prefer local Ollama
      - ``"colibri"`` — prefer local JustVugg/colibri (GLM-5.2 744B MoE on :8081)
      - ``"auto"``    — let priority decide (same as "nvidia" in practice)

    Set via ``BRAIN_PREFERENCE`` env var or the Admin SPA toggle
    (``PATCH /admin/api/policy/brain``).
    """
    raw = os.environ.get("BRAIN_PREFERENCE", "nvidia").strip().lower()
    if raw in ("nvidia", "ollama", "auto", "colibri"):
        return raw
    return "nvidia"


def is_anthropic_model(model: str | None) -> bool:
    """True when *model* names a paid Anthropic/Bedrock-Claude model.

    Covers native Anthropic ids (``claude-*``), Bedrock ids
    (``us.anthropic.claude-*``), and the generic ``opus`` alias the agent uses.
    """
    m = (model or "").strip().lower()
    if not m:
        return False
    return (
        m.startswith("claude")
        or m.startswith("us.anthropic")
        or m.startswith("anthropic")
        or "anthropic." in m
        or "opus" in m
    )


def resolve_free_nvidia_brain() -> tuple[str, dict, str] | None:
    """Resolve the free NVIDIA NIM brain from env, or ``None`` if unconfigured.

    Returns ``(openai_compatible_base_url, auth_headers, model)`` where the base
    URL already ends in ``/v1`` so the OpenAI-compatible client can append
    ``/chat/completions`` directly. Returns ``None`` when ``NVIDIA_API_KEY`` is
    not set — callers must then refuse to fall back to paid Anthropic.
    """
    key = (os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey") or "").strip()
    if not key:
        return None
    base = (os.environ.get("NVIDIA_BASE_URL") or "").strip().rstrip("/") or "https://integrate.api.nvidia.com"
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    model = (os.environ.get("NVIDIA_DEFAULT_MODEL") or "").strip() or DEFAULT_FREE_NVIDIA_MODEL
    return base, {"Authorization": f"Bearer {key}"}, model


# ── Single source of truth: the active brain LLM ────────────────────────────────
#
# These helpers consolidate every brain selector behind ONE resolution path.
# Previously, ``services/workflow_orchestrator._resolve_brain_provider``,
# ``router/model_router._opus_model``, ``runtimes/adapters/internal_agent.
# _best_cloud_primary_base``, ``agents/harness_adapter.HARNESS_CATALOG.
# default_model``, and ``services/ceo_dispatcher.ROLE_RUNTIME_PREFERENCE``
# each had their own selector that could disagree with the Providers UI.
#
# User intent ("one place changes it in all places"): the Providers screen
# drag-and-drop priority reorder now drives every selector via these helpers.
#
# Design invariants:
#   - Free-first by default. ``ALLOW_PAID_BRAIN`` must be explicitly truthy for
#     any paid (Anthropic / Bedrock) call path to run.
#   - Env override ``AGENT_LLM_BASE_URL`` always wins (operator kill-switch).
#   - The cached sync getter (``get_active_brain_sync()``) is updated by
#     ``resolve_active_brain()`` after each fresh resolution and whenever
#     the UI calls ``invalidate_brain_cache()`` after a provider edit.

from dataclasses import dataclass, field
from typing import Any

PAID_TYPES: frozenset[str] = frozenset({"anthropic", "emergent-anthropic"})


@dataclass(frozen=True)
class BrainResolution:
    """Resolved brain LLM for the current agency configuration.

    ``provider_id`` is the record's provider_id (the UI badge). ``base_url``
    ends with ``/v1`` for OpenAI-compatible providers so the OpenAI client
    can append ``/chat/completions`` directly. Anthropic-shaped providers
    keep the bare base URL because they hit ``/v1/messages``.
    ``role`` is one of:
      - ``"brain"``         — currently selected, in use
      - ``"fallback"``      — paid, last-resort (Anthropic / Bedrock)
      - ``"sub-agent"``     — reachable, not brain, used on failover
      - ``"unconfigured"``  — record exists but key/base missing
      - ``"env_override"``  — AGENT_LLM_BASE_URL was set
      - ``"free_fallback"`` — fell through to the free NVIDIA default
      - ``"ollama_local"``  — local Ollama fallback
      - ``"env_colibri"``   — env-shim fallback for BRAIN_PREFERENCE=colibri
    """

    provider_id: str
    base_url: str
    auth_headers: dict | None
    model: str | None
    role: str
    free_tier: bool = True
    source: str = "records"
    priority: int = 0


# In-memory cache so sync callers (model router, harness adapter, scripts)
# read this without needing asyncio.
_cached_brain: BrainResolution | None = None


def invalidate_brain_cache() -> None:
    """Clear the cached brain so the next read re-resolves.

    Called from webui/providers.py after create/delete/update so the next
    agent run picks up the drag-and-drop reorder immediately.
    """
    global _cached_brain
    _cached_brain = None


def get_active_brain_sync() -> BrainResolution | None:
    """Return the cached brain read by sync callers. None if never resolved."""
    return _cached_brain


def _norm(base: str) -> str:
    return (base or "").strip().rstrip("/")


def _host_is_openai_compatible(base_url: str) -> bool:
    """True when the base URL should get an /v1 prefix appended (openai-compat).

    Native Anthropic endpoints (api.anthropic.com) keep the bare URL because
    they hit /v1/messages — appending /v1 would break them.
    """
    host = (base_url or "").lower()
    return bool(host) and "anthropic.com" not in host


async def resolve_active_brain(
    *,
    exclude_base_urls: set[str] | None = None,
) -> BrainResolution:
    """Single source of truth for the active brain LLM.

    Resolution order (matches the binding contract pinned in
    ``tests/test_brain_priority_scanner.py``):

      1. ``AGENT_LLM_BASE_URL`` env override (role: env_override)
      2. **DB-persisted ``BrainConfig``** (PR #824 follow-up) — when the
         admin UI has applied a brain config, that provider wins over both
         env vars and provider records. role: ``brain_config``.
      3. Highest-priority configured provider record (role: brain)
         - paid providers skipped unless no free alternative exists AND
           ``ALLOW_PAID_BRAIN=true`` is explicitly set.
         - any base_url whose /v1-normalised form is in ``exclude_base_urls``
           is skipped (failover retry path).
      4. ``brain_policy.resolve_free_nvidia_brain()`` default (role: free_fallback)
         - Skipped when ``BRAIN_PREFERENCE=ollama`` — operator wants local only.
      5. Local Ollama fallback (role: ollama_local)
    """
    global _cached_brain
    exclude = {_norm(u) for u in (exclude_base_urls or set())}

    # 1. Env override — always wins. Contract is "use as-is, normalized"
    # (no /v1 auto-append); tests/test_orchestrator_failover.py::test_env_override_wins
    # pins ``base == AGENT_LLM_BASE_URL exactly. Operators rely on this as a
    # kill-switch and need to know what URL the brain resolver will hit.
    env_base = os.environ.get("AGENT_LLM_BASE_URL", "").strip()
    if env_base:
        env_key = os.environ.get("AGENT_LLM_API_KEY", "").strip()
        env_model = os.environ.get("AGENT_LLM_MODEL", "").strip() or None
        headers = {"Authorization": f"Bearer {env_key}"} if env_key else None
        base = _norm(env_base)
        resolution = BrainResolution(
            provider_id="env_override",
            base_url=base,
            auth_headers=headers,
            model=env_model,
            role="env_override",
            free_tier=True,
            source="env_override",
            priority=10_000,
        )
        _cached_brain = resolution
        return resolution

    # 2. DB-persisted BrainConfig (PR #824). The admin UI writes here via
    # PATCH /admin/api/policy/brain, with a mandatory liveness probe before
    # save so we never persist a dead model. When set, it wins over both
    # env vars (other than the kill-switch above) and the provider records
    # — that's the whole point of "one-click change from the UI".
    try:
        from packages.ai.brain_config import (
            get_brain_config,
            provider_api_key,
            provider_base_url,
            SAFE_DEFAULT_MODEL,
        )
        cfg = await get_brain_config()
        # Only honour the DB config when it has actually been set by an
        # operator (updated_at is empty on the safe-default boot state).
        # This keeps the existing test contract intact: when no PATCH has
        # been issued, the resolver falls through to provider records / env.
        if cfg.updated_at:
            preference = get_brain_preference()
            # If operator wants ollama-only, ignore a stale cloud config.
            # This is the fix for Issue 1 (chat 240s timeout): when
            # BRAIN_PREFERENCE=ollama but the persisted BrainConfig points
            # at a cloud provider (e.g. a stale "nvidia" config from before
            # the operator switched to ollama), every task routes to a cloud
            # provider the operator explicitly opted out of — and if that
            # provider's model is dead (410 Gone), every task blocks until
            # the 240s agent-run budget expires.
            if preference == "ollama" and cfg.primary_provider != "ollama":
                log.warning(
                    "brain_policy: ignoring persisted BrainConfig (provider=%s) "
                    "because BRAIN_PREFERENCE=ollama — falling through to ollama",
                    cfg.primary_provider,
                )
            else:
                provider = cfg.primary_provider
                base = provider_base_url(provider)
                if base:
                    key = provider_api_key(provider)
                    if provider == "ollama" or key:
                        if not base.endswith("/v1") and provider != "ollama":
                            base = f"{base}/v1"
                        headers = {"Authorization": f"Bearer {key}"} if key else None
                        # Pick the role model — executor is the hot-path call.
                        model = cfg.executor_model or cfg.planner_model or SAFE_DEFAULT_MODEL
                        if _norm(base) not in exclude:
                            resolution = BrainResolution(
                                provider_id=f"brain_config:{provider}",
                                base_url=base,
                                auth_headers=headers,
                                model=model,
                                role="brain_config",
                                free_tier=True,
                                source="brain_config_store",
                                priority=9_000,
                            )
                            _cached_brain = resolution
                            return resolution
    except Exception as exc:  # noqa: BLE001 — never block resolution
        log.debug("brain_policy: BrainConfig lookup failed (%s) — continuing", exc)

    # 2. Configured provider records — read the same source the Providers UI uses.
    #
    # When BRAIN_PREFERENCE=ollama, prefer Ollama-type records over cloud providers
    # rather than skipping records entirely (operator may have custom Ollama endpoints).
    records, fetch_failed = await _read_provider_records()
    if records:
        pref = get_brain_preference()
        if pref == "ollama":
            # Filter to Ollama-type records only so a custom Ollama endpoint
            # (e.g. a remote Ollama server) is preferred over the local fallback.
            ollama_records = [r for r in records if str(r.get("type") or "").lower() == "ollama"]
            if ollama_records:
                picked = _pick_from_records(ollama_records, exclude)
                if picked is not None:
                    _cached_brain = picked
                    return picked
        elif pref == "colibri":
            # Colibri is registered in provider_router via env (COLIBRI_ENABLED),
            # NOT in DB provider records — so a stale DB record (e.g. seeded nvidia
            # at priority=-10) would otherwise preempt the operator's colibri intent via
            # _pick_from_records. Skip the general records branch and fall through to
            # the env-shim below which reads COLIBRI_URL + COLIBRI_MODEL.
            pass
        else:
            picked = _pick_from_records(records, exclude)
            if picked is not None:
                _cached_brain = picked
                return picked
        # Records exist but none are usable (all excluded / all missing key /
        # only paid with ALLOW_PAID_BRAIN unset). Even when NVIDIA_API_KEY is
        # set we refuse to silently call it here — the operator configured
        # explicit records and they're all unavailable. Going to NVIDIA would
        # be a fresh HTTP blast they didn't sanction. Fall through to local
        # Ollama (mirrors services.workflow_orchestrator._resolve_brain_provider
        # precedent and the binding contract in
        # tests/test_brain_priority_scanner.py).
        log.warning(
            "brain_policy: provider records exist but no usable brain "
            "(exclude_set=%d); falling back to local Ollama.",
            len(exclude),
        )

    # 3. Free NVIDIA NIM brain — default ONLY when the operator has no
    # configured provider records (not a DB outage). Skipping on fetch-failed
    # preserves the test_records_list_failure_falls_back_to_ollama_env
    # contract: when MongoDB is down, fall straight to local Ollama rather
    # than firing an environment-based NVIDIA request the operator didn't
    # sanction.
    #
    # BRAIN_PREFERENCE=ollama OR colibri skips this step — the operator wants local only.
    # 2.5: Colibri (local GLM-5.2) env shim (BRAIN_PREFERENCE=colibri).
    # Reads COLIBRI_URL + COLIBRI_MODEL and resolves to a
    # BrainResolution(provider_id="colibri").  Priority 100 sits in
    # between the DB BrainConfig (9_000) and the free-NVIDIA fallback (-5), so
    # the resolver reaches colibri whenever the operator has set the env gate
    # without conflicting with DB-persisted or env-override paths.
    if get_brain_preference() == "colibri":
        colibri_url = os.environ.get("COLIBRI_URL", "").strip().rstrip("/")
        if colibri_url:
            if not colibri_url.endswith("/v1"):
                colibri_url = f"{colibri_url}/v1"
            colibri_model = (
                os.environ.get("COLIBRI_MODEL")
                or os.environ.get("AGENT_LLM_MODEL")
                or "glm-5.2"
            ).strip()
            _cached_brain = BrainResolution(
                provider_id="colibri",
                base_url=colibri_url,
                auth_headers=None,
                model=colibri_model,
                role="brain",
                free_tier=True,
                source="env_colibri",
                priority=100,
            )
            return _cached_brain
        # Operator typed the preference but forgot COLIBRI_URL — log loudly
        # so the silent ollama fallback below is not a surprise.
        log.warning(
            "brain_policy: BRAIN_PREFERENCE=colibri but COLIBRI_URL is unset; "
            "falling back to ollama_local (set COLIBRI_URL=http://localhost:8081/v1 "
            "or start `coli serve` with scripts\\start_colibri_server.ps1)."
        )

    # 3. Free NVIDIA NIM brain — default ONLY when the operator has no
    # configured provider records (not a DB outage). Skipping on fetch-failed
    # preserves the test_records_list_failure_falls_back_to_ollama_env
    # contract: when MongoDB is down, fall straight to local Ollama rather
    # than firing an environment-based NVIDIA request the operator didn't
    # sanction.
    #
    # BRAIN_PREFERENCE=ollama OR colibri skips this step — the operator wants local only.
    if not records and not fetch_failed and get_brain_preference() not in ("ollama", "colibri"):
        nv = resolve_free_nvidia_brain()
        if nv is not None:
            nv_base, nv_headers, nv_model = nv
            _cached_brain = BrainResolution(
                provider_id="nvidia-nim-free-default",
                base_url=nv_base,
                auth_headers=nv_headers,
                model=nv_model,
                role="free_fallback",
                free_tier=True,
                source="free_fallback",
                priority=-5,
            )
            return _cached_brain

    # 4. Local Ollama fallback. The base URL is UI-configurable (DB-persisted)
    #    so the operator can point the brain at a local/tunnelled Ollama from
    #    the Brain card without a Render env edit. DB value wins over env.
    try:
        from packages.ai.brain_config import resolve_ollama_base_url
        ollama_base = resolve_ollama_base_url()
    except Exception:  # pragma: no cover - defensive; keep the fallback alive
        ollama_base = os.environ.get("OLLAMA_BASE", "http://localhost:11434").rstrip("/")
    _cached_brain = BrainResolution(
        provider_id="ollama-local-fallback",
        base_url=ollama_base,
        auth_headers=None,
        model=None,
        role="ollama_local",
        free_tier=True,
        source="ollama_local",
        priority=-100,
    )
    return _cached_brain


async def get_provider_role_tags() -> dict[str, dict[str, Any]]:
    """Map provider_id -> ``{is_brain, role, reason}``.

    Mirrors the surface area previously exposed by
    ``services/workflow_orchestrator.get_provider_role_tags`` so the Providers
    UI keeps the same BRAIN/fallback/sub-agent badges.
    """
    try:
        brain = await resolve_active_brain()
    except Exception as exc:  # noqa: BLE001 - defensive: never block the UI
        log.debug("brain_policy.get_provider_role_tags: brain resolution failed: %s", exc)
        brain = None

    try:
        records, _fetch_failed = await _read_provider_records()
    except Exception:
        records = []

    out: dict[str, dict[str, Any]] = {}
    brain_base_norm = _norm(brain.base_url) if brain else None

    for rec in records:
        pid = str(rec.get("provider_id") or "").strip()
        if not pid:
            continue
        rtype = str(rec.get("type") or "").lower()
        base = _norm(str(rec.get("base_url") or ""))
        key = str(rec.get("api_key") or "").strip()
        name = str(rec.get("name") or "").strip()

        is_brain = bool(
            brain_base_norm
            and base
            and (brain_base_norm == base or brain_base_norm == f"{base}/v1")
        )

        if not base or (rtype != "ollama" and not key):
            role = "unconfigured"
            reason = "Missing base_url or API key"
        elif is_brain:
            role = "brain"
            reason = "Used as the brain for agent execution"
        elif rtype in PAID_TYPES:
            role = "fallback"
            reason = (
                "Paid commercial fallback — only selected when no free provider "
                "is configured. Will incur costs."
            )
        else:
            role = "sub-agent"
            reason = (
                "Reachable backup — used by provider-router failover when the "
                "brain is excluded (cooldown / 5xx)."
            )
        # ``base_url`` and ``name`` are included so the Admin SPA can match
        # role tags to operators' locally-defined webui provider records
        # (which use a different provider_id namespace than the backend
        # Mongo store). Without these, every UI-added provider would render
        # an empty badge even when it maps to the same brain.
        out[pid] = {
            "is_brain": is_brain,
            "role": role,
            "reason": reason,
            "base_url": base,
            "name": name,
        }

    return out


async def _read_provider_records() -> tuple[list[dict[str, Any]], bool]:
    """Read provider records from the live store.

    Returns ``(records, fetch_failed)``. When MongoDB is unreachable (the
    typical ``RuntimeError`` from the underlying Motor client) we return
    ``([], True)`` so the resolver can distinguish a missing-records-config
    from a DB outage — and the contract pinned in
    tests/test_orchestrator_failover.py::test_records_list_failure_falls_back_to_ollama_env
    says: on DB outage the brain drops to OLLAMA_BASE rather than silently
    escalating to ``resolve_free_nvidia_brain()`` (which would mask that
    the operator's configured providers are unreachable).
    """
    try:
        from backend.server import _list_configured_provider_records  # type: ignore
        records = list(await _list_configured_provider_records())
        return records, False
    except Exception as exc:
        log.debug("brain_policy: provider record fetch failed: %s", exc)
        return [], True


def _pick_from_records(
    records: list[dict[str, Any]],
    exclude: set[str],
) -> BrainResolution | None:
    """Pick the highest-priority free provider, with paid opt-in fallback."""
    def _prio(rec: dict[str, Any]) -> int:
        try:
            return int(rec.get("priority") or 0)
        except (TypeError, ValueError):
            return 0

    sorted_recs = sorted(records, key=_prio, reverse=True)

    def _build(rec: dict[str, Any], role: str, source: str) -> BrainResolution | None:
        base_raw = _norm(str(rec.get("base_url") or ""))
        if not base_raw:
            return None
        rtype = str(rec.get("type") or "").lower()
        key = str(rec.get("api_key") or "").strip()
        base = base_raw
        if rtype != "anthropic" and not base.endswith("/v1"):
            base = f"{base}/v1"
        if base in exclude or _norm(base) in exclude:
            return None  # failover retry excluded this URL
        if rtype == "anthropic":
            headers = (
                {"x-api-key": key, "anthropic-version": "2023-06-01"} if key else None
            )
        else:
            headers = {"Authorization": f"Bearer {key}"} if key else None
            if rtype != "ollama" and not key:
                return None
        model = str(rec.get("default_model") or "").strip() or None
        return BrainResolution(
            provider_id=str(rec.get("provider_id") or "").strip() or "unknown",
            base_url=base,
            auth_headers=headers,
            model=model,
            role=role,
            free_tier=rtype not in PAID_TYPES,
            source=source,
            priority=_prio(rec),
        )

    # First pass: free providers only.
    for rec in sorted_recs:
        rtype = str(rec.get("type") or "").lower()
        if rtype in PAID_TYPES:
            continue
        built = _build(rec, role="brain", source="records")
        if built is not None:
            return built

    # No free provider usable: paid is selected ONLY when the operator
    # explicitly opted in (ALLOW_PAID_BRAIN=true). Without explicit opt-in we
    # refuse to silently escalate to Anthropic even when the operator's only
    # configured record is paid — the binding contract in
    # tests/test_brain_priority_scanner.py::test_brain_does_not_escalate_to_paid_by_default
    # pins this behaviour. The caller wraps None into the Ollama fallback.
    if allow_paid_brain():
        for rec in sorted_recs:
            rtype = str(rec.get("type") or "").lower()
            if rtype not in PAID_TYPES:
                continue
            built = _build(rec, role="brain", source="records")
            if built is not None:
                return built