# NVIDIA NIM — Free Tier Setup

> **Purpose**: This runbook covers setting up NVIDIA NIM as the free primary brain provider
> for the Autonomous AI Agency. NVIDIA NIM is **free** (no billing) and provides access to
> frontier models like Qwen3-Coder 480B and Nemotron Super 120B.

---

## What you get

NVIDIA NIM provides free API access to:

| Model | Role | Use case |
|-------|------|----------|
| `qwen/qwen3-coder-480b-a35b-instruct` | Executor | Primary coding agent |
| `nvidia/llama-3.3-nemotron-super-49b-v1` | Planner/Verifier | Planning and review |
| `nvidia/llama-3.1-nemotron-ultra-253b-v1` | Reasoning | Complex analysis |

The Agency auto-selects the best model for each agent role when NVIDIA NIM is configured.

---

## Setup (5 minutes)

### 1. Get your free API key

1. Visit [build.nvidia.com](https://build.nvidia.com/explore/discover)
2. Sign up / sign in with your NVIDIA account (free)
3. Navigate to any model page (e.g. Qwen3-Coder)
4. Click **"Get API Key"**
5. Copy the key (starts with `nvapi-`)

### 2. Set the environment variable

**Local / Render:**
```bash
export NVIDIA_API_KEY="nvapi-..."
```

**GitHub Actions (for CI scripting):**
Add `NVIDIA_API_KEY` as a repository secret at:
`Settings → Secrets and variables → Actions → New repository secret`

**Render dashboard:**
Add `NVIDIA_API_KEY` in the Environment Variables section of your web service.

### 3. Restart the server

```bash
# Local
uvicorn backend.server:app --reload --port 8001

# Or if using the proxy
python proxy.py
```

### 4. Verify

The dashboard Providers screen will show **"Nvidia NIM (Free)"** with a green **configured** badge. The free-tier brain is automatically preferred over any paid provider when both are available.

---

## How the kill switch protects you

The Agency has a **paid-provider kill switch** that defaults to **OFF** (`allow_paid=false`):

- ✅ **NVIDIA NIM** is always allowed (free tier)
- ✅ **Ollama local** is always allowed
- ❌ **Anthropic Claude** is BLOCKED by default (paid — $3-$15 per million tokens)
- ❌ Other paid providers are blocked unless explicitly enabled

You control this at **Settings → Providers → Provider Policy**. The toggle reads:
- **"Paid providers are blocked"** (default — safe, zero billing)
- **"Paid providers are allowed"** (opt-in — enables Anthropic et al.)

Even when paid providers are allowed, **NVIDIA NIM is always preferred** (priority -10 vs Anthropic at -50 to -90) — so the free tier is used first, and paid providers are only tried as a last resort.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Nvidia NIM (Free)" shows **unconfigured** | `NVIDIA_API_KEY` is not set or invalid. Check the env var. |
| Agent keeps using Ollama even with NVIDIA key set | Check `AGENT_LLM_BASE_URL` env var — it overrides the brain selection. Remove it to let the priority system work. |
| CI scripts fail with "NVIDIA_API_KEY not set" | Add `NVIDIA_API_KEY` as a GitHub Actions secret. |
| Model returns 404 / "model not found" | Some models require explicit access on build.nvidia.com. Visit the model page and click "Get API Key" to activate it. |

---

## Related

- [Provider policy kill switch](/docs/architecture/provider-policy.md) — how `allow_paid` gates all paid providers
- [NVIDIA NIM docs](https://docs.api.nvidia.com/nim/) — official API documentation
- [Model catalog](https://build.nvidia.com/explore/discover) — available free models
