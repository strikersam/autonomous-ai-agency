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
        # Never silently fall back to a hardcoded secret — fail fast in production.
        # Tests set TESTING=true so they get the empty-string default.
        self.jwt_secret: str = os.environ.get("SECRET_KEY", "")
        if not self.jwt_secret and os.environ.get("TESTING", "").lower() != "true":
            raise RuntimeError(
                "SECRET_KEY must be set in the environment (or set TESTING=true for tests). "
                "Never hardcode JWT secrets — a missing SECRET_KEY weakens every token issued."
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

    @property
    def is_testing(self) -> bool:
        return self.testing == "true"

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


@lru_cache(maxsize=1)
def _get_settings() -> Settings:
    return Settings()


settings: Settings = _get_settings()
