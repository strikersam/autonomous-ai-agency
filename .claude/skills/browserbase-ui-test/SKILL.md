---
name: browserbase-ui-test
description: >
  Adversarial UI testing via browser automation — tries to BREAK the app,
  not confirm it works. Analyzes git diffs to test changed code, or explores
  the full app for defects. Use before merging UI changes or to audit the
  deployed platform.
triggers:
  - "test the UI"
  - "UI test"
  - "check if the frontend works"
  - "test the platform"
  - "verify the deployment"
  - "audit the UI"
  - "find UI bugs"
upstream: https://github.com/browserbase/skills
---

# Skill: browserbase-ui-test — Adversarial UI Testing

## Core philosophy

Your job is to **try to break things**, not confirm they work. If the happy path
passes, immediately try edge cases, empty states, rapid interactions, and
unexpected inputs.

## Three planning rounds (REQUIRED before any browser interaction)

### Round 1 — Core flow mapping
List every user flow that exists. For each flow: what does success look like?
What does failure look like? Which flows are critical (login, data save, payment)?

### Round 2 — Adversarial scenarios
For each flow: what happens with empty input? Invalid format? Very long strings?
Clicking submit twice? Going back mid-flow? Network timeout simulation?

### Round 3 — Accessibility + mobile
Does each screen work at 375px width? Are form labels connected to inputs?
Can keyboard-only users complete every flow? Any console errors?

## Execution pattern

```bash
export BROWSERBASE_API_KEY="bb_live_..."
export PLATFORM_URL="https://local-llm-server.strikersam.workers.dev"

# --- Flow 1: Unauthenticated access ---
browse open "$PLATFORM_URL" --remote
browse snapshot
# Verify: login page or landing, no sensitive data exposed
browse screenshot   # Evidence

# --- Flow 2: Login ---
browse fill "@eN" "admin@example.com"
browse fill "@eN" "wrong-password"
browse click "@eN"    # Submit
browse snapshot       # Verify: error message shown, not logged in
browse screenshot     # Evidence of error state

# --- Flow 3: Correct login ---
browse fill "@eN" "admin@example.com"
browse fill "@eN" "correct-password"
browse click "@eN"
browse snapshot       # Verify: dashboard visible
browse screenshot

# --- Flow 4: Core feature test ---
# Navigate to Agents screen
browse click "@eN"
browse snapshot
# Try creating an agent with empty name
browse click "@eN"    # New agent button
browse click "@eN"    # Submit without filling
browse snapshot       # Verify: validation error, not 500

browse stop
```

## Reporting

For each test step, mark:
- `STEP_PASS: <description>` — with snapshot/screenshot evidence
- `STEP_FAIL: <description>` — with screenshot, reproduction steps, suggested fix

Final report format:
```
## UI Test Report — YYYY-MM-DD
Platform: https://local-llm-server.strikersam.workers.dev
Pass rate: N/M flows passing

### Failures
1. [CRITICAL] Login with empty email crashes with 500 instead of validation error
   Screenshot: .context/ui-test-screenshots/login-empty-crash.png
   Fix: Add frontend validation before submit in LoginForm.jsx

### Passes
1. [PASS] Unauthenticated access redirects to /login
2. [PASS] Invalid credentials show error message (no 500)
```

## Applying to local-llm-server platform

Key flows to test:
1. Unauthenticated → redirects to login
2. Login with wrong password → error, not 500
3. Login with correct credentials → dashboard loads
4. Agents screen → lists agents, no console errors
5. Quick Notes FAB → can submit a note
6. Doctor screen → shows health checks
7. Company/onboarding → scan a URL works
8. Admin actions → only visible to admins
