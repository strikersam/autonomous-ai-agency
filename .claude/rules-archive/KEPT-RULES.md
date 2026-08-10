# Kept Rules — the 44 that survive the audit

> Proposal, not yet in force. `CLAUDE.md`, `AGENTS.md`, and `ENGINEERING_STANDARDS.md`
> are unchanged. This file is what would replace their normative content if you
> approve it. See `REMOVED-RULES.md` for what was cut and `CONFLICTS.md` for the
> contradictions that had to be resolved before these could be written.

**Survival test applied to each rule:** an agent that had never seen it would
get this repo wrong. Rules describing generally-good engineering, or that
restate what the Claude Code harness already instructs, did not survive.

---

## A. Prime directive

1. Do not change user-visible behaviour that was not requested. If a refactor
   could alter an output, capture the before/after and revert on any difference.

## B. Wiring — where things must go

2. All LLM/provider calls go through `packages/ai/router.py` (ProviderManager).
   Never call a provider SDK or HTTP endpoint directly.
3. Every provider implements `generate`, `chat`, `stream`, `health`, `cost`, `limits`.
4. Failover chain is Cerebras → Groq → NVIDIA NIM → Ollama. `429` → failover plus
   exponential backoff; `410` → permanent removal plus long cooldown; `419` → skip
   that model only and try the next on the same provider.
5. Read environment variables only in config modules: `packages/ai/brain.py`,
   `packages/ai/brain_config.py`, `app_settings.py`, `packages/config/`. No
   `os.environ.get()` anywhere else.
6. Secrets are environment-only: never written to disk, never logged (not even
   partially), never in test files.
7. Frontend HTTP goes through the shared axios instance in `frontend/src/api.js`.
   No API calls elsewhere in the frontend.
8. One auth system: `get_current_user` / `get_optional_user`, `_require_admin` for
   admin surfaces, `verify_api_key` for the proxy surface, `X-Service-Token` for
   Telegram→backend only.
9. One `BrainConfig` model, in `packages/ai/brain_config.py`. The scheduler decides
   and workers execute; workers emit events and never touch the UI.

## C. Security invariants

10. Every new endpoint is authenticated. The only unauthenticated endpoints are
    `/health`, `/version`, and `/api/doctor/public`.
11. Validate request bodies with Pydantic v2 models before use. No raw `dict` as an
    external-facing return type.
12. `subprocess` in list form only — never `shell=True` with interpolated data.
13. Agent file writes go through `WorkspaceTools._resolve_path()`. Never widen the
    workspace boundary.
14. Any externally-influenced URL — direct user input, LLM-constructed, or read out
    of fetched content — must pass `unsafe_target_reason()` in `agent/web_reach.py`
    before the first request, and every redirect hop must be re-validated. Never call
    `httpx` with `follow_redirects=True` on such a URL.

## D. Risky modules

15. Run the `risky-module-review` skill before modifying `admin_auth.py`,
    `key_store.py`, `agent/tools.py`, the `proxy.py` auth middleware,
    `handlers/v3_auth.py`, `rbac.py`, or `social_auth.py`.

## E. Agent loop invariants (`agent/`)

16. The Verifier must return `pass` before `apply_diff()` runs. Never bypass it.
17. `max_steps` is always enforced; per-file retry limit is 3; JSON extraction retries
    3 times and then raises rather than swallowing.
18. `_local_syntax_check()` runs before verification — it catches parse errors cheaply.
19. Registering a tool in the capability registry is silent. The Executor only calls
    tools listed by `build_tool_prompt()` in `agent/prompts.py` — add it there too.
20. `_commit_step()` commits only `changed_files`, never the whole working tree.

## F. Router invariants (`router/`)

21. `route()` never raises. It returns a `RoutingDecision` with a non-empty
    `resolved_model` and a list `fallback_chain`, falling back to defaults on failure.
22. `is_model_available()` returns `True` when health checks are disabled. This is the
    safe-degrade path — never invert it.
23. A new model needs a `MODEL_REGISTRY` entry with accurate `strengths` and
    `cost_tier`, plus a routing test in `tests/test_model_router.py`.

## G. Conventions that are not inferable from the code

24. `from __future__ import annotations` at the top of every module; type hints on all
    public functions.
25. All I/O is async; no blocking I/O in async context. Exception: `WorkspaceTools` is
    legacy sync — do not add new sync I/O there.
26. Module logger is `log = logging.getLogger("qwen-proxy")`. Use `%s` lazy formatting.
    Use `logging`, never `print()`.
27. Never return internal error detail to a client: raise
    `HTTPException(status_code=..., detail="<generic message>")` and `log.exception()`
    separately.
28. Max 50 lines per function; max 800 lines per Python file. Two exceptions are on
    record in `AGENTS.md` (`packages/config/control_catalogue.py`,
    `services/ceo_dispatcher.py`) — add to that list rather than silently exceeding.
29. Comment only where the *why* is non-obvious. Docstrings on public functions.

## H. Tests

30. Run `pytest -x` before commit and before push (the pre-push hook enforces it). If
    the baseline is already red, report that before fixing anything.
31. New endpoint → a test. Bug fix → a regression test that fails first. A test body of
    only `pass` fails review.
32. Tests are hermetic. The `client` fixture is function-scoped and calls
    `reset_store()` to avoid motor event-loop binding; reset module singletons with
    `monkeypatch.setattr(module, "_store", None)`.
33. Test environment is `TESTING=true`, `AGENCY_CEO_ENABLED=false`,
    `RUN_BACKGROUND_IN_WEB=false` (set in conftest). Tests needing real credentials are
    marked `@pytest.mark.live`. Layout: `tests/test_<module>.py`,
    `tests/test_<feature>_integration.py`, `tests/e2e/`.

## I. Ship gates

34. Every behaviour-changing PR adds an entry under `## [Unreleased]` in **both**
    `CHANGELOG.md` and `docs/changelog.md`, kept byte-identical
    (`python scripts/check_changelog_parity.py`). Commits prefixed `chore:`, `docs:`,
    `ci:`, `test:`, `style:`, `revert:`, or `build:` are exempt — the `commit-msg` hook
    keys off exactly these prefixes.
35. A new or changed workflow requires a `loops/registry.yaml` update and a green
    `python agent/loop_registry.py audit --check`.
36. `python -m compileall -q .` must be clean.
37. A new env var is documented in `docs/configuration-reference.md` and `.env.example`.
    A new endpoint is documented in `docs/api-surfaces.md`.
38. Squash-merge to `master`, only with CI green. Never force-push to `master`. Never
    `--no-verify` or otherwise bypass a hook or CI check — fix the root cause.

## J. Autonomy limits

39. Query the knowledge graph before reading raw source: `graphify query "..."`,
    `graphify explain "..."`, `graphify path "A" "B"`, or `graphify-out/GRAPH_REPORT.md`.
    Run `graphify update .` after making changes.
40. Stop and ask a human before: modifying a risky module (rule 15), a database
    migration, a change to GitHub Actions permissions, a breaking API or schema change,
    a dependency upgrade with a breaking change, or a change spanning more than 5 files
    in `proxy.py`, `router/`, or `agent/loop.py`.
41. Production safety: database and API changes stay backward-compatible;
    `CORS_ORIGINS` is never `*` in production; `RATE_LIMIT_RPM` is always set; API
    responses carry `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, and
    `X-Frame-Options: DENY`.
42. `GH_PAT` is the only GitHub credential. It is read at runtime by the git credential
    helper — never paste a token into config, code, a commit, a workflow file, or chat.

## K. Session state

43. `.claude/state/` is tracked in git. Never write credentials, PII, or raw
    request/response payloads there. Session-private material goes in
    `.claude/state/sessions/<session-id>/`, which is gitignored.
44. Update `.claude/state/active-tasks.md` at milestones and `NEXT_ACTION.md` before
    ending a session.
