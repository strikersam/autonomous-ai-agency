# CLAUDE.md — router/

> Model routing affects every request in the system.
>
> The invariants you must not break are `CLAUDE.md` rules 21–23. Read those first. This
> file covers how selection works and how to extend it.


## Verification rule (mirrored from CLAUDE.md §2, binding on every agent)

<!-- pstack-verification:start -->
49. **No "done" without an independent verifier (pstack).** Before any task is reported
    done, by a coding agent or by an agency agent, a verifier that did not write the
    change exercises the real artifact (runs the feature, the tests, the built page; not
    "it compiles", not the author's own report) and returns `PASS`, `PASS+NOTES`, or
    `FAIL` with the evidence it observed. `FAIL` sends the work back. Only `PASS` or
    `PASS+NOTES` permits a done claim, and the report quotes that verdict. Work in small
    units that each end in a check, and verify each before starting the next. Source:
    pstack's `principle-prove-it-works` and its independent per-PR verdict
    (github.com/cursor/plugins/tree/main/pstack, github.com/michael-denyer/pstack-claude).
    This rule is mirrored byte-for-byte in every agent instruction file;
    `python scripts/check_verification_rule.py` fails if a copy drifts.
<!-- pstack-verification:end -->

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
| `DENIED_MODEL_IDS` | Operator deny-list (`packages/ai/model_policy.py`): `route()` moves a denied `resolved_model` to the next allowed fallback and drops denied ids from `fallback_chain`; if every option is denied the decision is left unchanged so `resolved_model` stays non-empty (rule 21) and dispatch refuses it |
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
