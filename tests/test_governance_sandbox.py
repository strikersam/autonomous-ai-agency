"""Tests for governed sandbox provisioning.

No Docker daemon is required. That is deliberate: the security property worth
testing is **which flags we ask the daemon for**, and a fake runner proves
that far more precisely than a live container would. If `--cap-drop=ALL` is
missing from the argv, no amount of integration testing against a permissive
daemon will tell you.

The one thing these tests cannot prove is that the *daemon* honours the flags
(or is rootless). That is a host property, reported at runtime by
`DockerBackend.probe()` and surfaced on `GET /api/governance/status`.
"""
from __future__ import annotations

import pytest

from packages.governance.identity import resolve_identity
from packages.governance.sandbox import (
    BUILTIN_PROFILES,
    DockerBackend,
    E2BBackend,
    LocalBackend,
    SandboxManager,
    SandboxProfile,
    SandboxUnavailableError,
    build_docker_run_argv,
    load_profiles,
)


class FakeRunner:
    """Records every argv it is asked to run and returns a canned result."""

    def __init__(self, code: int = 0, stdout: str = "container123", stderr: str = "") -> None:
        self.calls: list[list[str]] = []
        self._result = (code, stdout, stderr)

    async def __call__(self, argv, timeout: float = 60.0):
        self.calls.append(list(argv))
        return self._result

    @property
    def last(self) -> list[str]:
        return self.calls[-1]


# ── The hardening flags ──────────────────────────────────────────────────────


def test_default_profile_argv_carries_every_hardening_flag():
    """One assertion per control the governance audit asks about."""
    argv = build_docker_run_argv(BUILTIN_PROFILES["python"], container_name="c1")
    joined = " ".join(argv)

    assert "--cap-drop=ALL" in argv, "dropped Linux capabilities"
    assert "--security-opt=no-new-privileges:true" in argv, "no privilege escalation"
    assert "--read-only" in argv, "read-only root filesystem"
    assert any(a.startswith("--tmpfs=") for a in argv), "writable scratch space"
    assert "--network=none" in argv, "network isolation"
    assert "--user" in argv and "65532:65532" in argv, "non-root execution"
    assert any(a.startswith("--pids-limit=") for a in argv), "pid cgroup limit"
    assert any(a.startswith("--memory=") for a in argv), "memory cgroup limit"
    assert any(a.startswith("--cpus=") for a in argv), "cpu cgroup limit"
    assert "--rm" in argv, "disposable by construction"
    assert "--privileged" not in joined, "never privileged"


def test_memory_swap_is_pinned_to_memory_so_the_limit_cannot_be_evaded():
    """Without this, a memory-capped container silently swaps instead."""
    argv = build_docker_run_argv(BUILTIN_PROFILES["python"], container_name="c1")
    assert "--memory=2g" in argv
    assert "--memory-swap=2g" in argv


def test_env_allowlist_drops_names_the_profile_did_not_declare():
    """The credential surface: a profile decides what a sandbox may authenticate as."""
    argv = build_docker_run_argv(
        BUILTIN_PROFILES["development"],
        container_name="c1",
        env={"GITHUB_TOKEN": "ghp_allowed", "AWS_SECRET_ACCESS_KEY": "leaked", "MONGO_URL": "x"},
    )
    joined = " ".join(argv)
    assert "GITHUB_TOKEN=ghp_allowed" in joined, "allow-listed name is forwarded"
    assert "AWS_SECRET_ACCESS_KEY" not in joined, "undeclared secret must not reach the sandbox"
    assert "MONGO_URL" not in joined


def test_env_allowlist_skips_names_the_caller_did_not_supply():
    argv = build_docker_run_argv(BUILTIN_PROFILES["development"], container_name="c1", env={})
    assert "--env" not in argv


def test_browser_profile_adds_back_two_capabilities_not_privileged():
    """Chromium needs SYS_ADMIN; that is not a reason to run privileged."""
    argv = build_docker_run_argv(BUILTIN_PROFILES["browser"], container_name="c1")
    assert "--cap-drop=ALL" in argv
    assert "--cap-add=SYS_ADMIN" in argv
    assert "--cap-add=SYS_CHROOT" in argv
    assert "--privileged" not in " ".join(argv)


def test_no_builtin_profile_mounts_the_docker_socket():
    """Mounting /var/run/docker.sock into an agent container is host root."""
    for name, profile in BUILTIN_PROFILES.items():
        argv = build_docker_run_argv(profile, container_name="c")
        assert "docker.sock" not in " ".join(argv), f"{name} mounts the docker socket"


def test_every_builtin_profile_is_non_root_and_capability_dropped():
    for name, profile in BUILTIN_PROFILES.items():
        assert not profile.user.startswith("0:"), f"{name} runs as root"
        assert "ALL" in profile.cap_drop, f"{name} does not drop all capabilities"
        assert any("no-new-privileges" in o for o in profile.security_opt), name


def test_seccomp_and_apparmor_profiles_are_passed_when_configured():
    profile = SandboxProfile(
        name="hardened", seccomp_profile="/etc/seccomp/agent.json",
        apparmor_profile="docker-agent",
    )
    argv = build_docker_run_argv(profile, container_name="c1")
    assert "--security-opt=seccomp=/etc/seccomp/agent.json" in argv
    assert "--security-opt=apparmor=docker-agent" in argv


def test_labels_make_a_container_attributable_to_an_agent():
    argv = build_docker_run_argv(
        BUILTIN_PROFILES["python"], container_name="c1",
        labels={"governance.agent_id": "agent:coder"},
    )
    assert "governance.agent_id=agent:coder" in argv


# ── Profile loading ──────────────────────────────────────────────────────────


def test_profiles_file_overrides_builtins_field_by_field(tmp_path):
    path = tmp_path / "profiles.yaml"
    path.write_text("profiles:\n  python:\n    memory: 8g\n", encoding="utf-8")
    profiles = load_profiles(str(path))
    assert profiles["python"].memory == "8g", "overridden"
    assert profiles["python"].network == "none", "untouched fields keep built-in defaults"


def test_unknown_profile_field_is_ignored_not_fatal(tmp_path):
    path = tmp_path / "profiles.yaml"
    path.write_text("profiles:\n  python:\n    made_up_field: 1\n", encoding="utf-8")
    assert "python" in load_profiles(str(path))


def test_malformed_profiles_file_falls_back_to_builtins(tmp_path):
    path = tmp_path / "profiles.yaml"
    path.write_text("profiles: [not, a, mapping]\n", encoding="utf-8")
    profiles = load_profiles(str(path))
    assert set(profiles) >= set(BUILTIN_PROFILES)


def test_shipped_profiles_file_loads_and_stays_hardened():
    """The committed config must not silently weaken the built-in defaults."""
    profiles = load_profiles("config/sandbox_profiles.yaml")
    for name, profile in profiles.items():
        assert "ALL" in profile.cap_drop, f"{name} lost cap_drop"
        assert not profile.user.startswith("0:"), f"{name} became root"
    assert profiles["security"].network == "none", "the scanner must not have egress"


# ── Manager lifecycle ────────────────────────────────────────────────────────


async def test_create_exec_and_destroy_round_trip():
    runner = FakeRunner()
    manager = SandboxManager(backend=DockerBackend(runner=runner))
    identity = resolve_identity(agent_name="coder")

    handle = await manager.create("python", identity, task="unit-test")
    assert handle.status == "running"
    assert "--cap-drop=ALL" in runner.calls[0]

    await manager.exec(handle.sandbox_id, "pytest -q")
    assert runner.last[:2] == ["docker", "exec"]
    assert "pytest -q" in runner.last

    assert await manager.destroy(handle.sandbox_id) is True
    assert runner.last[:3] == ["docker", "rm", "-f"]


async def test_destroy_is_idempotent():
    manager = SandboxManager(backend=DockerBackend(runner=FakeRunner()))
    handle = await manager.create("python", resolve_identity(agent_name="c"))
    assert await manager.destroy(handle.sandbox_id) is True
    assert await manager.destroy(handle.sandbox_id) is False


async def test_concurrency_cap_produces_backpressure_not_exhaustion():
    """Bounded concurrency is what makes 100+ agents safe to run."""
    manager = SandboxManager(backend=DockerBackend(runner=FakeRunner()), max_concurrent=2)
    identity = resolve_identity(agent_name="coder")
    await manager.create("python", identity)
    await manager.create("python", identity)
    with pytest.raises(SandboxUnavailableError, match="limit reached"):
        await manager.create("python", identity)


async def test_expired_sandboxes_are_reaped():
    """A crashed agent must leak at most one TTL, not a container forever."""
    manager = SandboxManager(backend=DockerBackend(runner=FakeRunner()))
    handle = await manager.create("python", resolve_identity(agent_name="c"), ttl_s=1)
    handle.created_at -= 100  # simulate the TTL elapsing
    assert handle.expired is True
    reaped = await manager.reap()
    assert handle.sandbox_id in reaped
    assert manager.list() == []


async def test_reap_leaves_live_sandboxes_alone():
    manager = SandboxManager(backend=DockerBackend(runner=FakeRunner()))
    handle = await manager.create("python", resolve_identity(agent_name="c"), ttl_s=3600)
    assert await manager.reap() == []
    assert len(manager.list()) == 1
    await manager.destroy(handle.sandbox_id)


async def test_docker_run_failure_surfaces_as_sandbox_unavailable():
    """Callers degrade to the local path; they must not see a raw subprocess error."""
    manager = SandboxManager(
        backend=DockerBackend(runner=FakeRunner(code=125, stdout="", stderr="no such image"))
    )
    with pytest.raises(SandboxUnavailableError, match="no such image"):
        await manager.create("python", resolve_identity(agent_name="c"))


async def test_exec_on_a_destroyed_sandbox_is_refused():
    manager = SandboxManager(backend=DockerBackend(runner=FakeRunner()))
    handle = await manager.create("python", resolve_identity(agent_name="c"))
    await manager.destroy(handle.sandbox_id)
    with pytest.raises(SandboxUnavailableError):
        await manager.exec(handle.sandbox_id, "echo hi")


async def test_unknown_profile_falls_back_to_a_defined_one_not_to_unrestricted():
    manager = SandboxManager(backend=DockerBackend(runner=FakeRunner()))
    profile = manager.profile("does-not-exist")
    assert profile.name == "development"
    assert "ALL" in profile.cap_drop


# ── Backend selection ────────────────────────────────────────────────────────


async def test_docker_probe_reports_unavailable_rather_than_raising():
    backend = DockerBackend(runner=FakeRunner(code=1, stdout="", stderr="daemon not running"))
    result = await backend.probe()
    assert result["available"] is False
    assert "daemon" in result["reason"]


async def test_docker_probe_surfaces_rootless_state():
    backend = DockerBackend(runner=FakeRunner(code=0, stdout="[name=rootless name=seccomp]"))
    result = await backend.probe()
    assert result["available"] is True
    assert result["rootless"] is True


async def test_local_backend_is_honest_about_providing_no_isolation():
    """A dashboard that implies containment where there is none is worse than none."""
    result = await LocalBackend().probe()
    assert result["available"] is True
    assert result["isolation"] == "none"


async def test_local_backend_refuses_to_execute():
    backend = LocalBackend()
    handle = await backend.create(BUILTIN_PROFILES["python"], _handle())
    with pytest.raises(SandboxUnavailableError):
        await backend.exec(handle, "echo hi")


def test_e2b_isolation_description_does_not_claim_container_flags():
    """E2B is a micro-VM; claiming cap_drop applies would overstate the control."""
    described = E2BBackend.describe_isolation()
    assert "micro-VM" in described["kernel"]
    assert described["cap_drop"].startswith("n/a")


async def test_status_reports_the_live_backend_and_posture():
    manager = SandboxManager(backend=DockerBackend(runner=FakeRunner()))
    status = await manager.status()
    assert status["backend"] == "docker"
    assert "hardening" in status["isolation"]
    assert "python" in status["profiles"]


def _handle():
    from packages.governance.sandbox import SandboxHandle

    return SandboxHandle(
        sandbox_id="sbx_test", backend="local", profile="python",
        owner_agent_id="agent:test", session_id="sess_test",
    )
