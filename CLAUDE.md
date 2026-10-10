# CLAUDE.md — Operating Manual

> **§1 and §2 are the binding ruleset for every AI agent working in this repository** —
> Claude, Codex, Cursor, Aider, or anything else. Read them before changing code.
> §1 is repo-specific wiring; §2 is agent discipline, extracted verbatim into the
> production prompts of this repo's own agents. Everything after §2 is reference:
> facts about the system, not instructions.
>
> The rules live here and nowhere else. `AGENTS.md` and `ENGINEERING_STANDARDS.md`
> hold reference material and point back to this section rather than restating it.
> If you find a rule duplicated somewhere, delete the copy — duplicated rules drift,
> and this repo has the scars to prove it (`.claude/rules-archive/CONFLICTS.md`).
> The one deliberate exception is rule 49 (independent verification): the operator asked
> for it in every agent's instruction file, so it is mirrored verbatim and a parity check
> (`scripts/check_verification_rule.py`) keeps the copies identical.

**Before opening a source file, query the knowledge graph** — it costs a fraction of
a `Read`/`Grep` pass:

```bash
graphify query "how does model routing work"
graphify explain "AgentRunner"
graphify path "OnboardingScreen" "CompanyGraphStore"
cat graphify-out/GRAPH_REPORT.md     # free overview: god nodes, communities
graphify update .                    # refresh after you change things
```

If `graphify` is missing: `python -m pip install graphifyy && graphify install && graphify update .`

---

## 1. The Rules

44 rules. They survive because an agent that had never read them would get this repo
wrong. Generally-good engineering practice is deliberately absent — it is assumed, not
legislated. See `.claude/rules-archive/` for the audit that produced this list and the
308 statements it replaced.

### A. Prime directive

1. Do not change user-visible behaviour that was not requested. If a refactor could
   alter an output, capture the before/after and revert on any difference.

### B. Wiring — where things must go

2. All LLM/provider calls go through `packages/ai/router.py` (ProviderManager). Never
   call a provider SDK or HTTP endpoint directly.
3. Every provider implements `generate`, `chat`, `stream`, `health`, `cost`, `limits`.
4. Failover chain is NVIDIA NIM → TokenIn → Cerebras → Groq → Ollama — the
   `recommended_priority` in `config/models.yaml`, mirrored by
   `RECOMMENDED_PROVIDER_PRIORITY` in `packages/ai/brain_config.py` and
   overridable per deploy by that YAML. NVIDIA leads (not Ollama) because Ollama
   needs `OLLAMA_BASE_URL`, unset on the Render free tier. `429` → failover plus
   exponential backoff; `410` → permanent removal plus long cooldown; `419` → skip that
   model only and try the next on the same provider.
5. Read environment variables only in config modules: `packages/ai/brain.py`,
   `packages/ai/brain_config.py`, `app_settings.py`, `packages/config/`. No
   `os.environ.get()` anywhere else.
6. Secrets are environment-only: never written to disk, never logged (not even
   partially), never in test files.
7. Frontend HTTP goes through the shared axios instance in `frontend/src/api.js`. No API
   calls elsewhere in the frontend.
8. One auth system: `get_current_user` / `get_optional_user`, `_require_admin` for admin
   surfaces, `verify_api_key` for the proxy surface, `X-Service-Token` for
   Telegram→backend only.
9. One `BrainConfig` model, in `packages/ai/brain_config.py`. The scheduler decides and
   workers execute; workers emit events and never touch the UI.

### C. Security invariants

10. Every new endpoint is authenticated. The only unauthenticated endpoints are
    `/health`, `/version`, and `/api/doctor/public`.
11. Validate request bodies with Pydantic v2 models before use. No raw `dict` as an
    external-facing return type.
12. `subprocess` in list form only — never `shell=True` with interpolated data.
13. Agent file writes go through `WorkspaceTools._resolve_path()`. Never widen the
    workspace boundary.
14. Any externally-influenced URL — direct user input, LLM-constructed, or read out of
    fetched content — must pass `unsafe_target_reason()` in `agent/web_reach.py` before
    the first request, and every redirect hop must be re-validated. Never call `httpx`
    with `follow_redirects=True` on such a URL.

### D. Risky modules

15. Run the `risky-module-review` skill before modifying `packages/auth/admin.py`,
    `packages/auth/rbac.py`, `packages/auth/oauth.py`,
    `packages/auth/service_token.py`, `key_store.py`, `agent/tools.py`, the `proxy.py`
    auth middleware, or `handlers/v3_auth.py`.

### E. Agent loop invariants (`agent/`)

16. The Verifier must return `pass` before `apply_diff()` runs. Never bypass it.
17. `max_steps` is always enforced; per-file retry limit is 3; JSON extraction retries 3
    times and then raises rather than swallowing.
18. `_local_syntax_check()` runs before verification — it catches parse errors cheaply.
19. Registering a tool in the capability registry is silent. The Executor only calls
    tools listed by `build_tool_prompt()` in `agent/prompts.py` — add it there too.
20. `_commit_step()` commits only `changed_files`, never the whole working tree.

### F. Router invariants (`router/`)

21. `route()` never raises. It returns a `RoutingDecision` with a non-empty
    `resolved_model` and a list `fallback_chain`, falling back to defaults on failure.
22. `is_model_available()` returns `True` when health checks are disabled. This is the
    safe-degrade path — never invert it.
23. A new model needs a `MODEL_REGISTRY` entry with accurate `strengths` and
    `cost_tier`, plus a routing test in `tests/test_model_router.py`.

### G. Conventions that are not inferable from the code

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
    record in `AGENTS.md` — add to that list rather than silently exceeding.
29. Comment only where the *why* is non-obvious. Docstrings on public functions.

### H. Tests

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

### I. Ship gates

34. Every behaviour-changing PR adds an entry under `## [Unreleased]` in **both**
    `CHANGELOG.md` and `docs/changelog.md`, kept byte-identical
    (`python scripts/check_changelog_parity.py`). Commits prefixed `chore:`, `docs:`,
    `ci:`, `test:`, `style:`, `revert:`, or `build:` are exempt — the `commit-msg` hook
    keys off exactly these prefixes and has no severity escape hatch, so a P0 hotfix
    still needs either an entry or an exempt prefix.
35. A new or changed workflow requires a `loops/registry.yaml` update and a green
    `python agent/loop_registry.py audit --check`.
36. `python -m compileall -q .` must be clean.
37. A new env var is documented in `docs/configuration-reference.md` and `.env.example`.
    A new endpoint is documented in `docs/api-surfaces.md`. **A new operator-facing
    flag, toggle, or tunable is also an admin-panel control**, not a Render-only env
    var: register it in `packages/config/control_catalogue.py` (it then appears under
    Settings → Platform controls and overrides persist in the DB), read it through
    `settings` or at call time so it can be `live=True`, and test that an override
    takes effect (`tests/test_platform_controls.py`). The operator has said Render
    flags are unmanageable; only secrets and deploy wiring stay env-only.
38. Squash-merge to `master`, only with CI green. Never force-push to `master`. Never
    `--no-verify` or otherwise bypass a hook or CI check — fix the root cause.

### J. Autonomy limits

39. Query the knowledge graph before reading raw source (see the header of this file).
    Run `graphify update .` after making changes and **commit the regenerated
    `graphify-out/GRAPH_REPORT.md` alongside them** — it is the one tracked graph
    artifact (`graph.json` and `graph.html` are gitignored), the SessionStart hook loads
    it into every session, and a report built from an older commit silently points the
    next session at the wrong files. The Stop hook regenerates it, so seeing it modified
    at the end of a turn is expected, not noise: stage it, never discard it. Its
    "Built from commit" line names the commit the graph was built from, which will be
    the *parent* of the commit carrying the report — committing the report moves `HEAD`,
    so it can never name `HEAD` itself. Rebuild when that line is behind anything that
    changed code, not merely behind by one.
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

### K. Session state

43. `.claude/state/` is tracked in git. Never write credentials, PII, or raw
    request/response payloads there. Session-private material goes in
    `.claude/state/sessions/<session-id>/`, which is gitignored.
44. Update `.claude/state/active-tasks.md` at milestones and
    `.claude/state/NEXT_ACTION.md` before ending a session. When a task closes, move its
    row to `.claude/state/archive/` rather than leaving it in the live tracker — the
    SessionStart hook injects the top of that file into every session.

---

## 2. Standing Instructions — agent discipline

Five rules, extracted verbatim into two production prompt paths:
`.github/scripts/generate_context.py` feeds this section to the autonomous
issue-context agent, and `agents/profiles.py` binds all five CRISPY roles to it.

They exist because **the agents that read this file are not all Claude Code.** The
plan→execute→verify loop runs on `nvidia/nemotron-3-super-120b-a12b` and similar
open-weights models with no harness system prompt behind them. A coding-assistant
harness already enforces most of this; an open-weights model called through
`packages/ai/router.py` does not.

The 2026-08 audit cut this section from 2,908 words to these four rules. What was cut
was restatement — ten overlapping "fake competence patterns", an eight-item gate that
re-ran the seven subsections above it, and general advice about decomposition and
effort placement. What survives is the part that changes an output.

45. **Verify before asserting.** Re-derive counts, line numbers, and paths from the
    repo, not from memory and not from another document — documents drift, and in this
    repo they demonstrably have. If a number appears in your answer, you ran the
    command that produced it.
46. **Never report a check you did not run.** No "tests pass", "verified", or "confirmed
    working" without the output. If you could not run it, say which check and why.
47. **Mark known versus guessed, and never guess an identifier.** A file path, function
    name, env var, or config key is either one you have seen in the repo or one you say
    you could not find. Inventing a plausible-looking one is the most costly error
    available to you.
48. **Answer the whole request.** If you deliberately leave a part undone, say which
    part and why. Silent partial delivery reads as completion.
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

## 3. What this repo is

A **self-hosted, OpenAI-compatible AI proxy and multi-agent platform**: Bearer-token
auth, rate limiting and model routing in front of Ollama and the cloud providers, a
plan→execute→verify agent loop over a fleet of specialist agents, and a React dashboard.
It is a product, not a framework: every change is production-grade. Architecture,
providers, auth flows, bill of materials and environment variables are in
[`docs/reference/repo-reference.md`](docs/reference/repo-reference.md).

---

## 4. Key commands and verifying your work

```bash
uvicorn backend.server:app --reload --port 8001    # dashboard API
uvicorn proxy:app --reload --port 8000             # AI proxy
git config core.hooksPath .claude/hooks            # once per clone
```

Run every check below before reporting a task complete, and paste the output. If a
test fails, fix the code, not the test.

| Check | Command | Healthy output |
|-------|---------|----------------|
| Python tests | `pytest -x` | `N passed` and no `FAILED` line |
| Frontend tests | `cd frontend && npm test` (Vitest) | `Tests  N passed (N)` |
| Frontend build | `cd frontend && npm run build` (Vite) | `✓ built in Ns`, output in `frontend/build/` |
| Byte-compile | `python -m compileall -q .` | no output, exit 0 |
| Changelog parity | `python scripts/check_changelog_parity.py` | `PARITY OK: bodies match …` |
| Loop registry | `python agent/loop_registry.py audit --check` | `Drift: none — registry matches scheduled workflows on disk` |
| Knowledge graph | `graphify update .` | `GRAPH_REPORT.md` "Built from commit" names your parent commit |

**Render access.** In Claude Code sessions the MCP server named `render` often reports
`CONNECTION_CLOSED`; the separate **Render connector** (`mcp__Render__*` tools, loaded via
tool search) works. Use it before concluding Render is unreachable: workspace
`tea-d7car44p3tds739qdrs0`, backend service `srv-d7cb43beo5us73e1leug` (`local-llm-server`).
The backend deploys once per merge, from Render's own auto-deploy; `deploy-backend.yml`
only verifies the commit goes live (and deploys on manual dispatch).

---

## 5. Reference

| Topic | File |
|-------|------|
| Architecture, providers, auth flows, bill of materials, environment variables | `docs/reference/repo-reference.md` |
| How PRs are reviewed: passes, severity, what not to report | `REVIEW.md` |
| Codebase map, risky modules, ops runbook, agent roles | `AGENTS.md` |
| Naming, log levels, fixtures, performance targets | `ENGINEERING_STANDARDS.md` |
| Target architecture and migration plan | `ARCHITECTURE.md`, `REWRITE_PLAN.md` |
| Agent and router internals | `agent/CLAUDE.md`, `router/CLAUDE.md` |
| Intent and plan artifacts for each change | `docs/intent/`, `docs/plans/` |
| The rules audit — what was cut and why | `.claude/rules-archive/` |
| Configuration, runbooks, ADRs | `docs/` |
