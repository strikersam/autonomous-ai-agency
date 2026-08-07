# Deployment, Docker & Troubleshooting Guide

How to run the governance layer in each environment, what the container
hardening does, and what to do when something breaks.

---

## 1. Which sandbox backend applies where

| Environment | Backend | How to get it |
|---|---|---|
| Developer laptop | `docker` (or `local`) | Any running Docker daemon |
| CI (GitHub Actions) | `docker` | Present on `ubuntu-latest` |
| Self-hosted / VPS | `docker` | Preferably a **rootless** daemon |
| **Render (production)** | **`e2b`** | `E2B_ENABLED=true` + `E2B_API_KEY` |
| Anywhere else | `local` | Automatic fallback — **no isolation** |

### Why production cannot use Docker

`render.yaml` deploys with `env: docker` and `dockerfilePath: ./Dockerfile.backend`.
The application **is** a container on a managed host. Render provides no Docker
socket, so the process cannot create sibling containers. This is a platform
property, not a configuration gap.

E2B works there because it is a remote Firecracker micro-VM reached over
HTTPS — no local daemon required, and a *stronger* boundary than a shared-kernel
container.

```bash
# Render dashboard → Environment
E2B_ENABLED=true
E2B_API_KEY=e2b_...
GOVERNANCE_SANDBOX_BACKEND=auto      # probes docker → e2b → local
```

Verify:
```bash
curl -s https://<host>/api/governance/status -H "Authorization: Bearer $ADMIN_JWT" \
  | jq '{backend: .sandbox.backend, isolation: .sandbox.isolation}'
```

If this returns `"backend": "local"`, **there is no sandbox isolation** — only
in-process policy. That is reported rather than hidden precisely so it can be
noticed.

---

## 2. Container hardening

### What each flag buys

| Flag | Stops |
|---|---|
| `--cap-drop=ALL` | Almost every privilege-escalation primitive (`CAP_SYS_ADMIN`, `CAP_SYS_PTRACE`, …) |
| `--security-opt=no-new-privileges:true` | setuid binaries gaining privileges after exec |
| `--read-only` | Persisting a payload into the image filesystem |
| `--tmpfs /tmp:noexec,nosuid` | Writing then executing a dropped binary |
| `--user 65532:65532` | Root inside the container (and root-mapped writes outside) |
| `--network=none` | All egress — the exfiltration half of prompt injection |
| `--pids-limit` | Fork bombs |
| `--memory` + `--memory-swap` | Memory exhaustion. **Both** are set: without pinning swap, a memory-capped container silently swaps instead of being limited |
| `--cpus` | CPU starvation of the host |
| `--rm` | Container accumulation |

### Applying the overlay to the local stack

```bash
docker compose -f docker-compose.yml -f docker-compose.hardening.yml up
```

**This overlay is opt-in and has not been verified against a live daemon** — no
Docker daemon was available in the environment where it was authored. Adopt it
service by service and watch for the failure modes below.

### Rootless daemon (self-hosted)

Rootless is a **host** setting; no application code can enable it.

```bash
dockerd-rootless-setuptool.sh install
export DOCKER_HOST=unix:///run/user/$UID/docker.sock
docker info --format '{{.SecurityOptions}}'    # expect: name=rootless
```

The governance status endpoint reports `rootless: true|false` under
`sandbox.isolation.daemon`.

### User-namespace remapping (alternative to rootless)

```json
// /etc/docker/daemon.json
{ "userns-remap": "default" }
```

Container root maps to an unprivileged host uid. Note that this breaks bind
mounts owned by the host user until ownership is adjusted.

### Never do this

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock    # ← host root, one step away
privileged: true                                  # ← host root, directly
```

Both void every other control on this page. `scripts/check_container_posture.py`
fails CI if either appears. For agent-driven image builds, point `DOCKER_HOST`
at a rootless or remote BuildKit endpoint instead.

---

## 3. Supply chain

`.github/workflows/supply-chain.yml` runs on PRs and pushes that touch
Dockerfiles, compose files, `requirements.txt`, or sandbox profiles.

| Job | Tool | Gate |
|---|---|---|
| Dockerfile lint | hadolint | Advisory |
| Image CVEs | Trivy → SARIF → code scanning | **Fails on fixable CRITICAL** |
| Dependency CVEs | Trivy fs → SARIF | Advisory |
| SBOM | Trivy CycloneDX | Artifact, 90-day retention |
| Posture | `scripts/check_container_posture.py` | **Fails** on privileged / socket mount / root user / weakened profile |

**Trivy rather than Docker Scout:** Scout's useful output requires an
authenticated Docker Hub account in CI. A scanner nobody can run is not a
control. Scout remains a good local complement — `docker scout cves <image>`.

The gate deliberately fires only on **fixable** CRITICALs: that always means
"a patched version exists and we are not on it", which is actionable. An
unfixable CVE blocking every merge trains people to bypass the gate.

Run the posture check locally:
```bash
python scripts/check_container_posture.py
```

---

## 4. Troubleshooting

### `backend: local` when you expected `docker`

```bash
docker info                      # daemon reachable?
echo $DOCKER_HOST
curl -s .../api/governance/status | jq .sandbox.probes
```
`probes` contains the exact reason each backend was rejected.

### `backend: local` when you expected `e2b`

Requires **all** of: `E2B_ENABLED=true` (a bare key does not auto-enable —
see `services/e2b_config.py`), a non-empty `E2B_API_KEY`, and the
`e2b-code-interpreter` SDK installed.

### Agents suddenly failing after enabling enforcement

Expected. Find what is being blocked:
```bash
curl -s '.../api/governance/audit?decision=deny&limit=50' \
  | jq '.events[] | {agent_id, action, rule_id, reason}'
```
`rule_id` names the exact rule. Either the rule is too broad — fix it, then
`POST /api/governance/policy/reload` — or it caught something real.

Emergency rollback, no deploy needed: set `mode: observe` and reload, or set
`GOVERNANCE_ENABLED=false`.

### An agent is stuck

Probably waiting on an approval:
```bash
curl -s .../api/governance/approvals | jq '.approvals[] | {approval_id, agent_id, action, seconds_remaining}'
```
Approve, deny, or wait for the TTL (default 300s) to expire it into a denial.
For local development, `GOVERNANCE_AUTO_APPROVE=true`.

### Container exits immediately under the hardening overlay

| Symptom | Cause | Fix |
|---|---|---|
| Mongo exits at boot | Needs `CHOWN`/`SETUID`/`SETGID` to drop privileges | Already handled in the overlay |
| `EACCES` writing a path | `read_only: true` | Add a `tmpfs` for that path, or drop `read_only` for that service |
| `EACCES` on a bind mount | Non-root uid cannot write a host dir | `chown 65532:65532` the host dir, or remove `user:` |
| Playwright won't start | Chromium needs `SYS_ADMIN` | Use the `browser` profile — it adds back exactly `SYS_ADMIN` and `SYS_CHROOT`. **Do not** use `privileged: true` |
| `bind: permission denied` on a low port | `cap_drop: ALL` removes `NET_BIND_SERVICE` | Publish a high port, or add that one capability back |

### Sandbox creation fails with "limit reached"

Working as intended — backpressure, not exhaustion.
```bash
curl -X POST .../api/governance/sandboxes/reap    # destroy expired
```
Raise `GOVERNANCE_MAX_SANDBOXES` only if the host can carry the concurrency.

### Audit trail is empty

Check `GOVERNANCE_ENABLED`, then that traffic is actually flowing through
`AgentRunner._dispatch_tool` — direct `WorkspaceTools` calls and the MCP server
HTTP surface are **not** governed (see the threat model, T11).

---

## 5. Scaling

| Agents | What changes |
|---|---|
| **10** | Defaults are fine. The 2000-event buffer holds hours. |
| **100** | Ship audit to a SIEM — the buffer now covers minutes. Raise `GOVERNANCE_MAX_SANDBOXES` to what the host can carry. Watch `would_block` per agent to catch a group whose limits are wrong. |
| **1000** | The in-process singletons are the limit. Approvals and audit need external storage; identity needs a real IdP rather than a name slug. Policy is read-mostly and shards fine. This is a design change, not a config change. |

Ship the audit stream:
```python
import logging
h = logging.FileHandler("/var/log/agency/audit.jsonl")
logging.getLogger("governance.audit.events").addHandler(h)
```
Each line is one self-contained JSON event, already redacted.
