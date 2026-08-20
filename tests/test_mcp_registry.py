"""tests/test_mcp_registry.py — the single MCP catalogue and the screen it backs.

The bug this file exists to prevent: Providers → MCP used to render four
hardcoded entries (filesystem, github, postgres, brave-search) with invented
"connected" statuses, while the two servers the deployment actually had — the
in-process server and Render — were absent. Status was whatever a human typed
into a CRUD table, never measured.

Covers:
  - every declared server is well-formed and probes are measured, not asserted
  - unconfigured servers report *why*, which is the actionable part
  - a probe that hangs, raises, or fails degrades to a status instead of
    breaking the page
  - the frontend no longer carries a fabricated default list
  - Render findings reach the verified-healing path, not just ImprovementLoop
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.integrations import mcp_registry  # noqa: E402
from packages.integrations.mcp_registry import (  # noqa: E402
    MCPServerSpec,
    _status_for,
    list_specs,
    status_all,
)

REPO_ROOT = Path(__file__).parent.parent


# ── catalogue shape ───────────────────────────────────────────────────────────

class TestCatalogue:
    def test_declares_the_servers_this_platform_actually_has(self):
        ids = {s["id"] for s in list_specs()}
        # The two that are real and were previously invisible on the screen.
        assert "internal" in ids
        assert "render" in ids

    def test_playwright_is_declared_for_agent_browser_work(self):
        assert "playwright" in {s["id"] for s in list_specs()}

    def test_every_spec_is_well_formed(self):
        for spec in list_specs():
            assert spec["id"] and spec["name"], spec
            assert spec["desc"].strip(), f"{spec['id']} has no description"
            assert spec["transport"] in {"http", "stdio", "in-process"}, spec
            assert spec["category"], spec

    def test_ids_are_unique(self):
        ids = [s["id"] for s in list_specs()]
        assert len(ids) == len(set(ids))

    def test_catalogue_is_rebuilt_per_call_not_frozen_at_import(self, monkeypatch):
        """Settings changes must be visible without reimporting the module."""
        monkeypatch.setattr(
            mcp_registry.settings, "render_mcp_url", "https://example.test/mcp", raising=False
        )
        render = next(s for s in list_specs() if s["id"] == "render")
        assert render["cmd"] == "https://example.test/mcp"


# ── status measurement ────────────────────────────────────────────────────────

def _spec(**kw: Any) -> MCPServerSpec:
    base = dict(
        server_id="t", name="t", description="d", category="test",
        transport="http", command="c",
    )
    base.update(kw)
    return MCPServerSpec(**base)  # type: ignore[arg-type]


class TestStatusMeasurement:
    @pytest.mark.asyncio
    async def test_unconfigured_reports_the_reason(self):
        """'unconfigured' with no reason just relocates the question."""
        spec = _spec(is_configured=lambda: (False, "API_KEY is not set"))
        row = await _status_for(spec)
        assert row["status"] == "unconfigured"
        assert row["reason"] == "API_KEY is not set"
        assert row["tools"] == 0

    @pytest.mark.asyncio
    async def test_reachable_server_reports_measured_tool_count(self):
        async def _probe():
            return True, 7, ""
        row = await _status_for(_spec(probe=_probe))
        assert row["status"] == "connected"
        assert row["tools"] == 7

    @pytest.mark.asyncio
    async def test_unreachable_server_is_error_with_reason(self):
        async def _probe():
            return False, 0, "connection refused"
        row = await _status_for(_spec(probe=_probe))
        assert row["status"] == "error"
        assert row["reason"] == "connection refused"

    @pytest.mark.asyncio
    async def test_raising_probe_degrades_to_status(self):
        """A probe exception must not break the Providers page."""
        async def _probe():
            raise RuntimeError("boom")
        row = await _status_for(_spec(probe=_probe))
        assert row["status"] == "error"
        assert "boom" in row["reason"]

    @pytest.mark.asyncio
    async def test_hanging_probe_times_out_rather_than_hanging_the_page(self, monkeypatch):
        monkeypatch.setattr(mcp_registry, "HEALTH_TIMEOUT_SECONDS", 0.05)

        async def _probe():
            await asyncio.sleep(10)
            return True, 1, ""

        row = await _status_for(_spec(probe=_probe))
        assert row["status"] == "error"
        assert "timed out" in row["reason"]

    @pytest.mark.asyncio
    async def test_no_probe_is_idle_not_connected(self):
        """Never claim connected without measuring it."""
        row = await _status_for(_spec(probe=None))
        assert row["status"] == "idle"

    @pytest.mark.asyncio
    async def test_managed_rows_are_not_editable(self):
        row = await _status_for(_spec(probe=None))
        assert row["managed"] is True
        assert row["editable"] is False

    @pytest.mark.asyncio
    async def test_status_all_returns_a_row_per_declared_server(self, monkeypatch):
        monkeypatch.setattr(mcp_registry, "HEALTH_TIMEOUT_SECONDS", 0.05)
        rows = await status_all()
        assert len(rows) == len(list_specs())
        for row in rows:
            assert row["status"] in {
                "connected", "available", "error", "idle",
                "unconfigured", "unavailable",
            }

    @pytest.mark.asyncio
    async def test_status_all_never_raises_when_a_probe_explodes(self, monkeypatch):
        def _boom_specs():
            async def _probe():
                raise ValueError("catalogue probe blew up")
            return [_spec(server_id="boom", probe=_probe)]

        monkeypatch.setattr(mcp_registry, "_specs", _boom_specs)
        rows = await status_all()
        assert rows[0]["status"] == "error"


class TestStdioServersAreHonest:
    @pytest.mark.asyncio
    async def test_stdio_server_explains_why_it_is_not_dialable(self, monkeypatch):
        """A stdio server isn't broken — the backend just can't dial it."""
        monkeypatch.setattr(mcp_registry.settings, "gh_pat", "tok", raising=False)
        rows = await status_all()
        github = next(r for r in rows if r["id"] == "github")
        assert github["transport"] == "stdio"
        assert "stdio" in github["reason"].lower()

    @pytest.mark.asyncio
    async def test_stdio_server_is_available_not_error(self, monkeypatch):
        """Regression: github rendered red, sending operators after a non-bug.

        The registry's own docstring said a stdio server must not "read as a
        fault", but _status_for mapped every unreachable server to 'error'
        regardless — so a correctly-configured GitHub entry showed up on the
        dashboard as broken. github is configured and its capability is served
        by agent/github_tools.py, so it must report the green 'available'
        state, never 'error' and not the muted 'unavailable' either.
        """
        monkeypatch.setattr(mcp_registry.settings, "gh_pat", "tok", raising=False)
        rows = await status_all()
        github = next(r for r in rows if r["id"] == "github")
        assert github["status"] == "available", (
            "github is configured and served by the backend — a usable, green state"
        )

    @pytest.mark.asyncio
    async def test_dialable_server_that_fails_is_still_an_error(self):
        """The distinction must not swallow genuine faults."""
        async def _probe():
            return False, 0, "connection refused"
        row = await _status_for(_spec(dialable=True, probe=_probe))
        assert row["status"] == "error"

    @pytest.mark.asyncio
    async def test_undialable_backend_served_server_reports_available(self):
        """An undialable server whose capability is served here is green."""
        async def _probe():
            return False, 0, "not dialable from here"
        row = await _status_for(
            _spec(dialable=False, served_by_backend=True, probe=_probe)
        )
        assert row["status"] == "available"

    @pytest.mark.asyncio
    async def test_undialable_server_with_no_alternate_path_is_unavailable(self):
        """Without a backend path, an undialable server stays muted, not green."""
        async def _probe():
            return False, 0, "not dialable from here"
        row = await _status_for(_spec(dialable=False, probe=_probe))
        assert row["status"] == "unavailable"

    def test_http_servers_stay_dialable_by_default(self):
        """Only servers explicitly marked undialable get the softer status."""
        specs = {s.server_id: s for s in mcp_registry._specs()}
        assert specs["render"].dialable is True
        assert specs["playwright"].dialable is True
        assert specs["github"].dialable is False

    def test_github_capability_is_served_by_the_backend(self):
        """github is undialable but usable — its capability is served here."""
        specs = {s.server_id: s for s in mcp_registry._specs()}
        assert specs["github"].served_by_backend is True
        # A default HTTP server makes no such claim.
        assert specs["render"].served_by_backend is False


class TestReasonsAreActionable:
    def test_playwright_reason_names_the_fix(self, monkeypatch):
        """'X is not set' leaves the operator to go find out what to do."""
        monkeypatch.setattr(mcp_registry.settings, "playwright_mcp_url", "", raising=False)
        configured, reason = mcp_registry._playwright_configured()
        assert configured is False
        assert "@playwright/mcp" in reason

    def test_frontend_colours_unavailable_neutrally(self):
        """Red is reserved for real faults."""
        src = (REPO_ROOT / "frontend/src/v5/screens/ProvidersScreen.jsx").read_text()
        assert "unavailable:'var(--text-muted)'" in src

    def test_frontend_colours_available_green(self):
        """A backend-served server reads as healthy, not as a warning."""
        src = (REPO_ROOT / "frontend/src/v5/screens/ProvidersScreen.jsx").read_text()
        assert "available:'#46d9a4'" in src


# ── the screen this backs ─────────────────────────────────────────────────────

class TestProvidersScreen:
    def _source(self) -> str:
        return (REPO_ROOT / "frontend/src/v5/screens/ProvidersScreen.jsx").read_text()

    def test_fabricated_default_server_list_is_gone(self):
        """The four invented 'connected' entries must not come back.

        Asserts on the *shape* of fabricated data — a literal server object
        carrying a hardcoded status — rather than on the vendor names, which
        legitimately appear in the "add your own server" input placeholder and
        in the comment explaining why the list was removed.
        """
        src = self._source()
        assert "MCP_SERVERS_DEFAULT" not in src
        for fake_status in ("status:'connected'", 'status:"connected"'):
            assert fake_status not in src, (
                f"hardcoded {fake_status} suggests a fabricated server entry returned"
            )

    def test_empty_list_renders_empty(self):
        """No seeding on an empty response — that is what made the page lie."""
        assert "_seeded" not in self._source()

    def test_managed_rows_render_a_reason(self):
        assert "srv.reason" in self._source()


class TestBackendMergesRegistryIntoTheEndpoint:
    def _server_py(self) -> str:
        return (REPO_ROOT / "backend/server.py").read_text()

    def test_endpoint_pulls_from_the_registry(self):
        assert "from packages.integrations.mcp_registry import status_all" in self._server_py()

    def test_user_rows_are_marked_unmanaged(self):
        src = self._server_py()
        assert 's.setdefault("managed", False)' in src


# ── self-heal wiring ──────────────────────────────────────────────────────────

class TestRenderFindingsReachTheHealer:
    @pytest.mark.asyncio
    async def test_recurrences_are_reported_even_inside_cooldown(self, monkeypatch):
        """A fix that did not hold must be detectable, or it looks healed forever."""
        import services.render_ops as ops
        from packages.integrations.render_mcp import RenderDeploy

        seen: list[str] = []

        class _Healer:
            def note_recurrence(self, sig: str) -> bool:
                seen.append(sig)
                return True

        monkeypatch.setattr(
            "agent.self_healing.get_self_healing_agent", lambda: _Healer(), raising=False
        )
        monkeypatch.setattr(ops, "_file_issue", lambda finding: True)
        monkeypatch.setattr(ops, "_report_to_healer", _noop_async)

        class _Fake:
            is_configured = True
            async def resolve_service_ids(self): return ["srv-1"]
            async def list_services(self): return [{"id": "srv-1", "name": "api"}]
            async def latest_deploy(self, sid):
                return RenderDeploy(deploy_id="d1", status="build_failed")
            async def list_logs(self, *a, **k): return []
            async def get_metrics(self, *a, **k): return {}

        monitor = ops.RenderOpsMonitor(_Fake())
        await monitor.tick()   # first: files + notes
        await monitor.tick()   # second: cooled down, but must still note
        assert len(seen) == 2, "recurrence must be reported on every observation"

    @pytest.mark.asyncio
    async def test_filed_finding_opens_a_verified_heal(self, monkeypatch):
        import services.render_ops as ops
        from services.render_ops import RenderFinding

        opened: list[dict] = []

        class _Healer:
            async def on_manual_report(self, title, description, severity, signature):
                opened.append({"title": title, "severity": severity, "signature": signature})

        monkeypatch.setattr(
            "agent.self_healing.get_self_healing_agent", lambda: _Healer(), raising=False
        )
        finding = RenderFinding(
            kind="deploy_failed", service_id="srv-1", service_name="api",
            severity="critical", title="Render deploy failed", detail="d",
            evidence={"deploy_id": "d1"},
        )
        await ops._report_to_healer(finding)
        assert opened and opened[0]["severity"] == "critical"
        assert opened[0]["signature"] == finding.signature

    @pytest.mark.asyncio
    async def test_missing_healer_does_not_break_the_monitor(self, monkeypatch):
        import services.render_ops as ops
        from services.render_ops import RenderFinding

        monkeypatch.setattr(
            "agent.self_healing.get_self_healing_agent", lambda: None, raising=False
        )
        finding = RenderFinding(
            kind="error_logs", service_id="s", service_name="n",
            severity="high", title="t", detail="d",
        )
        await ops._report_to_healer(finding)   # must not raise
        ops._note_recurrence(finding)          # must not raise


async def _noop_async(*_a: Any, **_k: Any) -> None:
    return None


# ── settings ──────────────────────────────────────────────────────────────────

class TestPlaywrightSettings:
    def test_playwright_url_defaults_empty(self, monkeypatch):
        from packages.config.settings import Settings
        monkeypatch.delenv("PLAYWRIGHT_MCP_URL", raising=False)
        assert Settings().playwright_mcp_url == ""

    def test_playwright_url_strips_trailing_slash(self, monkeypatch):
        from packages.config.settings import Settings
        monkeypatch.setenv("PLAYWRIGHT_MCP_URL", "http://pw:8931/mcp/")
        assert Settings().playwright_mcp_url == "http://pw:8931/mcp"
