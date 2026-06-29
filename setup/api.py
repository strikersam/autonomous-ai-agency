"""setup/api.py — First-run Setup Wizard backend.

Five-step wizard:
  Step 1: Provider setup         (select local vs cloud; enter API keys)
  Step 2: Local model detection  (show detected hardware; pick default model)
  Step 3: Runtime configuration  (choose which runtimes to enable)
  Step 4: Default agent          (configure default agent profile)
  Step 5: Policy preferences     (cost / privacy / escalation preferences)

After completion:
  - Settings are persisted per-user in the WizardState store.
  - The wizard stops auto-blocking login once complete, but can be reopened later for edits.
  - Admins can reset any user's wizard state.

Routes:
  GET  /api/setup/state              → current wizard state
  PUT  /api/setup/step/{step_num}    → save a single step
  POST /api/setup/complete           → mark wizard complete
  POST /api/setup/reset              → reset wizard (admin only)
  GET  /api/setup/detect/models      → detect available Ollama models
  GET  /api/setup/detect/hardware    → return hardware profile (delegates to hardware/)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:  # pragma: no cover - optional in some minimal environments
    AsyncIOMotorClient = None

from packages.auth.rbac import UserRole, audit, get_user_role, require_admin
from packages.config.activation import is_activated
from packages.config.activation_api import is_user_onboarding_allowed
from packages.auth.secrets_store import get_secrets_store, SecretRecord

log = logging.getLogger("qwen-proxy")

DEFAULT_LANGFUSE_HOST = (
    os.environ.get("LANGFUSE_BASE_URL")
    or os.environ.get("LANGFUSE_HOST")
    or os.environ.get("LANGFUSE_URL")
    or "https://cloud.langfuse.com"
)

setup_router = APIRouter(prefix="/api/setup", tags=["setup"])

# ── Wizard state model ────────────────────────────────────────────────────────

class WizardState(BaseModel):
    user_id:       str
    completed:     bool  = False
    current_step:  int   = 1
    started_at:    float = Field(default_factory=time.time)
    completed_at:  float | None = None
    # Per-step data (stored as raw dicts for flexibility)
    step1_providers:   dict = Field(default_factory=dict)   # provider selections
    step2_model:       dict = Field(default_factory=dict)   # default model choice
    step3_runtimes:    dict = Field(default_factory=dict)   # runtime enable flags
    step4_agent:       dict = Field(default_factory=dict)   # default agent config
    step5_policy:      dict = Field(default_factory=dict)   # policy preferences

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump()


# ── Step request models ────────────────────────────────────────────────────────

class Step1Request(BaseModel):
    """Provider setup: which providers to use and their API keys."""
    use_nvidia_nim:   bool = True   # default ON — free cloud, no local infra needed
    use_ollama:       bool = False  # default OFF — only needed for local inference
    ollama_base_url:  str  = "http://localhost:11434"
    repo_path:        str | None = None   # local-llm-server repo folder
    models_path:      str | None = None   # Ollama models folder
    use_openai:       bool = False
    use_anthropic:    bool = False
    use_google:       bool = False
    use_azure:        bool = False
    use_groq:         bool = False
    use_copilot:      bool = False
    # Note: API key values are stored via secrets_store, not here
    openai_secret_id:    str | None = None
    anthropic_secret_id: str | None = None
    google_secret_id:    str | None = None
    azure_secret_id:     str | None = None
    groq_secret_id:      str | None = None
    copilot_secret_id:   str | None = None


class Step2Request(BaseModel):
    """Local model detection results and default model selection.

    Defaults are pinned to the four NVIDIA-NIM free-tier models verified live
    today (2026-06-20 live probe — qwen3-coder-480b, qwen2.5-coder-32b,
    deepseek-r1, granite-34b, phi-3-medium, mistral-large-2, codestral-22b,
    llama-3.1-405b, codellama-70b, qwen3-235b-a22b all returned 404/410 and
    are NOT used here). Per-role asymmetry is preserved: planner/architect/
    reviewer/verifier/judge use the 120B MoE (reasoning-tuned); coder/executor
    use the dense 49B (JSON-clean tool-calling); scout uses 70B (fast
    read-only summarisation).

    SINGLE SOURCE OF TRUTH: packages/ai/registry.py. All model defaults below
    are resolved at instance creation via model_for_role() so changing the
    registry propagates here automatically.
    """
    # These are class-level defaults; instance-level resolution uses the
    # registry so env var overrides (NVIDIA_DEFAULT_MODEL, AGENT_PLANNER_MODEL,
    # etc.) take effect without code changes.
    default_model:      str  = ""  # resolved at runtime
    coder_model:        str  = ""
    planner_model:      str  = ""
    executor_model:     str  = ""
    reviewer_model:     str  = ""
    verifier_model:     str  = ""
    judge_model:        str  = ""
    scout_model:        str  = ""
    architect_model:    str  = ""
    fallback_model:     str  = ""
    embedding_model:    str  = "nomic-embed-text"
    accepted_degraded:  bool = False   # user acknowledges degraded compatibility
    repo_path:          str | None = None  # path to local-llm-server repo
    models_path:        str | None = None  # path to models directory

    def __init__(self, **data):
        super().__init__(**data)
        # Resolve all model defaults from the registry (single source of truth)
        from packages.ai.registry import model_for_role, default_model_for_provider, fallback_chain
        provider = "nvidia"  # setup wizard defaults to NVIDIA
        default = default_model_for_provider(provider)
        if not self.default_model:
            self.default_model = default
        if not self.coder_model:
            self.coder_model = model_for_role("executor", provider)
        if not self.planner_model:
            self.planner_model = model_for_role("planner", provider)
        if not self.executor_model:
            self.executor_model = model_for_role("executor", provider)
        if not self.reviewer_model:
            self.reviewer_model = model_for_role("verifier", provider)
        if not self.verifier_model:
            self.verifier_model = model_for_role("verifier", provider)
        if not self.judge_model:
            self.judge_model = model_for_role("judge", provider)
        if not self.scout_model:
            self.scout_model = default
        if not self.architect_model:
            self.architect_model = model_for_role("planner", provider)
        if not self.fallback_model:
            chain = fallback_chain(default)
            self.fallback_model = chain[-1] if chain else default


class Step3Request(BaseModel):
    """Runtime configuration."""
    enable_hermes:     bool = True
    enable_opencode:   bool = False
    enable_goose:      bool = False
    enable_openhands:  bool = False
    enable_task_harness: bool = False
    enable_aider:      bool = False
    hermes_base_url:   str  = "http://localhost:4444"


class Step4Request(BaseModel):
    """Default agent configuration."""
    agent_name:        str  = "My Agent"
    agent_model:       str  = ""  # resolved from registry at runtime
    runtime_id:        str | None = None
    cost_policy:       str  = "free_only"
    system_prompt:     str  = ""


class Step5Request(BaseModel):
    """Policy preferences."""
    never_use_paid_providers:        bool = True
    require_approval_before_paid:    bool = True
    max_paid_escalations_per_day:    int  = 0
    enable_langfuse:                 bool = False
    langfuse_public_key_secret_id:   str | None = None
    langfuse_secret_key_secret_id:   str | None = None
    langfuse_host:                   str  = DEFAULT_LANGFUSE_HOST
    send_anonymous_telemetry:        bool = False


# ── Persistent state store ────────────────────────────────────────────────────

_WIZARD_STATE_DIR = Path.home() / ".local-llm-server" / "wizard-states"
_WIZARD_STATE_DIR.mkdir(parents=True, exist_ok=True)

_wizard_states: dict[str, WizardState] = {}
_wizard_state_collection: Any | None = None
_wizard_state_collection_configured = False
_wizard_state_client: Any | None = None


def set_wizard_state_collection(collection: Any | None) -> None:
    """Override the persistence collection used for wizard state.

    Tests and hosted backends can inject a Mongo-style collection here. Pass
    ``None`` to fall back to auto-detection (or disk persistence when no DB is
    configured).
    """
    global _wizard_state_collection, _wizard_state_collection_configured
    _wizard_state_collection = collection
    _wizard_state_collection_configured = collection is not None


def clear_wizard_state_cache() -> None:
    """Clear the in-memory wizard-state cache."""
    _wizard_states.clear()


def _get_wizard_state_collection() -> Any | None:
    global _wizard_state_client, _wizard_state_collection
    if _wizard_state_collection_configured:
        return _wizard_state_collection
    if _wizard_state_collection is not None:
        return _wizard_state_collection
    mongo_url = (os.environ.get("MONGO_URL") or "").strip()
    if not mongo_url or AsyncIOMotorClient is None:
        return None
    try:
        db_name = (os.environ.get("DB_NAME") or "llm_wiki_dashboard").strip() or "llm_wiki_dashboard"
        _wizard_state_client = _wizard_state_client or AsyncIOMotorClient(mongo_url)
        _wizard_state_collection = _wizard_state_client[db_name]["wizard_states"]
    except Exception as exc:  # pragma: no cover - defensive fallback
        log.warning("Wizard state DB unavailable; falling back to disk: %s", exc)
        _wizard_state_collection = None
    return _wizard_state_collection


def _get_state_file(user_id: str) -> Path:
    """Get the file path for a user's wizard state."""
    safe_id = user_id.replace('/', '_').replace('\\', '_')
    return _WIZARD_STATE_DIR / f"{safe_id}.json"


def _wizard_state_checksum(state_dict: dict[str, Any]) -> str:
    """SHA-256 of the JSON-serialised state, EXCLUDING the '_checksum' field itself.

    The checksum guards against silent truncation from a crashed mid-write
    (process OOM, disk-full, etc. \u2014 we have seen truncated wizard-state files
    in the wild where the wizard thought the user finished setup, then on next
    login reported an empty state because only the first ~30% of the bytes
    landed).
    """
    payload = {k: v for k, v in state_dict.items() if k != "_checksum"}
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _validate_wizard_state_checksum(data: dict[str, Any], user_id: str) -> WizardState:
    """Verify the embedded checksum; reject on mismatch, accept legacy files.

    A legacy file (no ``_checksum`` key \u2014 shipped before the v5 hardening)
    is LOADED AS-IS with a debug log so the user is not silently signed out of
    the wizard on upgrade. A mismatched checksum means the bytes do not match
    the state we wrote: log at WARNING and return a fresh empty wizard so the
    operator is prompted to re-run setup (instead of acting on corrupted
    half-data, e.g. a model choice + no policy).
    """
    expected = data.get("_checksum")
    if expected is None:
        log.debug(
            "Wizard state for %s has no checksum (legacy file); trusting as-is",
            user_id,
        )
        data.pop("_checksum", None)
        return WizardState(**data)
    actual = _wizard_state_checksum(data)
    if expected != actual:
        log.warning(
            "Wizard state for %s failed checksum verification (expected %s, "
            "actual %s) \u2014 possible truncation; returning fresh state so the "
            "operator re-runs setup rather than acting on corrupted data",
            user_id, expected[:12], actual[:12],
        )
        return WizardState(user_id=user_id)
    data.pop("_checksum")
    return WizardState(**data)


async def _load_wizard_state(user_id: str) -> WizardState:
    """Load wizard state from disk (or DB), verifying checksum if present.

    Legacy files without ``_checksum`` are still loaded (forward-compatible
    rollout). Files WITH a checksum that no longer matches are rejected \u2014
    defensive against silent truncation / disk corruption that would
    previously manifest as the wizard quietly thinking setup had finished
    while half the user's choices were lost.
    """
    collection = _get_wizard_state_collection()
    if collection is not None:
        try:
            data = await collection.find_one({"user_id": user_id}, {"_id": 0})
            if data:
                return _validate_wizard_state_checksum(data, user_id)
        except Exception as e:
            log.warning("Failed to load wizard state for %s from DB: %s", user_id, e)

    state_file = _get_state_file(user_id)
    if state_file.exists():
        try:
            with open(state_file) as f:
                data = json.load(f)
            return _validate_wizard_state_checksum(data, user_id)
        except Exception as e:
            log.warning("Failed to load wizard state for %s: %s", user_id, e)
    return WizardState(user_id=user_id)


async def _save_wizard_state(state: WizardState) -> None:
    """Persist wizard state to disk (or DB) with a SHA-256 checksum.

    Disk writes go via a ``<file>.tmp`` + atomic ``replace`` so a process
    crash mid-flush cannot leave a half-written wizard state behind. The
    payload contains ``_checksum`` (SHA-256 of the rest of the payload) so
    the loader can detect even partial / silently-truncated files.
    """
    payload = state.as_dict()
    payload["_checksum"] = _wizard_state_checksum(payload)

    collection = _get_wizard_state_collection()
    if collection is not None:
        try:
            await collection.replace_one(
                {"user_id": state.user_id},
                payload,
                upsert=True,
            )
            return
        except Exception as e:
            log.error("Failed to save wizard state for %s to DB: %s", state.user_id, e)

    state_file = _get_state_file(state.user_id)
    try:
        tmp_path = state_file.with_suffix(state_file.suffix + ".tmp")
        with open(tmp_path, 'w') as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, state_file)
    except Exception as e:
        log.error("Failed to save wizard state for %s: %s", state.user_id, e)


async def _delete_wizard_state(user_id: str) -> None:
    collection = _get_wizard_state_collection()
    if collection is not None:
        try:
            await collection.delete_one({"user_id": user_id})
        except Exception as e:
            log.warning("Failed to delete wizard state for %s from DB: %s", user_id, e)
    state_file = _get_state_file(user_id)
    try:
        if state_file.exists():
            state_file.unlink()
    except Exception as e:
        log.warning("Failed to delete wizard state file for %s: %s", user_id, e)


async def get_wizard_state(user_id: str) -> WizardState:
    """Get wizard state, loading from disk if not already in memory."""
    if user_id not in _wizard_states:
        _wizard_states[user_id] = await _load_wizard_state(user_id)
    return _wizard_states[user_id]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _uid(request: Request) -> str:
    user = getattr(request.state, "user", None) or {}
    if isinstance(user, dict):
        return user.get("email") or user.get("_id") or "anonymous"
    return str(getattr(user, "email", "anonymous"))


async def _detect_ollama_models(base_url: str = "http://localhost:11434") -> list[dict]:
    """Query Ollama /api/tags to get the list of locally available models."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                data   = resp.json()
                models = data.get("models", [])
                return [
                    {
                        "name":     m.get("name", ""),
                        "size_gb":  round(m.get("size", 0) / 1e9, 1),
                        "modified": m.get("modified_at", ""),
                    }
                    for m in models
                ]
    except Exception as e:
        log.debug("Ollama model detection failed: %s", e)
    return []


# ── Routes ────────────────────────────────────────────────────────────────────

@setup_router.get("/state")
async def get_setup_state(request: Request):
    """Return the current wizard state for this user.

    Includes activation/onboarding gate flags so the frontend can show
    the appropriate wizard screen without extra round-trips.
    """
    uid   = _uid(request)
    state = await get_wizard_state(uid)
    result = state.as_dict()
    # Activation gate: if instance is not activated, block onboarding entirely
    activated = is_activated()
    onboarding_allowed = is_user_onboarding_allowed(uid) if activated else False
    result["_activation"] = {
        "instance_activated": activated,
        "onboarding_allowed": onboarding_allowed,
        # If blocked, tell the frontend why
        "blocked_reason": (
            None if (activated and onboarding_allowed)
            else ("instance_not_activated" if not activated else "onboarding_not_allowed")
        ),
    }
    return result


@setup_router.get("/detect/providers")
async def detect_configured_providers():
    """Return which providers are already configured server-side via env vars.

    Called by the setup wizard on load so it can show 'already configured'
    indicators (e.g. Nvidia NIM key already set on Render) without exposing
    the actual key values to the browser.
    """
    nvidia_key = (
        os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey") or ""
    ).strip()
    openai_key = (
        os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_COMPAT_API_KEY") or ""
    ).strip()
    anthropic_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    langfuse_pk = (os.environ.get("LANGFUSE_PUBLIC_KEY") or "").strip()
    langfuse_sk = (os.environ.get("LANGFUSE_SECRET_KEY") or "").strip()

    return {
        "nvidia_nim": {
            "configured": bool(nvidia_key),
            "base_url": os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com",
            "default_model": __import__('packages.ai.registry', fromlist=['nvidia_default_model']).nvidia_default_model(),
            # Curated roster of free-tier NVIDIA NIM models verified live in the
            # live probe on 2026-06-20. qwen3-coder-480b / qwen2.5-coder-32b /
            # deepseek-r1 / granite-34b / phi-3-medium / mistral-large-2 /
            # codestral-22b / llama-3.1-405b / codellama-70b / qwen3-235b-a22b
            # all returned 404/410 and are intentionally excluded.
            "live_free_models": [
                "meta/llama-3.3-70b-instruct",
                "meta/llama-3.3-70b-instruct",
                "meta/llama-3.3-70b-instruct",
                "meta/llama-3.1-70b-instruct",
            ],
        },
        "openai": {"configured": bool(openai_key)},
        "anthropic": {"configured": bool(anthropic_key)},
        "langfuse": {
            "configured": bool(langfuse_pk and langfuse_sk),
            "host": DEFAULT_LANGFUSE_HOST,
        },
    }


@setup_router.get("/detect/hardware")
async def detect_hardware_for_wizard():
    """Return hardware profile (used in Step 2 of wizard)."""
    from hardware.detector import get_hardware_profile
    import asyncio, functools
    profile = await asyncio.get_event_loop().run_in_executor(None, get_hardware_profile)
    return profile.as_dict()


@setup_router.get("/detect/models")
async def detect_models_for_wizard(ollama_url: str = "http://localhost:11434"):
    """Return list of locally available Ollama models (used in Step 2)."""
    models  = await _detect_ollama_models(ollama_url)
    return {"models": models, "total": len(models), "ollama_url": ollama_url}



def _require_onboarding_gate(request: Request) -> None:
    """Raise 403 if instance is not activated or user is not allowed to onboard."""
    uid = _uid(request)
    if not is_activated():
        raise HTTPException(
            status_code=403,
            detail={
                "code": "instance_not_activated",
                "message": "This Autonomous AI Agency instance has not been activated. "
                           "Email strikersam@gmail.com with your Instance ID to request an activation code.",
            },
        )
    if not is_user_onboarding_allowed(uid):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "onboarding_not_allowed",
                "message": "Your account has not been approved for onboarding. "
                           "Contact your administrator.",
            },
        )

@setup_router.put("/step/1")
async def save_step1(request: Request, body: Step1Request):
    _require_onboarding_gate(request)
    """Save Step 1: Provider setup."""
    uid   = _uid(request)
    state = await get_wizard_state(uid)
    state.step1_providers = body.model_dump()
    state.current_step    = max(state.current_step, 2)
    await _save_wizard_state(state)
    audit("setup.step1", getattr(request.state, "user", {}), resource="setup")
    return {"step": 1, "saved": True, "next_step": 2}


@setup_router.put("/step/2")
async def save_step2(request: Request, body: Step2Request):
    _require_onboarding_gate(request)
    """Save Step 2: Model selection."""
    uid   = _uid(request)
    state = await get_wizard_state(uid)
    state.step2_model  = body.model_dump()
    state.current_step = max(state.current_step, 3)
    await _save_wizard_state(state)
    audit("setup.step2", getattr(request.state, "user", {}), resource="setup")
    return {"step": 2, "saved": True, "next_step": 3}


@setup_router.put("/step/3")
async def save_step3(request: Request, body: Step3Request):
    _require_onboarding_gate(request)
    """Save Step 3: Runtime configuration."""
    uid   = _uid(request)
    state = await get_wizard_state(uid)
    state.step3_runtimes = body.model_dump()
    state.current_step   = max(state.current_step, 4)
    await _save_wizard_state(state)
    audit("setup.step3", getattr(request.state, "user", {}), resource="setup")
    return {"step": 3, "saved": True, "next_step": 4}


@setup_router.put("/step/4")
async def save_step4(request: Request, body: Step4Request):
    _require_onboarding_gate(request)
    """Save Step 4: Default agent."""
    uid   = _uid(request)
    state = await get_wizard_state(uid)
    state.step4_agent  = body.model_dump()
    state.current_step = max(state.current_step, 5)
    await _save_wizard_state(state)
    audit("setup.step4", getattr(request.state, "user", {}), resource="setup")
    return {"step": 4, "saved": True, "next_step": 5}


@setup_router.put("/step/5")
async def save_step5(request: Request, body: Step5Request):
    _require_onboarding_gate(request)
    """Save Step 5: Policy preferences."""
    uid   = _uid(request)
    state = await get_wizard_state(uid)
    state.step5_policy = body.model_dump()
    state.current_step = 5
    await _save_wizard_state(state)
    audit("setup.step5", getattr(request.state, "user", {}), resource="setup")
    return {"step": 5, "saved": True, "next_step": "complete"}


@setup_router.post("/complete")
async def complete_wizard(request: Request):
    _require_onboarding_gate(request)
    """Mark wizard as complete.  Will not be shown again on next login."""
    uid   = _uid(request)
    state = await get_wizard_state(uid)
    state.completed    = True
    state.completed_at = time.time()
    await _save_wizard_state(state)
    audit("setup.complete", getattr(request.state, "user", {}), resource="setup", outcome="success")
    log.info("Setup wizard completed for user %s", uid)
    return {"completed": True, "user_id": uid}


@setup_router.post("/reset")
async def reset_wizard(request: Request):
    """Reset wizard state.  Admin only."""
    require_admin(request)
    target_uid = (await request.json()).get("user_id", _uid(request))
    if target_uid in _wizard_states:
        del _wizard_states[target_uid]
    await _delete_wizard_state(target_uid)
    audit("setup.reset", getattr(request.state, "user", {}), resource="setup", resource_id=target_uid)
    return {"reset": True, "user_id": target_uid}


@setup_router.post("/secret")
async def store_secret_during_setup(request: Request):
    """Store API keys/secrets during setup wizard (accessible without full auth).

    Used by the setup wizard frontend to store provider API keys (OpenAI, Anthropic, etc)
    before the user has completed setup and may not have full authentication yet.
    """
    try:
        body = await request.json()
        name = body.get("name")
        value = body.get("value")
        description = body.get("description", "")

        if not name or not value:
            raise HTTPException(status_code=400, detail="name and value are required")

        user = getattr(request.state, "user", {}) or {}
        uid = user.get("email") or user.get("_id") or "setup-user"

        rec = SecretRecord(owner_id=uid, name=name, description=description)
        rec.set_value(value)

        store = get_secrets_store()
        await store.create(rec)

        audit("setup.secret_created", user, resource="secret", resource_id=rec.secret_id)
        return {"id": rec.secret_id, "name": rec.name}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to store secret during setup: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store secret: {str(e)}")
