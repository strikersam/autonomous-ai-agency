# LLM Router — provider guide

Four adapters cover every supported endpoint. Adding a provider is normally a
`providers.yaml` entry, not code.

| Adapter (`kind`) | Wire format | Covers |
|------------------|-------------|--------|
| `openai` | OpenAI chat-completions | OpenAI, Azure, Groq, Cerebras, NVIDIA NIM, OpenRouter, Together, Fireworks, DeepInfra, Mistral, LM Studio, vLLM, LiteLLM, LocalAI, and any other OpenAI-compatible REST endpoint |
| `anthropic` | Messages API | Anthropic |
| `gemini` | `generateContent` | Google AI Studio / Gemini |
| `ollama` | Native `/api/chat` | Ollama |

Readability aliases (`groq`, `lmstudio`, `vllm`, `together`, …) all resolve to
the `openai` adapter, so `kind: lmstudio` reads better and behaves identically.

## Cloud providers

### Free tiers

| Provider | Env | Notes |
|----------|-----|-------|
| Cerebras | `CEREBRAS_API_KEY` | Fastest free inference. Tight RPM — pool keys. |
| Groq | `GROQ_API_KEY` | Very fast, generous free tier, good tool support. |
| NVIDIA NIM | `NVIDIA_API_KEY` | The always-on free floor. Broad catalogue. |
| Google Gemini | `GEMINI_API_KEY` | 1M context — the context-overflow escalation target. |

These four are the backbone. Configure at least two, ideally with multiple keys
each.

### Cheap tiers

`OPENROUTER_API_KEY`, `TOGETHER_API_KEY`, `FIREWORKS_API_KEY`,
`DEEPINFRA_API_KEY`, `MISTRAL_API_KEY`. Reached only when `allow_paid` is true.

### Premium

`OPENAI_API_KEY`, `AZURE_OPENAI_API_KEY`, `ANTHROPIC_API_KEY`. Last resort;
requires explicit `ALLOW_PAID_BRAIN=true`.

Azure needs three extra settings:

```yaml
azure:
  kind: openai
  base_url: https://your-resource.openai.azure.com
  auth_style: api-key            # not Authorization: Bearer
  api_version: 2024-10-21
  deployment: your-deployment
```

## Adding any OpenAI-compatible provider

```yaml
providers:
  some-new-vendor:
    kind: openai
    base_url: https://api.newvendor.com/v1
    key_env: [NEWVENDOR_API_KEY]
    tier: cheap
    priority: 45
    max_concurrency: 8
```

Then add its models to `models.yaml`, or call
`POST /api/llm/models/discover` to read them from its `/models` endpoint.

Custom headers, if the vendor needs them:

```yaml
    extra_headers:
      HTTP-Referer: https://your-app.example
      X-Title: Your App
```

## Auth styles

| `auth_style` | Header sent |
|--------------|-------------|
| `bearer` *(default)* | `Authorization: Bearer <key>` |
| `x-api-key` | `x-api-key: <key>` (Anthropic) |
| `api-key` | `api-key: <key>` (Azure) |
| `none` | no auth header |

Or set `auth_header` to name the header explicitly.

The Gemini adapter sends `x-goog-api-key` rather than a `?key=` query
parameter, so the key does not end up in proxy access logs.

## Multiple keys

The highest-leverage change you can make for 429 resilience:

```bash
export GROQ_API_KEY=key-one
export GROQ_API_KEY_2=key-two
export GROQ_API_KEY_3=key-three
```

`NAME`, `NAME_2` … `NAME_10`, `NAME_S`, and `NAME_POOL` are auto-detected. A
single variable may also hold several comma-separated keys.

When one key hits a 429 the router cools that key and retries the *same
provider* with the next one. Per-key health is visible on the Providers page by
digest — never by value.

## Writing a custom adapter

Only necessary for a genuinely different wire format. Implement `LLMProvider` — `chat`, `stream`, `health`, and `cost` are required
(`cost` feeds per-request spend attribution and the `cost_optimized`
strategy; the base class derives it from the model registry, so override it
only for vendor-specific pricing). `list_models` is optional. Then register it:

```python
from packages.llm.providers import register_adapter
from packages.llm.providers.base import LLMProvider

class MyProvider(LLMProvider):
    ...

register_adapter("myvendor", MyProvider)
```

Then use `kind: myvendor` in `providers.yaml`. Read
`packages/llm/providers/gemini.py` first — it is the clearest example of a
non-OpenAI format.

Adapters must classify errors through `classify_error()` so the router gets the
right failure scope. Getting that wrong is the difference between a 429 costing
you one key and costing you a provider.
