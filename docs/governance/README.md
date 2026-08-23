# Agent Governance Guide

Runtime governance for autonomous agents: identity, policy, approvals, audit,
and sandboxed execution. Modelled on
[Docker AI Governance](https://www.docker.com/blog/docker-ai-governance-unlock-agent-autonomy-safely/)
and implemented natively for this platform's topology.

**Companion documents**
- [Gap analysis](gap-analysis.md) — the full audit, capability by capability
- [Threat model](threat-model.md) — what this defends against, and what it does not
- [Deployment & Docker guide](deployment.md) — hardening, backends, troubleshooting
- [Migration notes](migration.md) — adopting this on a running install
- [Final report](final-report.md) — architecture review, risk assessment, security review

---

## The one thing to know first

**This ships in `observe` mode. Nothing is blocked until you change that.**

Enabling governance gives you an identity-attributed audit trail and a
`would_block` count. It changes no agent behaviour. Turning on enforcement is a
separate, deliberate decision — see [Turning on enforcement](#turning-on-enforcement).

---

## Why this exists

Before this layer, an agent tool call in this repo was anonymous. `AgentRunner._dispatch_tool`
received a tool name and an argument dict, with no notion of which agent asked,
who owned it, or what it was allowed to do. Three consequences:

1. **No attribution.** Logs recorded what happened, never who did it.
2. **No restriction.** A research agent and a deploy agent had identical power.
3. **No evidence.** Nothing joined an action to an actor, a cost, and a rule.

The controls that did exist were correct but scattered — `agent/autonomy_gate.py`,
`services/guardrails.py`, `unsafe_target_reason()`, `_require_admin` — each
solving one problem in one place, none inspectable as a policy.

---

## Architecture

```
   AgentRunner._dispatch_tool   mcp_server tools/call   runtimes route_and_execute
        (agent loop)              (HTTP surface)          (executor choice)
              └───────────────────────┼───────────────────────┘
                                      │
                        GovernanceGate.guard()
                                   │
        ┌──────────────┬───────────┼───────────┬──────────────┐
        │              │           │           │              │
    identity       policy      budget      approvals       audit
   who is acting  what rules  cost caps   human-in-loop   evidence
        │              │           │           │              │
        └──────────────┴───────────┼───────────┴──────────────┘
                                   │
                          SandboxManager
                                   │
              ┌────────────────────┼────────────────────┐
           docker                 e2b                 local
        hardened container    micro-VM (prod)     no isolation
```

Judgement (`policy`) is separated from action (`enforcement`) so the engine is
testable without side effects, and so "what blocked this?" has exactly one
answer.

### Modules

Three seams feed one engine. `AgentRunner._dispatch_tool` covers the agent
loop; `mcp_server/`'s `tools/call` covers the HTTP surface that exposes
clone/write/run_command/git_push over the network (identity propagates across
that process boundary via `X-Agent-*` headers); and
`runtimes/routing.py::route_and_execute` covers which *executor* a task may be
dispatched to — including every fallback runtime, not just the primary, since a
fallback runs a different adapter than the one that was checked.

| Module | Responsibility | Can it fail? |
|---|---|---|
| `identity.py` | Who is acting | No — pure dataclass, no I/O |
| `policy.py` | What the rules say | No — pure evaluation |
| `approvals.py` | Human decisions on high-risk actions | Bounded by TTL |
| `audit.py` | The evidence trail | Never raises into the caller |
| `sandbox.py` | Hardened execution environments | Degrades to `local` |
| `enforcement.py` | **The only module that acts on a decision** | Fails open, logged |

---

## Control surfaces

Docker AI Governance defines four (network, filesystem, credentials, MCP
tools). All 13 surfaces this platform exposes to agents are modelled:

| Surface | Governs | Rules written against |
|---|---|---|
| `tool` | Which tools an agent may call | tool name globs |
| `filesystem` | File reads and writes | path globs, `read`/`write` split |
| `network` | Outbound reach | domain globs, CIDRs |
| `credential` | Which secret **names** resolve | env var names |
| `shell` | Command execution | command-line globs |
| `github` | Repo operations | `owner/repo` globs |
| `docker` | Sandbox and image operations | profile / image names |
| `database` | Data access | collection / query globs |
| `mcp` | MCP server and tool access | server / tool names |
| `browser` | Browser automation | URLs |
| `memory` | Vector / memory store access | key globs |
| `llm_provider` | Which providers a group may use | provider ids |
| `runtime` | Which executor an agent may dispatch to | runtime ids |

---

## Writing policy

Policy lives in `config/agent_policy.yaml` — a git-reviewed file, not a
live-editable resource. There is deliberately **no HTTP endpoint that rewrites
the live policy file**: one would make "who changed the rules" unanswerable and
would let anyone who steals an admin session silently disable the controls.

Editing still happens in-product, the safe way — *propose, don't write*. The
**Governance** dashboard has a policy editor that:

1. loads the raw file (`GET /api/governance/policy/raw`),
2. validates a proposed document against the real `PolicyEngine` and the org
   baseline (`POST /api/governance/policy/validate`), and
3. opens a pull request carrying the change (`POST /api/governance/policy/propose`).

The change then reaches production exactly like any other: review, CI, merge.
"Who changed the rules" stays answerable — the proposer is written to the audit
trail (`action=governance.policy.propose`) and the merge is a reviewed commit —
and a compromised admin session can only open a PR a human must still merge, not
disable a control silently. Proposing requires a GitHub credential (`GH_PAT`);
without one the propose route says so rather than pretending to queue a change.

**The baseline can be tightened from the dashboard but never loosened.** A
proposal that removes any `baseline.*.deny` or `baseline.*.require_approval`
pattern is refused before a branch or PR is created — loosening an org guardrail
is exactly the "silently disable the controls" move this design prevents, so it
must go through a hand-authored git change, not the dashboard. Logic lives in
`packages/governance/authoring.py`.

### Evaluation order

```
1. baseline.deny             → DENY               (immediately; groups never consulted)
2. baseline.require_approval → REQUIRE_APPROVAL   (immediately)
3. group.deny                → DENY
4. group.require_approval    → REQUIRE_APPROVAL
5. group.allow declared but unmatched → DENY      (default-deny inside an allow-list)
6. otherwise                 → ALLOW
```

Steps 1–2 return *before* any group rule is read. That is the structural
guarantee behind "organization-wide guardrails that can't be overridden": a
group cannot re-allow a baseline denial because its allow-list is never
consulted on that path.

### `[]` and absent mean opposite things

```yaml
groups:
  reader:
    filesystem:
      read: ["**"]
      write: []      # DECLARED AND EMPTY → no writes at all
  writer:
    filesystem:
      read: ["**"]
                     # ABSENT → writes unrestricted
```

This distinction is load-bearing and tested. An earlier build dropped empty
lists as falsy, which silently turned the strictest expressible rule into the
most permissive one.

### A tool call is judged twice

`write_file` on `src/app.py` is both a TOOL fact (`write_file`) and a
FILESYSTEM fact (`src/app.py`). Both surfaces are evaluated and **the stricter
verdict wins**. Without this, `tool.allow: [read_file]` would silently fail to
refuse `write_file`, because most tools carry a path or a URL and would be
judged only on that surface.

### Example: a read-only research agent

```yaml
groups:
  research:
    extends: default
    tool:
      allow: [read_file, list_files, search_code, fetch_url, web_search]
    filesystem:
      read: ["**"]
      write: []
    limits:
      max_tool_calls: 100
      max_cost_usd: 2.0
    sandbox_profile: python

assignments:
  - match: "agent:*research*"
    group: research
```

`extends` **appends** to the parent's rules rather than replacing them, so a
child can tighten but never shrink a parent's deny-list.

---

## Cost and runaway governance

A policy file cannot stop a loop; a counter can. Per-session ceilings come from
the agent's policy group:

| Limit | Stops |
|---|---|
| `max_tool_calls` | runaway loops |
| `max_cost_usd` | token explosions |
| `max_tokens` | LLM storms |
| `max_duration_s` | wall-clock exhaustion |
| `max_depth` | recursive agent spawning |
| `max_retries` | infinite retry loops |

A **missing** limit key means unlimited, never zero — absence must not silently
block everything. Budgets are per `session_id`, so one agent exhausting its
allowance never blocks a different run.

---

## Approvals

When policy returns `REQUIRE_APPROVAL`, the action is held and a request
appears at `GET /api/governance/approvals`.

- Every request has a **TTL**; expiry **denies**. An approval gate that opens
  when ignored is theatre.
- **First decision wins** — a retried webhook cannot flip an approval.
- `resolved_by` is always recorded. "Approved" without "by whom" answers none
  of the questions an auditor asks.
- Arguments are scrubbed before a reviewer sees them.
- `GOVERNANCE_AUTO_APPROVE=true` self-approves for local development. Off by
  default, and audited as `resolved_by=auto-approve` whenever it fires.

---

## Audit trail

Every governed action emits a structured event with all 20 required fields:
who (`agent_id`, `owner`, `session_id`, `roles`, `policy_group`), what
(`surface`, `action`, `tool`, `arguments`, `result`), when (`timestamp`,
`duration_ms`), why (`decision`, `reason`, `rule_id`, `mode`, `task_id`),
where (`repo`, `branch`, `commit`, `sandbox_id`, `container_id`, `source_ip`),
and cost (`llm_provider`, `llm_model`, `total_tokens`, `cost_usd`).

**Secrets are redacted at write time, in `__post_init__` — before the event is
stored anywhere.** Redacting at render time would leave the secret sitting in
the ring buffer, one serialisation bug from a response body. This repo leaked a
live MongoDB password into a log line on 2026-08-01; that is the failure mode
being designed against. Redaction covers 7 provider token shapes, connection
URIs, and any argument key containing a secret marker, and **fails closed**.

### Shipping to a SIEM

The in-memory ring buffer serves the dashboard. The durable record is a
one-line JSON stream on the `governance.audit.events` logger:

```python
import logging
handler = logging.FileHandler("/var/log/agency/audit.jsonl")
logging.getLogger("governance.audit.events").addHandler(handler)
```

At 100+ concurrent agents, SIEM shipping stops being optional — the 2000-event
buffer covers minutes, not hours.

---

## Sandbox profiles

Eight profiles in `config/sandbox_profiles.yaml`, all least-privilege by
default. A profile must opt *out* explicitly, which makes the diff that grants
a privilege reviewable.

| Profile | Purpose | Network | Root FS |
|---|---|---|---|
| `development` | Coding, tests, patches | bridge (allow-listed) | read-only |
| `browser` | Playwright, scraping, UI QA | bridge | writable |
| `python` | Data analysis, ML | **none** | read-only |
| `node` | Frontend / Node backend | bridge (allow-listed) | writable |
| `security` | Scans, SAST, secrets | **none** | read-only |
| `documentation` | MkDocs, diagrams | **none** | writable |
| `review` | Lint, format, review | **none** | read-only |
| `docker` | Container build/test | bridge | writable |

Every profile: `--cap-drop=ALL`, `--security-opt=no-new-privileges:true`,
non-root `65532:65532`, cpu/memory/pids limits, memory-swap pinned to memory,
and a TTL.

**The `security` profile has no egress on purpose.** A scanner that reads the
whole repo *and* can reach the internet is an exfiltration path with a job
title. `scripts/check_container_posture.py` fails CI if that changes.

### Backends

| Backend | Where | Isolation |
|---|---|---|
| `docker` | Self-hosted, laptop, CI | Shared kernel + namespaces/cgroups, hardened per profile |
| `e2b` | **Production (Render)** | Firecracker micro-VM — stronger boundary |
| `local` | Neither available | **None.** Reported as such. |

Production runs on Render with `env: docker` — the app *is* a container, with
no Docker socket, so it cannot create sibling containers. E2B works there
because it is reached over HTTPS. Set `E2B_ENABLED=true` and `E2B_API_KEY` to
engage it.

`GET /api/governance/status` reports the live backend and what it actually
enforces, including `isolation: none` on `local` and a rootful Docker daemon. A
dashboard that overstates containment is worse than no dashboard.

---

## Turning on enforcement

Do not skip step 2. Flipping straight to `enforce` will break agent runs —
that is what a policy that says no does.

1. **Deploy in observe.** No behaviour change.
2. **Watch for a full workload cycle.** Open **Governance** in the dashboard
   (`/v5/governance`, admin only): it shows the live would-block count, the
   decisions behind it with the rule that fired, pending approvals, and which
   sandbox backend is actually in force. Or, from a terminal:
   ```bash
   curl -s .../api/governance/metrics | jq .audit.would_block
   curl -s '.../api/governance/audit?decision=deny&limit=100' | jq '.events[] | {agent_id, action, rule_id}'
   ```
   Every would-block is either a real finding or a rule that is too broad.
3. **Simulate before committing a rule change.**
   ```bash
   curl -X POST .../api/governance/policy/simulate \
     -H 'Content-Type: application/json' \
     -d '{"tool":"write_file","args":{"path":"render.yaml"},"policy_group":"coding"}'
   ```
   Simulation shares one implementation with live enforcement, so it cannot
   disagree with what will actually happen.
4. **Iterate until `would_block` is only what you want stopped.**
5. **Set `mode: enforce`** in `config/agent_policy.yaml` and
   `POST /api/governance/policy/reload` — no redeploy needed.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GOVERNANCE_ENABLED` | `true` | Master switch. `false` removes the layer entirely. |
| `GOVERNANCE_POLICY_PATH` | `config/agent_policy.yaml` | Policy file |
| `GOVERNANCE_SANDBOX_PROFILES_PATH` | `config/sandbox_profiles.yaml` | Profiles file |
| `GOVERNANCE_SANDBOX_BACKEND` | `auto` | `auto` \| `docker` \| `e2b` \| `local` |
| `GOVERNANCE_AUDIT_CAPACITY` | `2000` | Ring-buffer size |
| `GOVERNANCE_APPROVAL_TTL_S` | `300` | Approval wait before expiry-deny |
| `GOVERNANCE_AUTO_APPROVE` | `false` | Local-dev only |
| `GOVERNANCE_MAX_SANDBOXES` | `8` | Concurrency cap → backpressure |
| `GOVERNANCE_ARTIFACTS_DIR` | `.artifacts` | Artifact capture destination |

Note that `GOVERNANCE_ENABLED=true` is **not** the enforcement switch. The
policy file's `mode` controls whether verdicts are acted on.

---

## API

All routes require an authenticated **admin**. Reads are admin-gated too: an
audit trail is an inventory of what the platform touches, which is what an
attacker wants first.

```
GET    /api/governance/status                 backend, isolation, sandboxes
GET    /api/governance/policy                 effective policy
GET    /api/governance/policy/raw             raw agent_policy.yaml (for the editor)
POST   /api/governance/policy/reload          re-read the file, no redeploy
POST   /api/governance/policy/simulate        dry-run a decision
POST   /api/governance/policy/validate        validate a proposed policy + diff
POST   /api/governance/policy/propose         open a PR carrying a proposed policy (needs GH_PAT)
GET    /api/governance/audit                  ?limit&agent_id&session_id&surface&decision
GET    /api/governance/metrics                counters, would_block, live budgets
GET    /api/governance/approvals              pending
GET    /api/governance/approvals/all          incl. resolved
POST   /api/governance/approvals/{id}/approve
POST   /api/governance/approvals/{id}/deny
GET    /api/governance/sandboxes              live sandboxes + profiles
POST   /api/governance/sandboxes/reap         destroy expired
DELETE /api/governance/sandboxes/{id}         destroy one
```

---

## Where governance does *not* reach

Stated plainly, because a control's boundary matters as much as its coverage:

| Path | Governed? |
|---|---|
| `AgentRunner._dispatch_tool` (all 34 autonomous loops) | ✅ |
| `mcp_server/` HTTP surface | ✅ |
| `runtimes/*` dispatch — which executor an agent may use | ✅ |
| Direct in-process `WorkspaceTools` calls | ❌ |

Runtime *dispatch* is governed on the `runtime` surface, so an agent
restricted in-process can no longer route the same work to an adapter that
would do it in a container. What remains ungoverned is a direct in-process
`WorkspaceTools` call — a path only reachable by code inside this repo, not by
an agent choosing a tool.

## Local development

Governance must not make local development annoying, or it gets disabled and
then protects nothing. Four deliberate choices:

1. `mode: observe` by default — nothing blocks.
2. `GOVERNANCE_ENABLED=false` is a complete, instant off switch.
3. `GOVERNANCE_AUTO_APPROVE=true` clears approval gates locally.
4. The `local` backend means **no Docker daemon is ever required**.

`docker compose up` is byte-for-byte unchanged.

---

## Failure behaviour

| Failure | Behaviour | Why |
|---|---|---|
| Policy file missing/malformed | Falls back to the embedded default policy, logs an error | Denying everything on a YAML typo would take the agency down while looking like a security feature. The embedded default is a real policy with real baseline denies. |
| Policy engine raises | **Allows**, audits `enforcement.error.fail-open` | A governance layer that can break tool dispatch is one that gets reverted. |
| Audit sink raises | Logged, other sinks still run | Observability must not become an outage. |
| Approval never answered | Expires → **denies** | Fail closed on approvals specifically. |
| Sandbox backend unavailable | `SandboxUnavailableError` → caller uses its existing local path | Mirrors the established `MCPUnavailableError` degradation pattern. |

The asymmetry is deliberate: the engine fails **open** (availability), the
approval gate fails **closed** (safety). See the threat model for why.
