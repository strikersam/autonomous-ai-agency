"""Contract tests for the provider on/off endpoints.

``GET /api/brain/providers`` and ``PUT /api/brain/providers/{id}/enabled`` power
the Providers screen's switch. They shipped without tests; this file closes that
gap and pins the three things a regression here would break silently: the switch
actually persists, an unknown provider is rejected rather than silently stored,
and no API key ever reaches the browser.
"""
from __future__ import annotations

import pytest

import services.brain_failover as bf


@pytest.fixture(autouse=True)
def one_configured_provider(monkeypatch, tmp_path):
    """A registry with exactly two known providers and isolated state."""
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "kv.db"))
    monkeypatch.setenv("GROQ_API_KEY", "test-key-groq")
    monkeypatch.setenv("CEREBRAS_API_KEY", "test-key-cerebras")
    for var in ("NVIDIA_API_KEY", "ZHIPU_API_KEY", "DEEPSEEK_API_KEY",
                "TOGETHER_API_KEY", "DASHSCOPE_API_KEY", "MOONSHOT_API_KEY",
                "ZAI_API_KEY", "MISTRAL_API_KEY", "ANTHROPIC_API_KEY",
                "OPENROUTER_API_KEY", "MINIMAX_API_KEY", "GOOGLE_API_KEY",
                "AEROLINK_API_KEY", "OLLAMA_BASE"):
        monkeypatch.delenv(var, raising=False)
    bf.reset_failover_manager()
    bf.reset_kv_state()
    yield
    bf.reset_failover_manager()
    bf.reset_kv_state()


def _get(client):
    r = client.get("/api/brain/providers")
    assert r.status_code == 200, r.text
    return r.json()


class TestListing:
    def test_lists_configured_providers_with_health_and_switch_state(
        self, app_client
    ) -> None:
        body = _get(app_client)
        ids = {p["id"] for p in body["providers"]}

        assert {"groq", "cerebras"} <= ids
        assert body["total_count"] == len(body["providers"])
        row = next(p for p in body["providers"] if p["id"] == "groq")
        assert row["enabled"] is True
        assert row["online"] is True
        assert row["disabled_reason"] == ""
        assert row["auto_disabled"] is False

    def test_never_returns_an_api_key(self, app_client) -> None:
        """The response reaches the browser — a leaked key would be a disclosure."""
        raw = app_client.get("/api/brain/providers").text
        assert "test-key-groq" not in raw
        assert "test-key-cerebras" not in raw
        assert "api_key" not in raw

    def test_reports_whether_the_state_survives_a_deploy(self, app_client) -> None:
        body = _get(app_client)
        assert body["state_durable"] is False, (
            "the suite runs with TESTING=true, which keeps operator state on the "
            "local SQLite mirror — so the flag must say the state is not durable"
        )

    def test_requires_authentication(self, unauth_client) -> None:
        assert unauth_client.get("/api/brain/providers").status_code == 401


class TestSwitch:
    def test_disable_then_enable_round_trips_through_the_listing(
        self, app_client
    ) -> None:
        r = app_client.put("/api/brain/providers/groq/enabled",
                           json={"enabled": False})
        assert r.status_code == 200, r.text
        assert r.json()["enabled"] is False
        assert r.json()["disabled_reason"] == "disabled by operator"

        row = next(p for p in _get(app_client)["providers"] if p["id"] == "groq")
        assert row["enabled"] is False
        assert row["online"] is False, "a disabled provider is never online"
        assert row["auto_disabled"] is False, "an operator switch is not an auto-disable"

        r = app_client.put("/api/brain/providers/groq/enabled",
                           json={"enabled": True})
        assert r.status_code == 200, r.text
        row = next(p for p in _get(app_client)["providers"] if p["id"] == "groq")
        assert row["enabled"] is True and row["disabled_reason"] == ""

    def test_a_disabled_provider_is_not_selected_for_dispatch(
        self, app_client
    ) -> None:
        """The switch has to reach the dispatcher, not just the listing."""
        app_client.put("/api/brain/providers/groq/enabled", json={"enabled": False})

        chosen = bf.get_failover_manager().next_provider()
        assert chosen is not None and chosen.id != "groq"

    def test_manual_enable_clears_an_auto_disable(self, app_client) -> None:
        bf.auto_disable_provider("groq", "401 invalid or expired API key")
        row = next(p for p in _get(app_client)["providers"] if p["id"] == "groq")
        assert row["auto_disabled"] is True
        assert "401" in row["disabled_reason"]

        app_client.put("/api/brain/providers/groq/enabled", json={"enabled": True})
        row = next(p for p in _get(app_client)["providers"] if p["id"] == "groq")
        assert row["enabled"] is True and row["disabled_reason"] == ""

    def test_unknown_provider_is_rejected_with_the_configured_list(
        self, app_client
    ) -> None:
        """Silently storing a typo'd id would leave a switch nothing can turn back on."""
        r = app_client.put("/api/brain/providers/nope/enabled",
                           json={"enabled": False})
        assert r.status_code == 404
        assert "groq" in r.json()["detail"]
        assert "nope" not in bf.disabled_providers(force=True)

    def test_requires_authentication(self, unauth_client) -> None:
        r = unauth_client.put("/api/brain/providers/groq/enabled",
                              json={"enabled": False})
        assert r.status_code == 401
        assert "groq" not in bf.disabled_providers(force=True)


class TestDisabledReasonIsReadableNextToTheSwitch:
    """The operator has to know WHY before deciding to switch it back on.

    The raw stored string is kept for fidelity, but the endpoint also returns the
    status code and a plain-language summary + remedy, so the UI can render them
    beside the toggle without parsing prose.
    """

    def test_auto_disable_exposes_code_summary_and_remedy(self, app_client) -> None:
        bf.auto_disable_provider("groq", "401 invalid or expired API key")

        row = next(p for p in _get(app_client)["providers"] if p["id"] == "groq")
        assert row["disabled_code"] == "401"
        assert row["disabled_summary"] == "Invalid or expired API key"
        assert "Update the key" in row["disabled_action"]
        assert row["auto_disabled"] is True
        assert row["disabled_reason"] == "auto: 401 invalid or expired API key", (
            "the raw reason must survive alongside the rendered one"
        )

    def test_out_of_credit_reports_its_own_code(self, app_client) -> None:
        bf.auto_disable_provider("cerebras", "402 out of credit")

        row = next(p for p in _get(app_client)["providers"] if p["id"] == "cerebras")
        assert row["disabled_code"] == "402"
        assert row["disabled_summary"] == "No credit left on the account"

    def test_manual_switch_off_is_not_reported_as_automatic(self, app_client) -> None:
        app_client.put("/api/brain/providers/groq/enabled", json={"enabled": False})

        row = next(p for p in _get(app_client)["providers"] if p["id"] == "groq")
        assert row["auto_disabled"] is False
        assert row["disabled_summary"] == "Turned off manually"

    def test_an_online_provider_reports_no_reason(self, app_client) -> None:
        row = next(p for p in _get(app_client)["providers"] if p["id"] == "groq")
        assert row["disabled_code"] == ""
        assert row["disabled_summary"] == ""
        assert row["disabled_action"] == ""
