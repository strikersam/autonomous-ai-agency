"""tests/test_prime_agent_runtime.py — PrimeAgentAdapter unit tests.

The event-stream fixtures in tests/fixtures/ are real output captured from the
`pi` CLI (the engine Prime Agent wraps) running headlessly against a local
OpenAI-compatible stub — not hand-written approximations. The failure fixture in
particular records the behaviour that makes naive adapters wrong: the CLI exits 0
after every LLM call has failed.

Hermetic: no binary, no network, no event loop needed for the parser tests.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from runtimes.adapters.prime_agent import (
    _UNTRUSTED_WORKSPACE_FLAGS,
    PrimeAgentAdapter,
    _child_env,
    parse_event_stream,
)
from runtimes.base import RuntimeCapability, RuntimeTier, TaskSpec

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> list[str]:
    return (FIXTURES / name).read_text().splitlines()


def _spec(**kwargs) -> TaskSpec:
    params = {
        "task_id": "t-1",
        "instruction": "Say hi.",
        "task_type": "code_generation",
        "timeout_sec": 60,
    }
    params.update(kwargs)
    return TaskSpec(**params)


class TestParseEventStream:
    """The parser is the trust boundary: everything downstream believes it."""

    def test_successful_run(self):
        run = parse_event_stream(_fixture("prime_agent_success.ndjson"))
        assert run.success is True
        assert run.error is None
        assert "Probe reply from the mock provider." in run.output
        assert run.stop_reason == "stop"
        assert run.settled is True

    def test_successful_run_reports_usage(self):
        run = parse_event_stream(_fixture("prime_agent_success.ndjson"))
        assert run.tokens_used == 18          # 11 input + 7 output, from the real stream
        assert run.cost_usd == 0.0
        assert run.provider == "agency"       # proves the extension routed to our proxy
        assert run.model == "mock-model"
        assert run.session_id

    def test_provider_failure_is_not_reported_as_success(self):
        """The regression this adapter exists to avoid.

        Every LLM call failed and the CLI still exited 0. Anything keying off the
        exit code would report this run as a success.
        """
        run = parse_event_stream(_fixture("prime_agent_provider_failure.ndjson"))
        assert run.success is False
        assert run.error == "Connection error."
        assert run.stop_reason == "error"
        assert run.retries == 3

    def test_last_agent_end_wins(self):
        """Retries emit several agent_end events; only the final one is the outcome."""
        lines = _fixture("prime_agent_provider_failure.ndjson")
        assert sum(1 for line in lines if '"type":"agent_end"' in line.replace(" ", "")) > 1
        assert parse_event_stream(lines).success is False

    def test_truncated_stream_fails_loudly(self):
        """A killed process yields no agent_end — that must not read as success."""
        lines = _fixture("prime_agent_success.ndjson")
        truncated = [line for line in lines if '"agent_end"' not in line]
        run = parse_event_stream(truncated)
        assert run.success is False
        assert "no agent_end" in (run.error or "")

    def test_non_json_lines_are_skipped(self):
        lines = _fixture("prime_agent_success.ndjson")
        noisy = ["npm warn: something", "", "not json at all", *lines, "trailing noise"]
        assert parse_event_stream(noisy).success is True

    def test_empty_stream(self):
        run = parse_event_stream([])
        assert run.success is False
        assert run.output == run.error
        assert run.tokens_used is None

    def test_tool_calls_are_collected(self):
        lines = [
            '{"type":"tool_execution_end","toolName":"read","result":"ok"}',
            '{"type":"agent_end","messages":[{"role":"assistant","content":'
            '[{"type":"text","text":"done"}],"stopReason":"stop"}]}',
            '{"type":"agent_settled"}',
        ]
        run = parse_event_stream(lines)
        assert run.success is True
        assert run.tool_calls == [{"name": "read", "ok": True, "detail": "ok"}]


class TestAdapterMetadata:
    def test_identity(self):
        adapter = PrimeAgentAdapter()
        assert adapter.RUNTIME_ID == "prime_agent"
        assert adapter.DISPLAY_NAME == "Prime Agent"
        assert adapter.TIER is RuntimeTier.TIER_2

    def test_declares_autonomous_loop(self):
        adapter = PrimeAgentAdapter()
        assert adapter.supports(RuntimeCapability.AUTONOMOUS_LOOP)
        assert adapter.supports(RuntimeCapability.REPO_EDITING)

    def test_as_dict_leaks_no_secrets(self):
        payload = PrimeAgentAdapter().as_dict()
        assert payload["runtime_id"] == "prime_agent"
        assert "api_key" not in str(payload).lower()


class TestBinaryResolution:
    def test_falls_back_to_pi(self, monkeypatch):
        monkeypatch.delenv("PRIME_AGENT_BIN", raising=False)
        monkeypatch.setattr(
            "runtimes.adapters.prime_agent.shutil.which",
            lambda name: "/usr/bin/pi" if name == "pi" else None,
        )
        assert PrimeAgentAdapter().resolve_bin() == "/usr/bin/pi"

    def test_explicit_bin_is_not_second_guessed(self, monkeypatch):
        monkeypatch.setattr(
            "runtimes.adapters.prime_agent.shutil.which",
            lambda name: "/opt/custom" if name == "custom-agent" else "/usr/bin/pi",
        )
        adapter = PrimeAgentAdapter(config={"bin": "custom-agent"})
        assert adapter.resolve_bin() == "/opt/custom"

    def test_health_check_reports_missing_binary(self, monkeypatch):
        monkeypatch.setattr("runtimes.adapters.prime_agent.shutil.which", lambda _: None)
        health = asyncio.run(PrimeAgentAdapter().health_check())
        assert health.available is False
        assert "not found in PATH" in (health.error or "")


class TestCommandConstruction:
    SUPPORTED = frozenset({"--no-approve", "--autonomous", "--autonomous-max-turns"})

    def test_headless_json_flags_always_present(self):
        cmd = PrimeAgentAdapter().build_command("/usr/bin/pi", _spec(), frozenset())
        assert cmd[0] == "/usr/bin/pi"
        assert "-p" in cmd and "--mode" in cmd and "json" in cmd
        assert cmd[-1] == "Say hi."

    def test_no_cwd_flag_is_passed(self):
        """plain `pi` rejects --cwd; the workspace is set on the subprocess instead."""
        cmd = PrimeAgentAdapter().build_command("/usr/bin/pi", _spec(), self.SUPPORTED)
        assert "--cwd" not in cmd

    def test_unsupported_flags_are_omitted(self):
        cmd = PrimeAgentAdapter().build_command("/usr/bin/pi", _spec(), frozenset())
        assert "--autonomous" not in cmd
        assert "--no-approve" not in cmd

    def test_workspace_is_untrusted_by_default(self):
        cmd = PrimeAgentAdapter().build_command("/usr/bin/pi", _spec(), self.SUPPORTED)
        assert "--no-approve" in cmd

    def test_trusting_workspace_is_opt_in(self, monkeypatch):
        monkeypatch.setenv("PRIME_AGENT_TRUST_WORKSPACE", "true")
        cmd = PrimeAgentAdapter().build_command("/usr/bin/pi", _spec(), self.SUPPORTED)
        assert "--no-approve" not in cmd

    def test_model_preference_overrides_config(self):
        adapter = PrimeAgentAdapter(config={"model": "default-model"})
        cmd = adapter.build_command("/usr/bin/pi", _spec(model_preference="better-model"), frozenset())
        assert cmd[cmd.index("--model") + 1] == "better-model"

    def test_extension_is_passed_when_configured(self, tmp_path):
        extension = tmp_path / "agency-provider.ts"
        adapter = PrimeAgentAdapter(config={"extension": str(extension)})
        cmd = adapter.build_command("/usr/bin/pi", _spec(), frozenset())
        assert cmd[cmd.index("--extension") + 1] == str(extension)


class TestPreflight:
    def test_missing_extension_file_fails_validation(self, tmp_path):
        adapter = PrimeAgentAdapter(config={"extension": str(tmp_path / "nope.ts")})
        issues = asyncio.run(adapter.validate_task_spec(_spec()))
        assert any(i.code == "missing_provider_extension" for i in issues)

    def test_existing_extension_passes(self, tmp_path):
        ext = tmp_path / "agency-provider.ts"
        ext.write_text("export default function () {}")
        adapter = PrimeAgentAdapter(config={"extension": str(ext)})
        issues = asyncio.run(adapter.validate_task_spec(_spec()))
        assert not any(i.code == "missing_provider_extension" for i in issues)

    def test_declares_binary_dependency(self):
        deps = PrimeAgentAdapter().required_dependencies()
        assert any(d.config_var == "PRIME_AGENT_BIN" for d in deps)


class TestShippedExtension:
    """The extension is load-bearing for the no-provider-bypass rule (§3)."""

    PATH = Path(__file__).parent.parent / "runtimes" / "extensions" / "prime_agent" / "agency-provider.ts"

    def test_extension_ships_with_the_repo(self):
        assert self.PATH.is_file()

    def test_extension_contains_no_hardcoded_secret(self):
        source = self.PATH.read_text()
        assert '"$PROXY_API_KEY"' in source      # env interpolation, resolved by the CLI
        assert "sk-" not in source

    def test_extension_targets_the_agency_proxy(self):
        source = self.PATH.read_text()
        assert "AGENCY_PROXY_URL" in source
        assert 'registerProvider("agency"' in source
        assert "openai-completions" in source


class TestReviewRegressions:
    """Regressions for defects found in review of this adapter."""

    SUPPORTED = frozenset({*_UNTRUSTED_WORKSPACE_FLAGS, "--autonomous"})

    def test_agent_end_without_assistant_message_is_a_failure(self):
        """An agent_end carrying no assistant message produced nothing."""
        run = parse_event_stream([
            '{"type":"agent_end","messages":[{"role":"user","content":[]}]}',
            '{"type":"agent_settled"}',
        ])
        assert run.success is False
        assert "without an assistant message" in (run.error or "")
        assert run.output == run.error

    def test_preflight_accepts_the_pi_fallback(self, monkeypatch, tmp_path):
        """health_check() and readiness_check() must agree about the binary.

        The base class re-resolves the declared dependency name, so a hardcoded
        "prime-agent" blocked hosts that only have the documented `pi` fallback.
        """
        monkeypatch.delenv("PRIME_AGENT_BIN", raising=False)
        monkeypatch.setattr(
            "runtimes.adapters.prime_agent.shutil.which",
            lambda name: "/usr/bin/pi" if name == "pi" else None,
        )
        deps = PrimeAgentAdapter().required_dependencies()
        assert deps[0].name == "pi"

    def test_agency_provider_requires_the_extension(self):
        """Preflight rejects agency without the proxy extension configured."""
        adapter = PrimeAgentAdapter(config={"provider": "agency", "extension": ""})
        issues = asyncio.run(adapter.validate_task_spec(_spec()))
        assert any(i.code == "missing_provider_extension" for i in issues)

    def test_execute_refuses_agency_without_extension(self, monkeypatch):
        """compare_runtimes.py calls execute() directly, bypassing preflight."""
        monkeypatch.setattr(
            "runtimes.adapters.prime_agent.shutil.which", lambda name: "/usr/bin/pi"
        )
        adapter = PrimeAgentAdapter(config={"provider": "agency", "extension": ""})
        with pytest.raises(Exception) as excinfo:
            asyncio.run(adapter.execute(_spec()))
        assert "PRIME_AGENT_EXTENSION" in str(excinfo.value)

    def test_untrusted_workspace_quarantines_context_files(self):
        """--no-approve alone still loads AGENTS.md/CLAUDE.md from the repo."""
        cmd = PrimeAgentAdapter().build_command("/usr/bin/pi", _spec(), self.SUPPORTED)
        for flag in _UNTRUSTED_WORKSPACE_FLAGS:
            assert flag in cmd

    def test_refuses_a_cli_that_cannot_isolate(self):
        adapter = PrimeAgentAdapter()
        missing = adapter.unsupported_isolation_flags(frozenset({"--no-approve"}))
        assert "--no-context-files" in missing

    def test_trusted_workspace_has_nothing_to_isolate(self, monkeypatch):
        monkeypatch.setenv("PRIME_AGENT_TRUST_WORKSPACE", "true")
        adapter = PrimeAgentAdapter()
        assert adapter.unsupported_isolation_flags(frozenset()) == []

    def test_child_env_excludes_worker_secrets(self, monkeypatch):
        """The CLI ships a model-controlled bash tool; os.environ must not leak."""
        monkeypatch.setenv("GH_PAT", "ghp-secret")
        monkeypatch.setenv("MONGO_URL", "mongodb://secret")
        monkeypatch.setenv("JWT_SECRET", "jwt-secret")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
        monkeypatch.setenv("PATH", "/usr/bin")
        env = _child_env()
        assert "GH_PAT" not in env
        assert "MONGO_URL" not in env
        assert "JWT_SECRET" not in env
        assert "ANTHROPIC_API_KEY" not in env
        assert env["PATH"] == "/usr/bin"

    def test_child_env_passes_what_the_extension_needs(self, monkeypatch):
        monkeypatch.setenv("AGENCY_PROXY_URL", "http://proxy:8000")
        monkeypatch.setenv("PROXY_API_KEY", "bearer-token")
        env = _child_env()
        assert env["AGENCY_PROXY_URL"] == "http://proxy:8000"
        assert env["PROXY_API_KEY"] == "bearer-token"


class TestFailClosed:
    """Second-round review findings: controls that quietly failed open."""

    def test_inconclusive_flag_discovery_refuses(self):
        """An unparseable --help must not read as 'nothing to isolate'.

        This was a fail-open in the isolation check itself: an empty `supported`
        set meant the probe failed, but it was treated as though the flags were
        simply unnecessary, so an untrusted workspace ran with none of them.
        """
        missing = PrimeAgentAdapter().unsupported_isolation_flags(frozenset())
        assert set(missing) == set(_UNTRUSTED_WORKSPACE_FLAGS)

    def test_inconclusive_discovery_is_fine_when_trusted(self, monkeypatch):
        monkeypatch.setenv("PRIME_AGENT_TRUST_WORKSPACE", "true")
        assert PrimeAgentAdapter().unsupported_isolation_flags(frozenset()) == []

    def test_execute_refuses_when_discovery_is_inconclusive(self, monkeypatch):
        monkeypatch.setattr(
            "runtimes.adapters.prime_agent.shutil.which", lambda name: "/usr/bin/pi"
        )
        adapter = PrimeAgentAdapter(config={"provider": "none", "extension": ""})
        monkeypatch.setattr(
            adapter, "_supported_flags", lambda _bin: asyncio.sleep(0, result=frozenset())
        )
        with pytest.raises(Exception) as excinfo:
            asyncio.run(adapter.execute(_spec()))
        assert "cannot isolate an untrusted workspace" in str(excinfo.value)

    def test_version_probe_is_reaped_on_timeout(self, monkeypatch):
        """Health is polled on a timer; a stuck CLI would leak one process per poll."""
        reaped: list[object] = []

        class StuckProc:
            returncode = None

            def communicate(self):
                # Deliberately not a coroutine: the patched wait_for below raises
                # before awaiting, and a real coroutine would warn about never
                # being awaited.
                return None

            def kill(self):
                reaped.append(self)

            async def wait(self):
                self.returncode = -9

        async def fake_exec(*args, **kwargs):
            return StuckProc()

        monkeypatch.setattr(
            "runtimes.adapters.prime_agent.shutil.which", lambda name: "/usr/bin/pi"
        )
        monkeypatch.setattr(
            "runtimes.adapters.prime_agent.asyncio.create_subprocess_exec", fake_exec
        )
        monkeypatch.setattr(
            "runtimes.adapters.prime_agent.asyncio.wait_for",
            lambda *a, **k: (_ for _ in ()).throw(asyncio.TimeoutError()),
        )
        health = asyncio.run(PrimeAgentAdapter().health_check())
        assert health.available is False
        assert reaped, "the timed-out --version process was never killed"
