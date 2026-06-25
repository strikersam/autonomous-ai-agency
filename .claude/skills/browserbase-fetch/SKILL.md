---
name: browserbase-fetch
description: >
  Fetch HTML, JSON, or headers from any URL via Browserbase infrastructure —
  handles proxies, redirects, and rate-limited sites without opening a browser.
  Use for API health checks, scraping static content, reading HTTP headers,
  or any fetch where JavaScript rendering is not needed.
triggers:
  - "fetch the page"
  - "get the HTML"
  - "check the headers"
  - "read the response"
  - "scrape"
  - "HTTP status"
upstream: https://github.com/browserbase/skills
---

# Skill: browserbase-fetch — Lightweight Web Fetch

## When to use vs browser

| Use fetch | Use browser |
|-----------|-------------|
| Static pages / APIs | JavaScript-rendered SPAs |
| HTTP header inspection | Login flows |
| JSON API responses | Form interactions |
| Redirect chains | CAPTCHA-protected pages |
| Fast bulk scraping | Visual verification |

## Setup

```bash
export BROWSERBASE_API_KEY="bb_live_..."
```

## Python snippet

```python
import os, json, urllib.request

def bb_fetch(url: str, allow_redirects: bool = True) -> dict:
    key = os.environ["BROWSERBASE_API_KEY"]
    payload = json.dumps({
        "url": url,
        "allowRedirects": allow_redirects,
    }).encode()
    req = urllib.request.Request(
        "https://api.browserbase.com/v1/fetch",
        data=payload,
        headers={"X-BB-API-Key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

result = bb_fetch("https://local-llm-server.strikersam.workers.dev/api/health")
print(result["status"], result["content"][:500])
```

## Checking the platform health

```python
# Check all public endpoints
endpoints = [
    "/api/health",
    "/api/doctor/public",
    "/api/version",
]
for path in endpoints:
    r = bb_fetch(f"https://local-llm-server.strikersam.workers.dev{path}")
    print(f"{path}: HTTP {r['status']}")
    print(r['content'][:200])
    print()
```
