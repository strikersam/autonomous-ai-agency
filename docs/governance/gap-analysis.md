# Docker AI Governance — Gap Analysis

Audit of this repository against every capability described in
[Docker AI Governance: Unlock Agent Autonomy, Safely](https://www.docker.com/blog/docker-ai-governance-unlock-agent-autonomy-safely/)
and the related Docker MCP Gateway / Catalog material.

**Date:** 2026-08-06 · **Baseline commit:** `8623f2b` · **Scope:** whole repository.

---

## 0. The finding that shapes everything else

**Docker AI Governance, as a product, cannot be deployed on this platform's
production topology — and a naïve port of it would have produced a security
control that silently does nothing in production.**

Evidence, verified in-repo:

| Fact | Source |
|---|---|
| Production backend runs `env: docker`, `dockerfilePath: ./Dockerfile.backend` | `render.yaml:2-6` |
| Render provides no Docker socket to a deployed service | Render platform model; no `docker.sock` mount exists anywhere in `render.yaml` |
| The only existing socket reference is an unused adapter comment | `runtimes/adapters/openhands.py:41` |

The production backend **is** a container on a managed host. It cannot create
sibling containers, so "every agent executes inside an isolated container" is
not achievable there by any amount of code. Docker AI Governance itself is
additionally a commercial SaaS control plane (admin console, SAML/SCIM,
policy push to enrolled Docker Desktop installs) — this is a self-hosted
platform with no Docker Desktop fleet and no IdP integration.

**Consequence for the design.** The valuable part of Docker AI Governance is
not the product; it is the *architecture*: one policy model, evaluated at a
single chokepoint, across four control surfaces, producing a structured audit
trail. That architecture is portable. It was implemented natively, and the
runtime-isolation surface was made backend-pluggable so it engages with
whatever the deployment can actually provide:

```
docker  → self-hosted / laptop / CI   (hardened `docker run`, kernel-enforced)
e2b     → Render production           (Firecracker micro-VM over HTTPS)
local   → neither available           (in-process policy only, reported as such)
```

The `local` backend exists specifically so the absence of a hard boundary is
**visible** (`GET /api/governance/status` → `backend: local`, `isolation: none`)
rather than silently assumed.

---

## 1. Capability-by-capability

Format per the audit request: Current State · Desired State · Benefits ·
Complexity · Risk · Recommendation · Approach · Priority.

### 1.1 Agent Identity

| | |
|---|---|
| **Current state** | **None.** `AgentRunner._dispatch_tool(tool, args, user_id, memory_store)` received no notion of which agent was acting. Agent actions were anonymous: audit rows could record *what* happened, never *who*. No per-agent restriction was expressible because there was no subject to attach one to. |
| **Desired state** | Every action carries a stable agent id, an owner, roles, a policy group, and a per-run session id, plus execution context (task, repo, branch, commit, runtime, sandbox, source IP). |
| **Benefits** | Measurable: audit rows attributable to an agent went 0% → 100%. Unlocks per-agent policy, per-session budgets, and per-agent audit history — none of which are expressible without it. |
| **Complexity** | Low. Pure dataclass, no I/O, cannot fail. |
| **Risk** | Very low. Derived from data call sites already hold. |
| **Recommendation** | **Implement.** Prerequisite for every other capability. |
| **Approach** | `packages/governance/identity.py`. Stable `agent_id` = slug of agent name; ephemeral `session_id` per run. `resolve_identity_for_runner()` derives one from an existing `AgentRunner` and caches it, so no call site had to be re-threaded. |
| **Priority** | **P0 — done** |

### 1.2 Tool Governance

| | |
|---|---|
| **Current state** | Partial and scattered. `agent/capability_registry.py` registers tools but has no allow/deny concept. `services/guardrails.py` filters LLM *content*, not tool calls. `agent/autonomy_gate.py` blocks two specific actions (master writes, agent merges) in one module. No per-agent tool restriction existed. |
| **Desired state** | Every tool allow-listed / deny-listed / approval-gated per agent, evaluated at one chokepoint. |
| **Benefits** | A research agent that cannot call `write_file` cannot be prompt-injected into writing files. Converts "the agent shouldn't do that" from a prompt instruction into an enforced property. |
| **Complexity** | Medium — the matcher and the precedence order need care. |
| **Risk** | **Medium-high**: a wrong allow-list breaks working agents. Mitigated by observe mode. |
| **Recommendation** | **Implement, ship in observe mode.** |
| **Approach** | `packages/governance/policy.py` + the single seam in `AgentRunner._dispatch_tool`. A tool call is evaluated on **two** surfaces (the tool name and its subject — path/host/repo) and the stricter verdict wins. |
| **Priority** | **P0 — done** |

### 1.3 Runtime Isolation

| | |
|---|---|
| **Current state** | Weak where it existed. `runtimes/adapters/docker_agent.py` spawns containers with **no** `cap_drop`, no `security_opt`, no read-only rootfs, no resource limits, and `--network host` by default. `docker-compose.yml` runs every service as root with no limits. E2B (`services/e2b_sandbox.py`) provides real micro-VM isolation but is opt-in, disabled by default, and only wired into the agent tool path. |
| **Desired state** | Rootless, cap-dropped, seccomp/AppArmor-constrained, read-only-rootfs, network-isolated, cgroup-limited, tmpfs-scratch, non-root sandboxes per profile. |
| **Benefits** | The only control that survives a fully prompt-injected agent. Everything else is in-process and shares a memory space with the attacker's instructions. |
| **Complexity** | **High** — and the production topology blocks the Docker path entirely (§0). |
| **Risk** | Medium. Over-tight isolation breaks legitimate work (Playwright needs `SYS_ADMIN`; npm needs a writable rootfs). |
| **Recommendation** | **Implement, backend-pluggable.** Do **not** make Docker mandatory. |
| **Approach** | `packages/governance/sandbox.py`: 8 profiles, all least-privilege by default; `docker`/`e2b`/`local` backends selected by capability probe. Hardening flags are asserted in unit tests against a fake runner, because "did we ask for `--cap-drop=ALL`" is the testable property; whether the daemon honours it is a host fact, reported by `probe()`. |
| **Priority** | **P0 — done** (Docker + E2B paths), **P2** for a rootless-daemon deployment recipe |

**Per-control status:**

| Control | Status | Note |
|---|---|---|
| Dropped Linux capabilities | ✅ `--cap-drop=ALL` on every profile | `browser` adds back exactly `SYS_ADMIN`, `SYS_CHROOT` |
| no-new-privileges | ✅ every profile | |
| Read-only filesystem | ✅ default on; off for `browser`, `node`, `docker`, `documentation` | Each opt-out is explicit and commented |
| tmpfs scratch | ✅ `noexec,nosuid` where the workload allows | |
| Network isolation | ✅ `--network=none` default; `bridge` only where needed | |
| cgroup limits | ✅ cpu, memory, memory-swap, pids | swap pinned to memory so the cap can't be evaded |
| Non-root user | ✅ `65532:65532` default | |
| seccomp / AppArmor | ⚠️ **plumbed, not shipped** | Fields exist and are passed when set; no profile authored yet — writing a seccomp profile without being able to run a container to test it would be fake competence. Tracked as P2. |
| Rootless daemon | ⚠️ **reported, not enforceable from here** | Host setting. `probe()` surfaces it on the status endpoint. |
| User namespaces | ❌ not addressed | Daemon-level (`--userns-remap`); documented, not code. |

### 1.4 Secret Management

| | |
|---|---|
| **Current state** | **The worst gap found.** `docker-compose.yml` gives `env_file: .env` to `proxy`, `hermes`, and `dashboard-backend` — every service receives *every* secret in the file, including ones it never uses. `Dockerfile` `COPY . /app` copies the build context wholesale. Against that, the app-layer discipline is genuinely good: `packages/config/settings.py` is a real single-reader, `services/e2b_config.py` never lets the key escape its dataclass, and `packages/security/redact.py` exists. **No hardcoded secrets were found in source.** |
| **Desired state** | Per-service, per-sandbox least-privilege credential scoping; session-scoped tokens; no secret in an audit row or an approval request. |
| **Benefits** | A compromised runtime sidecar currently reads the Anthropic key, the GitHub PAT, the Mongo URL, and the JWT secret. Scoping turns one compromise into one credential. |
| **Complexity** | Medium for sandboxes (done), **high** for the compose split (behavioural). |
| **Risk** | Changing `env_file` breaks anyone relying on a variable being present — a real Golden Rule violation. |
| **Recommendation** | **Partially implement.** Do the parts that are additive; document the compose split rather than forcing it. |
| **Approach** | Sandbox `env_allowlist` — a profile decides what a sandbox may authenticate as, and an undeclared name is dropped even if the caller passes it (tested). Audit + approval redaction at write time, covering 7 provider token shapes and connection URIs. Docker Secrets **not** adopted: they require Swarm, which this stack does not use; the equivalent on Render/Compose is per-service environment scoping. |
| **Priority** | **P0 — done** (sandbox + redaction); **P1 — documented, not forced** (compose split) |

### 1.5 Policy Engine

| | |
|---|---|
| **Current state** | None. Scattered ad-hoc checks: `agent/autonomy_gate.py`, `services/guardrails.py`, `unsafe_target_reason()` in `agent/web_reach.py`, `_require_admin` in routers. Each is correct; none is a policy, and none is inspectable as one. |
| **Desired state** | One declarative engine covering tools, filesystem, network, credentials, shell, GitHub, Docker, database, MCP, browser, memory, LLM providers. |
| **Benefits** | Rules become reviewable in a PR instead of distributed across five modules. Adding a rule stops requiring a code change. |
| **Complexity** | Medium-high. |
| **Risk** | Medium — mitigated by observe mode and by degrading to an embedded default on a bad file rather than denying everything. |
| **Recommendation** | **Implement.** All 13 requested surfaces are modelled. |
| **Approach** | `config/agent_policy.yaml`. Baseline rules are structurally non-overridable: `evaluate()` returns on a baseline DENY *before* reading any group rule, so a group's allow-list is never consulted on that path. |
| **Priority** | **P0 — done** |

### 1.6 Approval Workflows

| | |
|---|---|
| **Current state** | Exists for *tasks* (`tasks/service.py`, `telegram_bot.py`, `schedules/api.py` — an `awaiting_approval` state), but nothing at the *action* level. An approved task could then take any action it liked. |
| **Desired state** | Per-action human-in-the-loop for git push, deletes, shell, Docker build/exec, deployment, production access, DB writes. |
| **Benefits** | Bounds the blast radius of a single bad plan without requiring approval of every step. |
| **Complexity** | Medium — the async wait across thread boundaries is the fiddly part. |
| **Risk** | **An approval that blocks forever is a hang**, and this repo already has a live history of 600s execution timeouts. |
| **Recommendation** | **Implement, with a mandatory TTL.** |
| **Approach** | `packages/governance/approvals.py`. Every request has a TTL; **timeout denies** (an approval that opens when ignored is theatre). First decision wins, so a retried webhook cannot flip an approval. `GOVERNANCE_AUTO_APPROVE` exists for local dev, is off by default, and is audited as `resolved_by=auto-approve` when it fires. |
| **Priority** | **P0 — done** |

### 1.7 Audit Trail

| | |
|---|---|
| **Current state** | Application logging only. `services/otel_tracing.py` and `services/cost_attribution.py` exist and are good, but nothing joins an action to an actor. None of the 20 requested fields were captured together. |
| **Desired state** | who / what / when / why / tool / arguments / result / duration / cost / LLM / model / tokens / container / IP / repo / branch / commit. |
| **Benefits** | The SOC2/ISO27001 evidence artefact, and the debugging artefact. Went from 0 → all 20 fields (test-asserted). |
| **Complexity** | Low-medium. |
| **Risk** | **Arguments carry secrets.** `clone_repo` takes a `github_token`; this repo leaked a live MongoDB password into a log line on 2026-08-01. |
| **Recommendation** | **Implement, redacting at write time.** |
| **Approach** | `packages/governance/audit.py`. Redaction happens in `__post_init__` — *before* the event is stored anywhere, so the secret is never in the ring buffer. Fails **closed** (`[redaction-failed:withheld]`). Bounded ring buffer + one-line JSON to a dedicated `governance.audit.events` logger for SIEM shipping. |
| **Priority** | **P0 — done** |

### 1.8 Observability

| | |
|---|---|
| **Current state** | **Already good.** `services/otel_tracing.py` (OTel with no-op fallback), Langfuse, `services/cost_attribution.py`, `agent/loop.py::_timed_phase` phase timing, `GET /api/metrics/self-heal`. |
| **Desired state** | Governance decisions visible alongside existing telemetry. |
| **Benefits** | Moderate — mostly additive to a working system. |
| **Complexity** | Low. |
| **Risk** | Low. |
| **Recommendation** | **Extend, do not rebuild.** Adding a second tracing stack would violate the no-duplicate-logic rule for no gain. |
| **Approach** | `GET /api/governance/metrics` exposes decision counters, per-agent activity, `would_block`, and live budgets. Duration and cost ride on the existing audit event. **Not implemented:** a parallel OTel exporter — `services/otel_tracing.py` already owns that concern. |
| **Priority** | **P1 — done (extension)** |

### 1.9 Container Security / Supply Chain

| | |
|---|---|
| **Current state** | **Nothing.** Verified by search: no Trivy, no Docker Scout, no Syft, no SBOM, no cosign, no hadolint anywhere in 40 workflows. 11 Dockerfiles shipped entirely unscanned. CodeQL and Bandit cover source only. |
| **Desired state** | Image CVE scanning, SBOM, dependency scanning, Dockerfile lint, provenance. |
| **Benefits** | Highest benefit-to-effort ratio in this entire audit. A critical base-image CVE currently reaches production undetected. |
| **Complexity** | **Low** — one workflow file. |
| **Risk** | Low. Scanners are advisory until you make them blocking. |
| **Recommendation** | **Implement immediately.** |
| **Approach** | `.github/workflows/supply-chain.yml`: hadolint (advisory), Trivy image scan → SARIF → code scanning, Trivy fs scan for dependency CVEs, CycloneDX SBOM (90-day retention), and `scripts/check_container_posture.py`. Gate fails only on **fixable CRITICAL** — the narrowest gate that is always actionable. **Trivy over Docker Scout** because Scout needs an authenticated Docker Hub account in CI; a scanner nobody can run is not a control. |
| **Priority** | **P0 — done** |
| **Not implemented** | **Image signing / attestation (cosign, SLSA provenance).** Images are built by Render and Cloudflare from source on merge; there is no registry push step in this repo to sign, and no verifying admission controller to check a signature. Signing here would produce an artefact nothing verifies — security theatre. Revisit if the platform moves to Kubernetes with a registry. |

### 1.10 Least Privilege

| | |
|---|---|
| **Current state** | Poor at the container layer, good at the app layer. Every compose service runs as root with no limits; Mongo publishes `27017` on `0.0.0.0`; `.env` is broadcast to three services. |
| **Desired state** | Minimum permissions per component; nothing privileged without justification. |
| **Recommendation** | **Implement for new surfaces; offer, don't force, for existing ones.** |
| **Approach** | New sandboxes are least-privilege by construction. Existing services get `docker-compose.hardening.yml` — an opt-in overlay, because `read_only` and `cap_drop` break containers in ways that only appear at runtime and **could not be verified in this environment** (no Docker daemon available). Shipping unverified hardening as the default would be exactly the "phantom verification" failure this repo's standing instructions forbid. |
| **Priority** | **P1 — overlay shipped, adoption is the operator's call** |

### 1.11 Multi-Agent Governance (10 / 100 / 1000 agents)

| | |
|---|---|
| **Current state** | No per-agent limits, no concurrency cap, no backpressure. |
| **Analysis** | **10 agents:** in-process policy is fine; the ring buffer holds. **100 agents:** the 2000-event buffer covers minutes, not hours — SIEM shipping via the `governance.audit.events` logger becomes mandatory, and `max_concurrent` sandboxes is what prevents host exhaustion. **1000 agents:** the in-process singleton engine and in-memory approval store are the limits. Policy is read-mostly so it shards fine; approvals and audit need external storage, and identity needs a real IdP rather than a name slug. |
| **Recommendation** | Implement bounded concurrency and per-session budgets now; document the 1000-agent architecture rather than building for a scale the platform is not at. |
| **Approach** | `SandboxManager(max_concurrent=…)` raises `SandboxUnavailableError` — backpressure, not exhaustion (tested). Per-session budgets. Every buffer is bounded with explicit eviction. |
| **Priority** | **P0 for ≤100 (done)**, **P3 for 1000 (documented)** |

### 1.12 Cost Governance

| | |
|---|---|
| **Current state** | `services/cost_attribution.py` **measures** spend; nothing **caps** it. `MAX_SUBAGENT_DEPTH` (`agent/loop.py:231`) is the only existing runaway guard. |
| **Desired state** | Enforced ceilings on runaway loops, token explosions, tool abuse, recursive agents, infinite retries, LLM storms, resource exhaustion. |
| **Benefits** | Directly addresses failure modes this repo has already suffered — see the schedule-backlog OOM crash loop (CHANGELOG 2026-08-02/03). |
| **Complexity** | Low. |
| **Risk** | A ceiling set too low kills legitimate long tasks. |
| **Recommendation** | **Implement.** A policy file cannot stop a loop; a counter can. |
| **Approach** | `SessionBudget` in `enforcement.py`: `max_tool_calls`, `max_cost_usd`, `max_tokens`, `max_duration_s`, `max_depth`, `max_retries`, per policy group. A missing limit key means *unlimited*, never *zero* — absence must not silently block everything (tested). |
| **Priority** | **P0 — done** |

### 1.13 Compliance (SOC2 / ISO27001 / GDPR)

| | |
|---|---|
| **Current state** | No structured evidence artefact. |
| **Assessment** | The audit trail is a genuine input to **SOC2 CC6.1** (logical access), **CC7.2** (monitoring), **CC8.1** (change management) and **ISO27001 A.9/A.12.4**. Honest framing: this produces *evidence*, not *compliance* — compliance is an organisational programme, and claiming otherwise would be the most dangerous sentence in this document. **GDPR:** largely out of scope; the trail records agent identities and operator emails, not end-user personal data. Note that `owner` is an email, so an audit export is in scope for a data-subject request — retention is the operator's decision, which is why the durable sink is a log stream you control rather than a database this repo manages. |
| **Recommendation** | Provide the evidence surface; do not claim compliance. |
| **Priority** | **P1 — done** |

### 1.14 Local Development Experience

| | |
|---|---|
| **Requirement** | Governance must not reduce developer productivity. |
| **Assessment** | The single biggest adoption risk. A governance layer that makes local development annoying gets disabled, and then it protects nothing. |
| **Approach** | Four deliberate choices: (1) **observe mode by default** — nothing blocks; (2) `GOVERNANCE_ENABLED=false` is a complete, instant off switch; (3) `GOVERNANCE_AUTO_APPROVE=true` for local approval gates; (4) the `local` sandbox backend means no Docker daemon is ever required. `docker compose up` is byte-for-byte unchanged. |
| **Priority** | **P0 — done** |

---

## 2. Deliberately not implemented

Per the brief: *"If a Docker AI Governance capability is not suitable, explicitly explain why and do not implement it."*

| Capability | Why not |
|---|---|
| **Docker MCP Gateway / Catalog** | This repo runs its own MCP server (`mcp_server/`) and `agent/mcp_client.py`. Adopting Docker's gateway means routing tool calls through a service that must be deployed alongside a Render backend that cannot run containers. The *value* of the gateway — one authenticated, authorised, logged chokepoint — was implemented natively at `_dispatch_tool`, which is a chokepoint the platform already has. |
| **Docker Secrets** | Requires Swarm mode. This stack uses plain Compose and Render. The equivalent control (per-service credential scoping) is implemented as sandbox `env_allowlist` and documented for Compose. |
| **SAML / SCIM identity federation** | Requires an enterprise IdP. This platform has GitHub and Google OAuth and a local admin. `AgentIdentity` carries `owner` and `roles` so an IdP can populate them later without a redesign, but building federation for a platform with one admin would be complexity with no user. |
| **Central admin console with policy push** | Docker's model pushes policy to enrolled Docker Desktop installs on developer laptops. This is one self-hosted deployment; policy is a git-reviewed file with a hot-reload endpoint, which is strictly better for a single deployment (reviewable, versioned, revertible). |
| **Image signing / attestation** | No registry push in this repo and no verifying admission controller. A signature nothing verifies is theatre. See §1.9. |
| **Seccomp / AppArmor profiles** | Plumbed but not authored. Writing and shipping a seccomp profile that could not be tested against a running container in this environment would be exactly the fabricated-verification failure mode this repo's standing instructions call out. The mechanism is ready; the profile is P2 work for someone with a daemon. |
| **User-namespace remapping** | Daemon-level host configuration (`--userns-remap`), not something application code can set. Documented in the deployment guide. |

---

## 3. Prioritised summary

| Priority | Capability | Status |
|---|---|---|
| P0 | Agent identity | ✅ Implemented |
| P0 | Policy engine (13 surfaces) | ✅ Implemented |
| P0 | Tool governance at one chokepoint | ✅ Implemented |
| P0 | Audit trail (20 fields, redacted) | ✅ Implemented |
| P0 | Approval workflows with TTL | ✅ Implemented |
| P0 | Cost / runaway governance | ✅ Implemented |
| P0 | Sandbox profiles + 3 backends | ✅ Implemented |
| P0 | Supply-chain CI | ✅ Implemented |
| P1 | Egress policy on Web Reach | ✅ Implemented |
| P1 | Governance API + metrics | ✅ Implemented |
| P1 | Compose hardening | ⚠️ Overlay shipped, opt-in |
| P1 | Per-service secret scoping | 📋 Documented, not forced |
| P2 | seccomp / AppArmor profiles | 📋 Plumbed, not authored |
| P2 | Rootless daemon recipe | 📋 Documented |
| P3 | External audit/approval storage (1000 agents) | 📋 Documented |
| — | MCP Gateway, Docker Secrets, SAML/SCIM, signing | ❌ Explicitly declined, §2 |
