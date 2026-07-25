"""Hermes must survive free-tier cold starts, and fallback must not log errors.

Production symptom: Hermes never took a task. The adapter is SIDECAR-mode — it
only speaks HTTP to an already-running server and never starts one — and
``agency-hermes`` is its own Render free-tier service, which sleeps after ~15 min
idle and takes 30-60s to wake. The old 5-second health probe could not survive
that, so Hermes read as permanently DOWN and every task fell back to
internal_agent, and each failed probe was logged at ERROR (which
``agent/log_monitor`` files GitHub issues from).
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]


class TestHermesColdStartTolerance:
    def test_health_probe_timeout_survives_a_render_cold_start(
        self, monkeypatch
    ) -> None:
        """A free Render service takes 30-60s to wake; 5s could never see it."""
        from runtimes.adapters.hermes import _env_float

        monkeypatch.delenv("HERMES_HEALTH_TIMEOUT_SEC", raising=False)
        timeout = _env_float("HERMES_HEALTH_TIMEOUT_SEC", 25.0)

        assert timeout >= 20.0, (
            f"health probe timeout is {timeout}s — too short to observe a "
            f"cold-starting free-tier sidecar"
        )
        # Must stay inside RuntimeHealthService's own asyncio.wait_for budget,
        # or the outer timeout fires first and the inner value is meaningless.
        assert timeout < 30.0, (
            f"timeout {timeout}s meets or exceeds the 30s outer budget in "
            f"runtimes/health.py, so it can never take effect"
        )

    def test_timeout_is_operator_overridable(self, monkeypatch) -> None:
        from runtimes.adapters.hermes import _env_float

        monkeypatch.setenv("HERMES_HEALTH_TIMEOUT_SEC", "12.5")
        assert _env_float("HERMES_HEALTH_TIMEOUT_SEC", 25.0) == 12.5

    @pytest.mark.parametrize("garbage", ["", "   ", "abc", "None"])
    def test_garbage_override_falls_back_to_default(
        self, monkeypatch, garbage: str
    ) -> None:
        """A typo in the env var must not brick the health probe."""
        from runtimes.adapters.hermes import _env_float

        monkeypatch.setenv("HERMES_HEALTH_TIMEOUT_SEC", garbage)
        assert _env_float("HERMES_HEALTH_TIMEOUT_SEC", 25.0) == 25.0

    def test_adapter_no_longer_hardcodes_the_five_second_probe(self) -> None:
        from runtimes.adapters.hermes import HermesAdapter

        source = inspect.getsource(HermesAdapter.health_check)

        assert "timeout=5.0" not in source, (
            "the hardcoded 5s probe is back; it cannot survive a cold start"
        )
        assert "HERMES_HEALTH_TIMEOUT_SEC" in source


class TestHermesKeepAlive:
    """The sidecar needs its own warm ping — the backend's does not cover it."""

    def test_keepalive_workflow_pings_hermes(self) -> None:
        workflow = yaml.safe_load(
            (_REPO_ROOT / ".github/workflows/keepalive.yml").read_text(
                encoding="utf-8"
            )
        )
        steps = workflow["jobs"]["ping"]["steps"]
        blob = yaml.dump(steps)

        assert "agency-hermes" in blob or "HERMES_KEEPALIVE_URL" in blob, (
            "keepalive does not warm the Hermes sidecar, so it will sleep and "
            "every task will fall back to internal_agent"
        )
        assert "/health" in blob

    def test_hermes_ping_failure_does_not_fail_the_job(self) -> None:
        """An undeployed sidecar must not turn keepalive red every 3 minutes."""
        raw = (_REPO_ROOT / ".github/workflows/keepalive.yml").read_text(
            encoding="utf-8"
        )
        hermes_step = raw.split("Warm the Hermes sidecar", 1)[1]

        assert "::warning::" in hermes_step
        assert "exit 1" not in hermes_step, (
            "the Hermes ping fails the job; Hermes being down only costs a "
            "fallback to internal_agent and must not break keepalive"
        )


class TestFallbackSeverity:
    """A handled fallback is a warning; only an unrecoverable state is an error."""

    def test_runtime_health_probe_failure_is_a_warning(self) -> None:
        import runtimes.health as health_mod

        source = inspect.getsource(health_mod.RuntimeHealthService._poll_one)

        assert 'log.error("Health check failed' not in source, (
            "a failed health probe is logged at ERROR; the circuit breaker "
            "retries and the router falls back, so this is a warning"
        )
        assert 'log.warning("Health check failed' in source

    def test_company_agency_runtime_fallback_is_a_warning(self) -> None:
        source = (
            _REPO_ROOT / "services/company_agency.py"
        ).read_text(encoding="utf-8")

        assert "CompanyAgency: failed to assign runtime" not in source, (
            "runtime-assignment fallback still logs at ERROR even though the "
            "next line successfully falls back to internal_agent"
        )
        assert "falling back to internal_agent" in source
