---
name: browserbase-search
description: >
  Search the web via Browserbase infrastructure and get structured results
  (title, URL, author, date) without opening a browser. Use before browsing
  to find the right URLs, research competitors, or look up documentation.
triggers:
  - "search for"
  - "find the URL"
  - "research"
  - "look up"
  - "find information about"
upstream: https://github.com/browserbase/skills
---

# Skill: browserbase-search — Structured Web Search

## Setup

```bash
export BROWSERBASE_API_KEY="bb_live_..."
```

## Python snippet

```python
import os, json, urllib.request

def bb_search(query: str, num_results: int = 10) -> list[dict]:
    key = os.environ["BROWSERBASE_API_KEY"]
    payload = json.dumps({"query": query, "numResults": num_results}).encode()
    req = urllib.request.Request(
        "https://api.browserbase.com/v1/search",
        data=payload,
        headers={"X-BB-API-Key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()).get("results", [])

results = bb_search("local-llm-server autonomous AI agency platform")
for r in results[:5]:
    print(r["title"])
    print(r["url"])
    print()
```

## Best practice: search → fetch → browse

```bash
# Step 1: Search to find the right URL
results = bb_search("FastAPI security headers best practices 2025")

# Step 2: Fetch the top result's content (if static)
content = bb_fetch(results[0]["url"])

# Step 3: Only open browser if you need to interact
browse open results[0]["url"] --remote
```
