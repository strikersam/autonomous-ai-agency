---
name: perplexity
description: >
  Deep web research using the Perplexity API — get cited, up-to-date answers
  to research questions without burning context on raw web pages. Use when
  you need current information, competitive analysis, library docs, CVE lookups,
  or any factual query that requires web sources.
triggers:
  - "research"
  - "look up"
  - "what is the latest"
  - "find information about"
  - "search the web"
  - "perplexity"
  - "current state of"
  - "is there a CVE"
  - "what are best practices for"
upstream: https://claudemarketplaces.com/skills/davila7/claude-code-templates/perplexity
---

# Skill: perplexity — Web Research via Perplexity API

## When to Use

Use this skill when you need current, cited web information:
- Library version history and changelogs
- CVE / security vulnerability lookups
- API documentation for external services
- Current best practices for a technology
- Competitive or market research
- Anything that requires an up-to-date source

## Prerequisites

Set your Perplexity API key (get one at https://www.perplexity.ai/settings/api):
```bash
export PERPLEXITY_API_KEY="pplx-..."   # add to .env or shell profile
```

## How to Query

### Quick query (one-shot Python call)
```python
import os, json, urllib.request

def perplexity_search(query: str, model: str = "sonar") -> dict:
    key = os.environ["PERPLEXITY_API_KEY"]
    payload = {
        "model": model,           # sonar (fast) | sonar-pro (deep, cited)
        "messages": [
            {"role": "system", "content": "Be precise and cite your sources."},
            {"role": "user", "content": query},
        ],
        "max_tokens": 1024,
        "return_citations": True,
    }
    req = urllib.request.Request(
        "https://api.perplexity.ai/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

result = perplexity_search("latest FastAPI security best practices 2025")
print(result["choices"][0]["message"]["content"])
# Citations are in result["citations"]
```

### Run inline
```bash
python3 -c "
import os, json, urllib.request
key = os.environ.get('PERPLEXITY_API_KEY', '')
if not key: print('Set PERPLEXITY_API_KEY'); exit(1)
q = 'YOUR QUERY HERE'
payload = json.dumps({'model':'sonar','messages':[{'role':'user','content':q}],'max_tokens':512}).encode()
req = urllib.request.Request('https://api.perplexity.ai/chat/completions', data=payload,
    headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'})
with urllib.request.urlopen(req, timeout=30) as r: d = json.loads(r.read())
print(d['choices'][0]['message']['content'])
"
```

## Skill Steps

### Step 1 — Formulate the query
Be specific. Include version numbers, programming language, and context.
Bad: "how do I do auth"
Good: "FastAPI Bearer token authentication with Python 3.13, JWT RS256, best practices 2025"

### Step 2 — Choose the model
- `sonar` — fast, free-tier friendly, good for factual lookups
- `sonar-pro` — deeper research, more citations, better for complex questions
- `sonar-reasoning` — chain-of-thought, best for technical analysis

### Step 3 — Run the query
```bash
python3 -c "... (inline query above with your question) ..."
```

### Step 4 — Cite sources in your answer
Always include the citation URLs from `result["citations"]` in any doc or PR
that incorporates Perplexity research findings.

## Applying to this Repo

Useful queries for local-llm-server maintenance:
```python
# Check for CVEs in dependencies
perplexity_search("CVE vulnerabilities fastapi pydantic 2025")

# Research a feature
perplexity_search("Ollama streaming API response format latest docs")

# Check best practices
perplexity_search("OpenAI-compatible proxy auth security best practices")

# Competitive research
perplexity_search("LiteLLM vs local-llm-server comparison 2025")
```

## No API Key? Use WebSearch

If `PERPLEXITY_API_KEY` is not set, fall back to the `WebSearch` tool or
`WebFetch` for direct URL fetches. Perplexity is preferred because it:
1. Returns pre-summarised, cited results (no page parsing needed)
2. Has real-time web access beyond training cutoff
3. Uses ~10× fewer tokens than fetching and summarising raw pages
