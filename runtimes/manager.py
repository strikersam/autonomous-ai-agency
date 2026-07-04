"""runtimes/manager.py — RuntimeManager.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from runtimes.base import RuntimeAdapter, RuntimeUnavailableError, TaskResult, TaskSpec
from runtimes.health import RuntimeHealthService
from runtimes.registry import RuntimeCapabilityRegistry
from runtimes.routing import RoutingDecision, RoutingPolicy, RuntimeRoutingPolicyEngine

log = logging.getLogger("qwen-proxy")


def _env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean env var. Accepts 'true'/'1'/'yes' (case-insensitive)."""
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"true", "1", "yes"}


class RuntimeManager:
    def __init__(self, policy: RoutingPolicy | None = None) -> None:
        self._registry = RuntimeCapabilityRegistry()
        self._health = RuntimeHealthService(
            self._registry,
            poll_interval_sec=int(os.environ.get("RUNTIME_HEALTH_POLL_SEC", "30")),
        )
        self._router = RuntimeRoutingPolicyEngine(self._registry, self._health, policy=policy)
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        for adapter in self._registry.all():
            try:
                await adapter.start()
            except Exception as exc:
                log.warning("Runtime %s start failed: %s", adapter.RUNTIME_ID, exc)
        self._health.start()
        self._started = True

    async def stop(self) -> None:
        await self._health.stop()
        for adapter in self._registry.all():
            try:
                await adapter.stop()
            except Exception as exc:
                log.warning("Runtime %s stop failed: %s", adapter.RUNTIME_ID, exc)
        self._started = False

    def register(self, adapter: RuntimeAdapter) -> None:
        self._registry.register(adapter)
        if self._started:
            import asyncio
            asyncio.create_task(self._health._poll_one(adapter.RUNTIME_ID))

    def unregister(self, runtime_id: str) -> None:
        self._registry.unregister(runtime_id)

    async def execute(self, spec: TaskSpec) -> tuple[TaskResult, RoutingDecision]:
        return await self._router.route_and_execute(spec)

    def select_runtime(
        self, task_type: str, preferred_id: str | None = None
    ) -> tuple[RuntimeAdapter | None, list[dict]]:
        return self._router._pick_runtime(task_type, preferred_id)

    def get_runtime(self, runtime_id: str) -> dict | None:
        """Return cached health snapshot for a runtime (sync, non-blocking)."""
        health = self._health.get_health(runtime_id)
        if health is None:
            return None
        return {"runtime_id": runtime_id, "health": health.as_dict()}

    def list_runtimes(self) -> list[dict]:
        """Return all registered runtimes with their cached health status."""
        result = []
        for adapter in self._registry.all():
            rid = adapter.RUNTIME_ID
            health = self._health.get_health(rid)
            result.append({
                "runtime_id": rid,
                "available": health.available if health is not None else False,
                "health": health.as_dict() if health is not None else None,
            })
        return result

    def get_policy(self) -> dict[str, Any]:
        """Return the active routing policy as a plain dict."""
        return self._router.policy.as_dict()

    def update_policy(self, **kwargs: Any) -> None:
        """Update the routing policy in-place."""
        self._router.update_policy(**kwargs)

    def health_summary(self) -> list[dict]:
        """Return health status for all registered runtimes."""
        return self._health.all_health()

    def get_decision_log(self, limit: int = 100) -> list[dict]:
        """Return routing decision audit log (newest first)."""
        return self._router.get_decision_log(limit)

    async def get_runtime_health(self, runtime_id: str) -> dict | None:
        circuit = self._health._circuits.get(runtime_id)
        if circuit:
            circuit.record_success()
        await self._health._poll_one(runtime_id)
        health = self._health.get_health(runtime_id)
        return health.as_dict() if health else None

    async def wake_all_sleeping_runtimes(self) -> dict[str, Any]:
        """Actively wake every sleeping/circuit-open runtime.

        The default health service only re-probes a runtime after its
        circuit-breaker recovers (CB_RECOVERY_SEC). This method short-circuits
        that wait by force-probing every registered runtime once and recording
        success so the routing engine can select it on the next decision.

        Returns a summary with counts of woken, still-sleeping, and the
        per-runtime state. Never raises — a missing runtime must not block
        an orchestrator or CEO request.
        """
        woken: list[str] = []
        still_sleeping: list[str] = []
        details: dict[str, dict[str, Any]] = {}
        try:
            adapters = self._registry.all()
            for adapter in adapters:
                rid = adapter.RUNTIME_ID
                try:
                    before = self._health.get_health(rid)
                    before_available = bool(before and before.available)
                    await self._health._poll_one(rid)
                    after = self._health.get_health(rid)
                    after_available = bool(after and after.available)
                    details[rid] = {
                        "before_available": before_available,
                        "after_available": after_available,
                    }
                    if after_available:
                        woken.append(rid)
                    else:
                        still_sleeping.append(rid)
                except Exception as exc:
                    log.debug("wake_all_sleeping_runtimes: %s probe failed: %s", rid, exc)
                    details[rid] = {"error": str(exc)}
                    still_sleeping.append(rid)
        except Exception as exc:
            log.warning("wake_all_sleeping_runtimes failed: %s", exc)
        log.info(
            "wake_all_sleeping_runtimes: woken=%d still_sleeping=%d",
            len(woken), len(still_sleeping),
        )
        return {
            "woken": woken,
            "still_sleeping": still_sleeping,
            "details": details,
            "woken_count": len(woken),
            "still_sleeping_count": len(still_sleeping),
        }

    def is_available_for_routing(self, runtime_id: str) -> bool:
        """True if the runtime is healthy enough for the router to select it."""
        try:
            return bool(self._health.is_available(runtime_id))
        except Exception:
            return False


_runtime_manager: RuntimeManager | None = None


def get_runtime_manager() -> RuntimeManager:
    global _runtime_manager
    if _runtime_manager is None:
        _runtime_manager = _build_default_manager()
    return _runtime_manager


def _build_default_manager() -> RuntimeManager:
    """Construct the default RuntimeManager.

    Production runtime (InternalAgentAdapter) is always registered.
    External runtimes are opt-in via RUNTIME_<NAME>_ENABLED=true env vars:

      RUNTIME_DOCKER_ENABLED      — DockerAgentAdapter  (also: AGENT_MODE_DOCKER=true)
      RUNTIME_HERMES_ENABLED      — HermesAdapter
      RUNTIME_OPENCODE_ENABLED    — OpenCodeAdapter
      RUNTIME_GOOSE_ENABLED       — GooseAdapter
      RUNTIME_CLAUDE_CODE_ENABLED — ClaudeCodeAdapter
      RUNTIME_AIDER_ENABLED       — AiderAdapter
      RUNTIME_JCODE_ENABLED       — JCodeAdapter
      RUNTIME_OPENHANDS_ENABLED   — OpenHandsAdapter
      TASK_HARNESS_ENABLED        — TaskHarnessAdapter  (legacy flag kept)

    This keeps the default surface minimal and avoids probing unavailable
    external runtimes on every health-poll cycle.
    """
    from runtimes.adapters.internal_agent import InternalAgentAdapter

    policy = RoutingPolicy(
        never_use_paid_providers=_env_flag("RUNTIME_NEVER_PAID"),
        require_approval_before_paid_escalation=_env_flag("RUNTIME_REQUIRE_APPROVAL"),
        max_paid_escalations_per_day=int(os.environ.get("RUNTIME_MAX_PAID_ESCALATIONS", "0")),
        preferred_runtime_id=os.environ.get(
            "RUNTIME_DEFAULT",
            "docker_agent"
            if (_env_flag("RUNTIME_DOCKER_ENABLED") or _env_flag("AGENT_MODE_DOCKER"))
            else "internal_agent",
        ),
        fallback_runtime_ids=["internal_agent"],
        task_type_runtime_overrides={
            k: v
            for k, v in {
                "code_generation": os.environ.get("RUNTIME_CODE_GENERATION"),
                "code_review": os.environ.get("RUNTIME_CODE_REVIEW"),
                "repo_editing": os.environ.get("RUNTIME_REPO_EDITING"),
                "git_operations": os.environ.get("RUNTIME_GIT_OPS"),
            }.items()
            if v
        },
    )

    mgr = RuntimeManager(policy=policy)

    # ── Production runtime (always on) ────────────────────────────────────────
    mgr.register(InternalAgentAdapter())

    # ── Optional runtimes (opt-in via env vars) ───────────────────────────────
    if _env_flag("RUNTIME_DOCKER_ENABLED") or _env_flag("AGENT_MODE_DOCKER"):
        from runtimes.adapters.docker_agent import DockerAgentAdapter
        mgr.register(DockerAgentAdapter())
        log.info("RuntimeManager: DockerAgentAdapter registered")

    # ── Tier 1-3 specialist runtimes (Hermes, Goose, Aider) ───────────────────
    # These are registered ON BY DEFAULT so the agency can use them whenever their
    # CLI/sidecar is present. Each adapter self-reports availability=False (via
    # shutil.which / connection probe) when its tool is absent, so an unavailable
    # runtime is simply skipped by the router and falls back to internal_agent —
    # never a crash. Set RUNTIME_EXTERNAL_DISABLED=true to register none of them
    # (e.g. on a constrained host where the health-poll overhead is unwanted), or
    # set RUNTIME_<NAME>_ENABLED=false to disable an individual one.
    _external_default_on = not _env_flag("RUNTIME_EXTERNAL_DISABLED")

    if _env_flag("RUNTIME_HERMES_ENABLED", default=_external_default_on):
        from runtimes.adapters.hermes import HermesAdapter
        mgr.register(HermesAdapter())
        log.info("RuntimeManager: HermesAdapter registered")

    if _env_flag("RUNTIME_OPENCODE_ENABLED"):
        from runtimes.adapters.opencode import OpenCodeAdapter
        mgr.register(OpenCodeAdapter())
        log.info("RuntimeManager: OpenCodeAdapter registered")

    if _env_flag("RUNTIME_GOOSE_ENABLED", default=_external_default_on):
        from runtimes.adapters.goose import GooseAdapter
        mgr.register(GooseAdapter())
        log.info("RuntimeManager: GooseAdapter registered")

    if _env_flag("RUNTIME_CLAUDE_CODE_ENABLED"):
        from runtimes.adapters.claude_code import ClaudeCodeAdapter
        mgr.register(ClaudeCodeAdapter())
        log.info("RuntimeManager: ClaudeCodeAdapter registered")

    if _env_flag("RUNTIME_AIDER_ENABLED", default=_external_default_on):
        from runtimes.adapters.aider import AiderAdapter
        mgr.register(AiderAdapter())
        log.info("RuntimeManager: AiderAdapter registered")

    if _env_flag("RUNTIME_JCODE_ENABLED"):
        from runtimes.adapters.jcode import JCodeAdapter
        mgr.register(JCodeAdapter())
        log.info("RuntimeManager: JCodeAdapter registered")

    if _env_flag("OPENHANDS_ENABLED") or _env_flag("RUNTIME_OPENHANDS_ENABLED"):
        from runtimes.adapters.openhands import OpenHandsAdapter
        mgr.register(OpenHandsAdapter())
        log.info("RuntimeManager: OpenHandsAdapter registered")

    if _env_flag("TASK_HARNESS_ENABLED"):
        from runtimes.adapters.task_harness import TaskHarnessAdapter
        mgr.register(TaskHarnessAdapter())
        log.info("RuntimeManager: TaskHarnessAdapter registered")

    # ── E2B Firecracker micro-VM sandbox (roadmap ★5) ─────────────────────
    # Auto-on whenever E2B_API_KEY is set and E2B_ENABLED is not explicitly
    # false. The adapter self-reports available=False (via health_check)
    # when the e2b-code-interpreter SDK is not installed, so an unavailable
    # E2B simply falls back to internal_agent via the router.
    # RUNTIME_E2B_ENABLED is an explicit opt-in flag for parity with the
    # other optional runtimes; the primary activation signal is the key.
    from services.e2b_config import e2b_enabled as _e2b_enabled
    if _env_flag("RUNTIME_E2B_ENABLED") or _e2b_enabled():
        from runtimes.adapters.e2b import E2BAdapter
        from services.e2b_config import e2b_enabled as _e2b_on, is_e2b_sdk_importable as _e2b_sdk
        mgr.register(E2BAdapter())
        log.info(
            "RuntimeManager: E2BAdapter registered (enabled=%s sdk=%s)",
            _e2b_on(), _e2b_sdk(),
        )
        # When E2B is fully available, prefer it for code_generation /
        # repo_editing so new tasks route to the sandbox automatically.
        # internal_agent stays as the fallback in fallback_runtime_ids.
        if _e2b_on() and _e2b_sdk():
            existing_overrides = policy.task_type_runtime_overrides or {}
            for task_type in ("code_generation", "repo_editing"):
                existing_overrides.setdefault(task_type, "e2b")
            policy.task_type_runtime_overrides = existing_overrides
            if policy.preferred_runtime_id == "internal_agent":
                policy.preferred_runtime_id = "e2b"

    registered = [a.RUNTIME_ID for a in mgr._registry.all()]
    log.info("RuntimeManager: %d runtime(s) registered: %s", len(registered), registered)
    return mgr
