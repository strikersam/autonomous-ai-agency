# Repo Checkup — July 2026

**Date:** 2026-07-10 · **Branch:** `claude/repo-checkup-improvements-hohdjv`

> **What this is:** a read-only health audit of the repository against its own constitution
> (`CLAUDE.md` §0–§13), followed by six **copy-paste-ready implementation prompts** sized for a
> lower-tier model to execute one PR at a time.
>
> **How to use it:** pick a prompt from Part B (they are ordered by value ÷ risk — start at P1),
> paste it verbatim into the implementing model, and review the resulting diff. Every finding in
> Part A ships with the exact command used to detect it, so each one can be re-verified before and
> after a fix.
>
> **PR titling:** this checkup document itself is `docs:`-prefixed (changelog-gate exempt per
> CLAUDE.md §12). The fixes in P2–P6 are **not** exempt — their prompts include the
> `CHANGELOG.md` + `docs/changelog.md` parity step.

All numbers below were measured on branch `claude/repo-checkup-improvements-hohdjv` at the time of
writing (July 2026). The repo moves fast — re-run the evidence command before acting on any number.

---

## Part A — Health Report

| # | Finding | Severity | Fix effort | Prompt |
|---|---------|----------|-----------|--------|
| F1 | CLAUDE.md/AGENTS.md reference **files that no longer exist** and stale counts | **High** (misleads every agent session) | Low (docs only) | P1 |
| F2 | 15 of 43 checked-in skills have **no frontmatter `description`** → degraded skill routing | Medium | Low | P2 |
| F3 | `packages/ai/router.py` reads `os.environ` **68 times** directly (constitution: config modules only) | Medium | Medium | P3 |
| F4 | `print()` in ~30 importable production modules (constitution: logging only) | Low-Medium | Low | P4 |
| F5 | `graphify-refresh` SessionStart hook prints an install nag every session when graphify is absent | Low | Trivial | P5 |
| F6 | `backend/server.py` is **9,667 lines / 243 functions**; `proxy.py` 4,098; five more files >1,600 | High (long-term) | High | P6 (first slice only) |

### F1 — CLAUDE.md documents an architecture that no longer exists

CLAUDE.md (§4, §5, §8, secrets table, env table) tells every agent that provider routing and brain
config live in these modules — **none of which exist**:

| CLAUDE.md says | Reality (verify before writing!) |
|---|---|
| `provider_router.py` (root, "1400+ lines") | Deleted. Routing is split between `packages/ai/router.py` (provider failover/brain routing) and `router/` (`model_router.py`, `classifier.py`, `circuit_breaker.py`, `harness_routing.py`) |
| `brain_policy.py` (root) | Deleted. Successor logic in `packages/ai/` (`brain.py`, `brain_config.py`); `backend/server.py` still exposes `brain_policy`-named endpoints (~line 3851) |
| `services/brain_config_store.py` | Deleted → `packages/ai/brain_config.py` |
| `services/brain_watchdog.py` | Deleted → `packages/ai/watchdog.py` |

Stale counts in the Bill of Materials: `server.py` is 9,667 lines (doc says "8700+"), 33 root-level
`.py` files (doc says 38), 40 GitHub workflow files (doc says 21 scheduled workflows), 311 test
files in `tests/` (doc says 297).

Evidence:
```bash
ls provider_router.py brain_policy.py services/brain_config_store.py services/brain_watchdog.py
# → all: No such file or directory
wc -l backend/server.py proxy.py          # 9667 / 4098
ls *.py | wc -l                            # 33
ls .github/workflows | wc -l               # 40
ls tests/*.py | wc -l                      # 311
```

**Why it matters:** CLAUDE.md is read *first* by every AI session and claims to "supersede
agent-specific instructions." An agent told to route all LLM calls through a file that doesn't
exist will either waste tokens hunting for it or, worse, recreate it — the exact duplicate-logic
failure the constitution forbids.

### F2 — 15 skills have no frontmatter description

Skills whose `SKILL.md` frontmatter lacks a `description:` key fall back to their first heading in
the session skill listing (e.g. literally "Skill: Agentic Agile"), which tells the routing model
nothing about *when* to invoke them. The 15:

`agentic-agile`, `agentic-portfolio`, `ai-engineering-insights`, `ecc-harness-patterns`,
`graphiti-temporal`, `karpathy-guidelines`, `managed-agents-dreams`, `multi-agent`,
`obsidian-knowledge-graph`, `research-coordinator`, `session-planning`, `stop-slop-quality`,
`superclaude-commands`, `user-research`, `workflow-engine`

Evidence:
```bash
for d in .claude/skills/*/; do f="$d/SKILL.md"; [ -f "$f" ] || continue; \
  desc=$(awk '/^---$/{c++; next} c==1 && /^description:/{print; exit}' "$f"); \
  [ -z "$desc" ] && basename "$d"; done
```

### F3 — Direct `os.environ` reads outside config modules

Constitution rule: "No `os.environ.get()` outside of config modules — centralize in
`brain_policy.py` / `app_settings.py`" (the sanctioned module today is
`packages/config/settings.py`, which legitimately holds 52 reads). Top offenders:

| File | `os.environ` occurrences |
|---|---|
| `packages/ai/router.py` | 68 |
| `telegram_bot.py` | 21 |
| `proxy.py` | 16 |
| `providers/kimi_bridge.py` | 11 |
| `webui/providers.py` | 11 |
| `agents/profiles.py` | 10 |
| `packages/ai/brain.py` | 9 |
| `packages/ai/brain_config.py` | 8 |
| `services/self_bootstrap.py` | 7 |
| `services/openclaw_gateway.py` | 6 |

Evidence: `grep -c "os.environ" packages/ai/router.py` etc.

### F4 — `print()` in importable production modules

~30 non-test production files contain `print()` (constitution: "No `print()` — use `logging`").
The two big apps are nearly clean (`backend/server.py`: 2, `proxy.py`: 1); the bulk sits in
`agent/` (7 files), `agents/` (4), `services/` (6), `packages/scheduler/scheduler.py`, and
`backend/hello_claude.py`. Root-level CLI scripts (`launcher.py`, `setup_local_models.py`,
`start_tunnel*.py`, `setup_ngrok.py`, `run-claude-code.py`, `task_runner.py`) also print, but CLI
entry points writing to stdout is arguably user-visible behaviour — see P4's scoping.

Evidence:
```bash
grep -rln "print(" --include="*.py" backend/ services/ agent/ router/ packages/ webui/ agents/ providers/ *.py \
  | grep -v -E "test|conftest|__pycache__"
```

### F5 — graphify hook nags every session

`.claude/hooks/graphify-refresh` is otherwise well built (never fails a turn, exits 0 when
graphify is absent), but in `--session` mode it prints
`[graphify] not installed — run: python -m pip install graphifyy …` at the start of **every**
session where graphify isn't on PATH — including every fresh remote container. Pure noise after
the first time.

### F6 — God files

| File | Lines |
|---|---|
| `backend/server.py` | 9,667 (243 `def`s) |
| `proxy.py` | 4,098 |
| `agent/loop.py` | 2,362 |
| `models/company_graph.py` | 2,170 |
| `services/workflow_orchestrator.py` | 1,940 |
| `services/seo_audit.py` | 1,754 |
| `services/scanner.py` | 1,726 |
| `services/company_graph_store.py` | 1,716 |
| `backend/company_api.py` | 1,664 |
| `packages/ai/router.py` | 1,606 |

`server.py` grows with every feature; each merge into it raises conflict and regression risk.
REWRITE_PLAN Phase 5 started (the `packages/` tree exists and is imported by `proxy.py`,
`webui/`, `services/`) but stalled before the root/backend god files were decomposed.

### Healthy signals

- `python -m compileall` passes on the god files.
- Only 4 `TODO/FIXME/XXX/HACK` markers across `server.py` + `proxy.py`.
- `scripts/check_changelog_parity.py` and `agent/loop_registry.py audit` exist and match CLAUDE.md.
- Git hooks + Claude hooks are wired defensively (graphify wrapper never blocks a turn).

---

## Part B — Implementation Prompts

Rules that apply to **every** prompt below (each prompt restates them so it stands alone):

- One prompt = one branch = one PR. Do not combine.
- Golden Rule: **no user-visible behaviour change** unless the prompt explicitly says otherwise.
- P2–P6 must add an entry under `## [Unreleased]` in **both** `CHANGELOG.md` and
  `docs/changelog.md` (CI enforces parity). P1 uses a `docs:` title and is exempt.
- Always finish with `python -m compileall -q .` and `pytest -x` before committing.

---

### P1 — Refresh CLAUDE.md and AGENTS.md to match the real architecture

> **Copy everything in this block into the implementing model.**
>
> You are updating stale documentation in the repo `autonomous-ai-agency`. This is a
> **docs-only** change: you may edit `CLAUDE.md` and `AGENTS.md` and nothing else. Do not touch
> any `.py`, `.js`, or config file. Title the PR/commit `docs: sync CLAUDE.md/AGENTS.md with
> packages/ architecture`. Because of the `docs:` prefix you do NOT need changelog entries.
>
> **The problem:** CLAUDE.md references modules that were deleted during the `packages/`
> migration, so every AI agent reading it is misdirected.
>
> **Step 1 — verify before you write.** For each of these claims, run the check and record the
> result. Do NOT trust this prompt's mapping blindly — verify each one:
> ```bash
> ls provider_router.py brain_policy.py services/brain_config_store.py services/brain_watchdog.py  # expect: missing
> ls packages/ai/          # expect: router.py, brain.py, brain_config.py, watchdog.py, ...
> ls router/               # expect: model_router.py, classifier.py, circuit_breaker.py, ...
> ls packages/config/      # expect: settings.py
> wc -l backend/server.py proxy.py
> ls *.py | wc -l
> ls .github/workflows | wc -l
> ls tests/*.py | wc -l
> grep -rn "class BrainConfig" --include="*.py" . | grep -v graphify-out
> ```
> **Step 2 — fix every stale reference in CLAUDE.md.** Search for each dead path and replace it
> with the verified successor. Known dead → successor pairs (re-verify each):
> - `provider_router.py` → provider failover/brain routing: `packages/ai/router.py`; model
>   selection/classification: `router/model_router.py` + `router/classifier.py`. Where CLAUDE.md
>   says "No new provider implementation may bypass `ProviderManager` / all LLM calls go through
>   `provider_router.py`", open `packages/ai/router.py`, find the actual class/entry point that
>   plays this role, and name that.
> - `brain_policy.py` → open `packages/ai/brain.py` and `packages/ai/brain_config.py`, determine
>   which one resolves the recommended brain, and reference it. Note in the doc that
>   `backend/server.py` still exposes `/api/brain/policy`-style endpoints.
> - `services/brain_config_store.py` → `packages/ai/brain_config.py`
> - `services/brain_watchdog.py` → `packages/ai/watchdog.py`
> - `os.environ` rule ("Centralize in `brain_policy.py` / `app_settings.py`") → the sanctioned
>   config modules are now `packages/config/settings.py` and `app_settings.py`.
> Update the same references in the Secrets inventory and External providers tables, §5 (AI
> Provider Architecture "Current state"), and §8 if they appear there.
> **Step 3 — fix the Bill of Materials numbers** with the values you measured in Step 1 (lines
> for server.py, root .py count, workflow count, test count). Add `packages/` and `router/` to
> the "Current folder structure" tree.
> **Step 4 — same pass over AGENTS.md**: grep it for the four dead paths and fix any hits the
> same way.
> **Step 5 — verify:** `grep -rn "provider_router\|brain_policy\.py\|brain_config_store\|brain_watchdog" CLAUDE.md AGENTS.md`
> must return zero hits referring to them as existing files (historical/changelog mentions are
> fine if clearly past-tense). Run `python -m compileall -q .` (should be untouched/green).
> **Done when:** both docs describe only files that exist, all counts match Step 1 measurements,
> and the diff touches nothing but `CLAUDE.md` and `AGENTS.md`.

---

### P2 — Add real frontmatter descriptions to 15 skills

> **Copy everything in this block into the implementing model.**
>
> In repo `autonomous-ai-agency`, 15 files under `.claude/skills/*/SKILL.md` have YAML
> frontmatter without a `description:` key, so Claude Code's skill listing shows a useless
> placeholder and skill routing degrades. Fix ONLY the frontmatter of these 15 skills — do not
> change skill bodies, `name:` keys, or any other file:
> `agentic-agile, agentic-portfolio, ai-engineering-insights, ecc-harness-patterns,
> graphiti-temporal, karpathy-guidelines, managed-agents-dreams, multi-agent,
> obsidian-knowledge-graph, research-coordinator, session-planning, stop-slop-quality,
> superclaude-commands, user-research, workflow-engine`
>
> **For each skill:** read its SKILL.md body (Purpose/Usage sections), then add ONE
> `description:` line to the frontmatter following this template — a single sentence of what it
> does + "Use when …" trigger clause, max ~250 chars, YAML double-quoted:
> ```yaml
> ---
> name: agentic-agile
> description: "Agile sprint management via agents/agile_sprints.py — velocity tracking, burndown metrics, multi-sprint orchestration. Use when creating or managing sprints, user stories, or sprint health reports."
> ---
> ```
> If a file has NO frontmatter block at all, add one with `name:` (the directory name) and
> `description:`. If it has frontmatter with `name:` only, insert just the `description:` line.
> **Never** put the characters `{`, `}`, backtick, or unescaped `"` inside the description value.
> **Validate after each file:** the frontmatter must parse —
> `python -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]).read().split('---')[1])" <file>`
> **Changelog:** add one line under `## [Unreleased]` in BOTH `CHANGELOG.md` and
> `docs/changelog.md` (identical text): "Added frontmatter descriptions to 15 skills for reliable
> skill routing." Verify with `python scripts/check_changelog_parity.py`.
> **Done when:** all 43 `.claude/skills/*/SKILL.md` files have a parsing `description:`, the diff
> touches only frontmatter + the two changelogs, `pytest -x` and `python -m compileall -q .` pass.

---

### P3 — Centralize `packages/ai/router.py` env reads into `packages/config/settings.py`

> **Copy everything in this block into the implementing model.**
>
> In repo `autonomous-ai-agency`, the constitution (CLAUDE.md §3) forbids reading `os.environ`
> outside config modules, yet `packages/ai/router.py` contains ~68 direct reads. Move them behind
> accessors in the sanctioned config module `packages/config/settings.py`. **Behaviour must be
> byte-identical** — same env var names, same defaults, same types, same read timing.
>
> **Hard constraints:**
> 1. Reads must stay **lazy** (happen at call time, not import time). Provide accessor
>    *functions*, e.g. `def nvidia_api_key() -> str: return os.environ.get("NVIDIA_API_KEY", "")`
>    — NEVER module-level constants like `NVIDIA_API_KEY = os.environ.get(...)`, which freeze
>    values at import and break tests that monkeypatch the environment.
> 2. Before adding an accessor, check whether `packages/config/settings.py` (or `app_settings.py`)
>    already exposes one for that variable — reuse, don't duplicate.
> 3. Do not rename, re-default, or coerce any variable differently than the original call site
>    did. `os.environ["X"]` (raising KeyError) and `os.environ.get("X", d)` are DIFFERENT —
>    preserve which one each site used.
> 4. Scope: `packages/ai/router.py` only. Do not touch the other offenders in this PR.
>
> **Steps:** (a) `grep -n "os.environ" packages/ai/router.py` and build a table: line, var name,
> default, access style. (b) For each distinct variable, find or add a lazy accessor in
> `packages/config/settings.py`. (c) Replace each read in router.py with the accessor call and
> remove the now-unused `os` import only if truly unused. (d) Verify:
> `grep -c "os.environ" packages/ai/router.py` must be 0;
> `python -m compileall -q .`; `pytest -x`; also run any router-specific tests:
> `pytest -x -k "router or brain or provider"`.
> **Changelog:** identical entry under `## [Unreleased]` in BOTH `CHANGELOG.md` and
> `docs/changelog.md`: "Centralized packages/ai/router.py environment reads into
> packages/config/settings.py accessors (no behaviour change)." Verify with
> `python scripts/check_changelog_parity.py`.
> **Done when:** zero `os.environ` in router.py, all tests green, diff touches only
> `packages/ai/router.py`, `packages/config/settings.py`, and the two changelogs.

---

### P4 — Replace `print()` with `logging` in importable production modules

> **Copy everything in this block into the implementing model.**
>
> In repo `autonomous-ai-agency`, the constitution forbids `print()` in production code. Convert
> `print()` calls to `logging` in **importable library/server modules only**. Run this to get the
> current offender list:
> ```bash
> grep -rln "print(" --include="*.py" backend/ services/ agent/ agents/ packages/ webui/ providers/ router/ \
>   | grep -v -E "test|conftest|__pycache__"
> ```
> **In scope:** files under `agent/`, `agents/`, `services/`, `packages/`, `backend/`, `webui/`,
> `providers/`, `router/` from that list.
> **OUT of scope — do not touch:** root-level CLI/setup scripts (`launcher.py`,
> `setup_local_models.py`, `setup_ngrok.py`, `start_tunnel*.py`, `run-claude-code.py`,
> `task_runner.py`, `activation.py`, `infra_cost.py`, `log_watcher.py`, `service_daemon.py`) —
> their stdout IS their user interface; converting it would change user-visible behaviour.
> Also skip any `print()` inside an `if __name__ == "__main__":` block even in in-scope files.
>
> **Per file:** ensure `import logging` and a module logger
> `logger = logging.getLogger(__name__)` exist (reuse an existing logger if the file has one —
> check first). Convert `print(x)` → `logger.info(x)`, keeping the message text EXACTLY as-is;
> use `logger.error(...)` only where the print is clearly an error path (inside `except` blocks).
> Preserve f-strings as they are — do not convert to %-style. Do not add try/except, do not
> reflow surrounding code.
> **Verify:** the grep above returns no in-scope files;
> `python -m compileall -q .`; `pytest -x`.
> **Changelog:** identical entry in BOTH `CHANGELOG.md` and `docs/changelog.md` under
> `## [Unreleased]`: "Replaced print() with logging in importable production modules (no
> behaviour change; CLI scripts unchanged)." Verify with
> `python scripts/check_changelog_parity.py`.
> **Done when:** zero `print()` in in-scope importable modules outside `__main__` blocks, tests
> green, CLI scripts untouched.

---

### P5 — Silence the per-session graphify install nag

> **Copy everything in this block into the implementing model.**
>
> In repo `autonomous-ai-agency`, edit ONLY `.claude/hooks/graphify-refresh`. Today, when the
> `graphify` command is not installed and the hook runs in `--session` mode, it echoes an install
> instruction — every single session, which is noise in ephemeral containers where graphify is
> never installed. Change: print the nag only if the marker file
> `graphify-out/GRAPH_REPORT.md` exists (i.e. the repo clearly expects graphify but the binary is
> missing) — otherwise stay silent. Keep everything else identical: still `exit 0`, still never
> block the turn, `--background` mode unchanged. The current block reads:
> ```sh
> if ! command -v graphify >/dev/null 2>&1; then
>   if [ "$MODE" = "--session" ]; then
>     echo "[graphify] not installed — run: python -m pip install graphifyy && graphify install && graphify update ."
>   fi
>   exit 0
> fi
> ```
> Wrap the `echo` in an additional `if [ -f "$REPORT" ]; then … fi` (note: `$REPORT` is defined
> above this block in the script — reuse it). Verify with `sh -n .claude/hooks/graphify-refresh`
> (syntax check) and by running `.claude/hooks/graphify-refresh --session` in an environment
> without graphify: it must exit 0. Since this is CI/tooling only, title the commit
> `chore: silence graphify session nag when graph output absent` — the `chore:` prefix skips the
> changelog gate, so no changelog entries are needed.
> **Done when:** the diff touches only that one file and the hook exits 0 silently when both
> graphify and the report are absent.

---

### P6 — (Advanced, optional) First extraction slice from `backend/server.py`

> ⚠️ Only attempt with a green CI baseline on master, and stop rather than force it if the
> characterization tests won't pass. This is the ONLY prompt with real regression risk.
>
> **Copy everything in this block into the implementing model.**
>
> In repo `autonomous-ai-agency`, `backend/server.py` is 9,667 lines with 243 functions. You will
> extract exactly ONE cohesive endpoint group into a FastAPI `APIRouter` module, changing zero
> behaviour. Target group: the **auth endpoints** (`/api/auth/login`, `/api/auth/register`,
> refresh, and the GitHub/Google OAuth callback routes — find them with
> `grep -n '@app\.\(get\|post\|put\|patch\|delete\)("/api/auth' backend/server.py`).
>
> **Step 1 — characterization first.** Before moving anything, run the existing auth tests and
> record the pass list: `pytest -x -k "auth or login or oauth" -v`. If fewer than ~5 tests cover
> these routes, STOP and instead write characterization tests (status codes + response JSON shape
> for login success, login failure, refresh, OAuth redirect) in
> `tests/test_auth_characterization.py`, get them green against the CURRENT code, and only then
> continue.
> **Step 2 — extract.** Create `backend/routers/__init__.py` and `backend/routers/auth.py`. Move
> the auth route functions into it on an `APIRouter` **with identical paths** (define
> `router = APIRouter()` and keep full paths on each route rather than using a prefix — this
> avoids subtle path changes). Move ONLY the route functions and helpers used exclusively by
> them; anything shared with other endpoints stays in server.py and gets imported by the new
> module (`from backend.server import ...` will create a cycle — instead, if a shared helper is
> needed, import it lazily inside the function, matching the repo's stated pattern for avoiding
> circular imports). In server.py, add `from backend.routers.auth import router as auth_router`
> and `app.include_router(auth_router)` at the point after `app` is created, and delete the moved
> code.
> **Step 3 — prove identity.** `python -m compileall -q .` then the full `pytest -x`. The
> characterization tests from Step 1 must pass UNCHANGED. Then boot the app
> (`uvicorn backend.server:app --port 8001 &`), hit `/api/health` and one auth route, kill it.
> Compare `python -c "from backend.server import app; print(sorted([r.path for r in app.routes]))"`
> before and after the change — the route list must be identical.
> **Rollback if stuck:** `git checkout -- backend/ tests/` restores everything.
> **Changelog:** identical entry in BOTH `CHANGELOG.md` and `docs/changelog.md` under
> `## [Unreleased]`: "Extracted auth endpoints from backend/server.py into
> backend/routers/auth.py (no behaviour change; route list verified identical)."
> **Done when:** route list identical pre/post, full test suite green, server.py shrank by the
> extracted amount, and no other endpoint group was touched.

---

## Suggested order and expected payoff

| Order | Prompt | Risk | Payoff |
|---|---|---|---|
| 1 | P1 docs sync | none | Every future agent session stops being misdirected |
| 2 | P5 hook nag | none | Cleaner session starts |
| 3 | P2 skill descriptions | trivial | Skill routing actually works; less wasted context |
| 4 | P4 print→logging | low | Observability rule §3 satisfied; logs become filterable |
| 5 | P3 env centralization | low-med | Biggest single constitution violation (68 reads) closed |
| 6 | P6 server.py slice | med | Proves the decomposition pattern; repeat per endpoint group |

After P6 succeeds once, the same prompt template can be re-run per endpoint group (companies,
schedules, brain, agents, …) to melt `server.py` incrementally — one verified slice per PR, per
REWRITE_PLAN Phase 5.
