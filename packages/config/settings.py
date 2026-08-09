"""packages/config/settings.py — typed configuration.

This is the ONLY module in the entire codebase that reads environment variables.
Every other module imports `from packages.config import settings` and accesses
typed attributes. This centralizes all configuration in one place.

Usage:
    from packages.config import settings
    if settings.nvidia_api_key:
        ...
"""
from __future__ import annotations

import os
from functools import lru_cache


def _env_int(name: str, default: int) -> int:
    """Read an int env var, falling back to *default* on a missing/bad value.

    Never raises: a typo in an operator-set interval must not stop the process
    from booting.
    """
    try:
        return int(os.environ.get(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


class Settings:
    """Typed configuration loaded from environment variables."""

    def __init__(self) -> None:
        # Storage
        self.storage_backend: str = os.environ.get("STORAGE_BACKEND", "mongo").lower()
        self.mongo_url: str = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        self.db_name: str = os.environ.get("DB_NAME", "llm_wiki_dashboard")
        self.sqlite_db_path: str = os.environ.get("SQLITE_DB_PATH", ".data/agency.db")
        self.redis_url: str = os.environ.get("REDIS_URL", "")

        # Auth
        # Never silently fall back to a hardcoded secret — that weakens every
        # JWT issued. If SECRET_KEY is missing, use a random ephemeral one
        # (matching backend/server.py's behaviour) and log a warning so the
        # operator knows sessions will be invalidated on restart.
        # Tests set TESTING=true to suppress the warning.
        self.jwt_secret: str = os.environ.get("SECRET_KEY", "")
        if not self.jwt_secret:
            import secrets as _secrets
            self.jwt_secret = _secrets.token_hex(32)
            if os.environ.get("TESTING", "").lower() != "true":
                import logging as _logging
                _logging.getLogger("agency-config").warning(
                    "SECRET_KEY not set — using a randomly generated secret. "
                    "Sessions will be invalidated on every server restart. "
                    "Set SECRET_KEY in production."
                )
        self.jwt_algorithm: str = "HS256"
        self.admin_email: str = os.environ.get("ADMIN_EMAIL", "admin@llmrelay.local")
        self.admin_password: str = os.environ.get("ADMIN_PASSWORD", "")
        self.admin_secret: str = os.environ.get("ADMIN_SECRET", "")
        self.activation_required: str = os.environ.get("ACTIVATION_REQUIRED", "true").lower()
        self.service_token: str = os.environ.get("SERVICE_TOKEN", "")

        # OAuth
        self.github_client_id: str = os.environ.get("GITHUB_CLIENT_ID", "")
        self.github_client_secret: str = os.environ.get("GITHUB_CLIENT_SECRET", "")
        self.google_client_id: str = os.environ.get("GOOGLE_CLIENT_ID", "")
        self.google_client_secret: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        self.oauth_redirect_base: str = os.environ.get("OAUTH_REDIRECT_BASE", "").rstrip("/")
        self.frontend_url: str = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")

        # LLM Providers
        self.nvidia_api_key: str = os.environ.get("NVIDIA_API_KEY", "")
        self.nvidia_base_url: str = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com")
        self.nvidia_default_model: str = os.environ.get("NVIDIA_DEFAULT_MODEL", "meta/llama-3.3-70b-instruct")
        self.cerebras_api_key: str = os.environ.get("CEREBRAS_API_KEY", "")
        self.groq_api_key: str = os.environ.get("GROQ_API_KEY", "")
        self.anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")

        # Agent Brain
        self.agent_planner_model: str = os.environ.get("AGENT_PLANNER_MODEL", "")
        self.agent_executor_model: str = os.environ.get("AGENT_EXECUTOR_MODEL", "")
        self.agent_verifier_model: str = os.environ.get("AGENT_VERIFIER_MODEL", "")
        self.agent_judge_model: str = os.environ.get("AGENT_JUDGE_MODEL", "")
        self.llm_provider: str = os.environ.get("LLM_PROVIDER", "nvidia-nim")

        # Ollama
        self.ollama_base: str = os.environ.get("OLLAMA_BASE", os.environ.get("OLLAMA_BASE_URL", ""))
        self.ollama_model: str = os.environ.get("OLLAMA_MODEL", "qwen3-coder:30b")

        # Brain Watchdog
        self.brain_watchdog_max_failures: int = int(os.environ.get("BRAIN_WATCHDOG_MAX_FAILURES", "3"))

        # Provider Router
        self.provider_cooldown_seconds: int = int(os.environ.get("PROVIDER_COOLDOWN_SECONDS", "30"))
        self.provider_ratelimit_cooldown_seconds: int = int(os.environ.get("PROVIDER_RATELIMIT_COOLDOWN_SECONDS", "20"))
        self.provider_ratelimit_cooldown_max_seconds: int = int(os.environ.get("PROVIDER_RATELIMIT_COOLDOWN_MAX_SECONDS", "120"))

        # Scheduler
        self.agency_ceo_enabled: str = os.environ.get("AGENCY_CEO_ENABLED", "true").lower()
        self.run_background_in_web: str = os.environ.get("RUN_BACKGROUND_IN_WEB", "true").lower()
        self.run_hermes_in_process: str = os.environ.get("RUN_HERMES_IN_PROCESS", "true").lower()
        self.cron_secret: str = os.environ.get("CRON_SECRET", "")

        # Testing
        self.testing: str = os.environ.get("TESTING", "").lower()

        # Telegram
        self.telegram_bot_token: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id: str = os.environ.get("TELEGRAM_CHAT_ID", "")

        # GitHub
        self.gh_pat: str = os.environ.get("GH_PAT", os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", "")))
        self.github_repository: str = os.environ.get("GITHUB_REPOSITORY", "strikersam/autonomous-ai-agency")

        # Runtime
        self.runtime_external_disabled: str = os.environ.get("RUNTIME_EXTERNAL_DISABLED", "").lower()
        self.runtime_hermes_enabled: str = os.environ.get("RUNTIME_HERMES_ENABLED", "true").lower()

        # Observability
        self.langfuse_secret_key: str = os.environ.get("LANGFUSE_SECRET_KEY", "")
        self.langfuse_public_key: str = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        self.langfuse_host: str = os.environ.get("LANGFUSE_HOST", "")

        # App
        self.api_keys: str = os.environ.get("API_KEYS", "")
        self.router_health_check_enabled: str = os.environ.get("ROUTER_HEALTH_CHECK_ENABLED", "true").lower()

        # Self-bootstrap
        self.self_bootstrap_enabled: str = os.environ.get("SELF_BOOTSTRAP_ENABLED", "true").lower()

        # Portfolio materializer (default ON — flag is the rollback lever)
        self.portfolio_materialize_enabled: str = os.environ.get("PORTFOLIO_MATERIALIZE_ENABLED", "true").lower()

        # Free-LLM-API model catalog sync (UNIT 8 — default ON).
        # When ON, the catalog (config/models.yaml) + active BrainConfig are
        # mirrored to the DB + the GET /api/catalog/models endpoint is enabled,
        # so external services can query which models are available. Advisory-
        # only — does NOT change brain routing (resolve_component_model() is
        # still the single source of truth for model resolution). The flag is
        # the rollback lever if the catalog endpoint causes issues.
        self.freellm_api_model_catalog_enabled: str = os.environ.get(
            "FREELLM_API_MODEL_CATALOG_ENABLED", "true"
        ).lower()

        # Whether the UNIT 8 catalog also publishes providers the LLM router
        # knows about (config/llm/providers.yaml, ADR-008). Default OFF: the
        # catalog document is a contract external services read, so widening
        # it is an operator decision, not a side effect of installing the
        # router.
        self.freellm_catalog_include_router: str = os.environ.get(
            "FREELLM_CATALOG_INCLUDE_ROUTER", "false"
        ).lower()

        # Self-repo autonomous shipping (default ON — flag is the rollback
        # lever). When ON, portfolio-materialized and ceo_direct GitHub-issue
        # tasks get auto_commit + repo context injected so the agent's
        # changes actually reach git (commit -> feature branch -> PR) instead
        # of being discarded when the worktree is cleaned up. Turning this
        # off reverts to report-only execution for these task types; it does
        # NOT affect the Telegram/chat agents, which set auto_commit
        # explicitly per-call regardless of this flag. Master can never be
        # touched directly and agents can never self-merge — see
        # agent/autonomy_gate.py — so this flag only controls whether a PR
        # gets opened at all, never a merge or a direct push.
        self.self_repo_auto_commit_enabled: str = os.environ.get(
            "SELF_REPO_AUTO_COMMIT_ENABLED", "true"
        ).lower()

        # North Mini Code default (Cohere Labs' Apache-2.0 agentic coding model,
        # north-mini-code-1.0 — 30B/3B-active MoE, 256K context, native tool use +
        # interleaved thinking). When ON (default), the agency's code-execution
        # loop + Hermes prefer North wherever the ACTIVE provider can serve it
        # (local Ollama, or OpenRouter's free tier). Providers that can't serve
        # it — e.g. NVIDIA NIM in production — fall back to the normal per-role
        # brain, so this flag never breaks a deployment that lacks North. The
        # flag is the on/off switch; per-model overrides still win, and the
        # Brain card can switch the executor preset back at any time.
        self.north_mini_code_default: str = os.environ.get(
            "NORTH_MINI_CODE_DEFAULT", "true"
        ).lower()

        # Explicit interleaved-thinking control for thinking-capable Ollama
        # models (North Mini Code, deepseek-r1, qwen3, …). Passed as
        # `reasoning_effort` on the Ollama OpenAI-compatible /v1/chat/completions
        # call ("high"/"medium"/"low" → thinking on at that effort). North Mini
        # Code "works best with thinking on", and Ollama already auto-enables it
        # for capable models when this is omitted — so the DEFAULT (unset) leaves
        # behaviour unchanged. Set this only to pin/force the effort level. Any
        # value other than high/medium/low is treated as unset.
        self.ollama_reasoning_effort: str = os.environ.get(
            "OLLAMA_REASONING_EFFORT", ""
        ).strip().lower()

        # ── Render MCP (platform-level debugging + environment monitoring) ──
        # The agency runs on Render, but nothing inside the process can see the
        # *platform* view: build/deploy failures, OOM kills, restarts, CPU and
        # memory ceilings. agent/log_monitor.py only ever sees logs this Python
        # process emitted, so a container that died before FastAPI booted is
        # invisible to it. The Render MCP server (render-oss/render-mcp-server)
        # exposes exactly that missing view over MCP, and these settings point
        # the agency at it.
        self.render_api_key: str = os.environ.get("RENDER_API_KEY", "")
        # Streamable-HTTP endpoint of a Render MCP server. In production this
        # is the `agency-render-mcp` sidecar declared in render.yaml, reached
        # over Render's private network. The default is the loopback form so a
        # developer running `render-mcp-server -t http` locally (it binds
        # :10000 and serves /mcp — upstream cmd/server.go) needs no config.
        self.render_mcp_url: str = os.environ.get(
            "RENDER_MCP_URL", "http://127.0.0.1:10000/mcp"
        ).rstrip("/")
        # Render workspace (owner) ID passed explicitly on every resource tool
        # call. Upstream deprecated implicit session-scoped workspace
        # selection, so we always pass it when known.
        self.render_workspace_id: str = os.environ.get("RENDER_WORKSPACE_ID", "")
        # Comma-separated Render resource IDs the ops loop watches. Empty means
        # "discover every service in the workspace via list_services".
        self.render_service_ids: str = os.environ.get("RENDER_SERVICE_IDS", "")
        # Master switch for the autonomous Render ops loop. Default ON:
        # platform monitoring is the standing state of this deployment, not an
        # opt-in an operator has to remember after an incident. This is safe to
        # default on only because `is_render_ops_enabled` also requires
        # RENDER_API_KEY — an install with no Render credentials stays dormant
        # rather than failing a tick every ten minutes.
        self.render_ops_enabled: str = os.environ.get("RENDER_OPS_ENABLED", "true").lower()
        self.render_ops_interval_seconds: int = _env_int("RENDER_OPS_INTERVAL_SECONDS", 600)
        # Default-deny for mutating Render tools (trigger_deploy,
        # update_environment_variables, create_*). Reading production state is
        # safe and is what "100% autonomous debugging" needs; changing a live
        # service's environment is not something a loop should do because a flag
        # was left at its default.
        self.render_mcp_allow_writes: str = os.environ.get(
            "RENDER_MCP_ALLOW_WRITES", "false"
        ).lower()

        # ── Playwright MCP (browser automation for agents) ──────────────────
        # Lets an agent verify a deployed UI actually works instead of
        # inferring it from the diff. Unset by default: it needs a running
        # `npx @playwright/mcp --port <n>` (or equivalent) to point at, and a
        # declared-but-absent server would just report unreachable forever.
        self.playwright_mcp_url: str = os.environ.get("PLAYWRIGHT_MCP_URL", "").rstrip("/")

        # ── Operational-incident tracker (agent/operational_incidents.py) ────
        # Operational failures (timeouts, "all runtimes failed", rate limits)
        # never become code-fix tasks — an LLM editing source cannot fix a
        # saturated free tier. They are counted instead, and a signature that
        # recurs past the threshold inside the window is diagnosed and filed
        # once. These four values are the anti-storm bounds: raising the
        # threshold or lowering the cap makes the tracker quieter, never
        # louder.
        self.ops_incident_threshold: int = _env_int("OPS_INCIDENT_THRESHOLD", 4)
        self.ops_incident_window_seconds: int = _env_int(
            "OPS_INCIDENT_WINDOW_SECONDS", 1800
        )
        self.ops_incident_cooldown_seconds: int = _env_int(
            "OPS_INCIDENT_COOLDOWN_SECONDS", 21600
        )
        self.ops_incident_max_per_hour: int = _env_int("OPS_INCIDENT_MAX_PER_HOUR", 3)
        # How far back the incident pulls Render logs when building evidence.
        self.ops_incident_lookback_minutes: int = _env_int(
            "OPS_INCIDENT_LOOKBACK_MINUTES", 20
        )

        # ── Agent governance (packages/governance) ───────────────────────
        # Master switch. Default ON, but note that the *policy* ships in
        # `observe` mode, so enabling governance changes no behaviour — it
        # only starts producing identity-attributed audit events and
        # would-block counts. Enforcement is a separate, deliberate step
        # (`mode: enforce` in the policy file). Set false to remove the layer
        # entirely without a deploy if it ever misbehaves.
        self.governance_enabled_raw: str = os.environ.get(
            "GOVERNANCE_ENABLED", "true"
        ).strip().lower()
        self.governance_policy_path: str = os.environ.get(
            "GOVERNANCE_POLICY_PATH", "config/agent_policy.yaml"
        )
        self.governance_sandbox_profiles_path: str = os.environ.get(
            "GOVERNANCE_SANDBOX_PROFILES_PATH", "config/sandbox_profiles.yaml"
        )
        # "auto" probes docker, then e2b, then falls back to local. Pin to a
        # named backend only when the probe order is wrong for your install.
        self.governance_sandbox_backend: str = os.environ.get(
            "GOVERNANCE_SANDBOX_BACKEND", "auto"
        ).strip().lower()
        # Ring-buffer size for the in-memory audit trail. The durable record
        # is the structured log line; this only bounds what the dashboard and
        # API can page back through.
        self.governance_audit_capacity: int = _env_int("GOVERNANCE_AUDIT_CAPACITY", 2000)
        # How long an agent waits on a human approval before the request
        # expires and the action is denied.
        self.governance_approval_ttl_s: int = _env_int("GOVERNANCE_APPROVAL_TTL_S", 300)
        # Local-development escape hatch: approve high-risk actions without a
        # human. Off by default and audited as `resolved_by=auto-approve`
        # whenever it fires, so its use is always visible in the trail.
        self.governance_auto_approve_raw: str = os.environ.get(
            "GOVERNANCE_AUTO_APPROVE", "false"
        ).strip().lower()
        # Backpressure rather than resource exhaustion once many agents run
        # at once — see the multi-agent scaling notes in docs/governance.
        self.governance_max_sandboxes: int = _env_int("GOVERNANCE_MAX_SANDBOXES", 8)
        self.governance_artifacts_dir: str = os.environ.get(
            "GOVERNANCE_ARTIFACTS_DIR", ".artifacts"
        )

    @property
    def governance_enabled(self) -> bool:
        """When True, the governance layer evaluates and audits agent actions.

        This is *not* the enforcement switch — the policy file's ``mode``
        controls whether verdicts are acted on. Enabling governance alone is
        behaviour-neutral by design.
        """
        return self.governance_enabled_raw in {"1", "true", "yes", "on"}

    @property
    def governance_auto_approve(self) -> bool:
        """When True, approval-gated actions self-approve. Local dev only."""
        return self.governance_auto_approve_raw in {"1", "true", "yes", "on"}

    @property
    def is_testing(self) -> bool:
        return self.testing == "true"

    @property
    def render_service_id_list(self) -> list[str]:
        """``RENDER_SERVICE_IDS`` split into a clean list (empty when unset)."""
        return [s.strip() for s in self.render_service_ids.split(",") if s.strip()]

    @property
    def is_render_mcp_configured(self) -> bool:
        """True when there is both an API key and an endpoint to reach."""
        return bool(self.render_api_key and self.render_mcp_url)

    @property
    def is_render_ops_enabled(self) -> bool:
        """When True, the Render ops loop runs. On by default.

        Also requires ``is_render_mcp_configured``. That is not a second
        off-switch: ``RENDER_API_KEY`` cannot be committed, so the credential
        check is what lets the flag default to on without an install that has
        no Render credentials failing a tick every ten minutes. Combined here
        rather than rediscovered at each call site."""
        return (
            self.render_ops_enabled in {"1", "true", "yes", "on"}
            and self.is_render_mcp_configured
        )

    @property
    def is_render_mcp_write_allowed(self) -> bool:
        """When True, mutating Render MCP tools may be called. Default False."""
        return self.render_mcp_allow_writes in {"1", "true", "yes", "on"}

    @property
    def ollama_reasoning_effort_value(self) -> str:
        """Validated `reasoning_effort` for Ollama thinking models, or ``""``.

        Returns one of ``"high"`` / ``"medium"`` / ``"low"`` when
        ``OLLAMA_REASONING_EFFORT`` is set to a valid value, else ``""``
        (meaning: don't send the field — keep Ollama's own auto-enable
        behaviour)."""
        v = self.ollama_reasoning_effort
        return v if v in ("high", "medium", "low") else ""

    @property
    def is_agency_ceo_enabled(self) -> bool:
        return self.agency_ceo_enabled == "true"

    @property
    def is_background_in_web(self) -> bool:
        return self.run_background_in_web == "true"

    @property
    def is_activation_required(self) -> bool:
        return self.activation_required == "true"

    @property
    def is_hermes_in_process(self) -> bool:
        return self.run_hermes_in_process == "true" and not self.is_testing

    @property
    def is_freellm_api_model_catalog_enabled(self) -> bool:
        """UNIT 8: when True, the catalog is mirrored to the DB + the
        ``GET /api/catalog/models`` endpoint is enabled. Advisory-only."""
        return self.freellm_api_model_catalog_enabled == "true"

    @property
    def is_freellm_catalog_router_included(self) -> bool:
        """When True, router-configured providers join the mirrored catalog."""
        return self.freellm_catalog_include_router in {"1", "true", "yes", "on"}

    @property
    def is_self_repo_auto_commit_enabled(self) -> bool:
        """When True, ship-code task types (portfolio_initiative / issue /
        quick_note) get auto_commit + repo context injected so agent changes
        reach git via a PR instead of being discarded. Rollback lever only —
        agent/autonomy_gate.py independently blocks direct writes to
        master/main and any agent-initiated merge regardless of this flag."""
        return self.self_repo_auto_commit_enabled == "true"

    @property
    def is_north_mini_code_default(self) -> bool:
        """When True (default), the agency's coding loop + Hermes prefer
        Cohere's ``north-mini-code-1.0`` wherever the active provider can
        serve it, with automatic fallback to the normal brain elsewhere
        (so NVIDIA-only production is unaffected). Switch off to disable."""
        return self.north_mini_code_default == "true"


@lru_cache(maxsize=1)
def _get_settings() -> Settings:
    return Settings()


settings: Settings = _get_settings()
