---
name: browserbase-browser
description: >
  Automate real browser interactions via the `browse` CLI — supports local Chrome
  and remote Browserbase cloud sessions with CAPTCHA solving and residential proxies.
  Use for Cloudflare-protected sites, login flows, form filling, and UI verification.
triggers:
  - "open the browser"
  - "navigate to"
  - "click on"
  - "fill in the form"
  - "login to"
  - "take a screenshot"
  - "browse the web"
  - "interact with the UI"
  - "test the UI"
upstream: https://github.com/browserbase/skills
---

# Skill: browserbase-browser — Real Browser Automation

## Setup

```bash
npm install -g browse          # Install the CLI
export BROWSERBASE_API_KEY="bb_live_..."   # Get from https://browserbase.com/dashboard
```

## Mode selection

| Situation | Flag | Notes |
|-----------|------|-------|
| Local dev / no bot detection | `--local` | Requires Chrome running locally |
| Cloudflare / CAPTCHA / IP limits | `--remote` | Uses Browserbase cloud (needs API key) |
| Reuse existing local Chrome session | `--auto-connect` | Picks up saved cookies/auth |

## Core commands

```bash
browse open <url> [--local|--remote]   # Navigate — always start here
browse snapshot                         # Accessibility tree with element refs (fast, low-token)
browse screenshot                       # Visual capture → .context/screenshots/
browse click "@e5"                      # Click element ref from snapshot
browse fill "@e3" "value"              # Fill input
browse type "text"                      # Type at cursor
browse press "Enter"                    # Key press
browse scroll down 3                    # Scroll
browse stop                             # End session
```

## Workflow pattern

```bash
# 1. Open — always with explicit mode flag
browse open "https://target.com" --remote   # remote for Cloudflare-protected sites

# 2. Snapshot to understand page state (NOT screenshot — 50× fewer tokens)
browse snapshot

# 3. Interact using @ref from snapshot output
browse fill "@e4" "admin@example.com"
browse fill "@e5" "password"
browse click "@e6"                          # Submit button

# 4. Snapshot again to verify state changed
browse snapshot

# 5. Screenshot only when you need visual evidence
browse screenshot

# 6. Always stop when done
browse stop
```

## Applying to local-llm-server platform

```bash
# Set env vars first
export BROWSERBASE_API_KEY="your-key"
export PLATFORM_URL="https://local-llm-server.strikersam.workers.dev"

# Login as admin
browse open "$PLATFORM_URL/login" --remote
browse snapshot
# Find email/password fields in snapshot, then:
browse fill "@eN" "strikersam@gmail.com"
browse fill "@eN" "YOUR_PASSWORD"
browse click "@eN"     # Login button
browse snapshot        # Confirm: dashboard visible

# Navigate to Agents screen
browse click "@eN"     # Agents nav item
browse snapshot

# Navigate to Quick Notes
browse click "@eN"     # Quick Notes FAB or nav
browse fill "@eN" "Feature request text here"
browse click "@eN"     # Submit

browse stop
```

## Troubleshooting

| Error | Fix |
|-------|-----|
| `BROWSERBASE_API_KEY not set` | Export the key or add to `.env` |
| `browse: command not found` | Run `npm install -g browse` |
| Cloudflare challenge page in snapshot | Use `--remote` flag (cloud sessions have residential IPs) |
| Element ref stale | Run `browse snapshot` again — refs reset on navigation |
| Session timed out | Run `browse open <url> --remote` again to restart |
