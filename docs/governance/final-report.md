# Docker AI Governance Audit — Final Report

Architecture review, risk assessment, security review, and summary of what was
implemented and why.

**Baseline commit:** `8623f2b` · **Date:** 2026-08-06 · **Scope:** whole repository

---

## 1. Executive summary

This platform's application-layer engineering is genuinely good — a real
single-source config module, secrets that never escape their dataclass, an SSRF
guard that resolves and re-validates every redirect hop, working OTel and cost
attribution. **No hardcoded secrets were found in source.**

Its *agent governance* layer did not exist, and its *container* layer was the
weakest part of the system.

Three findings drove everything implemented:

1. **Agent actions were anonymous.** `AgentRunner._dispatch_tool` received a
   tool name and an argument dict with no notion of which agent asked. No
   per-agent restriction was expressible, because there was no subject to
   attach one to.

2. **The container supply chain was entirely unscanned.** Across 11 Dockerfiles
   and 40 workflows: no Trivy, no Scout, no Syft, no SBOM, no cosign, no
   hadolint. CodeQL and Bandit cover source only. A critical base-image CVE
   reached production undetected. This was the highest benefit-to-effort gap
   found, and it was closed with one workflow file.

3. **Docker AI Governance cannot be deployed on this topology at all** — and a
   naïve port would have shipped a control that silently does nothing in
   production. `render.yaml` deploys with `env: docker`: the application *is* a
   container on a managed host, with no Docker socket. It cannot create sibling
   containers. The valuable part of Docker's model is the *architecture* — one
   policy, one chokepoint, four surfaces, a structured trail — and that is what
   was implemented, with the isolation surface made backend-pluggable so it
   engages with whatever the deployment can actually provide.

Everything ships in **observe mode**: rules are evaluated and audited, nothing
is blocked, no behaviour changes. That is a requirement of this repo's Golden
Rule and also the only honest way to enable a policy engine in a system running
34 autonomous loops — you cannot know a rule is correct until you have seen
what it would have caught.

---

## 2. Architecture review

### What was already right, and was extended rather than replaced

| Existing | Assessment | Decision |
|---|---|---|
| `packages/config/settings.py` | A real single env reader | Extended with 9 settings |
| `services/e2b_config.py` | Key never escapes the dataclass; explicit opt-in after a bad experience | Reused verbatim |
| `services/e2b_sandbox.py` | Full micro-VM session, token scrubbing, seed/extract data flow | Wrapped as a backend — **no sandbox mechanics reimplemented** |
| `unsafe_target_reason()` | Resolves every address, re-validates redirect hops | Kept as the primary check; policy consulted strictly after |
| `services/otel_tracing.py`, `cost_attribution.py` | Working observability with no-op fallbacks | Extended, **not** duplicated with a second tracing stack |
| `agent/autonomy_gate.py` | Correct, but one module | Left in place; its intent now also expressed as policy |
| Router builder pattern (`spec_router`, `ceo_router`) | Clean auth injection | Followed exactly |

### What was added

```
packages/governance/
  identity.py      who is acting          — pure dataclass, cannot fail
  policy.py        what the rules say     — pure evaluation, no side effects
  approvals.py     human decisions        — TTL-bounded, fails closed
  audit.py         the evidence trail     — redacts before storing
  sandbox.py       hardened execution     — docker / e2b / local
  enforcement.py   the ONLY module that acts on a decision
```

Judgement is separated from action so the engine is testable without side
effects and "what blocked this?" has exactly one answer.

### The integration decision that mattered most

`_dispatch_tool` has ~170 lines of branches, every one an early `return`. A
guard placed inline would have to be repeated per branch to be complete, and
one missed branch is a silent hole in the control.

Instead the method was renamed to `_dispatch_tool_unguarded` — **byte-identical
body** — and a thin wrapper added. This makes the behavioural question small
enough to actually verify: not "did I correctly modify 170 lines of dispatch
logic" but "is this wrapper transparent", which four tests pin directly.

### Constitution compliance

| Rule | Status |
|---|---|
| No duplicate logic | ✅ E2B reused; OTel extended; `evaluate_call()` shared by enforcer and simulator |
| No env reads outside config modules | ✅ All 9 settings in `packages/config/settings.py` |
| No secrets to disk | ✅ Redaction before storage; `env_allowlist` holds names only, CI-enforced |
| No duplicate auth | ✅ `get_current_user` injected, RBAC mirrored |
| No circular imports | ✅ Lazy `__getattr__` + function-local imports |
| Every endpoint has a test | ✅ 13 routes, all covered |
| compileall passes | ✅ Verified |
| Changelog parity | ✅ Verified |

---

## 3. Risk assessment

### Risks introduced by this change

| # | Risk | Likelihood | Impact | Mitigation | Residual |
|---|---|---|---|---|---|
| R1 | The gate breaks agent dispatch | Low | **Critical** | Every path wrapped, fails open with an audited `enforcement.error.fail-open`; wrapper transparency tested; observe mode default | **Low** |
| R2 | A bad policy blocks legitimate work | Medium | High | Observe default; `would_block` metric; simulate endpoint; hot reload; three rollback levers needing no deploy | **Low** |
| R3 | Malformed policy YAML denies everything | Low | High | Falls back to the embedded default (a real policy, not allow-all) and logs an error | **Very low** |
| R4 | Approval gate hangs an agent | Medium | High | Mandatory TTL; expiry denies; `GOVERNANCE_AUTO_APPROVE` for local | **Low** |
| R5 | Audit buffer leaks memory | Low | High | Bounded deques with explicit eviction everywhere (audit, approvals, budgets) | **Very low** |
| R6 | Audit trail leaks a secret | Medium | **Critical** | Redaction in `__post_init__`, before storage; 7 token shapes + connection URIs + key markers; fails closed | **Low** |
| R7 | Compose hardening breaks containers | **High** | Medium | Shipped as an **opt-in overlay**, not a default. Could not be verified — no Docker daemon available | **Accepted, opt-in** |
| R8 | Supply-chain gate blocks all merges | Low | Medium | Fires only on **fixable** CRITICAL; hadolint advisory | **Low** |
| R9 | Performance overhead per tool call | Low | Low | Two in-memory glob evaluations; no I/O, no network, no DB | **Very low** |
| R10 | False sense of security | **Medium** | **High** | Status endpoint reports `isolation: none` and rootful daemons honestly; limits documented explicitly in three places | **Medium** — see §5 |

**R10 is the one to watch.** The most dangerous outcome of this work is not a
bug; it is someone reading "governance implemented" and believing agents are
contained when the backend is `local` and the mode is `observe`. Every document
here states that explicitly, and the status endpoint refuses to overstate.

### Risks this change reduces

| Threat | Before | After |
|---|---|---|
| Prompt injection → credential theft | No control | Baseline denies `.env`, `.ssh`, `*.pem` (enforce mode); traversal-normalised |
| Base-image CVE reaching production | Undetected | CI gate on fixable CRITICAL |
| Runaway loop / cost explosion | Measured only | Six enforced per-session ceilings |
| Sandbox escape via unhardened container | No `cap_drop`, `--network host` | `cap_drop=ALL`, non-root, no-new-privileges, cgroup limits, `network=none` default |
| Unattributable agent action | 100% unattributable | 100% attributed |
| Over-broad credential exposure | Whole `.env` to every sandbox | Per-profile `env_allowlist`, undeclared names dropped |

---

## 4. Security review

Reviewed against this repo's own risky-module standards.

### Findings addressed during implementation

Three real defects were found by testing rather than assumed away:

1. **Empty allow-lists were dropped as falsy.** `write: []` — the strictest
   rule expressible — silently became "unrestricted", the most permissive
   outcome. Now `None` (absent) and `[]` (declared empty) are distinguished
   throughout. *Regression-tested.*

2. **Tool allow-lists were bypassed by any tool carrying a subject.**
   `write_file` classified to the FILESYSTEM surface, so `tool.allow: [read_file]`
   never refused it — and that applies to nearly every tool, since most carry a
   path or URL. Now both surfaces are evaluated and the stricter verdict wins,
   so the second evaluation can only ever tighten. *Regression-tested.*

3. **The simulate endpoint judged differently from the enforcer.** It skipped
   the read/write mode and the dual-surface evaluation, so it would have lied to
   exactly the operator using it to decide whether enforcement was safe.
   Extracted `evaluate_call()`; both now share one implementation. *Regression-tested.*

### Deliberate design decisions, stated for review

| Decision | Rationale |
|---|---|
| Engine fails **open** | It sits in the path of every tool call in an auto-restarting platform. Fail-closed turns a governance bug into a total outage that looks like a security feature — and the realistic result is the layer being disabled during an incident and never re-enabled. |
| Approvals fail **closed** | Small set of specifically high-risk actions where wrongly proceeding costs more than wrongly stopping. |
| Bad policy → embedded default, not deny-all | A YAML typo must not take the agency down. The fallback is a real policy with real baseline denies. |
| No HTTP endpoint writes policy | Would make "who changed the rules" unanswerable and let a stolen admin session silently disable the controls. Policy is git-reviewed. |
| Audit reads are admin-gated | An audit trail is an inventory of repos, branches, paths, and owners — what an attacker wants first. |
| Redaction at write, not read | Redacting at render time leaves the secret in the ring buffer, one serialisation bug from a response body. This repo leaked a live MongoDB password into a log line on 2026-08-01. |
| `security` profile has no egress | A scanner that reads everything *and* can reach the internet is an exfiltration path with a job title. CI-enforced. |
| No image signing | No registry push in this repo and no verifying admission controller. A signature nothing verifies is theatre. |
| No seccomp profile authored | Could not be tested against a running container here. Shipping an untested seccomp profile would be fabricated assurance. Mechanism plumbed; profile is P2. |

### Verification status — stated precisely

| Claim | Evidence |
|---|---|
| 132 governance tests pass | `pytest tests/test_governance_*.py` — executed |
| Existing tests unaffected | Full suite executed; only failure is a MongoDB connection error (no DB in this container; CI provides `mongo:7`) |
| Hardening flags are emitted | Asserted against a fake runner — the argv is the testable property |
| Observe mode is transparent | Four dedicated tests |
| Policy engine correct | 43 tests incl. 3 regressions |
| **Compose overlay works** | ❌ **NOT verified.** No Docker daemon available. Shipped opt-in for this reason. |
| **Sandbox flags honoured by a daemon** | ❌ **NOT verified.** Host property; `probe()` reports it at runtime. |
| **Supply-chain workflow runs green** | ❌ **NOT verified.** Cannot execute GitHub Actions here. Will run on first PR. |

---

## 5. What was implemented

| # | Capability | Files |
|---|---|---|
| 1 | Agent identity | `packages/governance/identity.py` |
| 2 | Policy engine, 13 surfaces (incl. `runtime`) | `packages/governance/policy.py`, `config/agent_policy.yaml` |
| 3 | Enforcement at three seams | `packages/governance/enforcement.py`, `agent/loop.py` (agent loop), `mcp_server/governance.py` (HTTP), `runtimes/routing.py` (executor choice + fallbacks) |
| 4 | Audit trail, 20 fields, redacted | `packages/governance/audit.py` |
| 5 | Approvals with TTL | `packages/governance/approvals.py` |
| 6 | Cost / runaway ceilings | `SessionBudget` in `enforcement.py` |
| 7 | Sandbox profiles + 3 backends | `packages/governance/sandbox.py`, `config/sandbox_profiles.yaml` |
| 8 | Egress policy on Web Reach | `agent/web_reach.py` |
| 9 | Governance API, 13 routes | `backend/governance_router.py` |
| 10 | Supply-chain CI | `.github/workflows/supply-chain.yml` |
| 11 | Posture guard | `scripts/check_container_posture.py` |
| 12 | Compose hardening overlay | `docker-compose.hardening.yml` |
| 13 | Tests | 4 files, 132 tests |
| 14 | Documentation | 6 documents |

### Measurable improvements

| Metric | Before | After |
|---|---|---|
| Agent actions attributable to an identity | 0% | 100% |
| Audit fields captured | 0 of 20 | 20 of 20 |
| Control surfaces with a policy model | 0 | 13 |
| Enforced cost/runaway ceilings | 1 (`MAX_SUBAGENT_DEPTH`) | 6 per session |
| Sandbox profiles dropping all capabilities | 0 of 1 | 8 of 8 |
| Container images CVE-scanned in CI | 0 of 11 | 1 of 11 (backend; the deployed one) |
| SBOMs produced | 0 | 1, 90-day retention |
| Governance tests | 0 | 132 |
| Behaviour changes on merge | — | **0** |

---

## 6. Explicitly not implemented

| Capability | Why |
|---|---|
| Docker MCP Gateway / Catalog | Requires deploying a gateway alongside a backend that cannot run containers. Its *value* — one authenticated, authorised, logged chokepoint — was implemented natively at a chokepoint the platform already has. |
| Docker Secrets | Requires Swarm. This stack uses plain Compose and Render. Equivalent control implemented as `env_allowlist`. |
| SAML / SCIM federation | Needs an enterprise IdP; this platform has OAuth and one admin. `AgentIdentity` carries `owner`/`roles` so an IdP can populate them later without redesign. |
| Central console with policy push | Docker pushes policy to enrolled Desktop installs. This is one self-hosted deployment; a git-reviewed file with hot reload is strictly better here. |
| Image signing / attestation | No registry push, no verifying admission controller. |
| seccomp / AppArmor profiles | Plumbed; not authored, because untestable here. |
| User-namespace remapping | Host daemon configuration, not application code. Documented. |

---

## 7. Remaining recommendations

| Priority | Work | Why |
|---|---|---|
| **P0** | Run 1–2 weeks in observe, then move to `enforce` | Until then nothing is blocked. This is the single highest-value follow-up. |
| **P0** | Set `E2B_ENABLED=true` in production | Without it the backend is `local` — no hard boundary at all. |
| ~~P1~~ ✅ | ~~Extend the gate to the MCP server HTTP surface~~ | **Done** — `mcp_server/governance.py`, plus runtime dispatch via the `runtime` surface. Remaining ungoverned route: direct in-process `WorkspaceTools` calls. |
| ~~P1~~ ✅ | ~~Split `env_file: .env` per service~~ | **Done, opt-in** — `.env.backend-secrets` keeps backend-only credentials out of the `hermes` sidecar. Inert until an operator moves the values, so nothing breaks on merge. |
| **P1** | Adopt the compose hardening overlay | Verify against your own daemon first. |
| **P2** | Author and test a seccomp profile | Mechanism is ready. |
| **P2** | Rootless daemon on self-hosted installs | Closes the container-escape-to-host-root path. |
| **P3** | Hash-chained audit records | Tamper evidence. |
| **P3** | External audit/approval storage | Needed past ~100 concurrent agents. |
| **P3** | Pinned-IP fetching | Closes DNS rebinding between check and request. |

---

## 8. Future enhancements

- ~~**Dashboard page.**~~ **Done** — `frontend/src/v5/screens/GovernanceScreen.jsx`
  shows live `would_block`, the decisions behind it, pending approvals with
  approve/deny, and the real sandbox backend. The observe phase no longer
  needs a terminal.
- **Policy-aware planning.** The planner does not know its own restrictions. Feeding
  the effective policy into the plan prompt would let agents avoid blocked
  actions rather than attempting and failing them.
- **Learned limits.** Budgets are estimates chosen above observed usage, not
  derived from it. The audit trail now contains the data to set them empirically.
- **Per-tenant policy.** `AgentIdentity` has the fields; multi-tenant policy
  groups would follow naturally from the company-graph model.
- **Sandbox warm pool.** Profiles and lifecycle exist; pre-warming would cut
  startup latency for the interactive path.

---

## 9. Bottom line

The platform is meaningfully closer to enterprise-secure: every agent action is
now attributable, every control surface has a policy model, runaway cost has
enforced ceilings, containers have a hardened default posture, and the supply
chain is scanned for the first time.

It is **not yet enforcing anything**, and that is deliberate and reversible in
one config line. The gap between "audited" and "enforced" is one week of
watching `would_block` and one edit to `config/agent_policy.yaml`.

The most important thing in this report is not a feature. It is that
`GET /api/governance/status` will tell you the truth — `backend: local`,
`isolation: none`, `mode: observe` — rather than letting a green dashboard
imply containment that is not there.
