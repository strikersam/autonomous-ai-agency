---
name: platform-setup
description: >
  Full autonomous AI agency setup for https://local-llm-server.strikersam.workers.dev.
  Uses browse CLI (Browserbase remote mode) to log in as admin, onboard the platform
  itself as a company, configure all specialists, verify agents are running, and
  fix any issues found. Run this skill to go from "deployed" to "fully autonomous."
triggers:
  - "set up the platform"
  - "configure the agency"
  - "onboard the platform"
  - "make it autonomous"
  - "platform setup"
  - "set up agency core"
upstream: https://github.com/strikersam/local-llm-server
---

# Skill: platform-setup — Autonomous Agency Bootstrap

## Prerequisites

```bash
npm install -g browse
export BROWSERBASE_API_KEY="bb_live_..."
export PLATFORM_URL="https://local-llm-server.strikersam.workers.dev"
# Admin credentials are in memory/test_credentials.md
```

## Phase 1 — Verify deployment health (no auth needed)

```bash
# 1a. Check public health endpoints
python3 -c "
import urllib.request, json, os
base = os.environ['PLATFORM_URL']
for path in ['/api/health', '/api/doctor/public']:
    try:
        with urllib.request.urlopen(f'{base}{path}', timeout=10) as r:
            print(f'{path}: HTTP {r.status}', json.loads(r.read()).get('status','?'))
    except Exception as e:
        print(f'{path}: ERROR {e}')
"

# 1b. If health endpoints are 403/404 — the Cloudflare Worker routing is broken.
#     Fix: check wrangler.jsonc BACKEND_ORIGIN points to correct Render URL.
```

## Phase 2 — Login as admin

```bash
browse open "$PLATFORM_URL/login" --remote

# Get page snapshot to find form field refs
browse snapshot
# Look for: email input, password input, submit button

# Fill credentials (from memory/test_credentials.md)
browse fill "@eN" "strikersam@gmail.com"    # replace @eN with actual ref
browse fill "@eN" "YOUR_ADMIN_PASSWORD"
browse click "@eN"    # Submit / Login button

# Verify login succeeded
browse snapshot
# Expected: dashboard visible, no /login redirect
browse screenshot
```

## Phase 3 — Onboard the platform itself as a company

```bash
# Navigate to Company / Onboarding
browse click "@eN"     # "+" or "New Company" button
browse snapshot

# Fill company details
browse fill "@eN" "Agency Core Platform"    # Company name
browse fill "@eN" "https://local-llm-server.strikersam.workers.dev"    # Website URL
browse click "@eN"    # "Scan" or "Start Onboarding" button

# Wait for scan to complete (may take 30-60s)
browse wait 30000
browse snapshot
# Expected: detected systems listed (Cloudflare, Render, FastAPI, React, etc.)
browse screenshot
```

## Phase 4 — Verify specialists were provisioned

```bash
browse click "@eN"    # Navigate to Agents/Specialists screen
browse snapshot
# Expected: specialists created for detected families
# (engineering, security, devops, frontend, backend)

# If no specialists: click "Provision Specialists" or "Setup Agency"
browse click "@eN"
browse snapshot
browse screenshot
```

## Phase 5 — Configure GitHub integration

```bash
# Navigate to Settings or Integrations
browse click "@eN"    # Settings / Integrations
browse snapshot

# Find GitHub token field
browse fill "@eN" "YOUR_GITHUB_PAT"    # GH_PAT from GitHub secrets
browse click "@eN"    # Save

# Verify: GitHub connection shows green / connected
browse snapshot
browse screenshot
```

## Phase 6 — Trigger first agency cycle manually

```bash
# Navigate to Agency / Workflow
browse click "@eN"    # Agency or Workflow section
browse snapshot

# If there's a "Run Agency Cycle" button:
browse click "@eN"
browse wait 5000
browse snapshot
# Expected: cycle started, assessment running

browse screenshot
```

## Phase 7 — Verify autonomous schedule is active

```bash
# Navigate to Tasks or Schedules
browse click "@eN"
browse snapshot
# Expected: scheduled tasks visible with next run times

# Check Doctor / Health screen
browse click "@eN"    # Doctor
browse snapshot
# Expected: all checks green, no red indicators

browse screenshot
browse stop
```

## Troubleshooting checklist

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| Login redirects back to /login | Wrong credentials or session issue | Check memory/test_credentials.md |
| Scan finds 0 systems | Scanner or Cloudflare blocking the scan | Run scan on a simpler URL first to verify scanner works |
| No specialists after onboarding | Onboarding didn't complete | Check `/api/company/{id}/onboarding/status` |
| Agent tasks fail with runtime error | internal_agent blocked by orchestrator | PR #396 fix must be merged |
| Agents not running on schedule | GitHub Actions quarantined | PR #396 restores all schedules |
| Doctor shows red for GitHub | GH_PAT not configured in Settings | Complete Phase 5 above |

## Post-setup verification

Once setup is complete, these should all be true:
- [ ] `GET /api/health` returns `{"status": "ok"}`
- [ ] At least 3 specialists visible in Agents screen
- [ ] At least 1 task created and visible in Tasks screen
- [ ] Doctor screen shows all green
- [ ] GitHub integration shows "Connected"
- [ ] Scheduled tasks show future run times
- [ ] Agency cycle can be triggered manually

## Ongoing autonomous operation

After setup, the platform maintains itself via:
- **agency-cycle** (every 6h): runs pytest, security scan, dispatches Claude agents
- **continuous-improvement** (daily): tracks quality metrics, creates/closes issues
- **ci-failure-autofix** (on CI fail): generates and applies patches automatically
- **process-quick-note** (every 4h): processes owner feature requests end-to-end
- **weekly-trend-digest** (Monday): surfaces relevant AI/tech trends as issues
