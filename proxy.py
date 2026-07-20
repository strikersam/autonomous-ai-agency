"""

Qwen3-Coder Authenticated Proxy

--------------------------------

Sits in front of Ollama, adds Bearer token auth, rate limiting, CORS,

and full streaming support. Exposes both:

  - Ollama native API  (/api/*)

  - OpenAI-compatible API (/v1/*)  ← works with Cursor, Continue, Aider, etc.

"""



import os

import sys

import json

import time

import logging

import asyncio

import threading

import hashlib

import subprocess

from pathlib import Path



from langfuse_obs import emit_chat_observation



from dotenv import load_dotenv



# Load .env before any config reads (uvicorn does not load .env by default).

load_dotenv()

from collections import defaultdict

from dataclasses import dataclass

from typing import AsyncIterator



import httpx

from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, Request, Header, Depends

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import StreamingResponse, JSONResponse



from starlette.middleware.sessions import SessionMiddleware



from packages.auth.admin import AdminAuthManager, AdminIdentity

from admin_gui import register_admin_gui

from agent.background import BackgroundAgent, BackgroundTask

from agent.browser import BrowserSession

from agent.commit_tracker import CommitAttribution, CommitTracker

from agent.context import ContextCompressor

from agent.coordinator import AgentCoordinator, WorkerSpec

from agent.loop import AgentRunner, FreeBuffAgent

from agent.memory import SessionMemory

from agent.models import AgentRunRequest, AgentSessionCreateRequest

from agent.permissions import AdaptivePermissions

from agent.playbook import PlaybookLibrary

from agent.scaffolding import ProjectScaffolder

from packages.scheduler.scheduler import AgentScheduler

from agent.skills import SkillLibrary

from agent.state import AgentSessionStore

from agent.terminal import TerminalPanel

from agent.token_budget import BudgetExceededError, TokenBudget

from agent.user_memory import UserMemoryStore

from agent.voice import VoiceCommandInterface
from agent.sam import SamAgent, get_sam

from agent.watchdog import ResourceWatchdog

from agent.quick_note import QuickNoteQueue, set_quick_note_queue, start_processor

from chat_handlers import handle_ollama_native_chat, handle_openai_chat_completions

from handlers.anthropic_compat import handle_anthropic_messages

from key_store import issue_new_api_key, load_key_store

from service_manager import WindowsServiceManager

from webui.config_store import JsonConfigStore

from webui.providers import ProviderManager

from webui.router import register_webui

from webui.workspaces import WorkspaceManager

from direct_chat import direct_chat_router

from features.api import features_router



# GATE: Golden Path #10 — Doctor diagnostics with public/authenticated split

from handlers.diagnostics import (

    list_available_fixes,

    run_deep_diagnostics,

    run_fix,

    run_public_status,

    _check_ollama,

)



# --- Config --------------------------------------------------------------------



OLLAMA_BASE    = os.environ.get("OLLAMA_BASE", "http://localhost:11434")

PROXY_PORT     = int(os.environ.get("PROXY_PORT", "8000"))

RAW_KEYS       = os.environ.get("API_KEYS", "")

VALID_API_KEYS = set(k.strip() for k in RAW_KEYS.split(",") if k.strip())

KEY_STORE      = load_key_store()

RATE_LIMIT_RPM = int(os.environ.get("RATE_LIMIT_RPM", "60"))   # requests per minute per key

LOG_LEVEL      = os.environ.get("LOG_LEVEL", "INFO")





def _strip_quoted_env(name: str) -> str:

    raw = os.environ.get(name, "") or ""

    v = raw.strip()

    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):

        v = v[1:-1].strip()

    return v





ADMIN_SECRET = _strip_quoted_env("ADMIN_SECRET")

WEAK_ADMIN_SECRETS = frozenset({

    "change-me",

    "admin",

    "password",

    "secret",

    "your-admin-secret",

})

# Comma-separated origins, or * (default). Example: https://app.example.com,https://other.com

_raw_cors = os.environ.get("CORS_ORIGINS", "*").strip()

CORS_ORIGINS = [o.strip() for o in _raw_cors.split(",") if o.strip()] or ["*"]

# Browsers refuse credentialed requests when Access-Control-Allow-Origin is "*",

# so only enable credentials when an explicit origin allow-list is configured.

# This keeps the admin session cookie usable cross-origin in production while

# never sending credentials to an open-wildcard origin.

CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS



# Refuse example / default keys from .env templates (must not be used in production)

WEAK_API_KEYS = frozenset({

    "change-me",

    "your-secret-key-here",

    "YOUR_API_KEY",

    "optional-second-key-for-another-device",

})



logging.basicConfig(

    level=getattr(logging, LOG_LEVEL),

    format="%(asctime)s [%(levelname)s] %(message)s",

)

log = logging.getLogger("qwen-proxy")



if not VALID_API_KEYS and len(KEY_STORE) == 0:

    log.warning(

        "⚠  No API keys configured: set API_KEYS and/or create keys with generate_api_key.py (KEYS_FILE). "

        "All authenticated routes will be rejected until at least one key exists.",

    )

elif VALID_API_KEYS:

    bad = VALID_API_KEYS & WEAK_API_KEYS

    if bad:

        log.error(

            "Refusing to start: API_KEYS contains placeholder or default keys: %s. "

            "Replace with secrets from openssl / PowerShell (see .env.example).",

            ", ".join(sorted(bad)),

        )

        sys.exit(1)



if ADMIN_SECRET and ADMIN_SECRET in WEAK_ADMIN_SECRETS:

    log.error(

        "Refusing to start: ADMIN_SECRET is a known weak placeholder. "

        "Generate a strong secret (e.g. Python: secrets.token_urlsafe(32)).",

    )

    sys.exit(1)



if ADMIN_SECRET and len(ADMIN_SECRET) < 32:

    log.error(

        "Refusing to start: ADMIN_SECRET must be at least 32 characters. "

        "Generate a strong secret: python -c \"import secrets; print(secrets.token_urlsafe(32))\"",

    )

    sys.exit(1)



if "*" in CORS_ORIGINS:

    log.warning(

        "⚠  CORS_ORIGINS is set to '*' (allow all). "

        "Set CORS_ORIGINS to your specific frontend origin(s) in production.",

    )



if ADMIN_SECRET and not KEY_STORE.is_configured():

    log.warning(

        "ADMIN_SECRET is set but KEYS_FILE is not — POST /admin/keys will return 503 until KEYS_FILE is configured.",

    )

elif ADMIN_SECRET:

    log.info(

        "Admin: POST /admin/keys (API) and browser UI at /admin/ui/login (session after login)",

    )



ADMIN_AUTH = AdminAuthManager(ADMIN_SECRET)

SERVICE_MANAGER = WindowsServiceManager(Path(__file__).resolve().parent)



# --- Auth context --------------------------------------------------------------



@dataclass(frozen=True)

class AuthContext:

    key: str

    email: str

    department: str

    key_id: str | None

    source: str  # "store" | "legacy"



# --- Rate limiter (in-memory, per key) -----------------------------------------



_rate_buckets: dict[str, list[float]] = defaultdict(list)

_rate_bucket_keys: set[str] = set()

_RATE_BUCKET_MAX_KEYS = 10_000

_rate_lock = asyncio.Lock()





def _rate_limit_exempt_key_ids() -> set[str]:

    """Key IDs explicitly exempted from rate limiting (read fresh from env).



    Configured via ``FREEBUFF_RATELIMIT_EXEMPT_KEY_IDS`` (comma-separated). This

    is intentionally narrow: it exempts the Telegram-driven FreeBuff service key

    so phone-driven free-NVIDIA agent runs aren't throttled by the per-key RPM

    limiter. Default empty → no key is exempt, so paid/general endpoints stay

    protected.

    """

    raw = os.environ.get("FREEBUFF_RATELIMIT_EXEMPT_KEY_IDS", "")

    return {x.strip() for x in raw.split(",") if x.strip()}





def is_rate_limit_exempt(key_id: str | None) -> bool:

    """True when this key is on the FreeBuff rate-limit exemption allowlist.



    Only store-backed keys (which carry a stable ``key_id``) can be exempted;

    legacy keys with no ``key_id`` are never exempt.

    """

    if not key_id:

        return False

    exempt = _rate_limit_exempt_key_ids()

    return bool(exempt) and key_id in exempt





def _is_freebuff_unlimited(request: Request | None) -> bool:

    """True when this request targets a FreeBuff route and should skip rate limiting.



    FreeBuff is the free-NVIDIA coding agent driven from the Telegram bot; the

    whole point is an *unlimited* free coding agent, so its routes are exempt

    from the per-key RPM limiter by default. Routes are still fully auth-gated

    (a valid API key is required) and only ever run free NVIDIA models. Set

    ``FREEBUFF_UNLIMITED=false`` to re-impose the limiter on FreeBuff routes.

    """

    if os.environ.get("FREEBUFF_UNLIMITED", "true").strip().lower() not in {"true", "1", "yes"}:

        return False

    try:

        path = request.url.path if request is not None else ""

    except Exception:

        path = ""

    return path.startswith("/freebuff")





async def _enforce_rate_limit(request: Request | None, key: str, key_id: str | None) -> None:

    """Apply the per-key RPM limiter unless this request is FreeBuff-exempt.



    Exemptions (both keep the route auth-gated, only the limiter is skipped):

      1. FreeBuff routes when ``FREEBUFF_UNLIMITED`` is on (default) — "unlimited".

      2. Specific key_ids listed in ``FREEBUFF_RATELIMIT_EXEMPT_KEY_IDS``.

    """

    if _is_freebuff_unlimited(request):

        return

    if is_rate_limit_exempt(key_id):

        log.info("FreeBuff rate-limit exemption applied for key_id=%s", key_id)

        return

    await check_rate_limit(key)





async def check_rate_limit(api_key: str) -> None:

    now = time.time()

    window = 60.0

    async with _rate_lock:

        # Evict keys that have had no activity in the last window to prevent unbounded growth

        if len(_rate_bucket_keys) >= _RATE_BUCKET_MAX_KEYS:

            stale = {

                k for k in _rate_bucket_keys

                if not _rate_buckets.get(k) or all(now - t >= window for t in _rate_buckets[k])

            }

            for k in stale:

                _rate_buckets.pop(k, None)

                _rate_bucket_keys.discard(k)

        _rate_bucket_keys.add(api_key)

        bucket = _rate_buckets[api_key]

        # Drop entries outside the 1-minute window

        _rate_buckets[api_key] = [t for t in bucket if now - t < window]

        if len(_rate_buckets[api_key]) >= RATE_LIMIT_RPM:

            raise HTTPException(

                status_code=429,

                detail=f"Rate limit exceeded: {RATE_LIMIT_RPM} req/min. Slow down."

            )

        _rate_buckets[api_key].append(now)



# --- Auth dependency ------------------------------------------------------------



async def verify_api_key(

    request: Request,

    authorization: str | None = Header(default=None),

    x_api_key: str | None = Header(default=None, alias="x-api-key"),

) -> AuthContext:

    """Accept both Authorization: Bearer <key> (standard) and x-api-key: <key> (Claude Code)."""

    key = ""

    if x_api_key:

        key = x_api_key.strip()

    elif authorization:

        if authorization.startswith("Bearer "):

            key = authorization[7:].strip()

        else:

            key = authorization.strip()



    if not key:

        raise HTTPException(

            status_code=401,

            detail="Missing API key. Set Authorization: Bearer <key> or x-api-key: <key>",

        )



    rec = KEY_STORE.lookup_plain_key(key)

    if rec:

        # FreeBuff routes are unlimited by default (free-NVIDIA agent via Telegram);

        # specific key_ids may also be exempted. Everything else is rate-limited.

        await _enforce_rate_limit(request, key, rec.key_id)

        return AuthContext(

            key=key,

            email=rec.email,

            department=rec.department,

            key_id=rec.key_id,

            source="store",

        )

    if key in VALID_API_KEYS:

        await _enforce_rate_limit(request, key, None)

        return AuthContext(

            key=key,

            email="unknown",

            department="legacy",

            key_id=None,

            source="legacy",

        )

    log.warning("Rejected request with invalid API key")

    raise HTTPException(status_code=403, detail="Invalid API key")





class AdminCreateKeyBody(BaseModel):

    email: str = Field(..., min_length=3, max_length=320)

    department: str = Field(..., min_length=1, max_length=128)





class AdminLoginBody(BaseModel):

    username: str = Field(default="", max_length=320)

    password: str = Field(..., min_length=1, max_length=512)





class AdminControlBody(BaseModel):

    action: str = Field(..., pattern="^(start|stop|restart)$")

    target: str = Field(..., pattern="^(ollama|proxy|tunnel|stack)$")





class AdminUpdateKeyBody(BaseModel):

    email: str = Field(..., min_length=3, max_length=320)

    department: str = Field(..., min_length=1, max_length=128)





def _require_admin(x_admin_secret: str | None, authorization: str | None) -> None:

    if not ADMIN_SECRET:

        raise HTTPException(status_code=404, detail="Not Found")

    got = (x_admin_secret or "").strip()

    if not got and authorization and authorization.startswith("Bearer "):

        got = authorization[7:].strip()

    if got != ADMIN_SECRET:

        raise HTTPException(status_code=401, detail="Unauthorized")





def _get_admin_identity_from_request(

    request: Request,

    authorization: str | None = Header(default=None),

) -> AdminIdentity:

    token = ""

    if authorization and authorization.startswith("Bearer "):

        token = authorization[7:].strip()

    # Allow direct ADMIN_SECRET as Bearer token (used by bot/API clients)

    if token and ADMIN_SECRET and token == ADMIN_SECRET:

        return AdminIdentity(username="api", auth_source="token")

    session = ADMIN_AUTH.sessions.get(token) if token else None

    if session:

        return session.identity

    # SessionMiddleware is only installed when ADMIN_AUTH.enabled is True.

    # Guard the access so missing middleware raises 401, not an unhandled 500.

    try:

        _session = request.session

    except AssertionError:

        _session = {}

    if _session.get("admin_ok"):

        username = str(_session.get("admin_user") or "admin")

        source = str(_session.get("admin_auth_source") or "session")

        return AdminIdentity(username=username, auth_source=source)

    raise HTTPException(status_code=401, detail="Unauthorized")



# --- App ------------------------------------------------------------------------



app = FastAPI(title="Qwen3-Coder Proxy", version="1.0.0", docs_url=None, redoc_url=None)



app.add_middleware(

    CORSMiddleware,

    allow_origins=CORS_ORIGINS,

    allow_credentials=CORS_ALLOW_CREDENTIALS,

    allow_methods=["*"],

    allow_headers=["*"],

)



if ADMIN_AUTH.enabled:

    _session_seed = ADMIN_SECRET or os.environ.get("COMPUTERNAME") or str(Path(__file__).resolve())

    _session_secret = hashlib.sha256(f"qwen-admin-session:{_session_seed}".encode()).hexdigest()

    app.add_middleware(

        SessionMiddleware,

        secret_key=_session_secret,

        session_cookie="qwen_admin_session",

        max_age=60 * 60 * 24 * 7,

        same_site="lax",

    )



register_admin_gui(app, KEY_STORE, ADMIN_AUTH, SERVICE_MANAGER)


import uuid as _uuid


@app.middleware("http")
async def _request_id_middleware(request: Request, call_next):
    """Attach X-Request-Id to every response for distributed tracing.

    Accepts an incoming ``X-Request-Id`` header and echoes it back; otherwise
    generates a fresh UUID.  Clients can correlate proxy logs with Langfuse
    observations by pinning the same ID across retry attempts.
    """
    req_id = request.headers.get("x-request-id") or _uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-Id"] = req_id
    return response


class ProviderRouter:

    """Holds external provider configs (e.g., NVIDIA NIM) for use in agent routing."""



    def __init__(self) -> None:

        self.providers: list = []





PROVIDER_ROUTER = ProviderRouter()

AGENT_SESSIONS = AgentSessionStore()

USER_MEMORY = UserMemoryStore()

_GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT") or None

AGENT_RUNNER = AgentRunner(

    ollama_base=OLLAMA_BASE,

    workspace_root=Path(__file__).resolve().parent,

    github_token=_GITHUB_TOKEN,

    session_store=AGENT_SESSIONS,

)



# --- Feature singletons --------------------------------------------------------

SESSION_MEMORY    = SessionMemory()

CTX_COMPRESSOR    = ContextCompressor()

PERMISSIONS       = AdaptivePermissions()

TOKEN_BUDGET      = TokenBudget()

PLAYBOOKS         = PlaybookLibrary()

SCAFFOLDER        = ProjectScaffolder()

SKILL_LIBRARY     = SkillLibrary()

TERMINAL_PANEL    = TerminalPanel()

COMMIT_TRACKER    = CommitTracker(repo_root=Path(__file__).resolve().parent)

VOICE_INTERFACE   = VoiceCommandInterface()

WATCHDOG          = ResourceWatchdog()

SCHEDULER         = AgentScheduler()

BACKGROUND_AGENT  = BackgroundAgent()

COORDINATOR       = AgentCoordinator(ollama_base=OLLAMA_BASE, workspace_root=str(Path(__file__).resolve().parent))

BROWSER_SESSION   = BrowserSession()

QUICK_NOTE_QUEUE  = QuickNoteQueue()

BACKGROUND_AGENT.start()

set_quick_note_queue(QUICK_NOTE_QUEUE)

start_processor(QUICK_NOTE_QUEUE)

try:

    from agent.agency import Agency, set_agency

    _AGENCY = Agency()

    set_agency(_AGENCY)

    # Gate the CEO agency loop with AGENCY_CEO_ENABLED (default true in prod,
    # false in tests via tests/conftest.py). Without this gate, importing
    # proxy.py (e.g. via test_auth_me_regression.py::proxy_client fixture)
    # starts a daemon thread that calls run_cycle() → chat_completion in the
    # background. That background call hits any monkeypatched _post_chat from
    # a test, polluting the test's call log — the root cause of
    # test_provider_router.py::test_419_short_retry_after_retries_same_model
    # failing with models_seen == ['model-a', 'Qwen/...', 'model-a'].
    _ceo_enabled = os.environ.get("AGENCY_CEO_ENABLED", "true").strip().lower() != "false"
    if _ceo_enabled:
        _AGENCY.start()
        log.info("CEO Agency started — tick=%dm", _AGENCY._tick // 60)
    else:
        log.info("CEO Agency loop NOT started (AGENCY_CEO_ENABLED=false)")

except Exception as exc:

    log.error("CEO Agency failed to start: %s", exc)



WEBUI_STORE = JsonConfigStore()

WEBUI_PROVIDERS = ProviderManager(WEBUI_STORE)

WEBUI_WORKSPACES = WorkspaceManager(WEBUI_STORE, default_local_root=Path(__file__).resolve().parent)

WEBUI_PROVIDERS.ensure_defaults(local_base_url=OLLAMA_BASE)

WEBUI_WORKSPACES.ensure_defaults()

register_webui(

    app,

    providers=WEBUI_PROVIDERS,

    workspaces=WEBUI_WORKSPACES,

    admin_enabled=ADMIN_AUTH.enabled,

    verify_user=verify_api_key,

    get_admin_identity=_get_admin_identity_from_request,

)



# --- Health (no auth) ----------------------------------------------------------



@app.post("/admin/keys")

async def admin_create_key(

    body: AdminCreateKeyBody,

    x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),

    authorization: str | None = Header(default=None),

):

    """Issue a new user API key (requires ADMIN_SECRET). Plain key returned once in JSON."""

    _require_admin(x_admin_secret, authorization)

    if not KEY_STORE.is_configured():

        raise HTTPException(status_code=503, detail="KEYS_FILE is not set on the server")

    plain, rec = issue_new_api_key(KEY_STORE, body.email.strip(), body.department.strip())

    log.info("Admin issued key_id=%s email=%s department=%s", rec.key_id, rec.email, rec.department)

    return {

        "api_key": plain,

        "key_id": rec.key_id,

        "email": rec.email,

        "department": rec.department,

        "created": rec.created,

    }





@app.post("/admin/api/login")

async def admin_login(body: AdminLoginBody):

    if not ADMIN_AUTH.enabled:

        raise HTTPException(status_code=404, detail="Admin login is not enabled")

    identity = ADMIN_AUTH.authenticate(body.username, body.password)

    if not identity:

        raise HTTPException(status_code=401, detail="Invalid admin credentials")

    session = ADMIN_AUTH.sessions.create(identity)

    return {

        "token": session.token,

        "username": identity.username,

        "auth_source": identity.auth_source,

        "expires_in": ADMIN_AUTH.sessions.ttl_seconds,

        "supports_windows_auth": ADMIN_AUTH.supports_windows_auth,

    }





@app.post("/admin/api/logout")

async def admin_logout(

    request: Request,

    authorization: str | None = Header(default=None),

    admin: AdminIdentity = Depends(_get_admin_identity_from_request),

):

    if authorization and authorization.startswith("Bearer "):

        ADMIN_AUTH.sessions.revoke(authorization[7:].strip())

    request.session.clear()

    return {"ok": True, "username": admin.username}





@app.get("/admin/api/status")

async def admin_status(admin: AdminIdentity = Depends(_get_admin_identity_from_request)):

    status = SERVICE_MANAGER.get_status()

    status["admin"] = {"username": admin.username, "auth_source": admin.auth_source}

    return status





@app.post("/admin/api/control")

async def admin_control(

    body: AdminControlBody,

    admin: AdminIdentity = Depends(_get_admin_identity_from_request),

):

    try:

        result = SERVICE_MANAGER.control(body.action, body.target, current_proxy_pid=os.getpid())

    except ValueError as exc:

        raise HTTPException(status_code=400, detail="Internal server error") from exc

    result["admin"] = {"username": admin.username}

    return result





@app.get("/admin/api/users")

async def admin_list_users(admin: AdminIdentity = Depends(_get_admin_identity_from_request)):

    if not KEY_STORE.is_configured():

        raise HTTPException(status_code=503, detail="KEYS_FILE is not set on the server")

    records = [

        {

            "key_id": rec.key_id,

            "email": rec.email,

            "department": rec.department,

            "created": rec.created,

        }

        for rec in KEY_STORE.list_records()

    ]

    return {"records": records, "count": len(records), "admin": {"username": admin.username}}





@app.post("/admin/api/users")

async def admin_create_user(

    body: AdminCreateKeyBody,

    admin: AdminIdentity = Depends(_get_admin_identity_from_request),

):

    if not KEY_STORE.is_configured():

        raise HTTPException(status_code=503, detail="KEYS_FILE is not set on the server")

    plain, rec = issue_new_api_key(KEY_STORE, body.email.strip(), body.department.strip())

    return {

        "api_key": plain,

        "record": {

            "key_id": rec.key_id,

            "email": rec.email,

            "department": rec.department,

            "created": rec.created,

        },

        "admin": {"username": admin.username},

    }





@app.patch("/admin/api/users/{key_id}")

async def admin_update_user(

    key_id: str,

    body: AdminUpdateKeyBody,

    admin: AdminIdentity = Depends(_get_admin_identity_from_request),

):

    rec = KEY_STORE.update_metadata(key_id, body.email, body.department)

    if not rec:

        raise HTTPException(status_code=404, detail="Unknown key_id")

    return {

        "record": {

            "key_id": rec.key_id,

            "email": rec.email,

            "department": rec.department,

            "created": rec.created,

        },

        "admin": {"username": admin.username},

    }





@app.delete("/admin/api/users/{key_id}")

async def admin_delete_user(

    key_id: str,

    admin: AdminIdentity = Depends(_get_admin_identity_from_request),

):

    if not KEY_STORE.delete_by_key_id(key_id):

        raise HTTPException(status_code=404, detail="Unknown key_id")

    return {"ok": True, "key_id": key_id, "admin": {"username": admin.username}}





@app.post("/admin/api/users/{key_id}/rotate")

async def admin_rotate_user(

    key_id: str,

    admin: AdminIdentity = Depends(_get_admin_identity_from_request),

):

    out = KEY_STORE.rotate_plain(key_id)

    if not out:

        raise HTTPException(status_code=404, detail="Unknown key_id")

    plain, rec = out

    return {

        "api_key": plain,

        "record": {

            "key_id": rec.key_id,

            "email": rec.email,

            "department": rec.department,

            "created": rec.created,

        },

        "admin": {"username": admin.username},

    }





@app.get("/live")

async def live():

    """Container liveness probe — always 200, no external dependencies checked."""

    from datetime import datetime, timezone as _tz

    return {"status": "ok", "timestamp": datetime.now(_tz.utc).isoformat()}





async def _health_response() -> JSONResponse:

    """Shared logic for /health and /api/health."""

    try:

        async with httpx.AsyncClient(timeout=3) as client:

            r = await client.get(f"{OLLAMA_BASE}/api/tags")

            models = [m["name"] for m in r.json().get("models", [])]

    except Exception as e:

        log.error("Ollama health check failed: %s", e)

        return JSONResponse({"status": "ollama_down", "error": "Ollama unreachable"}, status_code=503)

    return JSONResponse({"status": "ok", "ollama": OLLAMA_BASE, "models": models})





@app.get("/health")

async def health():

    return await _health_response()





@app.get("/api/health")

async def api_health():

    """Public health endpoint — used by the setup wizard and frontend."""

    return await _health_response()


@app.get("/api/ping")
async def ping():
    """Lightweight liveness probe — no auth required, no Ollama dependency."""
    from datetime import datetime, timezone as _tz
    return {"status": "ok", "timestamp": datetime.now(_tz.utc).isoformat()}


@app.get("/api/tags")
async def api_tags_public():
    """Public Ollama model listing — no auth required.

    The brain liveness probe (services/brain_liveness.py) calls this endpoint
    to verify the Ollama backend is reachable and the requested models are
    available.  This route is intentionally unauthenticated so the probe can
    run without an API key.
    """
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as exc:
        log.warning("Public /api/tags — Ollama unreachable: %s", exc)
        return JSONResponse(
            content={"models": []},
            status_code=200,
        )





@app.post("/agent/sessions")

async def create_agent_session(

    body: AgentSessionCreateRequest,

    auth: AuthContext = Depends(verify_api_key),

):

    title = body.title or f"Session for {auth.email}"

    return AGENT_SESSIONS.create(title=title, provider_id=body.provider_id, workspace_id=body.workspace_id)





@app.get("/agent/sessions")

async def list_agent_sessions(auth: AuthContext = Depends(verify_api_key)):

    return {"sessions": AGENT_SESSIONS.list_all()}





@app.get("/agent/sessions/{session_id}")

async def get_agent_session(session_id: str, auth: AuthContext = Depends(verify_api_key)):

    session = AGENT_SESSIONS.get(session_id)

    if session is None:

        raise HTTPException(status_code=404, detail="Unknown session")

    return session





@app.post("/agent/sessions/{session_id}/run")

async def run_agent_task(

    session_id: str,

    body: AgentRunRequest,

    auth: AuthContext = Depends(verify_api_key),

):

    session = AGENT_SESSIONS.get(session_id)

    if session is None:

        raise HTTPException(status_code=404, detail="Unknown session")



    AGENT_SESSIONS.append_message(session_id, "user", body.instruction)

    history = [item.model_dump() for item in (AGENT_SESSIONS.get(session_id) or session).history]

    try:

        provider_id = body.provider_id or session.provider_id

        workspace_id = body.workspace_id or session.workspace_id

        runner = AGENT_RUNNER

        requested_model = body.model

        if provider_id or workspace_id:

            provider_id = provider_id or "prov_local"

            workspace_id = workspace_id or "ws_current"

            secret = WEBUI_PROVIDERS.get_secret(provider_id)

            ws = WEBUI_WORKSPACES.get(workspace_id)

            if not secret:

                raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")

            if not ws:

                raise HTTPException(status_code=404, detail=f"Unknown workspace: {workspace_id}")

            if requested_model is None and provider_id != "prov_local" and secret.default_model:

                requested_model = secret.default_model

            _api_key = secret.api_key or auth.key

            headers = {"Authorization": f"Bearer {_api_key}"} if _api_key else None

            runner = AgentRunner(

                ollama_base=secret.base_url,

                workspace_root=ws.path,

                provider_headers=headers,

                provider_temperature=secret.default_temperature,

                github_token=_GITHUB_TOKEN,

                session_store=AGENT_SESSIONS,

                email=auth.email,

                department=auth.department,

                key_id=auth.key_id,

            )

        result = await runner.run(

            instruction=body.instruction,

            history=history,

            requested_model=requested_model,

            auto_commit=body.auto_commit,

            max_steps=body.max_steps,

            user_id=auth.email,

            department=auth.department,

            key_id=auth.key_id,

            memory_store=USER_MEMORY,

            session_id=session_id,

        )

    except Exception:

        log.exception("Agent run failed")  # nosec B506 — intentional error logging for debugging agents

        result = {

            "goal": body.instruction,

            "plan": None,

            "steps": [],

            "commits": [],

            "summary": "Agent run failed. Check server logs for details.",

            "status": "failed",

        }

    AGENT_SESSIONS.append_message(session_id, "assistant", result["summary"])

    updated = AGENT_SESSIONS.update_result(

        session_id,

        plan=result["plan"] or {"goal": body.instruction, "steps": []},

        result=result,

    )

    return {"session": updated, "result": result}





@app.post("/agent/run")

async def run_agent_once(body: AgentRunRequest, auth: AuthContext = Depends(verify_api_key)):

    temp = AGENT_SESSIONS.create(

        title=f"One-off run for {auth.email}",

        provider_id=body.provider_id,

        workspace_id=body.workspace_id,

    )

    AGENT_SESSIONS.append_message(temp.session_id, "user", body.instruction)

    history = [item.model_dump() for item in (AGENT_SESSIONS.get(temp.session_id) or temp).history]

    try:

        provider_id = body.provider_id

        workspace_id = body.workspace_id

        runner = AGENT_RUNNER

        requested_model = body.model

        if provider_id or workspace_id:

            provider_id = provider_id or "prov_local"

            workspace_id = workspace_id or "ws_current"

            secret = WEBUI_PROVIDERS.get_secret(provider_id)

            ws = WEBUI_WORKSPACES.get(workspace_id)

            if not secret:

                raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")

            if not ws:

                raise HTTPException(status_code=404, detail=f"Unknown workspace: {workspace_id}")

            if requested_model is None and provider_id != "prov_local" and secret.default_model:

                requested_model = secret.default_model

            _api_key = secret.api_key or auth.key

            headers = {"Authorization": f"Bearer {_api_key}"} if _api_key else None

            runner = AgentRunner(

                ollama_base=secret.base_url,

                workspace_root=ws.path,

                provider_headers=headers,

                provider_temperature=secret.default_temperature,

                github_token=_GITHUB_TOKEN,

                session_store=AGENT_SESSIONS,

                email=auth.email,

                department=auth.department,

                key_id=auth.key_id,

            )

        result = await runner.run(

            instruction=body.instruction,

            history=history,

            requested_model=requested_model,

            auto_commit=body.auto_commit,

            max_steps=body.max_steps,

            user_id=auth.email,

            department=auth.department,

            key_id=auth.key_id,

            memory_store=USER_MEMORY,

            session_id=temp.session_id,

        )

    except Exception:

        log.exception("Agent one-off run failed")  # nosec B506 — intentional error logging for debugging agents

        result = {

            "goal": body.instruction,

            "plan": None,

            "steps": [],

            "commits": [],

            "summary": "Agent run failed. Check server logs for details.",

            "status": "failed",

        }

    AGENT_SESSIONS.append_message(temp.session_id, "assistant", result["summary"])

    updated = AGENT_SESSIONS.update_result(

        temp.session_id,

        plan=result["plan"] or {"goal": body.instruction, "steps": []},

        result=result,

    )

    return {"session": updated, "result": result}





# --- FreeBuff: free-NVIDIA coding agent (Telegram phone control) ----------------



class FreeBuffRunRequest(BaseModel):

    """Request body for FreeBuff plan/run endpoints.



    ``model`` must be one of the free NVIDIA NIM models (see GET /freebuff/models);

    anything else is coerced to a free model by ``FreeBuffAgent.resolve_model``.

    """

    instruction: str = Field(..., min_length=1, max_length=8000)

    model: str | None = Field(default=None, max_length=128)

    auto_commit: bool = False

    open_pr: bool = False

    repo_url: str | None = Field(default=None, max_length=512)

    max_steps: int = Field(default=10, ge=1, le=20)





@app.get("/freebuff/models")

async def freebuff_models(auth: AuthContext = Depends(verify_api_key)):

    """List the free NVIDIA NIM models FreeBuff can route to (for model pickers)."""

    return {"models": FreeBuffAgent.available_models()}





@app.post("/freebuff/plan")

async def freebuff_plan(body: FreeBuffRunRequest, auth: AuthContext = Depends(verify_api_key)):

    """Generate a read-only plan with the chosen free model — no files written.



    The Telegram bot shows this plan with Accept/Reject buttons before any code

    is changed. Planning never touches the filesystem, so it is safe to preview.

    """

    agent = FreeBuffAgent(

        model=body.model,

        github_token=_GITHUB_TOKEN,

        email=auth.email,

        department=auth.department,

        key_id=auth.key_id,

    )

    try:

        plan = await agent.plan(

            instruction=body.instruction,

            history=[],

            requested_model=body.model,

            max_steps=body.max_steps,

            user_id=auth.email,

            memory_store=USER_MEMORY,

        )

    except Exception:

        log.exception("FreeBuff plan failed")  # nosec B506 — intentional error logging

        raise HTTPException(status_code=502, detail="FreeBuff planning failed. Check server logs.")

    return {"model": agent.resolve_model(body.model), "plan": plan.model_dump()}





@app.post("/freebuff/run")

async def freebuff_run(body: FreeBuffRunRequest, auth: AuthContext = Depends(verify_api_key)):

    """Execute a FreeBuff task with the chosen free model (optionally commit + PR).



    Mirrors /agent/run but pins routing to free NVIDIA models. When ``open_pr`` is

    set and a repo URL is available the runner's existing auto-push/PR path opens

    a PR (still gated by ``AGENT_AUTO_PR_ENABLED``); commits and PRs are never made

    to protected branches directly.

    """

    temp = AGENT_SESSIONS.create(title=f"FreeBuff run for {auth.email}")

    AGENT_SESSIONS.append_message(temp.session_id, "user", body.instruction)

    history = [item.model_dump() for item in (AGENT_SESSIONS.get(temp.session_id) or temp).history]

    repo_url = body.repo_url or os.environ.get("FREEBUFF_REPO_URL") if body.open_pr else None

    agent = FreeBuffAgent(

        model=body.model,

        github_token=_GITHUB_TOKEN,

        session_store=AGENT_SESSIONS,

        email=auth.email,

        department=auth.department,

        key_id=auth.key_id,

        repo_url=repo_url,

    )

    try:

        result = await agent.run(

            instruction=body.instruction,

            history=history,

            requested_model=body.model,

            auto_commit=body.auto_commit or body.open_pr,

            max_steps=body.max_steps,

            user_id=auth.email,

            department=auth.department,

            key_id=auth.key_id,

            memory_store=USER_MEMORY,

            session_id=temp.session_id,

        )

    except Exception:

        log.exception("FreeBuff run failed")  # nosec B506 — intentional error logging

        result = {

            "goal": body.instruction,

            "plan": None,

            "steps": [],

            "commits": [],

            "summary": "FreeBuff run failed. Check server logs for details.",

            "status": "failed",

        }

    AGENT_SESSIONS.append_message(temp.session_id, "assistant", result["summary"])

    updated = AGENT_SESSIONS.update_result(

        temp.session_id,

        plan=result.get("plan") or {"goal": body.instruction, "steps": []},

        result=result,

    )

    return {"session": updated, "result": result, "model": agent.resolve_model(body.model)}





@app.post("/agent/sessions/{session_id}/rollback-last-commit")

async def rollback_agent_commit(session_id: str, auth: AuthContext = Depends(verify_api_key)):

    session = AGENT_SESSIONS.get(session_id)

    if session is None:

        raise HTTPException(status_code=404, detail="Unknown session")

    last_result = session.last_result or {}

    commits = last_result.get("commits") or []

    if not commits:

        raise HTTPException(status_code=400, detail="No agent commit available to roll back")

    target = commits[-1]

    cwd = Path(__file__).resolve().parent

    if session.workspace_id:

        ws = WEBUI_WORKSPACES.get(session.workspace_id)

        if ws:

            cwd = Path(ws.path)

    try:

        proc = subprocess.run(

            ["git", "revert", "--no-edit", target],

            cwd=cwd,

            check=True,

            capture_output=True,

            text=True,

        )

    except subprocess.CalledProcessError:

        raise HTTPException(

            status_code=500,

            detail="git revert failed. Check server logs for details.",

        )

    AGENT_SESSIONS.append_message(session_id, "system", f"Rolled back commit {target}")

    return {"status": "ok", "reverted_commit": target, "git_output": proc.stdout.strip()}



# --- Session Memory -----------------------------------------------------------



@app.post("/agent/memory/{session_id}/snapshot")

async def memory_snapshot(session_id: str, auth: AuthContext = Depends(verify_api_key)):

    session = AGENT_SESSIONS.get(session_id)

    if session is None:

        raise HTTPException(status_code=404, detail="Unknown session")

    state = session.model_dump()

    path = SESSION_MEMORY.snapshot(session_id, state)

    return {"session_id": session_id, "path": str(path)}





@app.get("/agent/memory/{session_id}")

async def memory_restore(session_id: str, auth: AuthContext = Depends(verify_api_key)):

    state = SESSION_MEMORY.restore(session_id)

    if state is None:

        raise HTTPException(status_code=404, detail="No snapshot for this session")

    return state





@app.get("/agent/memory")

async def memory_list(auth: AuthContext = Depends(verify_api_key)):

    return {"snapshots": SESSION_MEMORY.list_snapshots()}





@app.delete("/agent/memory/{session_id}")

async def memory_delete(session_id: str, auth: AuthContext = Depends(verify_api_key)):

    deleted = SESSION_MEMORY.delete(session_id)

    return {"deleted": deleted}





# --- Context Compression ------------------------------------------------------



class ContextCompressRequest(BaseModel):

    messages: list[dict] = Field(..., min_length=1)

    strategy: str = Field(default="reactive", pattern="^(reactive|micro|inspect)$")





@app.post("/agent/context/compress")

async def context_compress(body: ContextCompressRequest, auth: AuthContext = Depends(verify_api_key)):

    compressed = CTX_COMPRESSOR.compress(body.messages, strategy=body.strategy)  # type: ignore[arg-type]

    stats = CTX_COMPRESSOR.inspect(compressed)

    return {"messages": compressed, "stats": stats.as_dict()}





@app.post("/agent/context/inspect")

async def context_inspect(body: ContextCompressRequest, auth: AuthContext = Depends(verify_api_key)):

    stats = CTX_COMPRESSOR.inspect(body.messages)

    needs = CTX_COMPRESSOR.needs_compression(body.messages)

    return {"stats": stats.as_dict(), "needs_compression": needs}





# --- Conversation Surgery -----------------------------------------------------



class HistorySnipRequest(BaseModel):

    indices: list[int] = Field(..., min_length=1)





@app.post("/agent/sessions/{session_id}/snip")

async def history_snip(

    session_id: str,

    body: HistorySnipRequest,

    auth: AuthContext = Depends(verify_api_key),

):

    """Remove specific messages from session history by index."""

    session = AGENT_SESSIONS.get(session_id)

    if session is None:

        raise HTTPException(status_code=404, detail="Unknown session")

    removed, remaining = AGENT_SESSIONS.snip_history(session_id, set(body.indices))

    return {"removed": removed, "remaining": remaining}





# --- Adaptive Permissions -----------------------------------------------------



@app.get("/agent/sessions/{session_id}/permissions")

async def session_permissions(session_id: str, auth: AuthContext = Depends(verify_api_key)):

    session = AGENT_SESSIONS.get(session_id)

    if session is None:

        raise HTTPException(status_code=404, detail="Unknown session")

    msgs = [m.model_dump() for m in session.history]

    assessment = PERMISSIONS.assess(msgs)

    return assessment.as_dict()





# --- Token Budget -------------------------------------------------------------



class BudgetSetRequest(BaseModel):

    cap: int = Field(..., ge=1)





@app.put("/agent/budget/{session_id}")

async def budget_set(session_id: str, body: BudgetSetRequest, auth: AuthContext = Depends(verify_api_key)):

    usage = TOKEN_BUDGET.set_cap(session_id, body.cap)

    return usage.as_dict()





@app.get("/agent/budget/{session_id}")

async def budget_get(session_id: str, auth: AuthContext = Depends(verify_api_key)):

    usage = TOKEN_BUDGET.get(session_id)

    if usage is None:

        raise HTTPException(status_code=404, detail="No budget set for this session")

    return usage.as_dict()





@app.get("/agent/budget")

async def budget_list(auth: AuthContext = Depends(verify_api_key)):

    return {"budgets": [u.as_dict() for u in TOKEN_BUDGET.list_all()]}




@app.post("/agent/budget/reset")

async def budget_reset_daily(auth: AuthContext = Depends(verify_api_key)):

    """Reset all session token counters for a new day (caps preserved).

    Mirrors the rollout-budget reset-credits model used by modern agent
    orchestrators: at the start of a new billing/quota day, call this endpoint
    to reclaim each session's full daily token allocation without losing the
    configured cap.
    """

    count = TOKEN_BUDGET.reset_daily()

    return {"sessions_reset": count, "message": f"Daily budget reset: {count} sessions cleared"}





# --- Multi-Agent Coordinator --------------------------------------------------



class CoordinateRequest(BaseModel):

    goal: str = Field(..., min_length=1, max_length=2000)

    # Legacy format: flat list of worker dicts with {instruction, ...}

    workers: list[dict] | None = Field(default=None, max_length=20)

    # New format: separate agent pool + dependency-aware task list

    agents: list[dict] | None = Field(default=None, max_length=20)

    tasks: list[dict] | None = Field(default=None, max_length=50)

    max_concurrent: int = Field(default=3, ge=1, le=10)





@app.post("/agent/coordinate")

async def coordinate(body: CoordinateRequest, auth: AuthContext = Depends(verify_api_key)):

    # New agents+tasks format — resolve dependencies then delegate to coordinator

    if body.tasks is not None:

        task_ids = {t["task_id"] for t in body.tasks if "task_id" in t}

        workers_out = []

        runnable = []

        for task in body.tasks:

            deps = task.get("dependencies", [])

            missing = [d for d in deps if d not in task_ids]

            if missing:

                workers_out.append({

                    "worker_id": task.get("task_id", "unknown"),

                    "status": "blocked",

                    "error": f"Missing dependencies: {', '.join(missing)}",

                })

            else:

                runnable.append(task)



        if runnable:

            specs = [

                WorkerSpec(

                    worker_id=t.get("task_id", f"t{i}"),

                    instruction=t["instruction"],

                    model=t.get("model"),

                    max_steps=int(t.get("max_steps", 3)),

                )

                for i, t in enumerate(runnable)

            ]

            result = await COORDINATOR.run(

                body.goal, specs, max_concurrent=body.max_concurrent,

                email=auth.email, department=auth.department, key_id=auth.key_id

            )

            base = result.as_dict()

            base["workers"] = base.get("workers", []) + workers_out

            return base



        return {"goal": body.goal, "workers": workers_out}



    # Legacy workers format

    if not body.workers:

        raise HTTPException(status_code=422, detail="Either 'workers' or 'tasks' must be provided")

    specs = [

        WorkerSpec(

            worker_id=w.get("worker_id", f"w{i}"),

            instruction=w["instruction"],

            model=w.get("model"),

            max_steps=int(w.get("max_steps", 3)),

        )

        for i, w in enumerate(body.workers)

    ]

    result = await COORDINATOR.run(

        body.goal, specs, max_concurrent=body.max_concurrent,

        email=auth.email, department=auth.department, key_id=auth.key_id

    )

    return result.as_dict()





# --- Background Agent ---------------------------------------------------------



class BackgroundTaskRequest(BaseModel):

    kind: str = Field(default="manual", max_length=64)

    payload: dict = Field(default_factory=dict)





@app.post("/agent/background/tasks")

async def background_submit(body: BackgroundTaskRequest, auth: AuthContext = Depends(verify_api_key)):

    task = BACKGROUND_AGENT.create_and_submit(kind=body.kind, payload=body.payload)

    return task.as_dict()





@app.get("/agent/background/tasks")

async def background_list(

    status: str | None = None,

    auth: AuthContext = Depends(verify_api_key),

):

    tasks = BACKGROUND_AGENT.list_tasks(status=status)

    return {"tasks": [t.as_dict() for t in tasks]}





@app.get("/agent/background/tasks/{task_id}")

async def background_get(task_id: str, auth: AuthContext = Depends(verify_api_key)):

    task = BACKGROUND_AGENT.get_task(task_id)

    if task is None:

        raise HTTPException(status_code=404, detail="Task not found")

    return task.as_dict()





# --- Scheduled Jobs -----------------------------------------------------------



class ScheduleJobRequest(BaseModel):

    name: str = Field(..., min_length=1, max_length=200)

    cron: str = Field(..., min_length=9, max_length=100)

    instruction: str = Field(..., min_length=1, max_length=4000)





@app.post("/agent/scheduler/jobs")

async def scheduler_create(body: ScheduleJobRequest, auth: AuthContext = Depends(verify_api_key)):

    job = SCHEDULER.create(name=body.name, cron=body.cron, instruction=body.instruction)

    return job.as_dict()





@app.get("/agent/scheduler/jobs")

async def scheduler_list(auth: AuthContext = Depends(verify_api_key)):

    return {"jobs": [j.as_dict() for j in SCHEDULER.list()]}





@app.get("/agent/scheduler/jobs/{job_id}")

async def scheduler_get(job_id: str, auth: AuthContext = Depends(verify_api_key)):

    job = SCHEDULER.get(job_id)

    if job is None:

        raise HTTPException(status_code=404, detail="Job not found")

    return job.as_dict()





@app.post("/agent/scheduler/jobs/{job_id}/trigger")

async def scheduler_trigger(job_id: str, auth: AuthContext = Depends(verify_api_key)):

    try:

        job = SCHEDULER.trigger(job_id)

    except KeyError:

        raise HTTPException(status_code=404, detail="Job not found")

    return job.as_dict()





@app.delete("/agent/scheduler/jobs/{job_id}")

async def scheduler_delete(job_id: str, auth: AuthContext = Depends(verify_api_key)):

    deleted = SCHEDULER.delete(job_id)

    return {"deleted": deleted}





# --- Automation Playbooks -----------------------------------------------------



class PlaybookRegisterRequest(BaseModel):

    name: str = Field(..., min_length=1, max_length=200)

    description: str = Field(default="", max_length=1000)

    steps: list[dict] = Field(..., min_length=1, max_length=20)

    tags: list[str] = Field(default_factory=list)





@app.post("/agent/playbooks")

async def playbook_register(body: PlaybookRegisterRequest, auth: AuthContext = Depends(verify_api_key)):

    pb = PLAYBOOKS.register(

        name=body.name,

        description=body.description,

        steps=body.steps,

        tags=body.tags,

    )

    return pb.as_dict()





@app.get("/agent/playbooks")

async def playbook_list(tag: str | None = None, auth: AuthContext = Depends(verify_api_key)):

    return {"playbooks": [p.as_dict() for p in PLAYBOOKS.list(tag=tag)]}





@app.get("/agent/playbooks/{playbook_id}")

async def playbook_get(playbook_id: str, auth: AuthContext = Depends(verify_api_key)):

    pb = PLAYBOOKS.get(playbook_id)

    if pb is None:

        raise HTTPException(status_code=404, detail="Playbook not found")

    return pb.as_dict()





@app.delete("/agent/playbooks/{playbook_id}")

async def playbook_delete(playbook_id: str, auth: AuthContext = Depends(verify_api_key)):

    deleted = PLAYBOOKS.delete(playbook_id)

    return {"deleted": deleted}





@app.post("/agent/playbooks/{playbook_id}/run")

async def playbook_run(playbook_id: str, auth: AuthContext = Depends(verify_api_key)):

    try:

        run = PLAYBOOKS.start_run(playbook_id)

    except KeyError:

        raise HTTPException(status_code=404, detail="Playbook not found")

    return run.as_dict()





@app.get("/agent/playbooks/{playbook_id}/runs")

async def playbook_runs(playbook_id: str, auth: AuthContext = Depends(verify_api_key)):

    return {"runs": [r.as_dict() for r in PLAYBOOKS.list_runs(playbook_id=playbook_id)]}





# --- Resource Watchdog --------------------------------------------------------



class WatchRequest(BaseModel):

    name: str = Field(..., min_length=1, max_length=200)

    kind: str = Field(..., pattern="^(url|file)$")

    target: str = Field(..., min_length=1, max_length=2000)

    action: str = Field(default="", max_length=500)





@app.post("/agent/watchdog/resources")

async def watchdog_add(body: WatchRequest, auth: AuthContext = Depends(verify_api_key)):

    resource = WATCHDOG.watch(name=body.name, kind=body.kind, target=body.target, action=body.action)

    return resource.as_dict()





@app.get("/agent/watchdog/resources")

async def watchdog_list(auth: AuthContext = Depends(verify_api_key)):

    return {"resources": [r.as_dict() for r in WATCHDOG.list()]}





@app.delete("/agent/watchdog/resources/{resource_id}")

async def watchdog_remove(resource_id: str, auth: AuthContext = Depends(verify_api_key)):

    removed = WATCHDOG.unwatch(resource_id)

    return {"removed": removed}





@app.post("/agent/watchdog/resources/{resource_id}/check")

async def watchdog_check(resource_id: str, auth: AuthContext = Depends(verify_api_key)):

    event = WATCHDOG.check_once(resource_id)

    return {"changed": event is not None, "event": event.as_dict() if event else None}





# --- Project Scaffolding ------------------------------------------------------



class ScaffoldRequest(BaseModel):

    template: str = Field(..., min_length=1, max_length=200)

    target_dir: str = Field(..., min_length=1, max_length=500)

    overwrite: bool = False





@app.get("/agent/scaffolding/templates")

async def scaffolding_list(auth: AuthContext = Depends(verify_api_key)):

    return {"templates": [t.as_dict() for t in SCAFFOLDER.list()]}





@app.post("/agent/scaffolding/apply")

async def scaffolding_apply(body: ScaffoldRequest, auth: AuthContext = Depends(verify_api_key)):

    result = SCAFFOLDER.apply(body.template, body.target_dir, overwrite=body.overwrite)

    return result.as_dict()





# --- Skill Registry Refresh -----------------------------------------------



class SkillsRefreshRequest(BaseModel):

    force: bool = Field(default=False, description="Bypass 1-hour TTL and force-refresh")





@app.post("/agent/skills/refresh")

async def skills_refresh(

    body: SkillsRefreshRequest,

    auth: AuthContext = Depends(verify_api_key),

):

    """Manually trigger a skill registry refresh from all GitHub registries.



    Use force=true to bypass the 1-hour TTL and always hit the GitHub API.

    Returns the count of new skills added.

    """

    try:

        from agent.skill_registry import get_skill_registry_safe

        sr = get_skill_registry_safe()

        if sr is None:

            return JSONResponse(

                {"error": "SkillRegistry not initialised"},

                status_code=503,

            )

        if body.force:

            added = await sr.refresh_remote_force()

        else:

            added = await sr.refresh_remote()

        return {

            "ok": True,

            "added": added,

            "total": len(sr.list()),

            "forced": body.force,

        }

    except Exception:

        log.exception("Skill registry refresh failed")

        return JSONResponse(

            {"error": "Skill registry refresh failed"},

            status_code=500,

        )





# --- Skill Library ------------------------------------------------------------



class MpcSkillRequest(BaseModel):

    name: str = Field(..., min_length=1, max_length=200)

    description: str = Field(default="", max_length=1000)

    content: str = Field(default="", max_length=50000)

    tags: list[str] = Field(default_factory=list)





@app.get("/agent/skills")

async def skills_list(source: str | None = None, auth: AuthContext = Depends(verify_api_key)):

    return {"skills": [s.as_dict() for s in SKILL_LIBRARY.list(source=source)]}





@app.get("/agent/skills/search")

async def skills_search(q: str, auth: AuthContext = Depends(verify_api_key)):

    return {"skills": [s.as_dict() for s in SKILL_LIBRARY.search(q)]}





@app.post("/agent/skills/mcp")

async def skills_register_mcp(body: MpcSkillRequest, auth: AuthContext = Depends(verify_api_key)):

    skill = SKILL_LIBRARY.register_mcp(

        name=body.name,

        description=body.description,

        content=body.content,

        tags=body.tags,

    )

    return skill.as_dict()





# --- AI Commit Tracking -------------------------------------------------------



@app.get("/agent/commits")

async def commit_log(limit: int = 10, auth: AuthContext = Depends(verify_api_key)):

    entries = COMMIT_TRACKER.log(limit=min(limit, 100))

    return {"commits": entries}





# --- Terminal Panel -----------------------------------------------------------



@app.get("/agent/terminal/snapshot")

async def terminal_snapshot(auth: AuthContext = Depends(verify_api_key)):

    snap = TERMINAL_PANEL.snapshot()

    return snap.as_dict()





class TerminalRunRequest(BaseModel):

    command: list[str] = Field(..., min_length=1, max_length=20)

    timeout: int = Field(default=30, ge=1, le=120)





@app.post("/agent/terminal/run")

async def terminal_run(body: TerminalRunRequest, auth: AuthContext = Depends(verify_api_key)):

    return TERMINAL_PANEL.run_and_capture(body.command, timeout=body.timeout)





# --- Browser Automation -------------------------------------------------------



class BrowserActionRequest(BaseModel):

    action: str = Field(..., pattern="^(navigate|click|fill|screenshot|evaluate|get_state)$")

    url: str | None = None

    selector: str | None = None

    value: str | None = None

    path: str | None = None

    expression: str | None = None





@app.post("/agent/browser/action")

async def browser_action(body: BrowserActionRequest, auth: AuthContext = Depends(verify_api_key)):

    if not BROWSER_SESSION.available:

        return {"available": False, "hint": "pip install playwright && playwright install chromium"}

    if body.action == "navigate" and body.url:

        result = await BROWSER_SESSION.navigate(body.url)

    elif body.action == "click" and body.selector:

        result = await BROWSER_SESSION.click(body.selector)

    elif body.action == "fill" and body.selector and body.value is not None:

        result = await BROWSER_SESSION.fill(body.selector, body.value)

    elif body.action == "screenshot" and body.path:

        result = await BROWSER_SESSION.screenshot(body.path)

    elif body.action == "evaluate" and body.expression:

        result = await BROWSER_SESSION.evaluate(body.expression)

    elif body.action == "get_state":

        state = await BROWSER_SESSION.get_state()

        return state.as_dict() if state else {"url": None, "title": None, "content_preview": ""}

    else:

        raise HTTPException(status_code=400, detail="Invalid action or missing required parameters")

    return result.as_dict()





@app.post("/agent/browser/start")

async def browser_start(auth: AuthContext = Depends(verify_api_key)):

    await BROWSER_SESSION.start()

    return {"started": True, "available": BROWSER_SESSION.available}





@app.post("/agent/browser/stop")

async def browser_stop(auth: AuthContext = Depends(verify_api_key)):

    await BROWSER_SESSION.stop()

    return {"stopped": True}





# --- Voice Commands -----------------------------------------------------------



class VoiceTranscribeRequest(BaseModel):

    audio_b64: str = Field(..., description="Base64-encoded raw PCM audio bytes")

    duration_hint_s: float = Field(default=5.0, ge=0.1, le=60.0)





@app.get("/agent/voice/status")

async def voice_status(auth: AuthContext = Depends(verify_api_key)):

    return {

        "mic_available": VOICE_INTERFACE.mic_available,

        "whisper_url": bool(VOICE_INTERFACE._whisper_url),

    }





@app.post("/agent/voice/transcribe")

async def voice_transcribe(body: VoiceTranscribeRequest, auth: AuthContext = Depends(verify_api_key)):

    import base64

    try:

        audio_bytes = base64.b64decode(body.audio_b64)

    except Exception:

        raise HTTPException(status_code=400, detail="Invalid base64 audio data")
    result = VOICE_INTERFACE.transcribe(audio_bytes)
    return result.as_dict()


# ── SAM Voice Agent endpoints ───────────────────────────────────────────────

SAM_AGENT: "SamAgent | None" = None


def _init_sam() -> "SamAgent":
    global SAM_AGENT
    if SAM_AGENT is None:
        SAM_AGENT = get_sam()
        log.info("SAM voice agent initialised")
    return SAM_AGENT


class SamChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="Transcribed voice command")
    session_id: str = Field(default="default", max_length=64)


class SamSpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="Text to synthesise as SAM's voice")



@app.get("/agent/sam/status")
async def sam_status(auth: AuthContext = Depends(verify_api_key)):
    """Get SAM's current status."""
    sam = _init_sam()
    return {
        "available": True,
        "name": "SAM",
        "description": "System Autonomy Manager — voice-controlled agency interface",
        **sam.get_status(),
    }


@app.post("/agent/sam/chat")
async def sam_chat(body: SamChatRequest, auth: AuthContext = Depends(verify_api_key)):
    """Send a voice command to SAM and get a spoken response.

    The frontend records audio, transcribes it, and sends the text here.
    SAM processes it through the agency CEO (NVIDIA NIM, free tier) and
    returns a concise, voice-friendly response.
    """
    sam = _init_sam()
    response_text = await sam.process_command(body.text, session_id=body.session_id)
    return {
        "text": response_text,
        "session_id": body.session_id,
    }


@app.post("/agent/sam/speak")
async def sam_speak(body: SamSpeakRequest, auth: AuthContext = Depends(verify_api_key)):
    """Synthesise SAM's response as audio (OGG Opus, Telegram-compatible).

    Uses gTTS (Google Text-to-Speech, free) via the voice/tts.py pipeline.
    Returns base64-encoded OGG audio for browser playback.
    """
    import base64
    try:
        from voice.tts import synthesize
        audio_bytes = await synthesize(body.text)
        if audio_bytes:
            return {
                "audio_b64": base64.b64encode(audio_bytes).decode(),
                "format": "ogg",
                "duration_s": round(len(audio_bytes) / 4000, 1),  # rough estimate
            }
        return {"audio_b64": "", "error": "TTS synthesis returned empty"}
    except Exception as exc:
        log.warning("SAM TTS failed: %s", exc)
        return {"audio_b64": "", "error": str(exc)}

@app.get("/api/auth/me")
async def auth_me_proxy(auth: AuthContext = Depends(verify_api_key)):
    """Return the current user's profile from the API key context.

    Mirrors backend/server.py's /api/auth/me so that API key users on the
    proxy port (8000) can also verify their tokens. The frontend AuthContext
    calls this after login to hydrate the user object.

    For API key auth, the 'user' identity is derived from the key metadata:
    email, department, and key_id. No password or DB lookup required.
    """
    return {
        "_id": auth.email,
        "id": auth.email,
        "email": auth.email,
        "name": auth.email.split("@")[0] if "@" in auth.email else auth.email,
        "role": "user",
        "department": auth.department,
        "key_id": auth.key_id,
        "source": auth.source,
    }


# --- Streaming proxy helper -----------------------------------------------------



async def stream_response(url: str, method: str, headers: dict, body: bytes) -> AsyncIterator[bytes]:

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:

        async with client.stream(method, url, content=body, headers=headers) as resp:

            if resp.status_code >= 400:

                content = await resp.aread()

                yield content

                return

            async for chunk in resp.aiter_bytes(chunk_size=512):

                yield chunk



async def proxy_request(request: Request, target_path: str, auth: AuthContext | None = None):

    body = await request.body()

    content_type = request.headers.get("content-type", "application/json")



    # Determine if client wants streaming

    is_stream = False

    if body:

        try:

            payload = json.loads(body)

            is_stream = bool(payload.get("stream", False))

        except (json.JSONDecodeError, AttributeError):

            pass



    target_url = f"{OLLAMA_BASE}/{target_path}"

    forward_headers = {"Content-Type": content_type}



    log.info("→ %s %s (stream=%s)", request.method, target_path, is_stream)

    start_time = time.perf_counter()



    if is_stream:

        return StreamingResponse(

            stream_response(target_url, request.method, forward_headers, body),

            media_type="text/event-stream",

            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},

        )

    else:

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:

            resp = await client.request(

                method=request.method,

                url=target_url,

                content=body,

                headers=forward_headers,

            )

        

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        is_json = resp.headers.get("content-type", "").startswith("application/json")

        data = resp.json() if is_json else resp.text



        # Track legacy generation/completion usage

        if auth and target_path in ("api/generate", "v1/completions") and request.method == "POST":

            try:

                payload = json.loads(body)

                model = payload.get("model", "unknown")

                prompt = payload.get("prompt", "")

                

                out_text = ""

                pt = 0

                ct = 0

                

                if target_path == "api/generate" and isinstance(data, dict):

                    out_text = data.get("response", "")

                    pt = int(data.get("prompt_eval_count") or 0)

                    ct = int(data.get("eval_count") or 0)

                elif target_path == "v1/completions" and isinstance(data, dict):

                    choices = data.get("choices", [])

                    if choices and isinstance(choices[0], dict):

                        out_text = choices[0].get("text", "")

                    usage = data.get("usage", {})

                    pt = int(usage.get("prompt_tokens") or 0)

                    ct = int(usage.get("completion_tokens") or 0)

                

                if out_text:

                    await asyncio.to_thread(

                        emit_chat_observation,

                        email=auth.email,

                        department=auth.department,

                        key_id=auth.key_id,

                        model=model,

                        messages=[{"role": "user", "content": prompt}] if isinstance(prompt, str) else prompt,

                        output_text=out_text,

                        prompt_tokens=pt,

                        completion_tokens=ct,

                        latency_ms=duration_ms,

                        task_name="generation",

                    )

            except Exception as exc:

                log.debug("Trackable proxy observation failed: %s", exc)



        if not is_json:

            from fastapi.responses import Response as _Response

            return _Response(content=data, status_code=resp.status_code, media_type=resp.headers.get("content-type", "text/plain"))

        return JSONResponse(

            content=data,

            status_code=resp.status_code,

        )



# --- Anthropic Messages API (/v1/messages) -------------------------------------

# Enables Claude Code CLI (set ANTHROPIC_BASE_URL=https://your-tunnel-url)



@app.post("/v1/messages")

async def anthropic_messages(request: Request, auth: AuthContext = Depends(verify_api_key)):

    """Anthropic Messages API — translates to Ollama OpenAI-compat internally."""

    return await handle_anthropic_messages(

        request=request,

        ollama_base=OLLAMA_BASE,

        email=auth.email,

        department=auth.department,

        key_id=auth.key_id,

    )





class _CountTokensRequest(BaseModel):

    model: str = Field(..., min_length=1, max_length=200)

    messages: list[dict] = Field(default_factory=list)

    system: str | None = None

    tools: list[dict] | None = None





@app.post("/v1/messages/count_tokens")

async def count_tokens(request: Request, auth: AuthContext = Depends(verify_api_key)):

    """Lightweight token estimation — no model call required.



    Returns Anthropic-compatible {input_tokens: N} with anthropic-version header.

    Uses a 4-chars-per-token heuristic plus fixed costs for images and tools.

    """

    try:

        raw = await request.json()

    except Exception:

        raise HTTPException(status_code=400, detail="Invalid JSON body")



    from handlers.anthropic_compat import _estimate_tokens_for_messages

    messages = raw.get("messages", [])

    system = raw.get("system")

    tools = raw.get("tools")

    if not isinstance(messages, list):

        raise HTTPException(status_code=400, detail="'messages' must be a list")

    n = _estimate_tokens_for_messages(messages, system, tools=tools)

    return JSONResponse(

        content={"input_tokens": n},

        headers={"anthropic-version": "2023-06-01"},

    )





@app.get("/v1/models")

async def list_models_openai(auth: AuthContext = Depends(verify_api_key)):

    """List available models — union of live Ollama models, router registry, and Claude aliases.



    Claude aliases (e.g. claude-sonnet-4-6) are included so that Claude Code and

    other Anthropic SDK clients can discover and select them without manual config.

    """

    from router.model_router import _get_model_map

    from router.registry import get_registry

    try:

        async with httpx.AsyncClient(timeout=5) as client:

            r = await client.get(f"{OLLAMA_BASE}/api/tags")

        ollama_models = [m["name"] for m in r.json().get("models", [])]

    except Exception:

        ollama_models = []



    registry = get_registry()

    ollama_set = set(ollama_models)



    # Models known to Ollama

    local_entries = [

        {"id": name, "object": "model", "owned_by": "ollama"}

        for name in ollama_models

    ]

    # Registry models not already reported by Ollama (e.g. not yet pulled)

    registry_only = [

        {"id": name, "object": "model", "owned_by": "router-registry"}

        for name in registry

        if name not in ollama_set

    ]

    # Claude/Anthropic model aliases from MODEL_MAP — lets Claude Code and

    # Anthropic SDK clients discover which model names this proxy accepts.

    alias_set = set(m["id"] for m in local_entries + registry_only)

    alias_entries = [

        {"id": alias, "object": "model", "owned_by": "autonomous-ai-agency-alias", "description": f"Alias → {_get_model_map().get(alias, alias)}"}

        for alias in _get_model_map()

        if alias not in alias_set

    ]

    return {"object": "list", "data": local_entries + registry_only + alias_entries}





# --- Quick Notes API (/v1/quick-notes) ----------------------------------------

# iPhone Shortcut → POST /v1/quick-notes → queue → processor → git push

# Also creates GitHub issues when GitHub token is configured so the

# process-quick-note workflow can pick them up for full implement→PR→merge.



class QuickNoteRequest(BaseModel):

    url: str = Field(..., min_length=5, max_length=4000)

    instruction: str = Field(default="", max_length=2000)





@app.post("/v1/quick-notes")

async def quick_notes_submit(

    body: QuickNoteRequest,

    request: Request,

    auth: AuthContext = Depends(verify_api_key),

):

    """Submit a quick-note URL or instruction from iPhone Shortcut or FAB.



    When GitHub is configured (GH_TOKEN or GITHUB_TOKEN env var), creates a

    GitHub issue with the quick-note label so the process-quick-note workflow

    picks it up.  Otherwise queues it in the local QuickNoteQueue.

    """

    url = body.url.strip()

    instruction = body.instruction.strip()



    # Try GitHub issue creation first (process-quick-note workflow picks these up)

    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN", "")

    gh_repo = os.environ.get("GITHUB_REPOSITORY", "")



    title = f"quick-note: {url[:80]}"

    issue_body_parts = [url]

    if instruction:

        issue_body_parts.append(f"\nTask: {instruction}")

    issue_body = "\n".join(issue_body_parts)



    if gh_token and gh_repo:

        try:

            async with httpx.AsyncClient(timeout=15) as client:

                resp = await client.post(

                    f"https://api.github.com/repos/{gh_repo}/issues",

                    json={

                        "title": title,

                        "body": issue_body,

                        "labels": ["quick-note"],

                    },

                    headers={

                        "Authorization": f"Bearer {gh_token}",

                        "Accept": "application/vnd.github+json",

                    },

                )

            if resp.status_code == 201:

                issue_data = resp.json()

                issue_number = issue_data["number"]

                log.info(

                    "Quick-note → GitHub issue #%d created: %s",

                    issue_number, url,

                )

                return {

                    "status": "created",

                    "channel": "github",

                    "issue_number": issue_number,

                    "issue_url": issue_data.get("html_url", ""),

                }

            else:

                log.warning(

                    "Quick-note GitHub issue creation failed (%d): %s",

                    resp.status_code, resp.text[:200],

                )

        except Exception as exc:

            log.warning("Quick-note GitHub issue creation error: %s", exc)



    # Fallback: queue locally

    note = QUICK_NOTE_QUEUE.add(url)

    log.info("Quick-note queued locally: %s → %s", note.note_id, url)

    return {

        "status": "queued",

        "channel": "local",

        "note_id": note.note_id,

        "hint": (

            "GitHub not configured — set GH_TOKEN / GH_PAT to enable the full "

            "implement→PR→review→merge pipeline."

        ),

    }





@app.get("/v1/quick-notes")

async def quick_notes_list(auth: AuthContext = Depends(verify_api_key)):

    """List queued quick-notes (local queue only)."""

    notes = QUICK_NOTE_QUEUE.list_all()

    return {"notes": [n.as_dict() for n in notes], "count": len(notes)}





# --- Agency Status -----------------------------------------------------------



@app.get("/agent/agency/status")

async def agency_status(auth: AuthContext = Depends(verify_api_key)):

    """Get CEO Agency status for the AlertsBell and Doctor dashboards."""

    try:

        from agent.agency import get_agency

        agency = get_agency()

        if agency is None:

            return {"running": False, "reason": "Agency not initialised"}

        status = agency.get_status()

        # Add recent directives as alerts

        alerts: list[dict] = []

        for d in agency._directives[-10:]:

            alerts.append({

                "id": d.directive_id,

                "title": d.title,

                "role": d.role.value,

                "status": d.status,

                "issued_at": d.issued_at,

                "priority": d.priority,

            })

        status["alerts"] = alerts

        return status

    except Exception:

        log.exception("Agency status check failed")

        return {"running": False, "error": "Agency status unavailable"}





# --- Doctor Diagnostics (Golden Path #10) -----------------------------------



@app.get("/api/diagnostics/status")

async def diagnostics_status():

    """Public health check — no auth required. Returns basic Ollama reachability."""

    return run_public_status()





@app.get("/api/diagnostics/health")

async def diagnostics_health():

    """Public quick health check — all services running? No auth required."""

    from handlers.diagnostics import check_ollama_async

    ollama_base = os.environ.get("OLLAMA_BASE", "http://localhost:11434")

    ollama_status = await check_ollama_async(ollama_base)

    healthy = ollama_status.get("reachable", False)

    return {"healthy": healthy, "ollama": ollama_status}





@app.get("/api/diagnostics/deep")

async def diagnostics_deep(auth: AuthContext = Depends(verify_api_key)):

    """Full system scan — requires authentication. Exposes DB, sessions, cooldowns."""

    return await run_deep_diagnostics()





@app.get("/api/diagnostics/fixes")

async def diagnostics_fixes_list(auth: AuthContext = Depends(verify_api_key)):

    """List all available one-click fixes — requires authentication."""

    return {"fixes": list_available_fixes()}





# --- Trend Analysis (issue #493 — last30days-style window) ------------------



@app.get("/api/trends")

async def get_trends(auth: AuthContext = Depends(verify_api_key)):

    """Run a 30-day trend analysis and return the typed report — requires auth.



    Backed by agent.trend_watcher (13 public sources, zero-config) and

    persisted to trends/trend_summary.md for the admin dashboard.

    """

    from trend_analysis import run_trend_analysis

    try:

        report = await run_trend_analysis()

        return report.model_dump()

    except Exception:

        log.exception("Trend analysis failed")

        return {"error": "Trend analysis failed — see server logs"}





from pydantic import BaseModel





class DiagnosticsFixRequest(BaseModel):

    """Request body for /api/diagnostics/fix."""

    fix_name: str





@app.post("/api/diagnostics/fix")

async def diagnostics_fix(req: DiagnosticsFixRequest, auth: AuthContext = Depends(verify_api_key)):

    """Attempt a named one-click fix — requires authentication. Runs privileged ops."""

    result = run_fix(req.fix_name)

    if "error" in result:

        return JSONResponse(status_code=400, content=result)

    return result





@app.get("/api/diagnostics/kpi")

async def diagnostics_kpi(auth: AuthContext = Depends(verify_api_key)):

    """Autonomy KPIs snapshot — requires authentication."""

    from agent.kpi import get_tracker

    return get_tracker().snapshot().as_dict()





# --- Features API router -----------------------------------------------------

app.include_router(features_router)



# --- Direct-chat router (JWT-authenticated; must be registered before Ollama catch-all) --

# These routes use their own JWT-based auth and must be registered before the

# /api/{path:path} catch-all so they are matched first.

app.include_router(direct_chat_router)

# Expose PROVIDER_ROUTER and webui_workspaces on app.state so direct_chat can read them.

app.state.PROVIDER_ROUTER = WEBUI_PROVIDERS  # type: ignore[attr-defined]

app.state.webui_workspaces = WEBUI_WORKSPACES  # type: ignore[attr-defined]





# --- Ollama native routes (/api/*) ---------------------------------------------



@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])

async def ollama_api(path: str, request: Request, auth: AuthContext = Depends(verify_api_key)):

    if path == "chat" and request.method == "POST":

        return await handle_ollama_native_chat(

            request=request,

            ollama_base=OLLAMA_BASE,

            email=auth.email,

            department=auth.department,

            key_id=auth.key_id,

        )

    return await proxy_request(request, f"api/{path}", auth=auth)



# --- OpenAI-compatible routes (/v1/*) ------------------------------------------

# Ollama natively serves OpenAI-compatible endpoints at /v1/*



@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])

async def openai_compat(path: str, request: Request, auth: AuthContext = Depends(verify_api_key)):

    if path == "chat/completions" and request.method == "POST":

        return await handle_openai_chat_completions(

            request=request,

            ollama_base=OLLAMA_BASE,

            email=auth.email,

            department=auth.department,

            key_id=auth.key_id,

        )

    return await proxy_request(request, f"v1/{path}", auth=auth)



# --- /agent/chat --------------------------------------------------------------





class AgentChatRequest(BaseModel):

    instruction: str

    session_id: str | None = None

    model: str | None = None

    auto_commit: bool = False

    max_steps: int = 10





@app.post("/agent/chat")

async def agent_chat(body: AgentChatRequest, auth: AuthContext = Depends(verify_api_key)):

    """Stateful chat endpoint: creates or resumes a session by session_id."""

    session_id = body.session_id

    if session_id:

        session = AGENT_SESSIONS.get(session_id)

        if session is None:

            session = AGENT_SESSIONS.create(

                title=f"Chat: {body.instruction[:60]}",

                session_id=session_id,

            )

    else:

        session = AGENT_SESSIONS.create(title=f"Chat: {body.instruction[:60]}")

        session_id = session.session_id



    AGENT_SESSIONS.append_message(session_id, "user", body.instruction)

    current = AGENT_SESSIONS.get(session_id)

    # history = all messages except the one we just appended (the current instruction)

    history = [item.model_dump() for item in (current.history[:-1] if current else [])]



    try:

        runner = AgentRunner(

            ollama_base=OLLAMA_BASE,

            workspace_root=Path(__file__).resolve().parent,

            github_token=_GITHUB_TOKEN,

            session_store=AGENT_SESSIONS,

            email=auth.email,

            department=auth.department,

            key_id=auth.key_id,

        )

        result = await runner.run(

            instruction=body.instruction,

            history=history,

            requested_model=body.model,

            auto_commit=body.auto_commit,

            max_steps=body.max_steps,

            user_id=auth.email,

            department=auth.department,

            key_id=auth.key_id,

            memory_store=USER_MEMORY,

            session_id=session_id,

        )

    except Exception:

        log.exception("Agent chat run failed")  # nosec B506 — intentional error logging for debugging agents

        result = {

            "goal": body.instruction,

            "plan": None,

            "steps": [],

            "commits": [],

            "summary": "Agent run failed. Check server logs for details.",

            "status": "failed",

        }



    AGENT_SESSIONS.append_message(session_id, "assistant", result["summary"])

    updated = AGENT_SESSIONS.update_result(

        session_id,

        plan=result["plan"] or {"goal": body.instruction, "steps": []},

        result=result,

    )

    return {"session_id": session_id, "session": updated, "result": result}





# --- Entry point ------------------------------------------------------------------



if __name__ == "__main__":

    import uvicorn

    uvicorn.run("proxy:app", host="0.0.0.0", port=PROXY_PORT, log_level=LOG_LEVEL.lower())  # nosec B104 — server bind to all interfaces is intentional