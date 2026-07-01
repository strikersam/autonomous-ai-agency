# OpenAI Codex CLI — Local LLM Server Config

Codex CLI (v0.142+) supports custom OpenAI-compatible endpoints.
Point it at this proxy to route requests through your local Ollama models.

## Setup

```bash
# Install Codex CLI (if not already installed)
npm install -g @openai/codex

# Configure to use your local proxy
export OPENAI_BASE_URL="https://YOUR_TUNNEL_URL/v1"
export OPENAI_API_KEY="YOUR_API_KEY"

# Or for localhost (no tunnel)
export OPENAI_BASE_URL="http://localhost:8000/v1"
export OPENAI_API_KEY="YOUR_API_KEY"
```

## Recommended Models

Set the model in your Codex config or via `--model` flag:

```bash
# Best local coder (77.2% SWE-bench, 24GB VRAM at Q4)
codex --model qwen3.6:27b "implement feature X"

# Strong general coding
codex --model qwen3-coder:30b "fix the auth bug"

# Deep reasoning + planning
codex --model deepseek-r1:32b "design the migration strategy"

# Flagship DeepSeek V4 (if running remotely / large VRAM)
codex --model deepseek-v4-0324 "refactor the payment module"
```

## Codex Config File (`~/.codex/config.yaml`)

```yaml
# Point Codex at your local-llm-server proxy
provider: openai
model: qwen3.6:27b
api_base: https://YOUR_TUNNEL_URL/v1
api_key: YOUR_API_KEY
```

## Notes

- The proxy auto-routes model names, so you can use aliases like
  `deepseek-chat` or `claude-sonnet-4-6` and the router maps them
  to your local models.
- Codex CLI v0.142+ supports plugins — the proxy's `/v1/models`
  endpoint lists all available models for auto-discovery.
- For Codex Remote (mobile app companion), set the base URL in
  your connected host's environment variables.
