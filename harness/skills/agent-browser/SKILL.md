---
name: agent-browser
description: >
  Browser automation via Chrome DevTools Protocol — use real Chrome to navigate,
  interact with, and test web UIs. 93% fewer tokens than Playwright MCP.
  Use when asked to test a UI, set up a web platform, fill in forms, or verify
  a deployed app works correctly.
triggers:
  - "test the UI"
  - "open the browser"
  - "navigate to"
  - "check the website"
  - "set up via browser"
  - "verify the platform"
  - "login to"
  - "fill in the form"
  - "take a screenshot"
  - "browser automation"
  - "use the browser"
upstream: https://github.com/CalebDane7/agent-browser
---

# Skill: agent-browser — Real Chrome Browser Automation

## Why This Exists

agent-browser connects Claude to your real Chrome browser via Chrome DevTools
Protocol (CDP) — no Playwright, no Puppeteer, no downloaded binaries. Your actual
browser session, cookies, and authentication are preserved. Sites see a real human.

Benefits over Playwright MCP:
- **93% fewer tokens** — ~200–400 tokens/page vs ~13,700
- **5× faster** — direct WebSocket, no Node.js relay
- **No bot detection** — no `navigator.webdriver` flag
- **Your real Chrome** — persistent sessions, saved passwords, cookies

## Installation (one-time)

```bash
npm install -g agent-browser    # Install CLI globally
```

Start Chrome with remote debugging enabled (required once per session):
```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222

# Windows
chrome.exe --remote-debugging-port=9222
```

## Core Commands

```bash
agent-browser open <url>          # Navigate to a URL
agent-browser snapshot            # Get accessibility tree (use for reading page state)
agent-browser screenshot          # Take a screenshot → /tmp/screenshot.png
agent-browser click "@e5"         # Click element by ref (from snapshot)
agent-browser fill "@e3" "value"  # Fill an input field
agent-browser type "text"         # Type text at cursor
agent-browser press "Enter"       # Press a key
agent-browser hover "@e7"         # Hover over element
agent-browser eval "js code"      # Execute JavaScript
agent-browser errors              # Get JS console errors
agent-browser wait 2000           # Wait milliseconds
agent-browser back / forward      # Browser navigation
agent-browser close               # Close the connection
```

## How to Use This Skill

### Step 1 — Check Chrome is running with debugging
```bash
curl -s http://localhost:9222/json | python3 -m json.tool | head -20
```
If this fails, start Chrome with `--remote-debugging-port=9222`.

### Step 2 — Navigate and snapshot
```bash
agent-browser open "https://your-target-url.com"
agent-browser snapshot    # Read the accessibility tree to understand the page
```

### Step 3 — Interact using element refs
The snapshot returns elements as `@e1`, `@e2`, etc. Use these refs to interact:
```bash
agent-browser snapshot    # Find the login button at @e12
agent-browser click "@e12"
agent-browser snapshot    # Verify the login form appeared
agent-browser fill "@e5" "admin@example.com"
agent-browser fill "@e6" "password123"
agent-browser press "Enter"
agent-browser snapshot    # Confirm login succeeded
```

### Step 4 — Verify state and take evidence
```bash
agent-browser screenshot  # Screenshot saved to /tmp/screenshot.png
agent-browser errors      # Check for JS errors
```

## Applying to the local-llm-server Platform

When testing `https://local-llm-server.strikersam.workers.dev`:

```bash
# 1. Open the platform
agent-browser open "https://local-llm-server.strikersam.workers.dev"
agent-browser snapshot

# 2. Login with admin credentials (from memory/test_credentials.md)
# Find login form fields in snapshot output, then:
agent-browser fill "@eN" "<email>"
agent-browser fill "@eN" "<password>"
agent-browser click "@eN"   # Submit button
agent-browser snapshot       # Verify dashboard loaded

# 3. Test a feature (e.g. Agents screen)
agent-browser click "@eN"    # Navigate to Agents
agent-browser snapshot
agent-browser screenshot

# 4. Report findings
agent-browser errors         # Any JS errors?
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ECONNREFUSED localhost:9222` | Start Chrome with `--remote-debugging-port=9222` |
| Element ref stale | Run `agent-browser snapshot` again to get fresh refs |
| Login persists unexpectedly | Clear cookies: `agent-browser eval "document.cookie=''"` |
| Page didn't load | Add `agent-browser wait 2000` after navigation |
