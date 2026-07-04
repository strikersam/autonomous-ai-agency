# Killer TODO Roadmap — local-llm-server

> **Purpose:** Comprehensive implementation backlog derived from deep analysis of six leading open-source
> AI projects (hermes-agent, agentic-os, Nemotron, OpenMythos, codebuff, companyhelm) cross-referenced
> against the current local-llm-server codebase. Each item is scoped to be implementable without
> architectural rewrites.
>
> **Status:** Proposal only — no implementation started. Each item links to a source project for reference.
> Priority: P0 = critical gap, P1 = high value, P2 = quality-of-life, P3 = future.

---

## Source Projects Referenced

| Abbreviation | Repo | Key Insight |
|---|---|---|
| **HRM** | NousResearch/hermes-agent | Structured tool calling, ChatML prompt format, multi-hop reasoning |
| **AOS** | modimihir07/agentic-os | Agent lifecycle, task queues, inter-agent messaging, capability registry |
| **NVD** | NVIDIA-NeMo/Nemotron | SteerLM, reward models, synthetic data gen, NIM API best practices |
| **MYT** | kyegomez/OpenMythos | Swarm coordination, blackboard shared memory, emergent agent behavior |
| **CBF** | CodebuffAI/codebuff | Precise line-level editing, context compression, semantic chunk selection |
| **CHM** | CompanyHelm/companyhelm | Helm packaging, K8s-native deployment, multi-tenant isolation |
| **ECC** | affaan-m/ECC | Cross-harness routing, harness adapter, session lifecycle hooks |

---

## TOP 6 — Highest-ROI Items (Validated by Opus Research Agent)

> These were identified as the highest-impact, lowest-effort items after deep reading of all 6 source repos.
> Implement these first.

### ★1 — 3-Phase Context-Pruner Middleware [P0] [CBF]
Codebuff's `context-pruner` agent is the single biggest agent-efficiency win available as open source.
It runs as middleware on the agent loop AND on long chat sessions via 3 phases:
1. **Truncate** oversized tool call outputs + summarise with a cheap model + strip `<think>` tags
2. **Backward walk** with separate token budgets (50k user / 20k assistant messages)
3. **XML historical-memory wrap** — older turns become `<historical_memory_only>` XML, keeping them as context but out of the live message window

Triggered on: `context-over-limit` OR 5-minute prompt-cache expiry.

**What to build:** `agent/context_pruner.py` — drop into `agent/loop.py` before every LLM call. Also wire into `chat_handlers.py` for long chat sessions.

---

### ★2 — Specialized Sub-Agents with Per-Role Cheap Models [P0] [CBF + HRM]
Codebuff beats single-model coding by using 4 specialized sub-agents (File Picker → Planner → Editor → Reviewer), each routed to the cheapest capable model. The local-llm-server Hermes agent is monolithic. Split it:

| Role | Current | Target model |
|---|---|---|
| File Picker | same loop | smallest/fastest Ollama model |
| Planner | deepseek-r1:32b | deepseek-r1:32b (keep) |
| Editor | qwen3-coder:30b | qwen3-coder:30b (keep) |
| Reviewer | deepseek-r1:32b | Nemotron reward model or small verifier |

**What to build:** Declarative agent-definition schema (`id`, `model`, `toolNames`, `spawnableAgents`, `instructionsPrompt`) in `agent/models.py`. Refactor `agent/loop.py` to spawn sub-agents by config, not hardcoded logic.

---

### ★3 — Reasoning Token Budget + Toggle [P0] [NVD]
Nemotron and the underlying vLLM serving show: `thinking_token_budget` controls reasoning depth and cost. This applies to **all** reasoning models the server already uses (DeepSeek-R1, Qwen3, Nemotron NIM). Currently the server has no way to cap reasoning tokens — a short task pays the same as a hard one.

**What to build:**
- Accept `reasoning_budget: low|medium|high|max` on chat/agent requests
- Map to `thinking_token_budget` parameter (low=512, medium=2048, high=8192, max=unbounded)
- Inject `detailed thinking on/off` into system prompt when model supports toggle
- Parse `<think>...</think>` blocks and expose as `reasoning_content` field in response (strip from assistant message by default, include when `include_reasoning: true`)
- Register vLLM OpenAI-compatible backend in `router/registry.py` as first-class target alongside Ollama (enables Nemotron Nano and full vLLM serving stack)

**Files:** `chat_handlers.py`, `router/model_router.py`, `router/registry.py`, `handlers/anthropic_compat.py`

---

### ★4 — Skill/Procedural Memory (agentskills.io compatible) [P1] [HRM]
After a successful agent run, Hermes distills the trajectory into a named skill file on disk. Next time a similar task comes in, the skill is retrieved and the planner skips re-planning that portion. This directly attacks the "not efficient" problem by amortizing planning cost across sessions.

**What to build:**
- `agent/skill_memory.py` — after verified-success, distill trajectory to `~/.local-llm-server/skills/<name>.md`
- Skill retrieval: at planning time, embed task description and retrieve top-3 matching skills (cosine similarity)
- Skill format: compatible with [agentskills.io](https://agentskills.io) open standard
- `/skills` Telegram command and admin UI listing available skills with score history
- Skill self-improvement: re-distill when a task improves on an existing skill's score

**Files:** `agent/skill_registry.py` (extend), `agent/loop.py`, `telegram_bot.py`

---

### ★5 — Sandboxed Agent Execution (E2B / Docker micro-VM) [P1] [CHM] ✅ Delivered 2026-07-04
CompanyHelm runs every agent in a fresh E2B micro-VM (clean isolation per session). The current `agent/tools.py` writes directly to the host filesystem — documented as RISKY. Sandboxing closes this gap and enables in-sandbox test verification (pytest inside the VM as the Reviewer step).

**Delivered in PR branch `claude/e2b-code-changes-integration-sgg21f`:**
- `services/e2b_config.py` — sole reader of E2B env (Constitution §1)
- `services/e2b_sandbox.py::E2BSandboxSession` — drop-in `runner._mcp` replacement implementing `call_tool(name, args)` for write_file/read_file/run_command/clone_repo/git_commit/git_push/git_diff
- `runtimes/adapters/e2b.py::E2BAdapter` — RuntimeAdapter declaring the full capability set; auto-registered when `E2B_API_KEY` set
- `runtimes/adapters/internal_agent.py` — calls `maybe_attach_e2b(runner, spec)` so every chat code-edit + default-runtime task runs in-sandbox with graceful fallback
- `tasks/models.py::Task.company_id` + `tasks/service.py::_build_spec` — onboarded-company tasks clone the REAL company repo into the sandbox
- In-sandbox `pytest` verifier step with one retry on failure (this section's original spec)
- Token scrubbing in clone/push mirrors `mcp_server/workspace.py`
- Activation: `E2B_API_KEY` env (auto-on), `E2B_ENABLED=false` kill-switch, `AGENT_SANDBOX_MODE=e2b` alt activation
- 67 tests across 4 test files (config, sandbox, adapter, task wiring)

**Original design notes (kept for reference):**
- `services/sandbox.py` — sandbox provider abstraction (E2B cloud, local Docker, subprocess fallback) — superseded by `services/e2b_sandbox.py` (E2B-only first; the abstraction layer was YAGNI)
- `AGENT_SANDBOX_MODE=docker|e2b|none` env var — `AGENT_SANDBOX_MODE=e2b` honoured; `docker|none` left as future work
- Agent file writes go into the sandbox; only extracted diffs escape to host — delivered via `git_diff` extraction
- In-sandbox `pytest` run as the Verifier step — results fed back to Editor for retry — delivered (one retry)
- Per-session cleanup on success/failure (no cross-session contamination) — delivered via `E2BSandboxSession.close()` in `finally`

**Files:** `services/e2b_config.py`, `services/e2b_sandbox.py`, `runtimes/adapters/e2b.py`, `runtimes/manager.py`, `runtimes/adapters/internal_agent.py`, `tasks/models.py`, `tasks/service.py`, `frontend/src/v5/screens/ProvidersScreen.jsx`, `frontend/src/api.js`, `requirements.txt`, `.env.example`, `render.yaml`, `tests/test_e2b_*.py`

---

### ★6 — Cost Analytics + FTS5 Shared Memory + Agent Constitution [P1] [AOS]
`agentic-os` (same FastAPI+SQLite+vanilla JS stack — patterns port nearly directly) contributes three high-value primitives:

**6a — Cost Analytics Dashboard:** Track tokens × price per provider/model/agent with budget alerts. Show in admin dashboard "Cost Explorer" tab.

**6b — SQLite FTS5 Shared Memory:** A full-text-searchable persistent memory layer queried by the agent at session start. Cheaper than re-reading files; complements existing graphify/repowise. Schema: `(session_id, key, value, tags, timestamp)`.

**6c — Constitution + Identity Files:** `config/constitution.md` and `config/identity.md` prepended to every agent system prompt for consistent behavior. Configurable per API key (enterprises get their own identity).

**What to build:** `services/agent_memory.py` (FTS5), `services/cost_tracker.py`, `config/constitution.md`, admin dashboard Cost Explorer tab.

**Files:** new `services/agent_memory.py`, new `services/cost_tracker.py`, `admin_auth.py`, `langfuse_obs.py`

---

### ★7 — Adaptive Loop Halting (Early Exit on High Confidence) [P1] [MYT + HRM]
The verify loop runs a fixed number of iterations. OpenMythos's Adaptive Computation Time concept applied here: stop the plan→execute→verify cycle as soon as the Verifier returns confidence ≥ threshold. On simple tasks (single-file edits) this reduces 3-call loops to 1.5 on average.

**What to build:**
- Verifier response includes `confidence: 0.0–1.0` (add to `agent/models.py` VerificationResult)
- Early-exit when `confidence ≥ AGENT_CONFIDENCE_THRESHOLD` (default 0.9)
- Track confidence scores in session state for skill-improvement feedback
- Dashboard sparkline showing confidence trend per session

**Files:** `agent/models.py`, `agent/loop.py`, `agent/state.py`

---

## SECTION A — Agent Efficiency (Hermes / AOS / MYT)

> The current `AgentRunner` plan→execute→verify loop exists but is costly (3 LLM calls/step),
> brittle on tool calls, and does not self-improve across sessions.

### A1 — Hermes ChatML Prompt Format for Tool Calling [P0] [HRM]
The current executor prompt is ad-hoc JSON in a system message. Hermes uses a strict
`<|im_start|>...<|im_end|>` ChatML format with embedded `<tool_call>` and `<tool_response>`
tokens that dramatically improves tool-use reliability on models fine-tuned with this format
(Qwen3-Coder and DeepSeek-R1 both respond to it).

**What to build:**
- `agent/hermes_prompt.py` — ChatML tool-call formatter using `<tool_call>` / `<tool_response>` tags
- Model-aware format selection in `agent/prompts.py` (Hermes format when model supports it)
- JSON Schema definitions for all existing tools in `agent/tools.py`
- Tool-call parser that validates the LLM output against the schema before execution

**Files:** `agent/prompts.py`, `agent/tools.py`, new `agent/hermes_prompt.py`

---

### A2 — Multi-Hop Reasoning Chain (ReAct / Tree-of-Thought) [P0] [HRM]
Hermes-agent implements ReAct (Reason + Act) loops where the model interleaves reasoning
steps with tool calls. The current loop fires tool → observe → next step with no persistent
reasoning trace. Complex multi-file tasks fail because the model loses context.

**What to build:**
- `agent/react_loop.py` — ReAct chain: thought → tool call → observation → repeat
- Structured "scratchpad" that accumulates across tool calls within a step
- Tree-of-Thought branching for ambiguous steps (try multiple approaches, pick best)
- Reasoning trace persisted to `.claude/state/<session_id>/reasoning_trace.json`

**Files:** `agent/loop.py`, new `agent/react_loop.py`, `agent/state.py`

---

### A3 — Agent Capability Registry + Dynamic Tool Discovery [P1] [AOS]
`agentic-os` has an agent marketplace where agents advertise capabilities and tasks are
matched to capable agents. The current system hardcodes tool lists per agent role. Adding
a tool to the system requires editing the executor — it should be plug-in.

**What to build:**
- `agent/capability_registry.py` — register/discover tools with JSON Schema, version, cost
- Auto-discovery of tools decorated with `@agent_tool(schema=...)` 
- Capability negotiation at session start (agent reports available tools to planner)
- Hot-reload of tool registry without server restart

**Files:** new `agent/capability_registry.py`, `agent/tools.py`, `agent/loop.py`

---

### A4 — Async Task Queue with Priority and Backpressure [P1] [AOS]
Tasks submitted to the agent are currently executed inline on the API request. Long tasks
block the connection and fail on timeout. `agentic-os` uses a priority queue with worker
pools and backpressure signals.

**What to build:**
- `services/task_queue.py` — asyncio-based priority queue (high/normal/low)
- Background worker pool with configurable concurrency (`AGENT_MAX_WORKERS` env)
- `/v1/tasks/queue` endpoint to check queue depth + estimated wait
- Backpressure: reject with `429` + `Retry-After` when queue is full
- SSE endpoint `/v1/tasks/{id}/stream` for real-time task progress

**Files:** new `services/task_queue.py`, `proxy.py`, `agent/loop.py`

---

### A5 — Inter-Agent Message Bus [P1] [AOS / MYT]
The current multi-agent swarm (`agents/swarm.py`) uses direct function calls. `agentic-os`
and `OpenMythos` both show that a shared message bus (even in-memory with asyncio queues)
dramatically improves swarm coordination — agents can subscribe to topics, broadcast
results, and react to each other's outputs without tight coupling.

**What to build:**
- `services/agent_bus.py` — pub/sub message bus with topic routing
- Agent roles (Planner, Executor, Verifier) publish events on task lifecycle
- Swarm agents subscribe to relevant topics instead of polling
- Durable event log to Redis (optional, falls back to memory)

**Files:** new `services/agent_bus.py`, `agents/swarm.py`, `agent/loop.py`

---

### A6 — Shared Blackboard Memory for Swarm Agents [P1] [MYT]
`OpenMythos` implements a shared blackboard (read/write shared state) for emergent swarm
behavior. Agents write intermediate results and other agents can read/extend them. This
enables specialised sub-agents to contribute to a shared working document without a 
central orchestrator bottleneck.

**What to build:**
- `services/blackboard.py` — in-memory + Redis-backed key-value blackboard
- Namespace isolation per task session
- Agents can `blackboard.write(key, value)` and `blackboard.read(key)` during execution
- Conflict resolution strategy (last-write-wins vs merge for dict types)
- Expose blackboard state in admin dashboard task view

**Files:** new `services/blackboard.py`, `agents/swarm.py`, `agent/loop.py`

---

### A7 — Agent Self-Improvement Loop [P2] [HRM / AOS]
Hermes and agentic-os both include mechanisms where agents rate their own outputs and
update their strategies. The current `agent/improvement_loop.py` exists but is thin.

**What to build:**
- Post-session evaluation: Verifier scores all steps, writes quality metrics to `.claude/state/quality_log.json`
- Strategy distillation: high-quality sessions are summarised into compressed few-shot examples stored in `agent/playbook.py`
- Automatic few-shot injection: top-3 matching examples prepended to Planner prompt for similar tasks
- Model evaluation: track per-model accuracy so ModelRouter can adjust selection weights

**Files:** `agent/improvement_loop.py`, `agent/playbook.py`, `agent/prompts.py`, `router/model_router.py`

---

## SECTION B — NVIDIA / Cloud Model Integration (Nemotron / NVD)

> NVIDIA integration exists but is fragile (double `/v1` bug was recently fixed, but
> the integration is still basic — no reward models, no structured NIM usage, no guardrails).

### B1 — Nemotron Reward Model for Agent Step Scoring [P0] [NVD]
NVIDIA Nemotron-4-340B-Reward is a top-ranked reward model available via NIM API.
The current Verifier uses an LLM call for verification. Replacing/augmenting with a
reward model gives cheaper, more consistent quality scores.

**What to build:**
- `services/reward_scorer.py` — call Nemotron reward endpoint for (prompt, response) pairs
- Integration into `agent/loop.py` Verifier phase: score each step, gate on threshold
- Score stored in session state; used by `improvement_loop.py` for quality tracking
- Fallback to LLM verifier when NIM is unavailable

**Files:** new `services/reward_scorer.py`, `agent/loop.py`, `agent/state.py`

---

### B2 — SteerLM / RLHF-Style Steering for Local Models [P1] [NVD]
Nemotron introduces SteerLM — runtime steering of model outputs via reward labels
injected into the prompt (helpfulness, correctness, complexity). We can implement a
simplified version for local models: inject quality-steering tokens before generation
to bias toward better code outputs.

**What to build:**
- `router/steering.py` — build steering prefix based on task type (code=high-complexity, chat=high-helpfulness)
- Inject steering tokens into system message before model call
- A/B test steering vs no-steering using Langfuse traces to measure quality delta
- Admin UI toggle to enable/disable steering per model

**Files:** new `router/steering.py`, `router/model_router.py`, `chat_handlers.py`

---

### B3 — Synthetic Training Data Generation Pipeline [P1] [NVD]
Nemotron's core use-case is generating high-quality synthetic data for fine-tuning.
Local LLMs can be fine-tuned (LoRA/QLoRA) to improve at common tasks. Building a
pipeline that auto-generates fine-tuning data from successful agent sessions enables
continuous model improvement.

**What to build:**
- `services/synthetic_data.py` — extract (instruction, response) pairs from successful sessions
- Filter by reward model score (only keep high-quality pairs)
- Export to JSONL in Alpaca/ShareGPT format for LoRA fine-tuning tools
- `/api/admin/export-training-data` endpoint to trigger export
- Optional: direct integration with Axolotl or unsloth for automated fine-tuning

**Files:** new `services/synthetic_data.py`, `admin_auth.py` (admin endpoint), `agent/state.py`

---

### B4 — NeMo Guardrails Integration [P1] [NVD]
NeMo Guardrails provides programmable safety rails for LLM applications: topic filters,
jailbreak detection, output validation. The current proxy has no content filtering.

**What to build:**
- `services/guardrails.py` — configurable guardrail pipeline (topic allow/deny lists, regex patterns)
- Pre-request filter on all chat completions
- Post-response filter for output validation
- Admin UI to configure guardrail rules per API key
- Colang-inspired rule format (simplified) in `config/guardrails.yaml`

**Files:** new `services/guardrails.py`, `proxy.py`, `admin_auth.py`

---

### B5 — NIM API Connection Pooling + Circuit Breaker [P1] [NVD]
The current NVIDIA integration creates a new httpx client per request. NIM APIs have
rate limits and the proxy should pool connections, implement circuit breaking, and 
exponentially back off on failures.

**What to build:**
- Persistent `httpx.AsyncClient` pool in `router/model_router.py` for cloud providers
- Circuit breaker per provider (open → half-open → closed state machine)
- Exponential backoff with jitter on 429/503 responses
- Provider health dashboard showing circuit state in admin UI

**Files:** `router/model_router.py`, `router/health.py`, `services/shared_state.py`

---

## SECTION C — Direct Chat Improvements (CBF / HRM)

> The direct chat endpoint (`/v1/chat/completions`) is functional but basic.
> Best-in-class open-source chat tools have features that are completely absent.

### C1 — Structured Output / JSON Mode [P0] [CBF / HRM]
Neither `chat_handlers.py` nor the Ollama passthrough enforces structured JSON output.
Modern LLM applications depend heavily on `response_format: {type: "json_object"}`.
Codebuff uses structured outputs extensively for precise code edits.

**What to build:**
- Parse `response_format` from OpenAI chat request
- When `json_object` requested: append JSON-mode system instruction + validate response is parseable JSON
- When `json_schema` requested: inject schema into system prompt + validate against schema with `jsonschema`
- Retry once on invalid JSON (structured-output self-healing)
- Pass `format: "json"` to Ollama models that support it natively

**Files:** `chat_handlers.py`, `handlers/anthropic_compat.py`

---

### C2 — Function Calling / Tool Use (OpenAI-Compatible) [P0] [CBF / HRM]
The `/v1/chat/completions` endpoint accepts `tools` parameter but does not implement
tool execution. Clients expect OpenAI `tool_calls` in the response. This is the single
biggest gap between the proxy and the real OpenAI API.

**What to build:**
- Parse `tools` and `tool_choice` from chat request
- Format tools as Hermes `<tool_call>` schema OR Qwen3 native tool format based on model
- Parse model output for tool call patterns and convert to OpenAI `tool_calls` response format
- Multi-turn tool execution loop (model → tool call → result → model) within the handler
- Client-side tool execution mode: return `finish_reason: "tool_calls"` for client to execute

**Files:** `chat_handlers.py`, new `handlers/tool_executor.py`, `router/model_router.py`

---

### C3 — Streaming with Proper Delta Reconstruction [P1] [CBF]
Current streaming in `chat_handlers.py` passes Ollama's NDJSON stream directly. When
tools are involved or the response needs post-processing (JSON validation, steering injection),
the stream is broken. Codebuff's approach: reconstruct the full response, process it, then
re-stream as SSE deltas.

**What to build:**
- `chat_handlers.py` buffer mode: accumulate full response when post-processing is needed
- Re-emit as SSE `data: {"choices":[{"delta":{"content":"..."}}]}` chunks after processing
- Backpressure-safe: use asyncio queue between accumulator and emitter
- Preserve streaming latency perception by emitting chunk-by-chunk from buffer

**Files:** `chat_handlers.py`

---

### C4 — Chat History Persistence + Retrieval [P1] [AOS / HRM]
Every chat session starts with zero context. There is no session continuity between
requests unless the client sends full history. Building server-side session storage
enables multi-turn chat UIs, chat replay for debugging, and context injection.

**What to build:**
- `services/chat_history.py` — per-key session store (SQLite + optional Redis)
- `session_id` support in request headers/body; auto-generated if absent
- `/v1/sessions/{id}/messages` CRUD endpoints
- Context window management: trim history to fit within model's context limit
- Admin UI session browser with message viewer

**Files:** new `services/chat_history.py`, `proxy.py`, `chat_handlers.py`, `db/sqlite_store.py`

---

### C5 — Context Window Management + Smart Truncation [P1] [CBF / HRM]
When conversation history exceeds model context, the current proxy sends too-long requests
and gets errors. Codebuff implements semantic chunking — keeping the most relevant parts of
history based on cosine similarity to the current query.

**What to build:**
- `services/context_manager.py` — count tokens (tiktoken or character approximation)
- Sliding window truncation: keep system prompt + last N turns + current message
- Semantic retrieval mode: embed all messages, retrieve top-K most relevant for context
- Per-model context limit registry in `router/registry.py`
- Warn when approaching limit: `X-Context-Used: 80%` response header

**Files:** new `services/context_manager.py`, `router/registry.py`, `chat_handlers.py`

---

### C6 — Prompt Caching (Anthropic-Compatible) [P1] [HRM]
The Anthropic API supports `cache_control` on message blocks for prefix caching.
The current `handlers/anthropic_compat.py` strips this. Local models don't support
native caching but we can implement KV-cache-aware routing (send long-context requests
to the same Ollama instance to leverage its implicit KV cache).

**What to build:**
- Parse `cache_control` blocks in Anthropic compat handler
- Track which model instance has a warm KV cache for a session (by system-prompt hash)
- Route subsequent requests with same system prompt to same model instance
- Expose `cache_read_input_tokens` / `cache_creation_input_tokens` in response (even if mocked)

**Files:** `handlers/anthropic_compat.py`, `router/model_router.py`

---

### C7 — Embeddings Pipeline + Vector Search [P2] [AOS / CBF]
The `/v1/embeddings` endpoint is a passthrough. There is no server-side vector store
for RAG. Both codebuff and agentic-os use embeddings as a core primitive.

**What to build:**
- `services/vector_store.py` — in-process FAISS or ChromaDB vector store
- Index chat history, code files, and agent memories as embeddings
- `/v1/similarity-search` endpoint for semantic retrieval
- RAG injection: automatically prepend relevant context chunks to agent prompts
- Configurable embedding model (default: `nomic-embed-text` via Ollama)

**Files:** new `services/vector_store.py`, `agent/rag_context.py`, `proxy.py`

---

## SECTION D — Deployment & Infrastructure (CHM / NVD)

> The server runs as a single Python process. Production deployments need containerization,
> K8s packaging, horizontal scaling, and operational observability.

### D1 — Helm Chart for Kubernetes Deployment [P1] [CHM]
`companyhelm` packages AI infrastructure as production-grade Helm charts with
proper values schema, health probes, HPA, and secrets management. The current
deployment is ad-hoc (`uvicorn` in a terminal).

**What to build:**
- `helm/local-llm-server/` chart with `Chart.yaml`, `values.yaml`, templates
- Deployment, Service, Ingress templates
- ConfigMap for model routing config
- External secrets integration (Vault / K8s secrets) for API keys
- HPA based on queue depth metric
- Helm tests for health probe validation

**Files:** new `helm/` directory

---

### D2 — Docker Compose Production Stack [P1] [CHM]
Current `docker/` directory exists but lacks a full production compose stack
(Ollama + proxy + Redis + Langfuse + Telegram bot together).

**What to build:**
- `docker-compose.prod.yml` — full production stack with networking
- Health checks on all services with proper depends_on ordering
- Volume mounts for model storage, key store, session state
- `make up` / `make down` convenience targets in `Makefile`
- Environment variable documentation in `.env.example`

**Files:** new `docker-compose.prod.yml`, `.env.example`, `Makefile`

---

### D3 — OpenTelemetry Distributed Tracing [P1] [NVD / CHM]
Langfuse captures LLM traces but there is no OTEL instrumentation for the HTTP layer,
agent phases, or database calls. In a distributed deployment (multiple workers, Redis,
Ollama on different machines), OTEL is essential for debugging latency.

**What to build:**
- Add `opentelemetry-sdk` + `opentelemetry-instrumentation-fastapi` to dependencies
- `services/telemetry.py` — OTEL tracer factory, span context propagation
- Instrument all FastAPI routes, httpx calls, and agent phase boundaries
- Export to OTEL Collector (configured via `OTEL_EXPORTER_OTLP_ENDPOINT` env)
- Correlate OTEL trace IDs with Langfuse trace IDs for unified observability

**Files:** new `services/telemetry.py`, `proxy.py`, `chat_handlers.py`, `agent/loop.py`

---

### D4 — Horizontal Scaling with Redis State Backend [P2] [CHM / AOS]
The server stores session state, rate limit counters, and circuit breaker state in
module-level dicts that don't survive restarts and can't be shared across workers.
A Redis-backed state layer (partially started with `services/shared_state.py`) needs
to be completed across all stateful modules.

**What to build:**
- Complete `services/shared_state.py` migration for ALL stateful modules (not just cooldowns)
- Session store → Redis (with TTL)
- Rate limit counters → Redis atomic increments (INCRBY with EXPIRE)
- Agent task state → Redis hash with pub/sub for live updates
- Graceful degradation: in-memory fallback when Redis is unavailable

**Files:** `services/shared_state.py`, `agent/state.py`, `key_store.py`, `proxy.py`

---

### D5 — Model Auto-Management (Pull, Warm, Evict) [P2] [NVD]
Ollama models must be pulled and warmed manually. There is no automation for
ensuring required models are available when the server starts, or for evicting
models that haven't been used to free VRAM.

**What to build:**
- `services/model_manager.py` — startup check: pull required models if absent
- Warm required models on startup (send a dummy request to load into VRAM)
- LRU eviction of models not used in `MODEL_EVICTION_TTL` seconds
- Webhook/event when a model is ready or evicted (for downstream notification)
- Admin UI model status panel (loaded / unloaded / downloading)

**Files:** new `services/model_manager.py`, `router/health.py`, `proxy.py`

---

## SECTION E — Autonomy & Self-Healing (AOS / MYT / ECC)

> The server should operate autonomously: detect its own failures, heal itself,
> adapt its configuration, and notify operators — without human intervention.

### E1 — Cross-Harness Routing (ECC Pattern) [P1] [ECC]
Different AI coding tools (Claude Code, Cursor, Aider, Continue) have different capability
signatures. The proxy should detect which harness is calling and adapt — routing Cursor
to faster models, Claude Code to higher-reasoning models, and so on.

**What to build:**
- `agents/harness_adapter.py` (partially exists) — complete detection logic from User-Agent + request patterns
- Harness-specific model preferences in `router/registry.py`
- `router/model_router.py` accepts `harness_id` in routing context
- Harness performance telemetry: track success rate per harness/model pair
- `.claude/state/harness-registry.json` updated after each session

**Files:** `agents/harness_adapter.py`, `router/model_router.py`, `router/registry.py`

---

### E2 — Self-Healing Agent Loop (Detect + Repair Own Failures) [P1] [AOS / MYT]
The current loop fails hard on executor errors. `agentic-os` implements a "doctor" pattern
where a separate micro-agent inspects a failed step, classifies the failure, and either
retries with a corrected prompt or rolls back.

**What to build:**
- `agent/doctor.py` — failure classification (syntax error / import error / test fail / timeout)
- Targeted repair prompts per failure class
- Auto-retry with repair prompt before escalating to human
- Failure pattern log in `.claude/state/failure_patterns.json` for trend analysis
- Alert via Telegram bot when repair fails after N attempts

**Files:** new `agent/doctor.py`, `agent/loop.py`, `telegram_bot.py`

---

### E3 — Autonomous Monitoring with Trend Watcher [P2] [AOS]
`agent/trend_watcher.py` exists. It should be wired to observe actual system metrics
(request rate, error rate, latency p95, model VRAM usage) and autonomously trigger
responses: warn via Telegram, scale down model, flush cache.

**What to build:**
- Connect `trend_watcher.py` to actual metrics from Langfuse + Ollama `/api/ps`
- Define alert thresholds in `config/monitoring.yaml`
- Auto-responses: on high latency → switch to faster model, on OOM → evict largest model
- Weekly trend summary emitted to admin dashboard + Telegram

**Files:** `agent/trend_watcher.py`, `telegram_bot.py`, `router/health.py`

---

### E4 — Nightly Self-Evaluation + Regression Tests [P2] [HRM / AOS]
The system should evaluate itself nightly: run a golden-set of prompts, compare outputs
to expected baselines, and flag regressions. `hermes-agent` includes evaluation harnesses
for this purpose.

**What to build:**
- `tests/eval/golden_set.jsonl` — curated (prompt, expected_output_pattern) pairs
- `scripts/nightly_eval.py` — run golden set, score with reward model, emit Langfuse traces
- Regression alert: Telegram message when score drops > 5% vs last week
- GitHub Actions nightly workflow to run evaluation
- Dashboard graph of quality score over time

**Files:** new `tests/eval/golden_set.jsonl`, new `scripts/nightly_eval.py`, `.github/workflows/nightly.yml`

---

## SECTION F — Developer Experience (CBF / ECC)

> The server is hard to develop against locally. Better tooling = faster iteration.

### F1 — Codebuff-Style Precise Diff Application [P0] [CBF]
The current `agent/tools.py` `apply_diff` method is fragile — it uses Python `difflib`
and fails on whitespace differences, line number mismatches, and file encoding edge cases.
Codebuff uses a semantics-aware diff engine.

**What to build:**
- Replace `apply_diff` with a robust implementation: try exact-match first, then fuzzy search
- Pre-apply validation: detect conflict markers, encoding issues, binary files
- Post-apply validation: `ast.parse()` for Python, ESLint for JS/TS
- Dry-run mode: show diff preview without applying
- Rollback support: keep a pre-edit snapshot for one-step undo

**Files:** `agent/tools.py` (risky module — requires `risky-module-review` skill)

---

### F2 — MCP Server Exposing Proxy Capabilities [P1] [CBF / ECC]
Codebuff and Claude Code both consume MCP tools. The proxy should expose its own
capabilities (run agent task, query model, check health, list models) as an MCP server
so AI coding tools can orchestrate the proxy as a tool.

**What to build:**
- `mcp_server.py` — FastMCP server exposing: `run_task`, `chat`, `list_models`, `get_health`, `get_logs`
- Run alongside `proxy.py` on a different port (`MCP_PORT` env, default 8001)
- Auth: same Bearer token as proxy API
- Claude Code integration: document in `client-configs/` how to add as MCP server
- Tool schema follows the MCP JSON Schema spec

**Files:** new `mcp_server.py`, `client-configs/mcp-server.json`

---

### F3 — Local Dev Dashboard with Live Metrics [P2] [CBF / CHM]
The admin dashboard exists but requires auth. For local development there should be
a zero-auth debug dashboard showing live request traces, model state, queue depth,
and agent session progress.

**What to build:**
- `/debug` route (only enabled when `DEBUG_DASHBOARD=true` env)
- Live SSE feed of all requests with timing, model used, token count
- Queue depth graph, circuit breaker state, VRAM usage (from Ollama `/api/ps`)
- Session trace viewer: step-by-step agent execution with diffs
- No external JS dependencies — pure HTML + HTMX or Vanilla JS

**Files:** `proxy.py`, new `templates/debug.html`

---

### F4 — SDK / Client Library Generation [P2] [CBF]
There are example configs in `client-configs/` but no typed SDK. Codebuff ships
a minimal Python client. A generated OpenAPI-based SDK would make the proxy
much easier to use programmatically.

**What to build:**
- `scripts/generate_sdk.py` — generate a typed Python client from FastAPI's `/openapi.json`
- `client_sdk/` — generated (and committed) minimal SDK with `ChatClient`, `AgentClient`
- Test the SDK against the live server in CI
- Publish as a private PyPI package (optional)

**Files:** new `scripts/generate_sdk.py`, new `client_sdk/`

---

## SECTION G — Observability (NVD / CHM)

### G1 — Per-Model Cost and Latency Attribution [P1] [NVD]
Langfuse traces exist but there is no per-model cost breakdown in the admin dashboard.
When multiple models are used in an agent session, it's impossible to know which model
is the bottleneck or most expensive.

**What to build:**
- Cost estimation table in `router/registry.py` (tokens/sec approximation per model)
- `langfuse_obs.py` emits per-phase token counts and latency
- Admin dashboard "Cost Explorer" tab showing cost by model, by user, by time
- Monthly cost report emitted to Telegram on the 1st

**Files:** `langfuse_obs.py`, `router/registry.py`, `admin_auth.py`

---

### G2 — Request Replay for Debugging [P2] [CBF]
When an agent session fails, it's hard to reproduce. Codebuff logs every request/response
pair and provides a replay mechanism. The proxy should do the same.

**What to build:**
- `services/request_log.py` — append-only log of all requests to SQLite (with TTL)
- `/api/admin/replay/{request_id}` — re-execute a logged request against current model
- Export session as curl command or Python snippet
- Diff replay output against original for regression detection

**Files:** new `services/request_log.py`, `admin_auth.py`, `proxy.py`

---

## SECTION H — Vision / Multimodal (NVD)

### H1 — Vision Input Support for Multimodal Models [P2] [NVD]
The current proxy is text-only. Llava, BakLLaVA, and newer Qwen-VL models support
vision. Nemotron includes vision models via NIM. The features doc explicitly lists
vision as a limitation.

**What to build:**
- Parse `image_url` and `image` base64 content blocks in `/v1/chat/completions`
- Convert to Ollama images format (`{"images": ["<base64>"]}`)
- Route image-containing requests to vision-capable models (`router/registry.py` vision flag)
- Anthropic compat: handle `image` content blocks in `handlers/anthropic_compat.py`
- Resize/compress large images before sending to model (stay within context limits)

**Files:** `chat_handlers.py`, `handlers/anthropic_compat.py`, `router/registry.py`, `router/model_router.py`

---

### H2 — Audio Input / Whisper Transcription [P3] [NVD]
NVIDIA NIM includes Whisper models for speech-to-text. Adding a `/v1/audio/transcriptions`
endpoint (OpenAI Whisper API compat) would make the proxy a drop-in replacement for more
use cases (voice coding, meeting transcription).

**What to build:**
- `/v1/audio/transcriptions` endpoint accepting multipart/form-data audio
- Route to local Whisper model (via Ollama) or NVIDIA NIM Whisper
- Return OpenAI Whisper response format
- Streaming transcription for long audio files

**Files:** `proxy.py`, new `handlers/audio.py`

---

## Priority Summary

| Priority | Count | Focus |
|---|---|---|
| **P0** | 5 | Hermes tool calling, ReAct loop, JSON mode, function calling, precise diffs |
| **P1** | 16 | Reward scoring, NIM circuit breaker, task queue, inter-agent bus, streaming, history, cross-harness routing, MCP server, Helm chart, OTEL, model manager, cost attribution, self-healing |
| **P2** | 10 | SteerLM, synthetic data, context management, blackboard, vector store, Docker Compose, Redis scaling, trend watcher, debug dashboard, request replay |
| **P3** | 2 | Audio/Whisper, SDK generation |

---

## Implementation Notes

1. **Do not start implementation until a specific item is selected and scoped.**
2. **All P0 items in Section A require the `risky-module-review` skill** before merging (agent/tools.py writes).
3. **Section B items need `NVIDIA_API_KEY` configured** to test against real NIM.
4. **Section D items are deployment-only** — safe to implement in parallel with feature work.
5. **Tests first:** Every item needs a test file created before implementation (`test-first-executor` skill).
6. **Changelog required:** Every item that ships must have a `docs/changelog.md` entry.
