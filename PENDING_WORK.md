# Pending Work — Autonomous AI Agency

> **Purpose:** Full context, implementation plans, agent prompts, and TODO checklists
> for every piece of work not yet in master. Any agent or developer can pick this up cold.
>
> **Repo:** strikersam/autonomous-ai-agency  
> **Last updated:** 2026-06-13  
> **Branch:** chore/pending-work-tracker

---

## What's Already in Master

All of the following were merged on 2026-06-13:

| PR | What landed |
|----|-------------|
| #566 | Chat agent 240s timeout; issue→PR workflow auto-dispatch; specialist loading watchdog; scanner SSL+CDN headers; orchestrator provider failover |
| #575 | Brand rename → "Autonomous AI Agency" everywhere; login screen high-value copy |
| #576 | Mobile-first CSS baseline (`box-sizing`, `overflow-x:hidden`, responsive media) |
| #577 | Scanner SSL `_analyze_ssl_cert` fixed (was silent no-op); CORS hardening in proxy.py |
| #578 | SVG chart kit (`Sparkline`, `BarChart`, `Donut`) in `frontend/src/v5/components/Charts.jsx` |
| #579 | README truthful feature maturity matrix (Stable/Beta/Experimental) |
| #580 | E2E Playwright test scaffold in `tests/e2e/test_critical_flows.py` |
| #582 | Dashboard `AgentActivityWidget`; CompanyScreen systems grouped by category with confidence bars |
| #583 | Sprint tracking issue #581 |
| #585 | Scanner subdomain enumeration (shop, api, cdn, checkout, account, …) |
| #587 | Mobile overflow: chat dropdowns, task board columns, tooltip max-width |

---

## PENDING ITEM 1 — E2E Playwright Tests (Live Run + Screenshots)

**Status:** Scaffold exists in `tests/e2e/test_critical_flows.py` (from PR #580).  
Tests currently self-skip when services are not running. Need to run live and capture screenshots for README.

**Acceptance criteria:**
- [ ] All 5 critical flows pass against live local services (backend :8001, proxy :8000)
- [ ] Screenshots captured for every page: Login, Dashboard, Company Onboarding, Scan Results, Task Board, Chat, Admin
- [ ] Screenshots saved to `docs/screenshots/web/` and `docs/screenshots/mobile/` (390px viewport)
- [ ] README.md updated with screenshot references
- [ ] CI step added so tests run in GitHub Actions (`tests/e2e/` suite, gated on service availability)

**Implementation plan:**

### Step 1 — Start local services
```bash
cd /path/to/repo
source .venv/bin/activate
# Terminal 1:
uvicorn backend.server:app --port 8001 &
# Terminal 2:
uvicorn proxy:app --port 8000 &
# Wait for health:
curl -s http://localhost:8001/health && curl -s http://localhost:8000/health
```

### Step 2 — Install Playwright
```bash
pip install playwright --break-system-packages
playwright install chromium
```

### Step 3 — Run existing tests + expand
```bash
pytest tests/e2e/ -v --headed  # or --headless
```

Expand `tests/e2e/test_critical_flows.py` to add:
- Screenshot capture at each step: `page.screenshot(path=f"docs/screenshots/web/{name}.png")`
- Mobile viewport run: `browser.new_context(viewport={"width":390,"height":844})`
- Save mobile screenshots to `docs/screenshots/mobile/{name}.png`

### Step 4 — Add GitHub Actions step
In `.github/workflows/ci.yml`, add:
```yaml
- name: E2E tests
  if: env.RUN_E2E == 'true'
  run: |
    uvicorn backend.server:app --port 8001 &
    uvicorn proxy:app --port 8000 &
    sleep 5
    pytest tests/e2e/ -v
  env:
    RUN_E2E: true
```

**Agent prompt (paste this to continue):**
```
You are working on strikersam/autonomous-ai-agency (workspace: /sessions/.../mnt/qwen-server/).
PAT: ghp_<YOUR_PAT_HERE>

Task: Run E2E Playwright tests live and capture screenshots.

1. Start backend (uvicorn backend.server:app --port 8001) and proxy (uvicorn proxy:app --port 8000) in background
2. Install playwright + chromium if needed
3. Run: pytest tests/e2e/test_critical_flows.py -v
4. If tests fail, diagnose and fix (check server logs, adjust selectors, fix auth flow)
5. Add screenshot capture to each test: page.screenshot(path="docs/screenshots/web/<page>.png")
6. Run again at 390px viewport for mobile: page.set_viewport_size({"width":390,"height":844})
7. Save mobile screenshots to docs/screenshots/mobile/
8. Update README.md to reference screenshots
9. Commit to branch feat/e2e-live-screenshots-20260613, push, open PR against master
10. Update docs/changelog.md
```

---

## PENDING ITEM 2 — Pre-mortem / User Research Bug Backlog

**Status:** Bugs catalogued in `.claude/state/user-research-scan.json` and `docs/pre-mortem-2026-06-10.md`.  
Many were fixed in earlier sessions. Need triage of what remains.

**Acceptance criteria:**
- [ ] All P0/P1 bugs from the pre-mortem fixed or explicitly deferred with reason
- [ ] Each fixed bug has a regression test
- [ ] `docs/pre-mortem-2026-06-10.md` updated with fix status per item

**Known remaining bugs (from session context):**

| # | Bug | Priority | File |
|---|-----|----------|------|
| 1 | Direct chat stuck at "planning" when agent mode ON — timeout fix landed, needs verification | P1 | backend/server.py |
| 2 | Specialist loading hangs > 30s with no error shown to user — watchdog added, needs verification | P1 | frontend/src/v5/screens/OnboardingScreen.jsx |
| 3 | Scanner returns 19/154 vs BuiltWith for gucci.com — SSL + subdomain added, DNS/MX already existed; needs real scan test | P1 | services/scanner.py |
| 4 | Skills not loaded / shown in UI — ECC skill disabled intentionally; others need check | P2 | services/skill_bindings.py |
| 5 | Issue→PR auto-dispatch regression — workflow fixed in #566, needs live verification | P2 | .github/workflows/ |
| 6 | "LLM relay" / "agency core" branding still in logs/emails/notifications | P3 | various |
| 7 | Remote admin dashboard (Vercel SPA) not updated with new brand name | P3 | remote-admin/ |
| 8 | Telegram bot control — test that `/status` and `/run` commands work | P3 | telegram_bot.py |
| 9 | `key_store.py` — no rate limiting on key lookup, HMAC-based comparison not verified | P2 | key_store.py |
| 10 | Agent loop `apply_diff` can write outside repo root (path traversal) | P0 | agent/tools.py |

**Implementation plan:**

### P0 first: agent/tools.py path traversal
```python
# In apply_diff(), before writing:
import os
repo_root = os.path.realpath(self.workspace_root)
target = os.path.realpath(os.path.join(repo_root, filepath))
if not target.startswith(repo_root + os.sep):
    raise SecurityError(f"Path traversal attempt: {filepath}")
```

### P1: Verify chat timeout fix
- Open the app, enable agent mode, send a message
- Confirm it resolves or times out cleanly within 240s (not hangs at "planning")
- If still broken, check `backend/server.py` `CHAT_AGENT_RUN_BUDGET_SEC` is wired to the right code path

### P1: Verify specialist loading
- Trigger onboarding, watch for spinner
- Confirm 30s watchdog kicks in if backend is slow

### P2: key_store.py security
- Verify keys are stored as HMAC-SHA256 hashes, not plaintext
- Add rate limiting: max 10 failed lookups per IP per minute

### P3: remote-admin/ brand update
```bash
grep -rn "LLM relay\|agency core\|local-llm-server" remote-admin/ | head -20
# Replace occurrences
```

**Agent prompt (paste this to continue):**
```
You are working on strikersam/autonomous-ai-agency (workspace: /sessions/.../mnt/qwen-server/).
PAT: ghp_<YOUR_PAT_HERE>

Task: Fix remaining pre-mortem bugs. Work in priority order:

P0 — agent/tools.py path traversal:
  Add realpath check before any file write in apply_diff(). Write regression test in tests/test_agent_tools.py.

P1 — Verify chat timeout + specialist loading watchdog actually work end-to-end.
  If verification fails, fix the root cause, don't just add another wrapper.

P2 — key_store.py: verify keys stored as hashes not plaintext. Add rate limiting.
  Read agent/CLAUDE.md and use risky-module-review skill before touching this file.

P3 — remote-admin/ brand update: grep for old names, replace with "Autonomous AI Agency".

P3 — Telegram bot: run a quick smoke test of /status command.

For each fix:
- Write a regression test
- Update docs/changelog.md
- Commit immediately and push to branch fix/premortem-remaining-20260613
- Open PR against master

Use shadow git: GIT_DIR=/tmp/repo.git GIT_WORK_TREE=/sessions/.../mnt/qwen-server
```

---

## PENDING ITEM 3 — Frontend Polish Remaining

**Status:** Charts added, scan results grouped. Still to do:

- [ ] Agent run timeline (Gantt-style) on task detail page
- [ ] Scan results export to CSV/PDF
- [ ] Dark mode consistency audit (some components missing `dark:` Tailwind classes)
- [ ] Loading skeleton screens instead of spinners on initial page load

**Agent prompt:**
```
You are working on strikersam/autonomous-ai-agency frontend (React/JSX in frontend/src/v5/).
PAT: ghp_<YOUR_PAT_HERE>

Task: Frontend polish remaining items:

1. TaskDetailScreen (or equivalent): Add a timeline/Gantt visualization of agent execution phases
   using the existing Charts.jsx or inline SVG. Data from task.execution_log.

2. CompanyScreen Systems tab: Add "Export CSV" button that downloads detected systems as CSV.

3. Dark mode audit: grep for hardcoded colors (text-gray-900, bg-white, border-gray-200)
   in JSX files and add dark: variants where missing.

4. Replace spinner on initial data load with skeleton screens (gray animated placeholder bars).

Commit to branch feat/frontend-polish-2-20260613, push, open PR against master.
```

---

## Checklist for Next Agent

- [ ] Read this file fully before starting
- [ ] Check `git log --oneline -20` on master to see what's already shipped
- [ ] Run `pytest -x` to confirm baseline green before making changes
- [ ] Work P0 → P1 → P2 → P3 order
- [ ] Push after every commit — don't accumulate
- [ ] Update this file's checklist as items complete
- [ ] When all items done, close this PR and update issue #581

---

## Quick-start for Any Agent

```bash
# Shadow git setup
git clone --bare "https://PAT@github.com/strikersam/autonomous-ai-agency.git" /tmp/repo.git

# All git commands
export G="GIT_DIR=/tmp/repo.git GIT_WORK_TREE=/sessions/.../mnt/qwen-server"
$G git log --oneline -5
$G git status

# Run tests
cd /sessions/.../mnt/qwen-server && python -m pytest tests/ -x -q 2>&1 | tail -20

# Push a branch
$G git push "https://PAT@github.com/strikersam/autonomous-ai-agency.git" HEAD:branch-name
```
