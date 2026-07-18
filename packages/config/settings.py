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

    @property
    def is_testing(self) -> bool:
        return self.testing == "true"

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
