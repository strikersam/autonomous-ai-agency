# Performance Analysis — local-llm-server

*Audit Date: 2026-06-04*

---

## Summary

The primary performance bottleneck is the upstream Ollama inference engine (not this proxy). However, several proxy-level and infrastructure-level issues can amplify latency, reduce throughput, and cause reliability degradation under load.

---

## 1. Rate Limiter Performance

### PERF-001 [HIGH] — Synchronous Lock in Async Context

**Issue:** The rate limiter in `proxy.py` uses `threading.Lock()`:
```python
_rate_lock = threading.Lock()

def check_rate_limit(api_key: str) -> None:
    with _rate_lock:  # Blocks the event loop thread
        ...
```

Under high concurrency, calling a synchronous lock from async request handlers causes event loop blocking. Every concurrent request waits on this lock, serializing throughput.

**Affected code:** `proxy.py:163-191`

**Fix:** Convert to `asyncio.Lock()` or use a non-blocking approach:
```python
_rate_lock = asyncio.Lock()

async def check_rate_limit(api_key: str) -> None:
    async with _rate_lock:
        ...
```

Or better — use a token bucket implementation backed by Redis for horizontal scaling.

**Estimated impact:** Up to 30% latency reduction at p99 under load (>50 concurrent requests)

---

### PERF-002 [MEDIUM] — Rate Bucket Key Eviction is O(n)

**Issue:** The key eviction logic in `check_rate_limit()` iterates all keys to find stale ones:
```python
stale = [k for k in list(_rate_bucket_keys) if not _rate_buckets.get(k)]
for k in stale:
    _rate_buckets.pop(k, None)
    try:
        _rate_bucket_keys.remove(k)  # O(n) list scan
    except ValueError:
        pass
```

`list.remove()` is O(n). For 10,000 keys, eviction can take significant CPU time.

**Fix:** Replace `_rate_bucket_keys: list[str]` with a `set` or use `collections.OrderedDict` for O(1) operations.

---

## 2. Ollama Connection Handling

### PERF-003 [MEDIUM] — New httpx Client Per Request

**Issue:** `chat_handlers.py` creates a new `httpx.AsyncClient` or uses a shared client per handler call. If not shared at module level, each request incurs TCP connection setup overhead (~10-50ms).

**Fix:** Use a module-level shared `httpx.AsyncClient` with connection pooling:
```python
_ollama_client = httpx.AsyncClient(
    base_url=OLLAMA_BASE,
    timeout=httpx.Timeout(connect=5.0, read=300.0, write=30.0),
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
)
```

---

### PERF-004 [MEDIUM] — No Connection Pooling for Langfuse

**Issue:** `langfuse_obs.py` creates HTTP connections for each trace emission. Langfuse traces are typically fire-and-forget — these calls should be batched or sent asynchronously off the critical path.

**Fix:**
1. Use Langfuse SDK's native batching (it buffers traces)
2. Or run Langfuse emission in a background task (`asyncio.create_task`)

---

## 3. Model Router Performance

### PERF-005 [MEDIUM] — Health Check on Every Request (Without Cache Miss)

**Issue:** The model router calls `is_model_available()` which caches the result for 60 seconds (TTL). However, on cache miss (first request after TTL), the health check makes a synchronous HTTP call to Ollama, blocking the routing decision.

**Affected code:** `router/health.py`

**Fix:** Serve stale health data while refreshing asynchronously (stale-while-revalidate pattern):
```python
# On TTL expiry, return last-known value and trigger background refresh
if cache_expired:
    asyncio.create_task(refresh_health_cache())
    return last_known_value
```

---

### PERF-006 [LOW] — Task Classifier is Pure Python String Matching

**Issue:** `router/classifier.py` uses keyword matching to classify tasks. For long messages, this is fine. But it runs synchronously and could be slow for very large message histories.

**Fix:** Apply classification only to the last few messages or a truncated version of the context. Cache classification results for identical message hashes.

---

## 4. Agent Execution Performance

### PERF-007 [HIGH] — Sequential Plan Steps (No Parallelism)

**Issue:** `agent/loop.py` executes plan steps sequentially. For steps that are independent (e.g., "read file A" and "read file B"), there is no parallelism.

**Fix:** Analyze the plan's dependency graph and execute independent steps in parallel using `asyncio.gather()`.

---

### PERF-008 [MEDIUM] — Large Context Window Growth

**Issue:** The agent's message history grows with each step. Without compaction, by step 15-20 the context window may hit token budget limits, forcing compaction (which adds an extra LLM call).

**Affected code:** `agent/context_manager.py`, `agent/loop.py`

**Fix:**
1. Compaction is already implemented — verify it fires before budget exhaustion, not after
2. Use progressive summarization: summarize after every N steps, not just at the end
3. Use the `InferenceCache` for repeated tool call results

---

### PERF-009 [MEDIUM] — RepowiseIntelligence Reads Files on Every Call

**Issue:** `agent/repowise.py` provides codebase analysis. Each `get_context()` / `get_overview()` call may re-read files from disk. For large repositories with frequent agent requests, this creates disk I/O pressure.

**Fix:** Add TTL-based in-memory caching to `RepowiseIntelligence` for file reads and overview summaries.

---

## 5. Backend Server Performance

### PERF-010 [HIGH] — `backend/server.py` is a 6,487-line Monolith

**Issue:** All API routes are registered in a single file. FastAPI route registration is linear at startup — 6,487 lines of route registrations is slow to import and increases memory usage.

**Fix:** Split into sub-routers using FastAPI's `APIRouter`. This also improves hot-reload performance during development.

---

### PERF-011 [MEDIUM] — MongoDB Queries May Lack Indexes

**Issue:** The codebase uses MongoDB for persistent storage. Without explicit index creation in `db/` or `services/company_graph_store.py`, queries on large collections will do full collection scans.

**Fix:** Audit MongoDB queries, identify high-frequency query patterns, and create appropriate indexes (`createIndex` on startup or via migration).

---

## 6. Frontend Performance

### PERF-012 [MEDIUM] — Large Bundle from CRA + No Code Splitting

**Issue:** CRA (Create React App) generates a single large JavaScript bundle. Without React.lazy() and dynamic imports, the entire application loads on first visit.

**Fix:**
1. Migrate to Vite (which uses ESBuild and generates smaller bundles)
2. Add route-level code splitting for each screen
3. Enable gzip/brotli compression on the Vercel deployment

---

### PERF-013 [LOW] — No Client-Side API Response Caching

**Issue:** The frontend makes API calls on every screen render without caching responses. Frequently-accessed endpoints (model lists, agent status) are called repeatedly.

**Fix:** Add SWR or React Query for client-side request deduplication and caching.

---

## 7. Streaming Performance

### PERF-014 [LOW] — Streaming Chunks May Be Buffered

**Issue:** FastAPI's `StreamingResponse` is used for LLM token streaming. If intermediate buffers accumulate chunks before flushing, time-to-first-token is degraded.

**Fix:** Verify `StreamingResponse` uses `media_type="text/event-stream"` and that uvicorn is configured with `--no-buffer` for streaming routes.

---

## Performance Benchmarks — Recommended Baselines

| Metric | Current (estimated) | Target |
|--------|---------------------|--------|
| Auth middleware overhead | ~2ms | <1ms |
| Rate limit check | ~1ms (sync lock) | <0.5ms (async) |
| Router decision time | ~5ms (on cache miss) | <1ms |
| Time to first token (streaming) | Ollama-dependent | Ollama-dependent |
| Agent step execution | 30-120s per step | 20-80s |
| Frontend initial load | ~3-5s (est.) | <2s |

---

## Priority Matrix

| ID | Severity | Effort | Impact | Priority |
|----|----------|--------|--------|----------|
| PERF-001 | High | Low | High throughput | **Immediate** |
| PERF-007 | High | Medium | Agent speed | **Sprint 1** |
| PERF-010 | High | High | Startup time | **Sprint 2** |
| PERF-003 | Medium | Low | Request latency | **Sprint 1** |
| PERF-004 | Medium | Low | Observability overhead | **Sprint 1** |
| PERF-005 | Medium | Low | Routing latency | **Sprint 1** |
| PERF-008 | Medium | Medium | Agent reliability | **Sprint 2** |
| PERF-009 | Medium | Medium | Codebase analysis | **Sprint 2** |
| PERF-011 | Medium | Medium | DB query speed | **Sprint 2** |
| PERF-012 | Medium | High | Frontend UX | **Sprint 3** |
| PERF-002 | Medium | Low | Memory usage | **Sprint 1** |
| PERF-006 | Low | Low | Routing speed | **Sprint 3** |
| PERF-013 | Low | Low | Frontend UX | **Sprint 3** |
| PERF-014 | Low | Low | Streaming UX | **Sprint 2** |
