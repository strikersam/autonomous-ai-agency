---
name: dev-browser
description: >
  Control a local or remote browser with sandboxed JavaScript scripts.
  Uses a QuickJS WASM sandbox (not Node.js) with a pre-connected `browser`
  global and full Playwright Page API. Backed by a persistent daemon that
  manages named browser instances between script runs. Use for UI testing,
  web scraping, and automation where you have local browser access.
triggers:
  - "automate the browser"
  - "browser automation"
  - "run a browser script"
  - "use dev-browser"
  - "control the browser"
upstream: https://github.com/SawyerHood/dev-browser
---

# Skill: dev-browser — Browser Automation via Sandboxed JS

## Installation

```bash
npm install -g dev-browser
dev-browser install          # Downloads Playwright + Chromium
```

Add to `.claude/settings.json` to pre-approve all commands:
```json
{"permissions": {"allow": ["Bash(dev-browser *)"]}}
```

## Primary invocation styles

```bash
# Inline heredoc (most common)
dev-browser <<'EOF'
  const page = await browser.getPage("main");
  await page.goto("https://example.com");
  console.log(await page.title());
EOF

# Run a .js file
dev-browser run script.js

# Named browser instance (persists across runs)
dev-browser --browser my-project < script.js

# Connect to existing Chrome (local debugging port)
dev-browser --connect http://localhost:9222 <<'EOF'
  const page = await browser.getPage("main");
  await page.goto("https://example.com");
EOF

# Auto-discover Chrome with remote debugging enabled
dev-browser --connect <<'EOF'
  const page = await browser.getPage("main");
  console.log(await page.title());
EOF
```

## CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--browser NAME` | `"default"` | Named daemon-managed browser instance |
| `--connect [URL]` | — | Connect to running Chrome (no URL = auto-discover) |
| `--headless` | — | Launch without visible window |
| `--ignore-https-errors` | — | Ignore self-signed TLS certificate errors |
| `--timeout SECONDS` | `30` | Max script execution time |

## Subcommands

```bash
dev-browser run FILE      # Run a JS file
dev-browser install       # Install Playwright browsers (Chromium)
dev-browser browsers      # List all managed browser instances
dev-browser status        # Show daemon status
dev-browser stop          # Stop daemon and all browsers
```

## Sandbox environment

Scripts run in **QuickJS WASM**, NOT Node.js. These are NOT available:
- `require()` / `import()` — no module loading
- `process` — no process access
- `fs` / `path` / `os` — no direct filesystem access
- `fetch` / `WebSocket` — no direct network access
- `__dirname` / `__filename` — no path globals

Available globals:
```javascript
browser                          // Pre-connected browser handle
console.log/info/warn/error(...)  // log/info → stdout; warn/error → stderr
setTimeout / clearTimeout         // Basic timers
await saveScreenshot(buf, name)   // Save to ~/.dev-browser/tmp/<name>
await writeFile(name, data)       // Write to ~/.dev-browser/tmp/<name>
await readFile(name)              // Read from ~/.dev-browser/tmp/<name>
```

Top-level `await` is available. Memory and CPU limits are enforced.

## Browser API

```javascript
browser.getPage(nameOrId)   // Get named page (creates if new); or connect by targetId
browser.newPage()           // Anonymous page (cleaned up when script exits)
browser.listPages()         // [{id, url, title, name}]
browser.closePage(name)     // Close and remove a named page
```

## Full script example (Playwright Page API)

```javascript
const page = await browser.getPage("main");

// Navigation
await page.goto("https://example.com", { waitUntil: "domcontentloaded" });

// Interaction
await page.click("button");
await page.fill("input[name='email']", "test@example.com");
await page.select("select", "option-value");

// AI-friendly snapshot (use before interacting with unknown UIs)
const snapshot = await page.snapshotForAI();
console.log(snapshot);

// Screenshots
const buf = await page.screenshot();
const path = await saveScreenshot(buf, "home.png");
console.log("saved to", path);

// Evaluation
const title = await page.title();
const url = page.url();
const content = await page.content();
const text = await page.textContent("h1");

// Waiting
await page.waitForTimeout(1000);
await page.waitForSelector(".loaded");
await page.waitForNavigation();
await page.waitForFunction(() => document.readyState === "complete");
```

## LLM usage patterns

**Discovery → action** (for unfamiliar UIs):
```javascript
// Step 1: snapshot to discover selectors
const page = await browser.getPage("app");
await page.goto("http://localhost:3000", { waitUntil: "domcontentloaded" });
const snapshot = await page.snapshotForAI();
console.log(snapshot);
EOF

# Step 2: use selectors from snapshot in next script
dev-browser <<'EOF'
  const page = await browser.getPage("app");
  await page.click(".btn-submit");        // use real selector from snapshot
  const buf = await page.screenshot();
  await saveScreenshot(buf, "after-click.png");
EOF
```

**Dev server navigation** (avoid HMR hangs):
```javascript
await page.goto("http://localhost:3000", { waitUntil: "domcontentloaded" });
```

**Cross-script state** (named pages persist between runs):
```javascript
// Script A: login
const page = await browser.getPage("session");
await page.goto("https://app.example.com/login");
await page.fill("#email", "user@example.com");
await page.fill("#password", "secret");
await page.click("#submit");
// Page stays open — named "session"

// Script B: use logged-in session
const page = await browser.getPage("session");
await page.goto("https://app.example.com/dashboard");
```

## Connect to existing Chrome

```bash
# Launch Chrome with debugging enabled
google-chrome --remote-debugging-port=9222
# or on macOS:
open -a "Google Chrome" --args --remote-debugging-port=9222

# Then connect
dev-browser --connect http://localhost:9222 <<'EOF'
  const page = await browser.getPage("main");
  console.log(await page.title());
EOF
```

## Performance

- **Time:** ~3m 53s for complex tasks
- **Cost:** $0.88/run
- **Success rate:** 100% in benchmarks
- Outperforms Playwright MCP (4m 31s) and Playwright Skill (8m 7s)
