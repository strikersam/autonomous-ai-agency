"""packages/governance/sandbox.py — governed, disposable execution environments.

Docker AI Governance's runtime-isolation premise is that policy must be
enforced "at the runtime layer where the agent actually executes", inside an
environment "where filesystem and network access are controlled by a hard
boundary". This module provides that boundary, with one adaptation that the
deployment forces.

**Why there are three backends.** This platform's production deployment
(``render.yaml``) runs the backend with ``env: docker`` — the application *is*
a container on a managed host, with no Docker socket and no privilege to
create sibling containers. A Docker-only design would therefore have shipped a
sandbox that works on a laptop and silently does nothing in production, which
is the worst possible outcome for a security control. So:

  * ``docker`` — a hardened ``docker run`` per sandbox. Used on self-hosted
    installs, developer laptops, and CI, where a daemon exists.
  * ``e2b``   — E2B Firecracker micro-VMs, reached over HTTPS and therefore
    usable *from inside* the Render container. Delegates to the existing
    :mod:`services.e2b_sandbox`, which already implements the session, the
    token scrubbing, and the worktree seed/extract data flow. No sandbox
    mechanics are reimplemented here.
  * ``local``  — no isolation. Explicitly named rather than implied, so an
    operator reading ``GET /api/governance/status`` sees ``backend=local`` and
    knows the hard boundary is absent and only in-process policy applies.

Backend selection is by capability probe, not configuration guesswork:
:func:`detect_backend` prefers an explicit setting, then a reachable Docker
daemon, then a configured E2B, then ``local``.

**Profiles are the unit of governance**, matching the specialised-environment
model: a *development* sandbox and a *browser* sandbox differ in image, CPU,
memory, network reach, and installed tools, and an agent requests a capability
rather than assuming one. Every profile's defaults are least-privilege —
``cap_drop: ALL``, ``no-new-privileges``, read-only root filesystem, no
network, non-root user, pid/memory/cpu ceilings — and a profile must opt
*out* explicitly, in a file a reviewer can read.
"""
from __future__ import annotations

import asyncio
import logging
import shlex
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

log = logging.getLogger("governance.sandbox")

# Non-root uid:gid used when a profile does not name one. 65532 is the
# conventional "nonroot" id in distroless images, so the default lines up with
# the minimal base images the supply-chain guidance recommends.
DEFAULT_NONROOT_USER = "65532:65532"

# Where a sandbox's work happens. Matches services/e2b_sandbox.SANDBOX_WORKDIR
# so a task's paths mean the same thing whichever backend runs it — a
# divergence here would make artifacts and diffs land in different places
# depending on deployment, which is exactly the class of bug the E2B module's
# docstring documents fixing.
SANDBOX_WORKDIR = "/home/user/repo"


@dataclass(frozen=True)
class SandboxProfile:
    """A named, least-privilege execution environment.

    Every field has a restrictive default. A profile that needs more says so
    explicitly in ``config/sandbox_profiles.yaml``, which makes the diff that
    grants a privilege reviewable — the property that makes this governance
    rather than configuration.
    """

    name: str
    description: str = ""
    image: str = "python:3.13-slim"
    cpus: float = 1.0
    memory: str = "1g"
    pids_limit: int = 256
    # "none" | "bridge" | a named network. Default none: an agent that never
    # asked for the internet does not get it.
    network: str = "none"
    internet: bool = False
    allowed_domains: tuple[str, ...] = ()
    read_only_rootfs: bool = True
    # nosec B108 — not a host temp path. This is a `docker run --tmpfs` mount
    # spec: `/tmp` here is inside the sandbox's own mount namespace, backed by
    # an in-memory filesystem that is destroyed with the container. It exists
    # precisely so a read-only root filesystem still has scratch space, and
    # `noexec,nosuid` is what stops a dropped payload being executed from it.
    tmpfs: tuple[str, ...] = ("/tmp:rw,noexec,nosuid,size=256m",)  # nosec B108
    cap_drop: tuple[str, ...] = ("ALL",)
    cap_add: tuple[str, ...] = ()
    security_opt: tuple[str, ...] = ("no-new-privileges:true",)
    seccomp_profile: str | None = None
    apparmor_profile: str | None = None
    user: str = DEFAULT_NONROOT_USER
    ttl_s: int = 1800
    workdir: str = SANDBOX_WORKDIR
    tools: tuple[str, ...] = ()
    # Env var names this profile may receive. An allow-list, never a
    # pass-through: the compose files hand whole `.env` files to containers
    # today, and that is precisely the credential over-exposure Docker AI
    # Governance's credential surface exists to stop.
    env_allowlist: tuple[str, ...] = ()
    writable_paths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "image": self.image,
            "cpus": self.cpus,
            "memory": self.memory,
            "pids_limit": self.pids_limit,
            "network": self.network,
            "internet": self.internet,
            "allowed_domains": list(self.allowed_domains),
            "read_only_rootfs": self.read_only_rootfs,
            "tmpfs": list(self.tmpfs),
            "cap_drop": list(self.cap_drop),
            "cap_add": list(self.cap_add),
            "security_opt": list(self.security_opt),
            "seccomp_profile": self.seccomp_profile,
            "apparmor_profile": self.apparmor_profile,
            "user": self.user,
            "ttl_s": self.ttl_s,
            "workdir": self.workdir,
            "tools": list(self.tools),
            "env_allowlist": list(self.env_allowlist),
            "writable_paths": list(self.writable_paths),
        }


# Built-in profiles. These are the fallback when config/sandbox_profiles.yaml
# is absent, and the documented starting point when it is written. Each maps
# to a real job an agent in this repo does.
BUILTIN_PROFILES: dict[str, SandboxProfile] = {
    "development": SandboxProfile(
        name="development",
        description="Coding, refactoring, running unit tests, producing patches.",
        image="python:3.13-slim",
        cpus=2.0, memory="2g", pids_limit=512,
        network="bridge", internet=True,
        allowed_domains=("github.com", "*.github.com", "pypi.org", "*.pypi.org", "files.pythonhosted.org"),
        tools=("git", "python", "pip", "pytest"),
        env_allowlist=("GITHUB_TOKEN", "GH_TOKEN"),
        writable_paths=(SANDBOX_WORKDIR,),
    ),
    "browser": SandboxProfile(
        name="browser",
        description="Playwright / Browser Use / scraping / UI QA.",
        image="mcr.microsoft.com/playwright/python:v1.49.0-jammy",
        cpus=2.0, memory="4g", pids_limit=1024,
        network="bridge", internet=True,
        # Chromium's sandbox needs these two; dropping ALL and adding back
        # exactly two is materially different from running the container
        # privileged, which is the usual shortcut for "Playwright won't start".
        cap_add=("SYS_ADMIN", "SYS_CHROOT"),
        read_only_rootfs=False,
        # nosec B108 — container-internal tmpfs mount specs, not host paths.
        # Chromium needs a large /dev/shm or it crashes on page load; both are
        # in-memory and destroyed with the container. `noexec` is deliberately
        # absent here because Chromium maps executable pages out of /tmp.
        tmpfs=("/tmp:rw,nosuid,size=1g", "/dev/shm:rw,nosuid,size=1g"),  # nosec B108
        tools=("playwright", "chromium", "node"),
        writable_paths=(SANDBOX_WORKDIR,),
    ),
    "python": SandboxProfile(
        name="python",
        description="Data analysis, ML, scripting. No network by default.",
        image="python:3.13-slim",
        cpus=2.0, memory="2g",
        network="none", internet=False,
        tools=("python", "pip"),
        writable_paths=(SANDBOX_WORKDIR,),
    ),
    "node": SandboxProfile(
        name="node",
        description="Frontend and Node backend work.",
        image="node:22-slim",
        cpus=2.0, memory="2g", pids_limit=512,
        network="bridge", internet=True,
        allowed_domains=("registry.npmjs.org", "*.npmjs.org", "github.com", "*.github.com"),
        tools=("node", "npm"),
        writable_paths=(SANDBOX_WORKDIR,),
    ),
    "security": SandboxProfile(
        name="security",
        description="Dependency scans, SAST, secret detection. Read-only, no network.",
        image="python:3.13-slim",
        cpus=1.0, memory="1g",
        network="none", internet=False,
        tools=("bandit", "pip-audit", "trivy"),
    ),
    "documentation": SandboxProfile(
        name="documentation",
        description="MkDocs, diagrams, README generation.",
        image="python:3.13-slim",
        cpus=1.0, memory="1g",
        network="none", internet=False,
        tools=("mkdocs",),
        writable_paths=(SANDBOX_WORKDIR,),
    ),
    "review": SandboxProfile(
        name="review",
        description="Linting, formatting, code review. No network, no writes.",
        image="python:3.13-slim",
        cpus=1.0, memory="1g",
        network="none", internet=False,
        tools=("ruff", "black", "mypy"),
    ),
    # Deliberately NOT default-on and deliberately not privileged: building
    # images from an agent-authored Dockerfile is the highest-risk profile
    # here. It is defined so the capability is governed and auditable rather
    # than improvised, and it is gated behind approval by the shipped policy.
    "docker": SandboxProfile(
        name="docker",
        description="Container build/test. Requires an explicitly provided builder endpoint.",
        image="docker:27-cli",
        cpus=2.0, memory="4g", pids_limit=1024,
        network="bridge", internet=True,
        read_only_rootfs=False,
        tools=("docker", "docker-compose"),
        env_allowlist=("DOCKER_HOST",),
        writable_paths=(SANDBOX_WORKDIR,),
    ),
}


class SandboxUnavailableError(RuntimeError):
    """Raised when no backend can provide the requested sandbox.

    Callers treat this the same way ``AgentRunner._dispatch_tool`` already
    treats ``MCPUnavailableError``: degrade to the existing local path rather
    than failing the task.
    """


@dataclass
class SandboxHandle:
    """A live sandbox and everything needed to audit and reap it."""

    sandbox_id: str
    backend: str
    profile: str
    owner_agent_id: str
    session_id: str
    task: str | None = None
    container_id: str | None = None
    created_at: float = field(default_factory=time.monotonic)
    created_iso: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    ttl_s: int = 1800
    status: str = "running"
    native: Any = None
    artifacts: list[str] = field(default_factory=list)

    @property
    def age_s(self) -> float:
        return time.monotonic() - self.created_at

    @property
    def expired(self) -> bool:
        return self.age_s >= self.ttl_s

    def to_dict(self) -> dict[str, Any]:
        return {
            "sandbox_id": self.sandbox_id,
            "backend": self.backend,
            "profile": self.profile,
            "owner_agent_id": self.owner_agent_id,
            "session_id": self.session_id,
            "task": self.task,
            "container_id": self.container_id,
            "created_at": self.created_iso,
            "age_s": round(self.age_s, 1),
            "ttl_s": self.ttl_s,
            "status": self.status,
            "artifacts": list(self.artifacts),
        }


def build_docker_run_argv(
    profile: SandboxProfile,
    *,
    container_name: str,
    env: dict[str, str] | None = None,
    labels: dict[str, str] | None = None,
    command: Sequence[str] | None = None,
) -> list[str]:
    """Build the hardened ``docker run`` argv for *profile*.

    Split out from the backend and kept pure so the security posture is
    directly assertable in a unit test without a Docker daemon — the flags
    below are the isolation, so "did we actually pass them" is the property
    that matters, and it is the one thing a mocked runner can prove.

    Every flag maps to a control the audit asks about: ``--cap-drop`` to
    dropped Linux capabilities, ``--security-opt`` to seccomp/AppArmor/
    no-new-privileges, ``--read-only`` + ``--tmpfs`` to an immutable root
    filesystem with scratch space, ``--pids-limit``/``--memory``/``--cpus`` to
    cgroup limits, ``--network`` to network isolation, ``--user`` to
    non-root execution.

    Note on rootless: whether the *daemon* is rootless is a host property this
    argv cannot set. :meth:`DockerBackend.probe` reports it so the dashboard
    can tell an operator their daemon is rootful.
    """
    argv: list[str] = ["docker", "run", "--rm", "--detach", "--name", container_name]

    argv += ["--user", profile.user]
    argv += [f"--cpus={profile.cpus}"]
    argv += [f"--memory={profile.memory}"]
    # Pin swap to the memory ceiling: without this a container throttled on
    # RAM silently swaps instead of being limited, defeating the quota.
    argv += [f"--memory-swap={profile.memory}"]
    argv += [f"--pids-limit={profile.pids_limit}"]

    for cap in profile.cap_drop:
        argv += [f"--cap-drop={cap}"]
    for cap in profile.cap_add:
        argv += [f"--cap-add={cap}"]

    for opt in profile.security_opt:
        argv += [f"--security-opt={opt}"]
    if profile.seccomp_profile:
        argv += [f"--security-opt=seccomp={profile.seccomp_profile}"]
    if profile.apparmor_profile:
        argv += [f"--security-opt=apparmor={profile.apparmor_profile}"]

    if profile.read_only_rootfs:
        argv += ["--read-only"]
    for mount in profile.tmpfs:
        argv += [f"--tmpfs={mount}"]

    argv += [f"--network={profile.network}"]

    argv += ["--workdir", profile.workdir]

    # Only allow-listed env names are forwarded, and only when the caller
    # actually supplied them. A name absent from the profile's allow-list is
    # dropped even if the caller passed it — the profile, not the call site,
    # decides what a sandbox may authenticate as.
    for key in profile.env_allowlist:
        if env and key in env and env[key]:
            argv += ["--env", f"{key}={env[key]}"]

    for key, value in (labels or {}).items():
        argv += ["--label", f"{key}={value}"]

    argv += [profile.image]
    if command:
        argv += list(command)
    else:
        # Idle placeholder so the container stays up for exec calls without
        # needing an image whose CMD happens to block.
        argv += ["sleep", str(profile.ttl_s)]
    return argv


class DockerBackend:
    """Runs sandboxes as hardened Docker containers.

    The subprocess runner is injectable so the argv can be asserted in tests
    without a daemon. In production it is :meth:`_run` (asyncio subprocess).
    """

    name = "docker"

    def __init__(self, runner: Any = None) -> None:
        self._runner = runner or self._run

    async def _run(self, argv: Sequence[str], timeout: float = 60.0) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return 124, "", f"timed out after {timeout}s"
        return (
            proc.returncode or 0,
            (out or b"").decode("utf-8", "replace"),
            (err or b"").decode("utf-8", "replace"),
        )

    async def probe(self) -> dict[str, Any]:
        """Report daemon reachability and whether it is rootless.

        Rootless is surfaced rather than assumed because it cannot be set from
        the client side: reporting "isolation: hardened" while the daemon runs
        as root would overstate the guarantee.
        """
        import shutil

        if not shutil.which("docker"):
            return {"available": False, "reason": "docker binary not on PATH"}
        code, out, err = await self._runner(
            ["docker", "info", "--format", "{{.SecurityOptions}}"], 15.0
        )
        if code != 0:
            return {"available": False, "reason": (err or out or "docker info failed").strip()[:200]}
        return {
            "available": True,
            "rootless": "rootless" in (out or "").lower(),
            "security_options": (out or "").strip(),
        }

    async def create(
        self, profile: SandboxProfile, handle: SandboxHandle, env: dict[str, str] | None = None
    ) -> SandboxHandle:
        container_name = f"gov-sbx-{handle.sandbox_id}"
        argv = build_docker_run_argv(
            profile,
            container_name=container_name,
            env=env,
            labels={
                "governance.sandbox_id": handle.sandbox_id,
                "governance.agent_id": handle.owner_agent_id,
                "governance.session_id": handle.session_id,
                "governance.profile": profile.name,
            },
        )
        code, out, err = await self._runner(argv, 120.0)
        if code != 0:
            raise SandboxUnavailableError(f"docker run failed: {(err or out).strip()[:300]}")
        handle.container_id = (out or "").strip()[:64] or container_name
        handle.native = container_name
        return handle

    async def exec(self, handle: SandboxHandle, command: str, timeout: float = 120.0) -> dict[str, Any]:
        argv = [
            "docker", "exec", "--workdir", SANDBOX_WORKDIR,
            str(handle.native), "sh", "-lc", command,
        ]
        code, out, err = await self._runner(argv, timeout)
        return {"exit_code": code, "stdout": out, "stderr": err}

    async def collect_artifact(self, handle: SandboxHandle, path: str, dest: str) -> bool:
        argv = ["docker", "cp", f"{handle.native}:{path}", dest]
        code, _, err = await self._runner(argv, 60.0)
        if code != 0:
            log.warning("Artifact capture failed for %s: %s", path, err.strip()[:200])
            return False
        return True

    async def destroy(self, handle: SandboxHandle) -> None:
        code, _, err = await self._runner(["docker", "rm", "-f", str(handle.native)], 30.0)
        if code != 0:
            log.warning("Sandbox %s teardown returned %s: %s", handle.sandbox_id, code, err.strip()[:200])


class E2BBackend:
    """Runs sandboxes as E2B Firecracker micro-VMs.

    Delegates entirely to :class:`services.e2b_sandbox.E2BSandboxSession`,
    which already owns session lifecycle, the single-working-directory data
    flow, GitHub token injection/scrubbing, and worktree seed/extract. This
    class only adds the governance wrapper: identity, profile, TTL, audit, and
    a uniform handle.

    The isolation knobs a ``docker run`` sets per container (cap_drop, seccomp,
    read-only rootfs) are not client-settable on E2B — isolation is the
    micro-VM boundary itself, which is stronger than a shared-kernel container
    for the untrusted-code case. :meth:`describe_isolation` states that
    plainly so the dashboard does not imply controls that are not being
    applied.
    """

    name = "e2b"

    async def probe(self) -> dict[str, Any]:
        try:
            from services.e2b_config import e2b_enabled, is_e2b_sdk_importable
        except Exception as exc:  # noqa: BLE001
            return {"available": False, "reason": f"e2b config import failed: {exc}"}
        if not is_e2b_sdk_importable():
            return {"available": False, "reason": "e2b-code-interpreter SDK not installed"}
        if not e2b_enabled():
            return {"available": False, "reason": "E2B not enabled (set E2B_ENABLED=true + E2B_API_KEY)"}
        return {"available": True, "isolation": "firecracker-microvm"}

    @staticmethod
    def describe_isolation() -> dict[str, Any]:
        return {
            "kernel": "per-sandbox (micro-VM)",
            "cap_drop": "n/a — not a shared-kernel container",
            "read_only_rootfs": "n/a — disposable VM image",
            "network": "provider-managed egress",
            "note": (
                "Per-container Linux hardening flags do not apply; the boundary "
                "is the VM. Network egress filtering is not client-configurable, "
                "so domain policy for E2B is enforced in-process by the policy "
                "engine, not at the sandbox edge."
            ),
        }

    async def create(
        self, profile: SandboxProfile, handle: SandboxHandle, env: dict[str, str] | None = None
    ) -> SandboxHandle:
        try:
            from agent.mcp_client import MCPUnavailableError
            from services.e2b_sandbox import E2BSandboxSession
        except Exception as exc:  # noqa: BLE001
            raise SandboxUnavailableError(f"E2B import failed: {exc}") from exc
        session = E2BSandboxSession()
        try:
            await session.open()
        except MCPUnavailableError as exc:
            raise SandboxUnavailableError(f"E2B open failed: {exc}") from exc
        handle.native = session
        handle.container_id = f"e2b:{handle.sandbox_id}"
        return handle

    async def exec(self, handle: SandboxHandle, command: str, timeout: float = 120.0) -> dict[str, Any]:
        import json as _json

        try:
            raw = await handle.native.call_tool(
                "run_command", {"cmd": command, "timeout": int(timeout)}
            )
        except Exception as exc:  # noqa: BLE001
            return {"exit_code": 1, "stdout": "", "stderr": str(exc)}
        try:
            return _json.loads(raw)
        except (ValueError, TypeError):
            return {"exit_code": 0, "stdout": str(raw), "stderr": ""}

    async def collect_artifact(self, handle: SandboxHandle, path: str, dest: str) -> bool:
        try:
            content = await handle.native.call_tool("read_file", {"path": path})
        except Exception as exc:  # noqa: BLE001
            log.warning("E2B artifact capture failed for %s: %s", path, exc)
            return False
        try:
            target = Path(dest)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                content if isinstance(content, str) else str(content), encoding="utf-8"
            )
            return True
        except OSError as exc:
            log.warning("E2B artifact write failed for %s: %s", dest, exc)
            return False

    async def destroy(self, handle: SandboxHandle) -> None:
        try:
            await handle.native.close()
        except Exception as exc:  # noqa: BLE001 - teardown is best-effort
            log.debug("E2B sandbox close failed: %s", exc)


class LocalBackend:
    """No isolation. Present so 'ungoverned' is a visible state, not a silent one.

    Creating a sandbox succeeds and executes nothing: the caller's existing
    local path continues to run as it always has, in-process policy still
    applies, and the audit trail records ``backend=local`` so nobody reads a
    green dashboard as evidence of containment.
    """

    name = "local"

    async def probe(self) -> dict[str, Any]:
        return {
            "available": True,
            "isolation": "none",
            "reason": "no Docker daemon and no E2B configured; in-process policy only",
        }

    async def create(
        self, profile: SandboxProfile, handle: SandboxHandle, env: dict[str, str] | None = None
    ) -> SandboxHandle:
        handle.container_id = None
        handle.status = "running"
        return handle

    async def exec(self, handle: SandboxHandle, command: str, timeout: float = 120.0) -> dict[str, Any]:
        raise SandboxUnavailableError(
            "local backend does not execute commands; the caller's existing "
            "local tool path handles execution"
        )

    async def collect_artifact(self, handle: SandboxHandle, path: str, dest: str) -> bool:
        return False

    async def destroy(self, handle: SandboxHandle) -> None:
        return None


def load_profiles(path: str | Path | None = None) -> dict[str, SandboxProfile]:
    """Load sandbox profiles from YAML, merged over the built-ins.

    A file may add profiles or override fields of a built-in; unknown fields
    are ignored with a warning rather than raising, so a profile written for a
    newer version of this module still loads on an older one.
    """
    profiles = dict(BUILTIN_PROFILES)
    if not path:
        return profiles
    p = Path(path)
    if not p.is_file():
        return profiles
    try:
        import yaml

        with p.open("r", encoding="utf-8") as fh:
            document = yaml.safe_load(fh) or {}
        raw_profiles = document.get("profiles") or {}
        if not isinstance(raw_profiles, dict):
            raise ValueError("'profiles' must be a mapping")
        for name, raw in raw_profiles.items():
            if not isinstance(raw, dict):
                continue
            base = profiles.get(name)
            fields = {f: getattr(base, f) for f in SandboxProfile.__dataclass_fields__} if base else {}
            fields["name"] = name
            for key, value in raw.items():
                if key not in SandboxProfile.__dataclass_fields__:
                    log.warning("Unknown sandbox profile field %r in %r; ignored", key, name)
                    continue
                current = fields.get(key)
                fields[key] = tuple(value) if isinstance(current, tuple) and isinstance(value, list) else value
            profiles[name] = SandboxProfile(**fields)
    except Exception as exc:  # noqa: BLE001 - bad config must not break boot
        log.error("Sandbox profiles at %s are invalid (%s); using built-ins", p, exc)
    return profiles


async def detect_backend(preferred: str = "auto") -> tuple[Any, dict[str, Any]]:
    """Pick a backend by capability probe.

    Order: explicit setting → Docker (strongest local isolation, no per-call
    cost) → E2B (works where Docker cannot) → local. Probing rather than
    trusting configuration is what stops a sandbox from silently not existing
    in an environment where it was assumed to.
    """
    candidates: list[Any]
    if preferred == "docker":
        candidates = [DockerBackend()]
    elif preferred == "e2b":
        candidates = [E2BBackend()]
    elif preferred == "local":
        candidates = [LocalBackend()]
    else:
        candidates = [DockerBackend(), E2BBackend()]

    probes: dict[str, Any] = {}
    for backend in candidates:
        try:
            result = await backend.probe()
        except Exception as exc:  # noqa: BLE001
            result = {"available": False, "reason": f"probe raised: {exc}"}
        probes[backend.name] = result
        if result.get("available"):
            return backend, probes

    fallback = LocalBackend()
    probes[fallback.name] = await fallback.probe()
    return fallback, probes


class SandboxManager:
    """Creates, tracks, reaps, and audits sandboxes.

    Lifecycle guarantees:

      * Every sandbox has a TTL and :meth:`reap` destroys expired ones, so a
        crashed agent leaks at most one TTL of resources rather than a
        container per failed run. This repo has already been taken down by an
        unbounded resource leak (the schedule-backlog OOM crash loop in the
        changelog); a per-sandbox TTL is the same lesson applied here.
      * ``max_concurrent`` bounds total live sandboxes. Under the 100- and
        1000-agent cases this is the difference between backpressure and
        resource exhaustion.
      * Creation, execution, and teardown each emit an audit event carrying
        the requesting identity, so the container is attributable.
    """

    def __init__(
        self,
        *,
        backend: Any = None,
        profiles: dict[str, SandboxProfile] | None = None,
        max_concurrent: int = 8,
        artifacts_dir: str | Path | None = None,
    ) -> None:
        self._backend = backend
        self._profiles = profiles or dict(BUILTIN_PROFILES)
        self._sandboxes: dict[str, SandboxHandle] = {}
        self._lock = asyncio.Lock()
        self._max_concurrent = max(1, max_concurrent)
        self._artifacts_dir = Path(artifacts_dir) if artifacts_dir else None
        self._probes: dict[str, Any] = {}
        self._counter = 0

    async def backend(self) -> Any:
        if self._backend is None:
            from packages.config import settings

            self._backend, self._probes = await detect_backend(settings.governance_sandbox_backend)
            log.info("Sandbox backend selected: %s", self._backend.name)
        return self._backend

    def profile(self, name: str) -> SandboxProfile:
        """Return a profile by name, falling back to ``development``.

        An unknown profile name is a caller bug, not an excuse to grant more
        access — the fallback is a defined profile, never an unrestricted one.
        """
        if name in self._profiles:
            return self._profiles[name]
        log.warning("Unknown sandbox profile %r; falling back to 'development'", name)
        return self._profiles.get("development", BUILTIN_PROFILES["development"])

    def profile_names(self) -> list[str]:
        return sorted(self._profiles)

    async def create(
        self,
        profile_name: str,
        identity: Any = None,
        *,
        task: str | None = None,
        env: dict[str, str] | None = None,
        ttl_s: int | None = None,
    ) -> SandboxHandle:
        """Provision a sandbox for *identity* under *profile_name*."""
        from packages.governance.audit import events_from_identity, record_event

        backend = await self.backend()
        profile = self.profile(profile_name)

        async with self._lock:
            live = [h for h in self._sandboxes.values() if h.status == "running"]
            if len(live) >= self._max_concurrent:
                raise SandboxUnavailableError(
                    f"sandbox limit reached ({len(live)}/{self._max_concurrent}); "
                    f"retry after a running sandbox is reaped"
                )
            self._counter += 1
            sandbox_id = f"sbx_{int(time.time()):x}{self._counter:03d}"

        handle = SandboxHandle(
            sandbox_id=sandbox_id,
            backend=backend.name,
            profile=profile.name,
            owner_agent_id=str(getattr(identity, "agent_id", "agent:unknown")),
            session_id=str(getattr(identity, "session_id", "")),
            task=task,
            ttl_s=int(ttl_s or profile.ttl_s),
        )

        started = time.monotonic()
        try:
            handle = await backend.create(profile, handle, env)
        except SandboxUnavailableError:
            record_event(**{
                **events_from_identity(identity),
                "surface": "docker",
                "action": f"sandbox.create:{profile.name}",
                "result_status": "error",
                "error": "sandbox creation failed",
                "sandbox_backend": backend.name,
                "duration_ms": (time.monotonic() - started) * 1000,
            })
            raise

        async with self._lock:
            self._sandboxes[sandbox_id] = handle

        record_event(**{
            **events_from_identity(identity),
            "surface": "docker",
            "action": f"sandbox.create:{profile.name}",
            "result_status": "ok",
            "result": f"sandbox {sandbox_id} on {backend.name} (ttl={handle.ttl_s}s)",
            "sandbox_id": sandbox_id,
            "sandbox_backend": backend.name,
            "container_id": handle.container_id,
            "duration_ms": (time.monotonic() - started) * 1000,
        })
        log.info(
            "Sandbox %s created backend=%s profile=%s agent=%s",
            sandbox_id, backend.name, profile.name, handle.owner_agent_id,
        )
        return handle

    async def exec(
        self, sandbox_id: str, command: str, *, identity: Any = None, timeout: float = 120.0
    ) -> dict[str, Any]:
        """Run *command* inside a sandbox, auditing the call.

        The command is audited but its *output* is deliberately not stored in
        full — a build log is not evidence and would blow the ring buffer. The
        exit code and a truncated tail are what an auditor needs.
        """
        from packages.governance.audit import events_from_identity, record_event

        handle = self._sandboxes.get(sandbox_id)
        if handle is None or handle.status != "running":
            raise SandboxUnavailableError(f"sandbox {sandbox_id} is not running")
        backend = await self.backend()
        started = time.monotonic()
        result = await backend.exec(handle, command, timeout)
        duration_ms = (time.monotonic() - started) * 1000
        exit_code = int(result.get("exit_code", 0) or 0)
        record_event(**{
            **events_from_identity(identity),
            "surface": "shell",
            "action": "sandbox.exec",
            "tool": "run_command",
            "arguments": {"cmd": command},
            "result_status": "ok" if exit_code == 0 else "error",
            "result": str(result.get("stdout", ""))[-1000:],
            "error": None if exit_code == 0 else str(result.get("stderr", ""))[-1000:],
            "sandbox_id": sandbox_id,
            "sandbox_backend": handle.backend,
            "container_id": handle.container_id,
            "duration_ms": duration_ms,
        })
        return result

    async def collect_artifacts(
        self, sandbox_id: str, paths: Sequence[str], *, identity: Any = None
    ) -> list[str]:
        """Copy artifacts out **before** teardown.

        Ordering is the whole point: a disposable sandbox that is destroyed
        before its outputs are captured has done the work and thrown it away.
        Failures are per-path and non-fatal, so one missing file does not lose
        the rest.
        """
        handle = self._sandboxes.get(sandbox_id)
        if handle is None:
            return []
        backend = await self.backend()
        base = self._artifacts_dir or Path(".artifacts")
        target_dir = base / sandbox_id
        captured: list[str] = []
        for path in paths:
            dest = target_dir / Path(path).name
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                log.warning("Cannot create artifact dir %s: %s", dest.parent, exc)
                continue
            if await backend.collect_artifact(handle, path, str(dest)):
                captured.append(str(dest))
        handle.artifacts.extend(captured)
        return captured

    async def destroy(self, sandbox_id: str, *, identity: Any = None, reason: str = "completed") -> bool:
        """Tear down a sandbox. Idempotent and never raises."""
        from packages.governance.audit import events_from_identity, record_event

        async with self._lock:
            handle = self._sandboxes.get(sandbox_id)
            if handle is None or handle.status == "destroyed":
                return False
            handle.status = "destroyed"

        backend = await self.backend()
        started = time.monotonic()
        try:
            await backend.destroy(handle)
        except Exception as exc:  # noqa: BLE001 - teardown must not raise
            log.warning("Sandbox %s destroy failed: %s", sandbox_id, exc)

        record_event(**{
            **events_from_identity(identity),
            "surface": "docker",
            "action": "sandbox.destroy",
            "result_status": "ok",
            "result": f"reason={reason} age={handle.age_s:.0f}s",
            "sandbox_id": sandbox_id,
            "sandbox_backend": handle.backend,
            "container_id": handle.container_id,
            "duration_ms": (time.monotonic() - started) * 1000,
        })
        async with self._lock:
            self._sandboxes.pop(sandbox_id, None)
        return True

    async def reap(self) -> list[str]:
        """Destroy every sandbox past its TTL. Returns the ids reaped."""
        expired = [h.sandbox_id for h in list(self._sandboxes.values()) if h.expired]
        for sandbox_id in expired:
            await self.destroy(sandbox_id, reason="ttl-expired")
        if expired:
            log.info("Reaped %d expired sandbox(es): %s", len(expired), ", ".join(expired))
        return expired

    def list(self) -> list[dict[str, Any]]:
        return [h.to_dict() for h in self._sandboxes.values()]

    async def status(self) -> dict[str, Any]:
        """Backend, isolation posture, live sandboxes, and profiles.

        Reports what is *actually* in force rather than what is configured —
        including ``isolation: none`` on the local backend and a rootful
        Docker daemon — because a governance dashboard that overstates
        containment is worse than none.
        """
        backend = await self.backend()
        isolation: dict[str, Any]
        if backend.name == "e2b":
            isolation = E2BBackend.describe_isolation()
        elif backend.name == "docker":
            isolation = {
                "kernel": "shared (namespaces + cgroups)",
                "hardening": "per-profile: cap_drop, no-new-privileges, read-only rootfs, pids/mem/cpu limits",
                "daemon": self._probes.get("docker", {}),
            }
        else:
            isolation = {"kernel": "shared with host process", "hardening": "none — in-process policy only"}
        return {
            "backend": backend.name,
            "probes": self._probes,
            "isolation": isolation,
            "max_concurrent": self._max_concurrent,
            "live": len([h for h in self._sandboxes.values() if h.status == "running"]),
            "sandboxes": self.list(),
            "profiles": {name: p.to_dict() for name, p in self._profiles.items()},
        }


_MANAGER: SandboxManager | None = None
_MANAGER_LOCK = threading.Lock()


def get_sandbox_manager() -> SandboxManager:
    global _MANAGER
    with _MANAGER_LOCK:
        if _MANAGER is None:
            from packages.config import settings

            _MANAGER = SandboxManager(
                profiles=load_profiles(settings.governance_sandbox_profiles_path),
                max_concurrent=settings.governance_max_sandboxes,
                artifacts_dir=settings.governance_artifacts_dir,
            )
        return _MANAGER


def reset_sandbox_manager(manager: SandboxManager | None = None) -> None:
    """Replace the process-wide manager. Tests only."""
    global _MANAGER
    with _MANAGER_LOCK:
        _MANAGER = manager


def quote_command(parts: Sequence[str]) -> str:
    """Shell-quote *parts* into a single command string.

    Used when a caller has an argv but a backend wants a command line.
    Centralised so no call site hand-rolls quoting and introduces an
    injection point.
    """
    return " ".join(shlex.quote(str(p)) for p in parts)
