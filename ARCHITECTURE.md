# ARCHITECTURE.md — Target Architecture

> **This document defines the future architecture.**
> Every migration step moves toward this design.
> The current architecture is documented in `CLAUDE.md` §4.

---

## 1. Target Repository Structure

```
autonomous-ai-agency/
├── apps/                           # Deployable applications
│   ├── api/                        # Main backend (FastAPI :8001)
│   │   ├── server.py               # Entry point (currently backend/server.py)
│   │   ├── routes/                 # API route modules (split from 8700-line server.py)
│   │   │   ├── auth.py             # /api/auth/*
│   │   │   ├── agents.py           # /api/agent/*
│   │   │   ├── tasks.py            # /api/tasks/*
│   │   │   ├── providers.py        # /api/providers/*
│   │   │   ├── autonomy.py         # /api/autonomy/*
│   │   │   ├── doctor.py           # /api/doctor/*
│   │   │   ├── activation.py       # /api/activation/*
│   │   │   ├── voice.py            # /agent/voice/*, /agent/sam/*
│   │   │   └── scheduler.py        # /api/scheduler/*
│   │   ├── middleware.py            # CORS, JWT, rate limit
│   │   └── lifespan.py             # Startup/shutdown hooks
│   │
│   ├── relay/                      # Proxy (FastAPI :8000, currently proxy.py)
│   │   ├── server.py
│   │   ├── auth.py                 # API key verification
│   │   └── routes/
│   │
│   ├── dashboard/                   # Frontend (React SPA)
│   │   ├── src/
│   │   │   ├── api/                # All HTTP calls (currently frontend/src/api.js)
│   │   │   ├── auth/               # AuthContext, login, callback
│   │   │   ├── screens/            # V5 screens
│   │   │   ├── hooks/              # Shared hooks
│   │   │   └── components/         # Shared components
│   │   └── package.json
│   │
│   ├── worker/                     # Cloudflare Worker
│   │   ├── index.js                # Proxy + SPA serving
│   │   └── wrangler.jsonc
│   │
│   └── voice/                      # Voice manager (currently in apps/api)
│       ├── stt.py                  # Speech-to-text
│       ├── tts.py                  # Text-to-speech
│       └── sam.py                  # SAM agent
│
├── packages/                       # Shared libraries (importable by any app)
│   ├── ai/                         # Provider abstraction
│   │   ├── provider.py             # Base Provider interface
│   │   ├── registry.py             # Provider registry (currently provider_router.py)
│   │   ├── fallback.py             # Failover + circuit breaker
│   │   ├── brain.py                # Brain config (currently brain_policy.py + brain_config_store.py)
│   │   └── adapters/               # Provider implementations
│   │       ├── nvidia.py
│   │       ├── cerebras.py
│   │       ├── groq.py
│   │       ├── anthropic.py
│   │       ├── ollama.py
│   │       └── openrouter.py
│   │
│   ├── auth/                       # Authentication
│   │   ├── jwt.py                  # Token creation/verification
│   │   ├── oauth.py                # OAuth flows (currently social_auth.py)
│   │   ├── api_key.py              # API key auth
│   │   ├── service_token.py        # Service token auth
│   │   └── rbac.py                 # Role-based access
│   │
│   ├── scheduler/                  # Task scheduling
│   │   ├── scheduler.py            # APScheduler wrapper
│   │   ├── store.py                # Durable persistence
│   │   └── cleanup.py              # Dedup + stale removal
│   │
│   ├── orchestration/              # Agent orchestration
│   │   ├── runner.py               # Plan→Execute→Verify
│   │   ├── agency.py               # CEO-coordinated agency
│   │   └── workflow.py             # CRISPY workflow engine
│   │
│   ├── tasks/                      # Task management
│   │   ├── store.py                # Task persistence
│   │   ├── dispatcher.py           # Task dispatch
│   │   └── models.py               # Task data models
│   │
│   ├── storage/                    # Database abstraction
│   │   ├── mongo.py                # MongoDB backend
│   │   ├── sqlite.py               # SQLite backend
│   │   └── interface.py            # Shared interface
│   │
│   ├── events/                     # Event bus (future)
│   │   ├── bus.py                  # Pub/sub
│   │   └── types.py                # Event types
│   │
│   ├── telemetry/                  # Observability
│   │   ├── langfuse.py             # Langfuse integration
│   │   ├── metrics.py              # Custom metrics
│   │   └── health.py               # Health checks
│   │
│   ├── config/                     # Configuration (single source of truth)
│   │   ├── settings.py             # Typed config (all env vars)
│   │   └── secrets.py              # Secret management
│   │
│   ├── security/                   # Security utilities
│   │   ├── slop_gate.py            # Auto-PR quality gate
│   │   └── audit.py                # Audit logging
│   │
│   └── shared/                     # Shared utilities
│       ├── logging.py
│       ├── caching.py
│       └── utils.py
│
├── agents/                         # Agent profiles (data-driven)
│   ├── ceo.yaml
│   ├── developer.yaml
│   ├── reviewer.yaml
│   └── ...
│
├── skills/                         # Reusable agent skills
│   ├── github/
│   ├── playwright/
│   ├── coding/
│   ├── debugging/
│   └── ...
│
├── workflows/                      # Workflow definitions
│   ├── crispy.yaml
│   └── ...
│
├── loops/                          # Loop Engineering governance
│   ├── registry.yaml
│   └── LOOP.md
│
├── docs/                           # Documentation
│   ├── architecture/
│   ├── runbooks/
│   ├── changelog.md
│   └── plans/
│
├── infra/                          # Infrastructure
│   ├── render.yaml
│   ├── docker/
│   ├── cloudflare/
│   └── github-actions/
│
├── tests/                          # All tests
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── playwright/
│
├── CLAUDE.md                       # This operating manual
├── ARCHITECTURE.md                 # This document
├── ENGINEERING_STANDARDS.md        # Coding/security/testing standards
├── REWRITE_PLAN.md                 # Phased migration strategy
├── CHANGELOG.md                    # Root changelog
├── README.md                       # Project README
└── requirements.txt                # Python dependencies
```

---

## 2. Dependency Rules

### Allowed dependencies (top-down only)
```
apps/api          → packages/* (all)
apps/relay        → packages/* (auth, ai, config, shared)
apps/dashboard    → packages/ui (if extracted)
apps/worker       → (none — standalone JS)
packages/ai       → packages/config, packages/shared, packages/telemetry
packages/auth     → packages/config, packages/storage
packages/scheduler→ packages/config, packages/storage, packages/events
packages/orchestration → packages/ai, packages/tasks, packages/events
packages/tasks    → packages/storage, packages/events
packages/storage  → packages/config
packages/events   → (none — leaf module)
packages/config   → (none — leaf module)
packages/shared   → (none — leaf module)
```

### Forbidden dependencies
- `apps/dashboard` → `apps/api` (frontend never imports backend code)
- `packages/storage` → `packages/tasks` (storage doesn't know about tasks)
- `packages/ai` → `packages/orchestration` (providers don't know about agents)
- Any `packages/*` → `apps/*` (libraries don't depend on applications)
- No circular imports at any level

---

## 3. Provider Architecture (Target)

```python
# packages/ai/provider.py
class Provider(ABC):
    """Every provider implements this interface."""
    
    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> ChatResponse: ...
    
    @abstractmethod
    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]: ...
    
    @abstractmethod
    async def health(self) -> HealthStatus: ...
    
    @abstractmethod
    def cost(self, input_tokens: int, output_tokens: int) -> float: ...
    
    @abstractmethod
    def limits(self) -> RateLimit: ...
```

### Provider Manager
```python
# packages/ai/registry.py
class ProviderManager:
    """Single entry point for all LLM calls."""
    
    async def chat(self, messages, *, preferred=None, allow_paid=False) -> ChatResponse:
        # 1. Try preferred provider
        # 2. On 429: exponential backoff + failover
        # 3. On 410: permanent removal + long cooldown
        # 4. On success: reset failure counter
        # 5. Brain watchdog monitors all outcomes
```

### Fallback chain (data-driven)
```yaml
# packages/ai/fallback.yaml
providers:
  - id: cerebras
    priority: 1
    key_env: CEREBRAS_API_KEY
    models: [qwen-3-coder-480b]
    
  - id: groq
    priority: 2
    key_env: GROQ_API_KEY
    models: [deepseek-r1-distill-llama-70b]
    
  - id: nvidia
    priority: 3
    key_env: NVIDIA_API_KEY
    models: [meta/llama-3.3-70b-instruct]
    
  - id: ollama
    priority: 4
    key_env: null  # local, no key
    models: [qwen3-coder:30b]
```

---

## 4. Configuration Architecture (Target)

```python
# packages/config/settings.py
from pydantic import BaseModel

class Settings(BaseModel):
    """Single source of truth for all configuration."""
    
    # Storage
    storage_backend: str = "mongo"
    mongo_url: str = "mongodb://localhost:27017"
    sqlite_db_path: str = ".data/agency.db"
    
    # Auth
    jwt_secret: str
    admin_email: str
    admin_password: str
    activation_required: bool = True
    
    # Providers
    nvidia_api_key: str | None = None
    cerebras_api_key: str | None = None
    groq_api_key: str | None = None
    anthropic_api_key: str | None = None
    
    # OAuth
    github_client_id: str | None = None
    github_client_secret: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    
    # ... etc
    
    @classmethod
    def from_env(cls) -> "Settings":
        """Load all settings from environment variables."""
        ...

# Usage — every module does this:
from packages.config import settings
model = settings.nvidia_default_model
```

**No module reads `os.environ` directly. Ever.**

---

## 5. Event Bus Architecture (Target)

```python
# packages/events/bus.py
class EventBus:
    """In-process pub/sub. No direct calls between modules."""
    
    async def publish(self, event: Event) -> None: ...
    def subscribe(self, event_type: str, handler: Callable) -> None: ...

# Event types
TaskCreated, TaskStarted, TaskCompleted, TaskFailed,
ProviderFailed, FallbackStarted, BrainSwitched,
ScheduleFired, AgentStarted, AgentCompleted
```

### Example flow
```
Task Created → publish(TaskCreated)
    → Scheduler subscribes → queues task
    → Dashboard subscribes → updates UI
    → Telegram subscribes → sends notification
    → Telemetry subscribes → records metric
```

Nobody knows who is listening. Everything is loosely coupled.

---

## 6. Scheduler Architecture (Target)

```
Scheduler (decides WHEN) → Queue (stores WHAT) → Worker (executes HOW) → State (persists RESULT)
```

- **Scheduler**: APScheduler, fires on cron + manual trigger
- **Queue**: MongoDB collection (durable, queryable)
- **Worker**: InternalAgentAdapter / HermesAdapter / etc.
- **State**: TaskStore (tracks run_count, status, last_run)

### Dedup rules
- One job per name (enforced at creation + force_cleanup)
- Run-once jobs auto-delete after firing
- Stuck jobs (run_count > 10) auto-removed
- Startup cleanup clears backlog

---

## 7. Dashboard Architecture (Target)

```
REST API → Cached Queries → Indexed Search → React Dashboard
```

- Backend never calculates — it queries + caches
- Frontend never fetches raw DB data — it calls typed REST endpoints
- Real-time updates via WebSocket (future) or polling (current)
- Pagination for large lists (tasks, schedules)
- TTL cache for expensive queries (dashboard, activity)

---

## 8. Migration Principles

1. **Strangler Fig pattern**: new code runs alongside old code, gradually replacing it
2. **Feature flags**: `WORKFLOW_MODE=legacy|orchestrator`, `STORAGE_BACKEND=mongo|sqlite`
3. **Dual-write period**: during migration, write to both old + new systems
4. **Verification**: characterization tests pin old behaviour, new code must match
5. **Cleanup**: old code deleted only after new code is verified in production for 7 days
