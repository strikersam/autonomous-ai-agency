# Migration Notes

Adopting the governance layer on a running install.

---

## TL;DR

**Nothing is required.** Merging this change alters no user-visible behaviour:
governance ships enabled but the policy ships in `observe` mode, so every rule
is evaluated and audited and nothing is blocked.

The work below is the path from "audited" to "enforced", at whatever pace suits
the install.

---

## What changed on merge

| Change | Behavioural impact |
|---|---|
| `packages/governance/` added | None until called |
| `AgentRunner._dispatch_tool` wrapped | **None in observe mode.** The original body is unchanged and now lives in `_dispatch_tool_unguarded`; the wrapper returns its result verbatim. Pinned by `tests/test_governance_api.py::test_dispatch_returns_the_unguarded_result_unchanged` |
| `unsafe_target_reason()` extended | **None in observe mode.** The new egress check runs strictly after the existing SSRF checks and returns `None` unless enforcing |
| `/api/governance/*` mounted | New admin-only routes; mounted defensively so a failure cannot block startup |
| `config/agent_policy.yaml` added | Read-only config |
| `config/sandbox_profiles.yaml` added | Read-only config |
| `docker-compose.hardening.yml` added | **Opt-in overlay.** `docker compose up` unchanged |
| `supply-chain.yml` added | New CI job. Fails only on a fixable CRITICAL image CVE |
| 9 settings added | All defaulted; none required |

No API responses changed shape. No database migration. No dependency added
(`PyYAML` and `httpx` were already present).

---

## Rollback

Three levers, in increasing order of scope, none requiring a deploy:

```bash
# 1. Stop enforcing, keep auditing
#    edit config/agent_policy.yaml → mode: observe
curl -X POST .../api/governance/policy/reload -H "Authorization: Bearer $ADMIN_JWT"

# 2. Turn the layer off entirely
GOVERNANCE_ENABLED=false        # then restart

# 3. Revert the commit
```

Lever 1 is the one to reach for during an incident: it takes effect in under a
second and preserves the audit trail that will tell you what went wrong.

---

## Path to enforcement

### Step 1 — Deploy and watch (1–2 weeks)

```bash
curl -s .../api/governance/metrics | jq '.audit.would_block'
```

`would_block` counts decisions that blocked, or would have. A steady non-zero
number means the shipped rules are catching legitimate work.

```bash
curl -s '.../api/governance/audit?decision=deny&limit=100' \
  | jq -r '.events[] | "\(.agent_id)\t\(.rule_id)\t\(.action)"' | sort | uniq -c | sort -rn
```

Each row is either a real finding or a rule that is too broad.

### Step 2 — Tune

Simulate before committing a change. Simulation shares one implementation with
live enforcement, so it cannot disagree with what will happen:

```bash
curl -X POST .../api/governance/policy/simulate \
  -H 'Content-Type: application/json' \
  -d '{"tool":"write_file","args":{"path":".github/workflows/ci.yml"},"policy_group":"coding"}'
```

### Step 3 — Enforce one group at a time

Rather than flipping the global mode, tighten a single low-risk group first —
`research` is a good candidate, since it is read-only by design. Confirm it
stays quiet, then move `mode: enforce`.

### Step 4 — Enable a real sandbox backend

In observe mode the policy engine is the only control, and it is in-process.
The hard boundary comes from a sandbox:

```bash
E2B_ENABLED=true        # production (Render) — micro-VM over HTTPS
E2B_API_KEY=e2b_...
```

Confirm with `GET /api/governance/status` → `sandbox.backend` should read
`e2b`, not `local`.

---

## Optional hardening (operator decisions)

### Compose secret scoping — shipped, opt-in

The `hermes` sidecar received the whole of `.env` — including the GitHub PAT
and the JWT signing secret — despite never issuing a JWT, authenticating an
admin, pushing to GitHub, or talking to Telegram.

(The services that execute model-authored code — `opencode`, `goose`, `aider`,
`jcode`, `task-harness`, `mcp-server` — were already scoped to explicit
`environment:` lists and never received `.env` at all. An earlier draft of the
threat model implied otherwise; it has been corrected.)

`docker-compose.yml` now loads an optional `.env.backend-secrets` into `proxy`
and `dashboard-backend` only. **Nothing is scoped until you split the file** —
the entry is `required: false`, so a single-file `.env` keeps working exactly
as before. That is what makes this safe to merge.

To adopt:

```bash
cp .env.backend-secrets.example .env.backend-secrets
# move SECRET_KEY, ADMIN_PASSWORD, GH_PAT, the OAuth client secrets,
# TELEGRAM_BOT_TOKEN, SERVICE_TOKEN, RENDER_API_KEY, CLOUDFLARE_API_TOKEN
# OUT of .env and INTO .env.backend-secrets
docker compose up -d

# verify hermes no longer sees them
docker compose exec hermes printenv | grep -E 'GH_PAT|SECRET_KEY|TELEGRAM'
# → should print nothing
```

`hermes` keeps the LLM provider keys deliberately: it runs the same agent
brain, so it needs them. Moving a credential a service genuinely needs just
produces a broken service and an operator who reverts the whole change.

Requires Compose v2.24+ for the long-form `env_file` syntax.

### Container hardening overlay

```bash
docker compose -f docker-compose.yml -f docker-compose.hardening.yml up
```

**Not verified against a live daemon** — no Docker daemon was available where it
was written. Adopt service by service; `docs/governance/deployment.md#4-troubleshooting`
lists the failure modes and fixes.

Also note the overlay binds Mongo and Ollama to `127.0.0.1`. The base compose
file publishes Mongo on `0.0.0.0:27017` — on a laptop on an untrusted network
that is an open, unauthenticated database.

### Rootless Docker daemon

```bash
dockerd-rootless-setuptool.sh install
export DOCKER_HOST=unix:///run/user/$UID/docker.sock
```

### Protect the policy file from agents

The `coding` group denies writes to `.github/workflows/**` and `render.yaml`
but **not** to `config/agent_policy.yaml`. That is deliberate — a self-improving
platform legitimately proposes policy changes via PR, and the control is human
review of that PR. For a stricter stance:

```yaml
groups:
  coding:
    filesystem:
      deny:
        - "render.yaml"
        - ".github/workflows/**"
        - "config/agent_policy.yaml"      # add this
```

---

## Tuning limits

Shipped defaults, per policy group:

| Limit | `default` | `research` | `coding` |
|---|---|---|---|
| `max_tool_calls` | 200 | 100 | 400 |
| `max_cost_usd` | 5.00 | 2.00 | 10.00 |
| `max_duration_s` | 1800 | 1800 | 3600 |
| `max_depth` | 5 | 5 | 5 |
| `max_retries` | 10 | 10 | 10 |

These are first estimates, not measurements — they were chosen to sit above
observed normal usage, not derived from it. Check real consumption before
tightening:

```bash
curl -s .../api/governance/metrics | jq '.budgets[] | {session_id, tool_calls, cost_usd}'
```

A **missing** limit key means unlimited, never zero. Removing a key relaxes the
ceiling; setting it to `0` also means unlimited. To forbid something entirely,
use a policy rule, not a limit of zero.

---

## Known limitations at merge

1. Governance covers `AgentRunner._dispatch_tool` **and** the MCP server HTTP
   surface. `runtimes/adapters/*` sidecars and direct `WorkspaceTools` calls
   are still **not** governed.
2. seccomp/AppArmor are plumbed but no profile is authored.
3. The audit trail has no cryptographic integrity guarantee.
4. Budgets are per-session and in-process; there is no global fleet budget.
5. The compose hardening overlay is unverified against a live daemon.

All are tracked in `docs/governance/threat-model.md#7-priority-follow-ups`.
