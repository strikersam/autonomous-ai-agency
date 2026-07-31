# LLM Router — local model guide

Local models are the tier that no quota can exhaust. They are slower than a
free cloud tier, but they are still serving at 3 a.m. when every free key is
cooling.

## Supported servers

| Server | `kind` | Default base URL | Notes |
|--------|--------|------------------|-------|
| Ollama | `ollama` | `http://localhost:11434` | Native API; reports load state and timings |
| LM Studio | `lmstudio` | `http://localhost:1234/v1` | OpenAI-compatible |
| vLLM | `vllm` | `http://localhost:8000/v1` | OpenAI-compatible; batches well |
| LocalAI | `localai` | `http://localhost:8080/v1` | OpenAI-compatible |
| LiteLLM proxy | `litellm` | — | OpenAI-compatible; see below |

Only Ollama gets a bespoke adapter, because its native `/api/chat` endpoint
reports information the health tracker uses. The rest speak the OpenAI
protocol, so they are plain config entries.

## Ollama

```bash
export OLLAMA_BASE=http://localhost:11434
export OLLAMA_DEFAULT_MODEL=qwen3-coder:30b
```

Already declared in the shipped `providers.yaml`. Note that with **no** config
file at all, an Ollama provider is created only if `OLLAMA_BASE` is actually
set — a hardcoded localhost default is not treated as operator intent, because
that would add a phantom provider to every deployment.

Inside Docker, `localhost` will not reach a host daemon. Use
`http://host.docker.internal:11434` on Mac/Windows, the LAN IP on Linux, or
`http://ollama:11434` in docker-compose.

## LM Studio

```bash
export LMSTUDIO_ENABLED=true
export LMSTUDIO_BASE_URL=http://localhost:1234/v1
```

Start the LM Studio local server and load a model. It needs no API key.

## vLLM

```bash
export VLLM_ENABLED=true
export VLLM_BASE_URL=http://localhost:8000/v1
export VLLM_API_KEY=optional-if-you-set-one
```

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-32B-Instruct \
  --port 8000
```

vLLM is the one local server that benefits from a large bulkhead — continuous
batching genuinely uses the concurrency. The shipped config gives it 16 slots
versus Ollama's 2.

## LocalAI

```bash
export LOCALAI_ENABLED=true
export LOCALAI_BASE_URL=http://localhost:8080/v1
```

## LiteLLM compatibility mode

If you already run a LiteLLM proxy, point the router at it:

```bash
export LITELLM_ENABLED=true
export LITELLM_BASE_URL=http://localhost:4000
export LITELLM_API_KEY=your-litellm-key
```

The router treats LiteLLM as one more provider. LiteLLM's own fanout keeps
working; this layer adds failover *across* LiteLLM and everything else, so a
LiteLLM outage is survivable rather than terminal.

## Preferring local

```yaml
routing:
  prefer_local: true
```

or `LLM_ROUTER_PREFER_LOCAL=true`.

This makes `adaptive` favour local providers and puts `local` first in
`automatic_failover`.

**Leave it off unless your local model is warm.** With it off, a cold local
model does not outrank a warm free cloud tier — you avoid paying a model-load
penalty on every request while still having local as the floor when the cloud
is exhausted.

## Sizing bulkheads

| Server | `max_concurrency` | Why |
|--------|-------------------|-----|
| Ollama | 1–2 | A single GPU serialises anyway; more just queues while holding router slots |
| LM Studio | 1–2 | Same |
| vLLM | 8–16 | Continuous batching genuinely parallelises |
| LocalAI | 2–4 | Depends on the backend |

Also raise `timeout_sec` for local servers (the shipped config uses 300s):
loading a 30B model into VRAM on the first request can take minutes, and a
120-second timeout would fail every cold start.

## Registering local models

```yaml
models:
  qwen3-coder:30b:
    provider: ollama
    context_window: 32768
    supports_tools: true
    supports_json: true
    priority: 40
    speed_tier: medium
```

Or run discovery, which reads Ollama's `/api/tags`:

```bash
curl -X POST localhost:8001/api/llm/models/discover -H "Authorization: Bearer $TOKEN"
```

Discovered models get cautious defaults — no tool support, 8k context — so
capability filtering never over-promises on a model nothing has declared.
Declare the ones you rely on explicitly.

## Embeddings

```yaml
models:
  nomic-embed-text:
    provider: ollama
    supports_embeddings: true
    supports_streaming: false
    supports_chat: false        # required
```

`supports_chat: false` is not optional. Without it the router will offer the
embedding model as a chat candidate, and it will accept the request and return
something useless.
