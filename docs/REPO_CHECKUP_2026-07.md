# Repo Checkup — July 2026

**Date:** 2026-07-10
**Branch:** `claude/repo-checkup-improvements-hohdjv`
**Scope:** Read-only diagnostic + implementation prompts for follow-up fixes.

---

## Part A — Health Report

### Finding 1: CLAUDE.md / AGENTS.md are dangerously stale (P1, docs-only, zero risk)

**Severity:** High — actively misroutes every agent that reads CLAUDE.md.
**Effort:** Low (docs-only, mechanical find-and-replace with verification).

CLAUDE.md references 4 files that no longer exist:

| Dead path (in CLAUDE.md) | Real location (verified) |
|---|---|
| `provider_router.py` | `packages/ai/router.py` |
| `brain_policy.py` | `packages/ai/brain.py` |
| `services/brain_config_store.py` | `packages/ai/brain_config.py` (store logic inlined) |
| `services/brain_watchdog.py` | `packages/ai/watchdog.py` |

**Evidence:**
```bash
# Dead files don't exist:
ls brain_policy.py provider_router.py services/brain_config_store.py services/brain_watchdog.py
# → NOT FOUND (all 4)

# Real files do exist:
ls packages/ai/router.py packages/ai/brain_config.py packages/ai/watchdog.py
# → all exist

# CLAUDE.md has 17 references to dead paths:
grep -c "provider_router\|brain_policy\|brain_config_store\|brain_watchdog" CLAUDE.md
# → 17
```

**Bill of Materials counts are wrong:**
- CLAUDE.md says `server.py` is ~8,700 lines → actually **9,667 lines**
- CLAUDE.md says 38 root `.py` files → actually **33**
- CLAUDE.md says 21 workflows → actually **40**

### Finding 2: Constitution violations — `os.environ` outside config modules (P3, medium risk)

**Severity:** Medium — Constitution §3 forbids this; creates hidden coupling.
**Effort:** Medium (68 reads in router.py alone, need lazy accessors).

Top offenders (by count of `os.environ` reads):

| File | Count |
|---|---|
| `packages/ai/router.py` | 68 |
| `telegram_bot.py` | 21 |
| `proxy.py` | 16 |
| `providers/kimi_bridge.py` | 11 |
| `webui/providers.py` | 11 |
| `agents/profiles.py` | 10 |
| `packages/ai/brain.py` | 9 |
| `packages/ai/brain_config.py` | 8 |

**Evidence:**
```bash
grep -c "os\.environ" packages/ai/router.py  # → 68
grep -c "os\.environ" telegram_bot.py        # → 21
# ... etc
```

### Finding 3: `print()` in production code (P2, low risk, mechanical)

**Severity:** Low — Constitution §3 forbids `print()` in production; only `logging` should be used.
**Effort:** Low (3 prints in the two god files, mechanical replacement).

**Evidence:**
```bash
grep -c "print(" backend/server.py  # → 2
grep -c "print(" proxy.py            # → 1
# 72 total files with print() across the repo (including tests)
```

### Finding 4: God files (structural debt, P6 is a first slice)

**Severity:** Medium — maintenance burden, merge conflict magnet.
**Effort:** High (each extraction is a careful refactor).

| File | Lines | Functions |
|---|---|---|
| `backend/server.py` | 9,667 | 243 |
| `proxy.py` | 4,098 | — |
| `agent/loop.py` | 2,362 | — |
| `models/company_graph.py` | 2,170 | — |

### Finding 5: Root clutter — 33 root-level `.py` files (P6-adjacent)

**Severity:** Low — cosmetic but confusing for agents.
**Effort:** Medium (each file needs an import audit before moving).

The `packages/` migration (REWRITE_PLAN Phase 5/6) stalled mid-way: `packages/` exists and is imported by `proxy.py`, `webui/`, `services/`, but the root twins were never fully retired.

### Finding 6: Skill frontmatter hygiene (P4, low risk)

**Severity:** Low — degrades skill routing quality.
**Effort:** Low (description-line-only edits).

15 of 43 skills have empty or placeholder `description:` lines in their `SKILL.md` frontmatter:

```
.claude/skills/agentic-agile/SKILL.md → (empty)
.claude/skills/agentic-portfolio/SKILL.md → (empty)
.claude/skills/ai-engineering-insights/SKILL.md → (empty)
.claude/skills/ecc-harness-patterns/SKILL.md → (empty)
.claude/skills/graphiti-temporal/SKILL.md → (empty)
.claude/skills/karpathy-guidelines/SKILL.md → (empty)
.claude/skills/managed-agents-dreams/SKILL.md → (empty)
.claude/skills/multi-agent/SKILL.md → (empty)
.claude/skills/obsidian-knowledge-graph/SKILL.md → (empty)
.claude/skills/research-coordinator/SKILL.md → (empty)
.claude/skills/session-planning/SKILL.md → (empty)
.claude/skills/stop-slop-quality/SKILL.md → (empty)
.claude/skills/superclaude-commands/SKILL.md → (empty)
.claude/skills/user-research/SKILL.md → (empty)
.claude/skills/workflow-engine/SKILL.md → (empty)
```

**Evidence:**
```bash
for f in .claude/skills/*/SKILL.md; do
  desc=$(grep "^description:" "$f" 2>/dev/null | head -1)
  if [ -z "$desc" ]; then echo "  $f → (empty)"; fi
done
# → 15 skills with empty descriptions
```

### Finding 7: graphify-refresh hook emits install nag (P5, low risk)

**Severity:** Low — noisy but harmless.
**Effort:** Trivial (one `if` condition change).

The hook prints an install instruction when graphify isn't installed and the mode is `--session`. It should degrade silently.

**Evidence:**
```bash
cat .claude/hooks/graphify-refresh | head -20
# Lines 14-17: prints "[graphify] not installed — run: ..." when mode is --session
```

### Finding 8: Healthy indicators ✅

- `compileall` passes on all god files
- Only 4 `TODO`/`FIXME` markers in `server.py` + `proxy.py`
- `check_changelog_parity.py` and `loop_registry.py audit --check` exist where CLAUDE.md says
- 33 registered loops, all L3, 100/100 readiness score

---

## Part B — Implementation Prompts

Each prompt is self-contained and copy-paste-ready for a lower-tier model.

---

### Prompt P1 — Refresh CLAUDE.md and AGENTS.md to match reality

**Goal:** Replace all references to dead files with their real locations; correct the Bill of Materials counts.

**Files:**
- `CLAUDE.md`
- `AGENTS.md`

**Steps:**

1. **Verify the old→new mapping** before editing. Run these commands and confirm the output:
   ```bash
   # Dead files (should NOT exist):
   ls brain_policy.py provider_router.py services/brain_config_store.py services/brain_watchdog.py
   # Real files (SHOULD exist):
   ls packages/ai/router.py packages/ai/brain_config.py packages/ai/watchdog.py packages/ai/brain.py
   ```

2. **Find-and-replace** in CLAUDE.md (use `grep -n` first to find every occurrence):
   - `provider_router.py` → `packages/ai/router.py`
   - `brain_policy.py` → `packages/ai/brain.py`
   - `services/brain_config_store.py` → `packages/ai/brain_config.py`
   - `services/brain_watchdog.py` → `packages/ai/watchdog.py`

3. **Correct the Bill of Materials counts:**
   - `server.py` line count: change ~8,700 to **9,667** (run `wc -l backend/server.py` to confirm)
   - Root `.py` file count: change 38 to **33** (run `ls *.py | wc -l` to confirm)
   - Workflow count: change 21 to **40** (run `ls .github/workflows/*.yml | wc -l` to confirm)

4. **Update the §5 provider-architecture section** to document what each successor module actually does:
   - `packages/ai/router.py` — OpenAI-compatible outbound router with Anthropic prompt caching + extended thinking
   - `packages/ai/brain.py` — Brain resolution (single source of truth for the active LLM)
   - `packages/ai/brain_config.py` — DB-persisted brain config (BrainConfig Pydantic model, provider presets, key env mapping)
   - `packages/ai/watchdog.py` — Brain health watchdog (consecutive failure tracking, auto-failover)

5. **Repeat steps 2-4 for AGENTS.md** if it has the same stale references.

6. **Commit:**
   ```bash
   git add CLAUDE.md AGENTS.md
   git commit -m "docs: refresh CLAUDE.md/AGENTS.md — fix dead file references + correct BoM counts"
   ```

**Constraints:**
- Golden Rule §0: no behaviour change (docs-only).
- No CHANGELOG edit needed (docs: prefix exempts from changelog gate per §12).
- Do NOT create new files — only edit existing CLAUDE.md and AGENTS.md.

**Verification:**
```bash
grep -c "provider_router\|brain_policy\|brain_config_store\|brain_watchdog" CLAUDE.md
# → 0 (all dead references removed)

wc -l backend/server.py   # → 9667 (matches CLAUDE.md)
ls *.py | wc -l            # → 33 (matches CLAUDE.md)
ls .github/workflows/*.yml | wc -l  # → 40 (matches CLAUDE.md)
```

**Done when:**
- Zero references to dead files in CLAUDE.md and AGENTS.md
- BoM counts match actual `wc -l` / `ls | wc -l` output
- Each successor module has a one-line description of what it does

---

### Prompt P2 — Replace print() with logging in server.py and proxy.py

**Goal:** Replace all `print()` calls in `backend/server.py` and `proxy.py` with `log.info()` / `log.warning()` / `log.error()`. Keep the message text byte-identical.

**Files:**
- `backend/server.py` (2 print calls)
- `proxy.py` (1 print call)

**Steps:**

1. **Find every print():**
   ```bash
   grep -n "print(" backend/server.py
   grep -n "print(" proxy.py
   ```

2. **For each print(), determine the log level:**
   - If it prints an error/failure → `log.error()`
   - If it prints a warning → `log.warning()`
   - Otherwise → `log.info()`

3. **Replace** each `print("message")` with `log.info("message")` (or the appropriate level). Use the SAME message string. Do NOT change f-string interpolation or variable names.

4. **Do NOT touch:**
   - `if __name__ == "__main__":` blocks (CLI entry points)
   - Test files
   - Any file other than `backend/server.py` and `proxy.py`

5. **Add CHANGELOG entries** (both `CHANGELOG.md` and `docs/changelog.md`):
   ```
   - **Replace print() with logging in server.py and proxy.py** (date). Constitution §3 compliance.
   ```

6. **Commit:**
   ```bash
   git add backend/server.py proxy.py CHANGELOG.md docs/changelog.md
   git commit -m "fix: replace print() with logging in server.py and proxy.py (Constitution §3)"
   ```

**Constraints:**
- Golden Rule §0: no behaviour change. The log messages must be byte-identical (same text, same variables).
- Changelog parity: `CHANGELOG.md` and `docs/changelog.md` must have identical entries.
- Do NOT change log format or add new log lines — only convert existing print() calls.

**Verification:**
```bash
grep -c "print(" backend/server.py  # → 0
grep -c "print(" proxy.py            # → 0
python scripts/check_changelog_parity.py  # → PARITY OK
python -m pytest -x  # → all green
```

**Done when:**
- `grep -c "print(" backend/server.py` returns 0
- `grep -c "print(" proxy.py` returns 0
- All tests pass
- Changelog parity OK

---

### Prompt P3 — Centralize router.py env reads into config accessors

**Goal:** Move the 68 `os.environ` reads in `packages/ai/router.py` into lazy accessor functions in `packages/config/settings.py` (the sanctioned config module). Read-through so defaults and env-var names stay identical.

**Files:**
- `packages/ai/router.py` (68 os.environ reads → accessor calls)
- `packages/config/settings.py` (add accessor functions)

**Steps:**

1. **Catalog every os.environ read** in router.py:
   ```bash
   grep -n "os\.environ" packages/ai/router.py
   ```

2. **For each unique env-var name**, create a lazy accessor in `packages/config/settings.py`:
   ```python
   # Example: if router.py reads os.environ.get("NVIDIA_API_KEY", "")
   # Add to settings.py:
   def nvidia_api_key() -> str:
       """NVIDIA NIM API key (lazy read — call-time, not import-time)."""
       return os.environ.get("NVIDIA_API_KEY", "")
   ```

3. **CRITICAL: Use lazy functions, NOT module-level constants.** Module-level constants freeze the value at import time, breaking tests that `monkeypatch.setenv()`. Every accessor must be a function that reads `os.environ` at call time.

4. **Replace** each `os.environ.get("X", "default")` in router.py with `settings.x()` (or the appropriate accessor name). Keep the same default values.

5. **Do NOT change any env-var names or defaults** — the accessor must return exactly what the original `os.environ.get()` would return.

6. **Add CHANGELOG entries** (both files, parity).

7. **Commit:**
   ```bash
   git add packages/ai/router.py packages/config/settings.py CHANGELOG.md docs/changelog.md
   git commit -m "refactor: centralize router.py env reads into settings.py accessors (Constitution §3)"
   ```

**Constraints:**
- Golden Rule §0: no behaviour change. Every accessor must return the same value as the original `os.environ.get()` call.
- Lazy reads only — no module-level constants.
- Identical env-var names and defaults.
- Changelog parity.

**Verification:**
```bash
grep -c "os\.environ" packages/ai/router.py  # → 0 (or very few, e.g. in the config module itself)
python -m pytest tests/test_brain_config_api.py tests/test_brain_resolution.py -x  # → green
python scripts/check_changelog_parity.py  # → PARITY OK
```

**Done when:**
- `grep -c "os\.environ" packages/ai/router.py` returns 0
- All brain/router tests pass
- Changelog parity OK

---

### Prompt P4 — Fix skill frontmatter descriptions

**Goal:** Write real trigger-oriented one-line descriptions for the 15 skills with empty `description:` fields.

**Files (15 skills):**
- `.claude/skills/agentic-agile/SKILL.md`
- `.claude/skills/agentic-portfolio/SKILL.md`
- `.claude/skills/ai-engineering-insights/SKILL.md`
- `.claude/skills/ecc-harness-patterns/SKILL.md`
- `.claude/skills/graphiti-temporal/SKILL.md`
- `.claude/skills/karpathy-guidelines/SKILL.md`
- `.claude/skills/managed-agents-dreams/SKILL.md`
- `.claude/skills/multi-agent/SKILL.md`
- `.claude/skills/obsidian-knowledge-graph/SKILL.md`
- `.claude/skills/research-coordinator/SKILL.md`
- `.claude/skills/session-planning/SKILL.md`
- `.claude/skills/stop-slop-quality/SKILL.md`
- `.claude/skills/superclaude-commands/SKILL.md`
- `.claude/skills/user-research/SKILL.md`
- `.claude/skills/workflow-engine/SKILL.md`

**Steps:**

1. **For each skill**, read the SKILL.md body to understand what it does.

2. **Write a description** following this template:
   ```yaml
   description: "Trigger-oriented one-liner that describes what this skill does and when to use it"
   ```
   Examples of good descriptions:
   - `description: "Agile sprint planning and story-point estimation for agent-managed projects"`
   - `description: "Portfolio rebalancing and risk analysis for AI-managed investment portfolios"`
   - `description: "Research coordination across multiple agents — deduplicates findings and assigns work"`

3. **Edit ONLY the `description:` line** in the YAML frontmatter. Do NOT change:
   - The skill name
   - The skill body
   - Any other frontmatter fields
   - File structure

4. **After each file**, validate the YAML frontmatter parses:
   ```bash
   python3 -c "
   import yaml, sys
   with open('$FILE') as f:
       text = f.read()
   # Extract frontmatter between first two ---
   parts = text.split('---', 2)
   if len(parts) >= 3:
       yaml.safe_load(parts[1])
       print('✅ YAML valid')
   else:
       print('❌ No frontmatter found')
   "
   ```

5. **Commit:**
   ```bash
   git add .claude/skills/*/SKILL.md
   git commit -m "docs: fix skill frontmatter descriptions — 15 skills with empty descriptions"
   ```

**Constraints:**
- Description-line-only edits — no body changes, no name changes.
- YAML-quoted strings (use double quotes).
- Description must be ≤120 characters.
- No CHANGELOG edit needed (docs: prefix).

**Verification:**
```bash
for f in .claude/skills/*/SKILL.md; do
  desc=$(grep "^description:" "$f" 2>/dev/null | head -1)
  if [ -z "$desc" ]; then echo "❌ $f still empty"; fi
done
# → no output (all fixed)
```

**Done when:**
- All 15 skills have non-empty `description:` lines
- All YAML frontmatter parses without errors

---

### Prompt P5 — Make graphify-refresh hook degrade silently

**Goal:** When graphify is not installed, the hook should exit 0 with no output (instead of printing an install nag).

**File:**
- `.claude/hooks/graphify-refresh`

**Steps:**

1. **Read the current hook:**
   ```bash
   cat .claude/hooks/graphify-refresh
   ```

2. **Find the install nag** (lines 14-17):
   ```sh
   if ! command -v graphify >/dev/null 2>&1; then
     if [ "$MODE" = "--session" ]; then
       echo "[graphify] not installed — run: ..."
     fi
     exit 0
   fi
   ```

3. **Remove the `echo` line** so the hook degrades silently:
   ```sh
   if ! command -v graphify >/dev/null 2>&1; then
     exit 0
   fi
   ```

4. **Commit:**
   ```bash
   git add .claude/hooks/graphify-refresh
   git commit -m "fix: graphify-refresh hook degrades silently when graphify not installed"
   ```

**Constraints:**
- Golden Rule §0: no behaviour change when graphify IS installed.
- Do NOT remove the `exit 0` — the hook must always succeed.
- No CHANGELOG edit needed (chore: prefix).

**Verification:**
```bash
# When graphify is not installed:
sh .claude/hooks/graphify-refresh --session  # → no output, exit 0
# When graphify IS installed (if available):
sh .claude/hooks/graphify-refresh --session  # → same behavior as before
```

**Done when:**
- Running the hook without graphify installed produces no output and exits 0
- Running the hook with graphify installed behaves exactly as before

---

### Prompt P6 — First router-extraction slice from server.py (advanced, optional)

**⚠️ This is an advanced refactor. Only attempt if CI is green and you have a clean working tree. If you can't complete it safely, stop and report rather than force it.**

**Goal:** Move the auth routes (login, logout, me, OAuth callbacks) out of `backend/server.py` into `backend/routers/auth.py` as a FastAPI `APIRouter`, then `include_router` back.

**Files:**
- New: `backend/routers/auth.py`
- Modified: `backend/server.py` (remove auth routes, add `include_router`)

**Steps:**

1. **Establish green baseline:**
   ```bash
   python -m pytest -x  # must be all green
   ```

2. **Identify the auth routes** in server.py:
   ```bash
   grep -n "@app.post.*login\|@app.post.*logout\|@app.get.*me\|@app.get.*github/oauth\|@app.get.*google/oauth" backend/server.py
   ```

3. **Write characterization tests** that verify the auth endpoints work (login returns token, logout clears session, /me returns user). These tests must pass BEFORE and AFTER the extraction.

4. **Create `backend/routers/auth.py`:**
   - Define `router = APIRouter(prefix="/api/auth", tags=["auth"])`
   - Move the auth route functions into this file
   - Import any dependencies they need (get_db, settings, etc.)

5. **In `backend/server.py`:**
   - Remove the moved auth route functions
   - Add `from backend.routers.auth import router as auth_router`
   - Add `app.include_router(auth_router)`

6. **Run tests:**
   ```bash
   python -m pytest -x  # must be all green
   ```

7. **If any test fails, ROLLBACK immediately:**
   ```bash
   git checkout -- .
   ```

8. **Add CHANGELOG entries** (both files, parity).

9. **Commit:**
   ```bash
   git add backend/routers/auth.py backend/server.py CHANGELOG.md docs/changelog.md
   git commit -m "refactor: extract auth routes from server.py into routers/auth.py"
   ```

**Constraints:**
- Golden Rule §0: no behaviour change. All auth endpoints must work identically after extraction.
- Characterization tests BEFORE moving code.
- One-command rollback: `git checkout -- .`
- Changelog parity.
- If you can't get tests green after extraction, STOP and rollback. Do not force it.

**Verification:**
```bash
python -m pytest -x  # → all green (including characterization tests)
python -m compileall -q backend/routers/auth.py backend/server.py  # → OK
python scripts/check_changelog_parity.py  # → PARITY OK
wc -l backend/server.py  # → should be smaller (by ~200-400 lines)
```

**Done when:**
- Auth routes are in `backend/routers/auth.py`
- `app.include_router(auth_router)` is in server.py
- All tests green
- `server.py` is smaller
- Changelog parity OK

**Rollback:**
```bash
git checkout -- .
```

---

## Re-check commands

Every finding above can be re-verified with these commands:

```bash
# Finding 1: stale docs
grep -c "provider_router\|brain_policy\|brain_config_store\|brain_watchdog" CLAUDE.md
wc -l backend/server.py
ls *.py | wc -l
ls .github/workflows/*.yml | wc -l

# Finding 2: os.environ outside config
grep -c "os\.environ" packages/ai/router.py
grep -c "os\.environ" telegram_bot.py

# Finding 3: print() in production
grep -c "print(" backend/server.py
grep -c "print(" proxy.py

# Finding 4: god files
wc -l backend/server.py proxy.py agent/loop.py models/company_graph.py

# Finding 5: root clutter
ls *.py | wc -l

# Finding 6: skill descriptions
for f in .claude/skills/*/SKILL.md; do desc=$(grep "^description:" "$f" | head -1); [ -z "$desc" ] && echo "$f"; done

# Finding 7: graphify hook
grep "echo.*graphify.*not installed" .claude/hooks/graphify-refresh
```

---

*Note: Any PR opened from this branch must keep the `docs:` title prefix to be exempt from the changelog gate (CLAUDE.md §12). The code-fix prompts (P2–P6) each include the CHANGELOG parity step since those PRs won't be exempt.*
