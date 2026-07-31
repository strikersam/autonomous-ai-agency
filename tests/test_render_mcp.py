"""tests/test_render_mcp.py — Render MCP integration.

Covers:
  - MCPClient Streamable-HTTP transport (SSE decoding, session id, rpc_path)
    without regressing the plain-JSON path used by /mcp-internal
  - RenderMCPClient payload normalisation and the write guard
  - RenderOpsMonitor findings (deploy failed/stalled, log spike, memory) and
    cooldown dedup
  - /api/render/* admin gating
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.mcp_client import MCPClient, MCPUnavailableError  # noqa: E402
from packages.integrations.render_mcp import (  # noqa: E402
    RenderDeploy,
    RenderMCPClient,
    RenderWriteBlockedError,
    _as_list,
    _coerce_payload,
    _unwrap,
)


def _response(
    *, body: str, content_type: str, headers: dict[str, str] | None = None
) -> httpx.Response:
    """Build an httpx.Response the client can parse, with a bound request."""
    return httpx.Response(
        200,
        content=body.encode(),
        headers={"content-type": content_type, **(headers or {})},
        request=httpx.Request("POST", "https://example.test/mcp"),
    )


# ── Transport ─────────────────────────────────────────────────────────────────

class TestStreamableHTTPTransport:
    def test_json_response_still_parsed(self):
        """The plain-JSON path (/mcp-internal) must be unchanged."""
        resp = _response(
            body='{"jsonrpc":"2.0","id":1,"result":{"ok":true}}',
            content_type="application/json",
        )
        assert MCPClient._parse_body(resp) == {
            "jsonrpc": "2.0", "id": 1, "result": {"ok": True}
        }

    def test_sse_response_parsed(self):
        """A Streamable-HTTP reply arrives as SSE data: frames."""
        body = (
            "event: message\n"
            'data: {"jsonrpc":"2.0","id":1,"result":{"tools":[]}}\n'
            "\n"
        )
        resp = _response(body=body, content_type="text/event-stream")
        assert MCPClient._parse_body(resp)["result"] == {"tools": []}

    def test_sse_skips_notification_frames(self):
        """Progress notifications precede the response; the response wins."""
        body = (
            'data: {"jsonrpc":"2.0","method":"notifications/progress"}\n'
            "\n"
            'data: {"jsonrpc":"2.0","id":7,"result":{"value":42}}\n'
            "\n"
        )
        resp = _response(body=body, content_type="text/event-stream")
        assert MCPClient._parse_body(resp)["result"]["value"] == 42

    def test_sse_multiline_data_is_joined(self):
        """Regression: one event may split its JSON across several data: lines.

        Parsing each line alone failed every json.loads, raised, and opened the
        circuit breaker — and Render's log/metric dumps are exactly the large
        responses a server splits.
        """
        body = (
            "event: message\n"
            'data: {"jsonrpc":"2.0","id":1,\n'
            'data:  "result":{"logs":["a","b"]}}\n'
            "\n"
        )
        resp = _response(body=body, content_type="text/event-stream")
        assert MCPClient._parse_body(resp)["result"] == {"logs": ["a", "b"]}

    def test_sse_final_event_without_trailing_blank_line(self):
        """A stream that ends without a terminating blank line still decodes."""
        body = 'data: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}'
        resp = _response(body=body, content_type="text/event-stream")
        assert MCPClient._parse_body(resp)["result"] == {"ok": True}

    def test_sse_crlf_line_endings(self):
        """SSE uses CRLF on the wire; the trailing \\r must not corrupt the JSON."""
        body = 'data: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\r\n\r\n'
        resp = _response(body=body, content_type="text/event-stream")
        assert MCPClient._parse_body(resp)["result"] == {"ok": True}

    def test_sse_without_response_frame_raises(self):
        resp = _response(
            body='data: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n',
            content_type="text/event-stream",
        )
        with pytest.raises(ValueError):
            MCPClient._parse_body(resp)

    def test_accept_header_lists_both_media_types(self):
        # nosec B106 - dummy token for a header-construction assertion, not a
        # credential. B106 matches the *argument name* against its password
        # wordlist ("secret_token" contains both "secret" and "token"), so any
        # literal here trips it regardless of the value.
        headers = MCPClient("https://example.test", secret_token="tok")._headers()  # nosec B106  # noqa: S106
        assert "application/json" in headers["Accept"]
        assert "text/event-stream" in headers["Accept"]
        assert headers["Authorization"] == "Bearer tok"

    def test_session_id_captured_and_echoed(self):
        client = MCPClient("https://example.test")
        assert "Mcp-Session-Id" not in client._headers()
        client._capture_session(
            _response(body="{}", content_type="application/json",
                      headers={"Mcp-Session-Id": "sess-abc"})
        )
        assert client._headers()["Mcp-Session-Id"] == "sess-abc"

    def test_rpc_path_default_appends_mcp(self):
        """Existing callers pass a base URL and expect /mcp appended."""
        assert MCPClient("http://host:8001/mcp-internal").endpoint == (
            "http://host:8001/mcp-internal/mcp"
        )

    def test_rpc_path_empty_uses_url_as_is(self):
        """Render's URL already names the endpoint, so nothing is appended."""
        assert MCPClient("http://127.0.0.1:10000/mcp", rpc_path="").endpoint == (
            "http://127.0.0.1:10000/mcp"
        )


# ── Payload normalisation ─────────────────────────────────────────────────────

class TestPayloadNormalisation:
    def test_coerce_parses_json_text_block(self):
        assert _coerce_payload('{"a": 1}') == {"a": 1}

    def test_coerce_leaves_plain_text_alone(self):
        assert _coerce_payload("not json") == "not json"

    def test_coerce_passes_structured_dict_through(self):
        assert _coerce_payload({"a": 1}) == {"a": 1}

    def test_as_list_handles_bare_array(self):
        assert _as_list([{"id": "a"}], "services") == [{"id": "a"}]

    def test_as_list_handles_named_key(self):
        assert _as_list({"services": [{"id": "a"}]}, "services") == [{"id": "a"}]

    def test_as_list_falls_back_to_first_list_value(self):
        """An upstream rename must degrade, not silently return nothing."""
        assert _as_list({"items": [{"id": "a"}]}, "services") == [{"id": "a"}]

    def test_as_list_on_garbage_returns_empty(self):
        assert _as_list("nope", "services") == []

    def test_unwrap_envelope(self):
        assert _unwrap({"service": {"id": "srv-1"}}, "service") == {"id": "srv-1"}

    def test_unwrap_passthrough_when_not_wrapped(self):
        assert _unwrap({"id": "srv-1"}, "service") == {"id": "srv-1"}


class TestRenderDeploy:
    def test_failed_status_detected(self):
        assert RenderDeploy(deploy_id="d1", status="build_failed").failed

    def test_live_status_not_failed(self):
        deploy = RenderDeploy(deploy_id="d1", status="live")
        assert deploy.live and not deploy.failed

    def test_failed_statuses_is_not_a_constructor_field(self):
        """ClassVar, not a dataclass field — positional args must not shift."""
        deploy = RenderDeploy("d1", "live", "abc", "then", "now")
        assert deploy.commit == "abc"


# ── Client behaviour ──────────────────────────────────────────────────────────

class _FakeInner:
    """Stands in for MCPClient inside RenderMCPClient."""

    def __init__(self, payload: Any = None) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []

    async def initialize(self) -> dict:
        return {}

    async def notify(self, method: str, params: dict | None = None) -> None:
        return None

    async def call_tool_structured(self, name: str, arguments: dict) -> Any:
        self.calls.append((name, arguments))

        class _Result:
            content = self.payload

        return _Result()

    async def list_tools(self) -> list[dict]:
        return [{"name": "list_services"}]


def _client(payload: Any = None, **kwargs: Any) -> tuple[RenderMCPClient, _FakeInner]:
    client = RenderMCPClient(
        url="https://render.test/mcp", api_key="key", workspace_id="own-1", **kwargs
    )
    inner = _FakeInner(payload)
    client._client = inner  # type: ignore[assignment]
    return client, inner


class TestRenderMCPClient:
    @pytest.mark.asyncio
    async def test_unconfigured_client_raises_unavailable(self):
        client = RenderMCPClient(url="https://render.test/mcp", api_key="")
        assert not client.is_configured
        with pytest.raises(MCPUnavailableError):
            await client.call("list_services")

    @pytest.mark.asyncio
    async def test_write_tool_blocked_by_default(self):
        client, _ = _client(allow_writes=False)
        with pytest.raises(RenderWriteBlockedError):
            await client.trigger_deploy("srv-1")

    @pytest.mark.asyncio
    async def test_write_tool_allowed_when_enabled(self):
        client, inner = _client({"ok": True}, allow_writes=True)
        await client.trigger_deploy("srv-1")
        assert inner.calls[0][0] == "trigger_deploy"

    @pytest.mark.asyncio
    async def test_workspace_id_injected_on_scoped_tools(self):
        client, inner = _client({"services": []})
        await client.list_services()
        assert inner.calls[0][1]["workspaceId"] == "own-1"

    @pytest.mark.asyncio
    async def test_workspace_id_not_injected_on_list_workspaces(self):
        client, inner = _client({"workspaces": []})
        await client.list_workspaces()
        assert "workspaceId" not in inner.calls[0][1]

    @pytest.mark.asyncio
    async def test_list_services_unwraps_envelope(self):
        client, _ = _client({"services": [{"service": {"id": "srv-1", "name": "api"}}]})
        assert await client.list_services() == [{"id": "srv-1", "name": "api"}]

    @pytest.mark.asyncio
    async def test_list_deploys_returns_typed_deploys(self):
        client, _ = _client(
            {"deploys": [{"deploy": {"id": "dep-1", "status": "build_failed",
                                     "commit": {"id": "abc123"}}}]}
        )
        deploys = await client.list_deploys("srv-1")
        assert deploys[0].deploy_id == "dep-1"
        assert deploys[0].commit == "abc123"
        assert deploys[0].failed

    @pytest.mark.asyncio
    async def test_latest_deploy_none_when_empty(self):
        client, _ = _client({"deploys": []})
        assert await client.latest_deploy("srv-1") is None

    @pytest.mark.asyncio
    async def test_list_logs_passes_filters(self):
        client, inner = _client({"logs": []})
        await client.list_logs(["srv-1"], level=["error"], limit=25)
        _, args = inner.calls[0]
        assert args["resource"] == ["srv-1"]
        assert args["level"] == ["error"]
        assert args["limit"] == 25

    @pytest.mark.asyncio
    async def test_concurrent_calls_handshake_once(self):
        """Regression: the admin routes and the ops loop share this singleton.

        Without the lock both would run `initialize`, a session-managing server
        would issue two sessions, and `_capture_session` keeps only the last —
        leaking the other.
        """
        import asyncio as _asyncio

        client, inner = _client({"services": []})
        handshakes = 0
        original = inner.initialize

        async def _counting_initialize() -> dict:
            nonlocal handshakes
            handshakes += 1
            await _asyncio.sleep(0)  # yield, so a racing caller can interleave
            return await original()

        inner.initialize = _counting_initialize  # type: ignore[assignment]
        await _asyncio.gather(*(client.list_services() for _ in range(5)))
        assert handshakes == 1

    @pytest.mark.asyncio
    async def test_failed_handshake_is_not_cached(self):
        """A handshake that raised must be retried, not remembered as done."""
        client, inner = _client({"services": []})
        calls = 0

        async def _flaky_initialize() -> dict:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise MCPUnavailableError("down")
            return {}

        inner.initialize = _flaky_initialize  # type: ignore[assignment]
        with pytest.raises(MCPUnavailableError):
            await client.list_services()
        await client.list_services()
        assert calls == 2

    @pytest.mark.asyncio
    async def test_health_reports_unconfigured_without_raising(self):
        client = RenderMCPClient(url="https://render.test/mcp", api_key="")
        health = await client.health()
        assert health == {
            "configured": False, "reachable": False, "reason": "RENDER_API_KEY not set"
        }

    @pytest.mark.asyncio
    async def test_health_reports_reachable(self):
        client, _ = _client()
        health = await client.health()
        assert health["reachable"] is True
        assert health["tool_count"] == 1


# ── Ops monitor ───────────────────────────────────────────────────────────────

class _FakeRender:
    """Minimal RenderMCPClient stand-in for the ops monitor."""

    is_configured = True

    def __init__(self, *, deploys=None, logs=None, metrics=None) -> None:
        self._deploys = deploys or []
        self._logs = logs or []
        self._metrics = metrics or {}

    async def resolve_service_ids(self) -> list[str]:
        return ["srv-1"]

    async def list_services(self) -> list[dict]:
        return [{"id": "srv-1", "name": "api"}]

    async def latest_deploy(self, service_id: str):
        return self._deploys[0] if self._deploys else None

    async def list_logs(self, *args: Any, **kwargs: Any) -> list[dict]:
        return self._logs

    async def get_metrics(self, *args: Any, **kwargs: Any) -> Any:
        return self._metrics


class TestRenderOpsMonitor:
    @pytest.mark.asyncio
    async def test_failed_deploy_becomes_finding(self):
        from services.render_ops import RenderOpsMonitor
        monitor = RenderOpsMonitor(
            _FakeRender(deploys=[RenderDeploy(deploy_id="dep-1", status="build_failed")])
        )
        findings = await monitor.scan()
        assert [f.kind for f in findings] == ["deploy_failed"]
        assert findings[0].severity == "critical"
        assert findings[0].service_name == "api"

    @pytest.mark.asyncio
    async def test_live_deploy_produces_no_finding(self):
        from services.render_ops import RenderOpsMonitor
        monitor = RenderOpsMonitor(
            _FakeRender(deploys=[RenderDeploy(deploy_id="dep-1", status="live")])
        )
        assert await monitor.scan() == []

    @pytest.mark.asyncio
    async def test_stalled_deploy_detected(self):
        from datetime import datetime, timedelta, timezone
        from services.render_ops import RenderOpsMonitor, STALLED_DEPLOY_SECONDS
        started = datetime.now(timezone.utc) - timedelta(seconds=STALLED_DEPLOY_SECONDS + 600)
        monitor = RenderOpsMonitor(
            _FakeRender(deploys=[RenderDeploy(
                deploy_id="dep-1",
                status="build_in_progress",
                created_at=started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )])
        )
        findings = await monitor.scan()
        assert [f.kind for f in findings] == ["deploy_stalled"]

    @pytest.mark.asyncio
    async def test_recent_in_progress_deploy_is_not_stalled(self):
        from datetime import datetime, timezone
        from services.render_ops import RenderOpsMonitor
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        monitor = RenderOpsMonitor(
            _FakeRender(deploys=[RenderDeploy(
                deploy_id="dep-1", status="build_in_progress", created_at=now
            )])
        )
        assert await monitor.scan() == []

    @pytest.mark.asyncio
    async def test_error_log_spike_detected(self):
        from services.render_ops import ERROR_LOG_THRESHOLD, RenderOpsMonitor
        logs = [{"message": f"boom {i}"} for i in range(ERROR_LOG_THRESHOLD + 5)]
        monitor = RenderOpsMonitor(_FakeRender(logs=logs))
        findings = await monitor.scan()
        assert [f.kind for f in findings] == ["error_logs"]
        assert findings[0].evidence["count"] == ERROR_LOG_THRESHOLD + 5
        assert findings[0].evidence["count_is_capped"] is False

    @pytest.mark.asyncio
    async def test_capped_log_count_is_reported_as_at_least(self):
        """At the fetch cap the true count is unknown — don't report the cap as the total."""
        from services.render_ops import LOG_FETCH_LIMIT, RenderOpsMonitor
        logs = [{"message": "boom"}] * LOG_FETCH_LIMIT
        findings = await RenderOpsMonitor(_FakeRender(logs=logs)).scan()
        assert findings[0].evidence["count_is_capped"] is True
        assert "at least" in findings[0].title

    @pytest.mark.asyncio
    async def test_error_logs_below_threshold_ignored(self):
        from services.render_ops import ERROR_LOG_THRESHOLD, RenderOpsMonitor
        logs = [{"message": "boom"}] * (ERROR_LOG_THRESHOLD - 1)
        assert await RenderOpsMonitor(_FakeRender(logs=logs)).scan() == []

    @pytest.mark.asyncio
    async def test_memory_pressure_detected(self):
        from services.render_ops import RenderOpsMonitor
        metrics = {
            "memory_usage": {"values": [{"value": 500_000_000}]},
            "memory_limit": {"values": [{"value": 536_870_912}]},
        }
        findings = await RenderOpsMonitor(_FakeRender(metrics=metrics)).scan()
        assert [f.kind for f in findings] == ["memory_pressure"]

    @pytest.mark.asyncio
    async def test_memory_below_threshold_ignored(self):
        from services.render_ops import RenderOpsMonitor
        metrics = {
            "memory_usage": {"values": [{"value": 100_000_000}]},
            "memory_limit": {"values": [{"value": 536_870_912}]},
        }
        assert await RenderOpsMonitor(_FakeRender(metrics=metrics)).scan() == []

    @pytest.mark.asyncio
    async def test_unrecognised_metric_shape_is_skipped_not_raised(self):
        from services.render_ops import RenderOpsMonitor
        monitor = RenderOpsMonitor(_FakeRender(metrics={"unexpected": "shape"}))
        assert await monitor.scan() == []

    @pytest.mark.asyncio
    async def test_scan_survives_unreachable_render(self):
        from services.render_ops import RenderOpsMonitor

        class _Broken(_FakeRender):
            async def resolve_service_ids(self):
                raise MCPUnavailableError("down")

        monitor = RenderOpsMonitor(_Broken())
        assert await monitor.scan() == []
        assert "service discovery failed" in monitor.get_status()["last_error"]

    def test_cooldown_dedups_identical_findings(self):
        from services.render_ops import RenderFinding, RenderOpsMonitor
        monitor = RenderOpsMonitor(_FakeRender())
        finding = RenderFinding(
            kind="deploy_failed", service_id="srv-1", service_name="api",
            severity="critical", title="t", detail="d", evidence={"deploy_id": "dep-1"},
        )
        assert monitor._is_cool(finding) is True
        monitor._claim(finding)
        assert monitor._is_cool(finding) is False

    @pytest.mark.asyncio
    async def test_cooldown_not_burned_when_filing_fails(self, monkeypatch):
        """A finding that could not be filed must be retried, not silenced 6h."""
        import services.render_ops as ops
        from services.render_ops import RenderOpsMonitor
        monitor = RenderOpsMonitor(
            _FakeRender(deploys=[RenderDeploy(deploy_id="dep-1", status="build_failed")])
        )
        monkeypatch.setattr(ops, "_file_issue", lambda finding: False)  # loop idle
        assert await monitor.tick() == []
        assert monitor._cooldowns == {}
        monkeypatch.setattr(ops, "_file_issue", lambda finding: True)
        assert len(await monitor.tick()) == 1

    @pytest.mark.asyncio
    async def test_partial_check_failure_keeps_last_error(self):
        """A check failing every tick must not be hidden by another that works."""
        from services.render_ops import RenderOpsMonitor

        class _HalfBroken(_FakeRender):
            async def get_metrics(self, *args: Any, **kwargs: Any):
                raise MCPUnavailableError("metrics down")

        monitor = _HalfBroken(deploys=[RenderDeploy(deploy_id="d", status="build_failed")])
        m = RenderOpsMonitor(monitor)
        findings = await m.scan()
        assert [f.kind for f in findings] == ["deploy_failed"]
        assert "metrics down" in m.get_status()["last_error"]

    def test_signature_is_not_time_derived(self):
        """Regression: an hourly bucket in the key made the 6h cooldown a no-op.

        `error_logs` and `memory_pressure` carry no deploy_id, so when the
        signature fell back to the hour-truncated `bucket` it changed every
        hour — a sustained spike filed 4x more issues than intended and
        `_cooldowns` grew forever.
        """
        from services.render_ops import RenderFinding

        def _finding(bucket: str) -> RenderFinding:
            return RenderFinding(
                kind="error_logs", service_id="srv-1", service_name="api",
                severity="high", title="t", detail="d",
                evidence={"count": 42, "bucket": bucket},
            )

        assert _finding("2026-07-31T09").signature == _finding("2026-07-31T10").signature

    def test_sustained_spike_files_once_across_hours(self):
        """The same ongoing condition stays deduped as the hour rolls over."""
        from services.render_ops import RenderFinding, RenderOpsMonitor
        monitor = RenderOpsMonitor(_FakeRender())

        def _finding(bucket: str) -> RenderFinding:
            return RenderFinding(
                kind="memory_pressure", service_id="srv-1", service_name="api",
                severity="medium", title="t", detail="d", evidence={"bucket": bucket},
            )

        first = _finding("2026-07-31T09")
        assert monitor._is_cool(first) is True
        monitor._claim(first)
        assert monitor._is_cool(_finding("2026-07-31T10")) is False
        assert len(monitor._cooldowns) == 1

    def test_different_deploys_are_separate_findings(self):
        from services.render_ops import RenderFinding, RenderOpsMonitor
        monitor = RenderOpsMonitor(_FakeRender())

        def _finding(deploy_id: str) -> RenderFinding:
            return RenderFinding(
                kind="deploy_failed", service_id="srv-1", service_name="api",
                severity="critical", title="t", detail="d",
                evidence={"deploy_id": deploy_id},
            )

        assert monitor._claim(_finding("dep-1")) is True
        assert monitor._claim(_finding("dep-2")) is True


# ── API surface ───────────────────────────────────────────────────────────────

class TestRenderRouter:
    def test_non_admin_is_rejected(self):
        from fastapi import HTTPException
        from backend.render_router import _require_admin
        with pytest.raises(HTTPException) as exc:
            _require_admin({"role": "user"})
        assert exc.value.status_code == 403

    def test_anonymous_is_rejected(self):
        from fastapi import HTTPException
        from backend.render_router import _require_admin
        with pytest.raises(HTTPException):
            _require_admin(None)

    def test_admin_is_accepted(self):
        from backend.render_router import _require_admin
        assert _require_admin({"role": "admin"})["role"] == "admin"

    def test_router_exposes_only_read_routes(self):
        """No mutating Render call may be one HTTP request away."""
        from backend.render_router import build_render_router
        router = build_render_router(lambda: {"role": "admin"})
        methods = {m for route in router.routes for m in getattr(route, "methods", set())}
        assert methods == {"GET"}


# ── Settings ──────────────────────────────────────────────────────────────────

class TestRenderSettings:
    def test_ops_loop_requires_credentials_not_just_the_flag(self):
        """An enabled loop with no API key would fail every tick — so it stays dormant."""
        from packages.config.settings import Settings
        s = Settings()
        s.render_ops_enabled = "true"
        s.render_api_key = ""
        assert s.is_render_ops_enabled is False
        s.render_api_key = "key"
        assert s.is_render_ops_enabled is True

    def test_ops_defaults_to_on(self, monkeypatch):
        """Monitoring is the standing state, not an opt-in after an incident."""
        from packages.config.settings import Settings
        monkeypatch.delenv("RENDER_OPS_ENABLED", raising=False)
        assert Settings().render_ops_enabled == "true"

    def test_writes_default_to_denied(self, monkeypatch):
        from packages.config.settings import Settings
        monkeypatch.delenv("RENDER_MCP_ALLOW_WRITES", raising=False)
        assert Settings().is_render_mcp_write_allowed is False

    def test_service_ids_parsed_from_csv(self):
        from packages.config.settings import Settings
        s = Settings()
        s.render_service_ids = " srv-1 , srv-2 ,"
        assert s.render_service_id_list == ["srv-1", "srv-2"]


# ── Deployment topology ───────────────────────────────────────────────────────

def _render_yaml() -> dict:
    import yaml
    return yaml.safe_load((Path(__file__).parent.parent / "render.yaml").read_text())


def _service(name: str) -> dict:
    for svc in _render_yaml()["services"]:
        if svc.get("name") == name:
            return svc
    raise AssertionError(f"service {name!r} not declared in render.yaml")


def _env(service: dict) -> dict[str, Any]:
    return {e["key"]: e for e in service.get("envVars", [])}


class TestRenderMCPSidecarService:
    def test_sidecar_service_is_declared(self):
        svc = _service("agency-render-mcp")
        assert svc["type"] == "web"
        assert svc["dockerfilePath"] == "./Dockerfile.render-mcp"

    def test_sidecar_declares_the_port_it_actually_binds(self):
        """The Go binary hardcodes :10000 and ignores $PORT, so Render must be told."""
        assert _env(_service("agency-render-mcp"))["PORT"]["value"] == "10000"

    def test_sidecar_holds_no_secrets(self):
        """In HTTP mode the token comes from the caller's header, so nothing here is secret."""
        for entry in _env(_service("agency-render-mcp")).values():
            assert "sync" not in entry, f"{entry['key']} declared as a secret"

    def test_sidecar_has_no_health_check_path(self):
        """The mux serves /mcp only; a health check there opens an SSE stream that never closes."""
        assert "healthCheckPath" not in _service("agency-render-mcp")

    def test_oauth_is_explicitly_disabled(self):
        """pkg/oauth fails the process at boot on a partial OAuth config."""
        assert _env(_service("agency-render-mcp"))["OAUTH_ENABLED"]["value"] == "false"

    def test_dockerfile_pins_transport_and_entrypoint(self):
        content = (Path(__file__).parent.parent / "Dockerfile.render-mcp").read_text()
        assert "ghcr.io/render-oss/render-mcp-server" in content
        assert 'ENTRYPOINT ["/server/render-mcp-server"]' in content
        assert 'CMD ["-t", "http"]' in content


class TestBackendWiring:
    def test_backend_points_at_the_sidecar_privately(self):
        """The backend must use the private-network address, not the public URL."""
        url = _env(_service("local-llm-server"))["RENDER_MCP_URL"]["value"]
        assert url == "http://agency-render-mcp:10000/mcp"
        assert ".onrender.com" not in url

    def test_ops_enabled_in_production(self):
        assert _env(_service("local-llm-server"))["RENDER_OPS_ENABLED"]["value"] == "true"

    def test_poll_interval_keeps_the_free_sidecar_warm(self):
        """A free service sleeps at ~15m idle; polling must stay under that."""
        interval = int(_env(_service("local-llm-server"))["RENDER_OPS_INTERVAL_SECONDS"]["value"])
        assert interval < 900

    def test_writes_stay_disabled_in_production(self):
        assert _env(_service("local-llm-server"))["RENDER_MCP_ALLOW_WRITES"]["value"] == "false"

    def test_api_key_is_never_committed(self):
        assert _env(_service("local-llm-server"))["RENDER_API_KEY"]["sync"] is False
