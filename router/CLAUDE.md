# CLAUDE.md — router/

> Model routing affects every request in the system.
>
> The invariants you must not break are `CLAUDE.md` rules 21–23. Read those first. This
> file covers how selection works and how to extend it.

---

## What this package does

The central model-selection layer for all API surfaces.

| File | Role |
|------|------|
| `model_router.py` | `ModelRouter.route()` → `RoutingDecision` |
| `classifier.py` | `classify_task()` → task category string |
| `registry.py` | Model capability registry, `best_model_for()` |
| `health.py` | Ollama `/api/tags` health check with TTL cache |

Selection priority, highest first:

1. Manual override — `X-Model-Override` header or `override_model` kwarg
2. `MODEL_MAP` env var, or the built-in Anthropic alias table
3. Heuristic — task classification into a capability-registry lookup
4. Default — `AGENT_EXECUTOR_MODEL`

Local Ollama model names are passthrough: they bypass the alias table entirely and
resolve to `RoutingDecision(selection_source="passthrough")`.

The health check is cached with TTL `ROUTER_HEALTH_CACHE_TTL` (default 60s). The cache is
deliberately invalidated before fallback retries — that is not a bug.

---

## Adding a model

1. Add an entry to `MODEL_REGISTRY` in `registry.py`.
2. Set `strengths` accurately — it drives heuristic selection.
3. Set `cost_tier` (1 = cheapest) — it drives fast-response routing.
4. Add a routing test in `tests/test_model_router.py` (rule 23).
5. Update `docs/architecture/overview.md` if the capability profile changes.

## Adding a task category

1. Add the category string to `classifier.py`.
2. Add its matching logic — keyword, heuristic, or metadata.
3. List the category in `strengths` on the `MODEL_REGISTRY` entries that serve it.
4. Add tests under "Task classification" in `tests/test_model_router.py`.

---

## Environment variables

| Variable | Effect |
|----------|--------|
| `MODEL_MAP` | Colon-separated alias overrides, e.g. `claude-sonnet-4-6:deepseek-r1:32b` |
| `ROUTER_EXTRA_MODELS` | Add models at runtime: `name:type:strength1+strength2` |
| `ROUTER_HEALTH_CHECK_ENABLED` | `false` disables health filtering (useful in tests) |
| `ROUTER_HEALTH_CACHE_TTL` | Health cache TTL in seconds (default 60) |
| `ROUTER_FAST_RESPONSE_CHARS` | Char threshold for `fast_response` classification (default 200) |
| `AGENT_EXECUTOR_MODEL` | Final fallback when nothing else resolves |

---

## Testing

All router tests are in `tests/test_model_router.py`:

```bash
pytest -x tests/test_model_router.py
```

Always cover after a change: manual override still wins; the built-in alias table maps
correctly; heuristic fallback fires when no alias matches; health-check bypass works with
`ROUTER_HEALTH_CHECK_ENABLED=false`; `reset_router()` isolates the singleton between
tests.
