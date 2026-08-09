# Prime Agent Runtime

[Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent) is Prime Intellect's
open-source coding and research agent, built for long-running autonomous work. This
runbook covers running it as an executor behind `RuntimeManager`.

It is registered as runtime id `prime_agent` and is **off by default**. When the binary
is absent the adapter reports `available=False` and the router falls back to
`internal_agent` — enabling the flag on a host without the binary is harmless.

## What the adapter drives

Prime Agent wraps `@earendil-works/pi-coding-agent` (the `pi` CLI). The adapter drives
either binary, preferring `prime-agent` and falling back to `pi`:

```bash
prime-agent -p --mode json --no-session \
  --no-approve --no-context-files --no-prompt-templates --no-themes --no-skills \
  --extension <ext>.ts --provider agency --model <model> "<instruction>"
```

Two observed behaviours of that CLI shape the implementation:

- **stdin must be closed.** With stdin attached the process waits for interactive
  input and never exits, even under `-p`. The adapter always passes `stdin=DEVNULL`.
- **The exit code is meaningless.** A run in which every LLM call failed still exits
  `0`. Success is derived only from the event stream: the *last* `agent_end` (retries
  emit several), `auto_retry_end.success`, and the final assistant `stopReason`.

There is no `--cwd` flag on the `pi` build, so the workspace is set as the subprocess
working directory, which both binaries honour.

## Installation

```bash
curl -fsSL https://app.primeintellect.ai/prime-agent/install.sh | sh   # official
npm install -g @earendil-works/pi-coding-agent                        # `pi` fallback
```

The package is **not** on the public npm registry under the name `prime-agent`; the
installer fetches a signed tarball from Prime Intellect's own CDN and verifies it
against `SHA256SUMS`. It requires Node.js 20.6+ and installs a standalone Node if none
is present.

## Routing LLM traffic through our proxy

The CLI has no base-URL environment variable. Registering a provider from an extension
is the only supported way to point it at an arbitrary endpoint, so
`runtimes/extensions/prime_agent/agency-provider.ts` ships with the repo and registers a
provider named `agency` against our OpenAI-compatible proxy.

This is load-bearing, not cosmetic: without it the CLI falls back to whatever provider
keys sit in the environment, bypassing `packages/ai/router.py` and losing failover, the
brain watchdog, and cost accounting (CLAUDE.md §3). The adapter refuses to run the
`agency` provider when `PRIME_AGENT_EXTENSION` is unset or points at a missing file —
in preflight *and* at the top of `execute()`, since direct callers such as
`scripts/compare_runtimes.py` never go through preflight. A silent bypass surfaces as
an error instead.

The API key is never written into the file — the extension declares the literal string
`"$PROXY_API_KEY"`, which the CLI interpolates from the environment at request time.

> **Which endpoint? Verify before enabling.** `/v1/chat/completions` is served by
> `proxy.py`, **not** by `backend/server.py`. No service in `render.yaml` currently runs
> `proxy.py`, so on Render there is nothing for `AGENCY_PROXY_URL` to point at until you
> run the proxy somewhere. `render.yaml` sets it to the deployed backend as a concrete
> starting value — confirm it answers before turning the runtime on:
>
> ```bash
> curl -s -o /dev/null -w '%{http_code}\n' "$AGENCY_PROXY_URL/v1/models"   # expect 200 or 401
> ```
>
> If it does not, either add a Render service running `proxy.py` (mirroring the
> `agency-hermes` service shape) and point `AGENCY_PROXY_URL` at it, or leave the runtime
> disabled. A wrong URL is not silent: runs fail with `Connection error.` rather than
> quietly falling back to another provider. Locally the default
> `http://localhost:8000` is correct when the proxy runs in-process.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `RUNTIME_PRIME_AGENT_ENABLED` | `false` | Register the adapter at all |
| `PRIME_AGENT_BIN` | `prime-agent`, then `pi` | Binary name or path |
| `PRIME_AGENT_MODEL` | (unset) | Model id passed to `--model` |
| `PRIME_AGENT_PROVIDER` | `agency` | Provider name passed to `--provider` |
| `PRIME_AGENT_EXTENSION` | (unset) | Path to `agency-provider.ts`; **required** when the provider is `agency` |
| `PRIME_AGENT_MODELS` | `meta/llama-3.3-70b-instruct` | Model ids the extension advertises |
| `PRIME_AGENT_WORKSPACE` | `.` | Default working directory |
| `PRIME_AGENT_TIMEOUT_SEC` | `900` | Default task timeout |
| `PRIME_AGENT_MAX_TURNS` | (unset) | `--autonomous-max-turns`, when supported |
| `PRIME_AGENT_TRUST_WORKSPACE` | `false` | Load workspace-local extensions, skills, and context files |
| `AGENCY_PROXY_URL` | `http://localhost:8000` | Base URL of the proxy |
| `PROXY_API_KEY` | (unset) | Bearer token sent to the proxy |

Autonomy flags (`--autonomous`, `--autonomous-max-turns`) exist on `prime-agent` but not
on plain `pi`, so the adapter parses `--help` once and passes only what the installed
build accepts.

### `PRIME_AGENT_TRUST_WORKSPACE`

Off by default. The adapter then passes the full isolation set — `--no-approve`,
`--no-context-files`, `--no-prompt-templates`, `--no-themes`, `--no-skills` — because
`--no-approve` alone still lets `AGENTS.md`/`CLAUDE.md`, prompt templates, themes and
skills load out of the repository under test. Those are instructions to the model from
whatever repo the task happens to be working on.

If the installed CLI does not accept every one of those flags, the adapter refuses to
run rather than degrading to a weaker posture. Set `PRIME_AGENT_TRUST_WORKSPACE=true`
only for workspaces you control.

The subprocess also receives an **allowlisted environment**, not the worker's: the CLI
ships a model-controlled `bash` tool, so inheriting `os.environ` would hand it `GH_PAT`,
`MONGO_URL`, `JWT_SECRET` and every provider key. Only PATH/locale settings and the
proxy variables the extension needs are passed through.

## Deploying on Render

The binary is not in the default image. `Dockerfile.backend` installs it only when built
with `--build-arg INSTALL_PRIME_AGENT=true`; the guarded `RUN` keeps the default image
byte-identical (a conditional `COPY` would not — a layer cannot be undone by a later
`rm`).

Enable it on the **worker** service, never the web service: prime-agent runs
model-generated shell with the container's own permissions and its own README states the
worker/kernel processes are not a security sandbox. `render.yaml` declares the variables
on `local-llm-server-worker` for that reason.

Render exposes a Docker service's environment variables as same-name build arguments,
so `render.yaml` declares `INSTALL_PRIME_AGENT` alongside `RUNTIME_PRIME_AGENT_ENABLED`.
Both must be `"true"`: one bakes the CLI into the image at build time, the other
registers the adapter at runtime. Setting only the second leaves the binary absent, and
the adapter simply reports `available=False`.

## Verifying

```bash
export RUNTIME_PRIME_AGENT_ENABLED=true
export PRIME_AGENT_EXTENSION=$PWD/runtimes/extensions/prime_agent/agency-provider.ts
curl -s localhost:8001/api/runtimes | jq '.[] | select(.runtime_id=="prime_agent")'
```

Unit tests run without the binary or the network:

```bash
pytest tests/test_prime_agent_runtime.py -v
```

The fixtures in `tests/fixtures/prime_agent_*.ndjson` are real captured CLI output, not
hand-written samples. `prime_agent_provider_failure.ndjson` records a run where every LLM
call failed and the process still exited `0` — the regression that keeps anyone from
reintroducing an exit-code success check.
