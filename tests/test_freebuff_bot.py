"""Tests for the always-on FreeBuff Telegram bot: embedded vs HTTP dispatch."""

from __future__ import annotations

import pytest

import telegram_bot as tb


@pytest.fixture(autouse=True)
def _restore_env():
    """Snapshot/restore os.environ — the launcher writes env vars directly."""
    import os
    snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snapshot)


def test_embedded_flag(monkeypatch):
    monkeypatch.setenv("FREEBUFF_EMBEDDED", "true")
    assert tb._embedded() is True
    monkeypatch.setenv("FREEBUFF_EMBEDDED", "false")
    assert tb._embedded() is False
    monkeypatch.delenv("FREEBUFF_EMBEDDED", raising=False)
    assert tb._embedded() is False


def test_max_steps_clamped(monkeypatch):
    monkeypatch.setenv("FREEBUFF_MAX_STEPS", "99")
    assert tb._freebuff_max_steps() == 20
    monkeypatch.setenv("FREEBUFF_MAX_STEPS", "0")
    assert tb._freebuff_max_steps() == 1
    monkeypatch.setenv("FREEBUFF_MAX_STEPS", "nan")
    assert tb._freebuff_max_steps() == 10


async def test_fb_models_embedded_uses_agent(monkeypatch):
    from agent.loop import FreeBuffAgent

    monkeypatch.setenv("FREEBUFF_EMBEDDED", "true")
    models = await tb._fb_models()
    assert models == FreeBuffAgent.available_models()


async def test_fb_models_http_uses_proxy(monkeypatch):
    monkeypatch.delenv("FREEBUFF_EMBEDDED", raising=False)

    async def fake_get(path, use_admin=True):
        assert path == "/freebuff/models"
        return {"models": ["x/y"]}

    monkeypatch.setattr(tb, "_proxy_get", fake_get)
    assert await tb._fb_models() == ["x/y"]


async def test_fb_plan_embedded_calls_agent_plan(monkeypatch):
    from agent.models import AgentPlan

    monkeypatch.setenv("FREEBUFF_EMBEDDED", "true")

    async def fake_plan(self, **kwargs):
        return AgentPlan(goal="do it", steps=[])

    monkeypatch.setattr("agent.loop.FreeBuffAgent.plan", fake_plan)
    out = await tb._fb_plan("task", "meta/llama-3.1-8b-instruct")
    assert out["plan"]["goal"] == "do it"
    # model is coerced to a real free model
    from agent.loop import FreeBuffAgent
    assert FreeBuffAgent.is_free_model(out["model"])


async def test_fb_run_embedded_dispatches_to_embedded_run(monkeypatch):
    monkeypatch.setenv("FREEBUFF_EMBEDDED", "true")
    seen = {}

    async def fake_embedded_run(task, model):
        seen["task"] = task
        seen["model"] = model
        return {"result": {"summary": "done"}}

    monkeypatch.setattr(tb, "_embedded_run", fake_embedded_run)
    out = await tb._fb_run("fix bug", "x/y")
    assert seen == {"task": "fix bug", "model": "x/y"}
    assert out["result"]["summary"] == "done"


async def test_fb_run_http_calls_proxy_with_commit_and_pr(monkeypatch):
    monkeypatch.delenv("FREEBUFF_EMBEDDED", raising=False)
    captured = {}

    async def fake_post(path, body, use_admin=True):
        captured["path"] = path
        captured["body"] = body
        return {"result": {"summary": "ok"}}

    monkeypatch.setattr(tb, "_proxy_post", fake_post)
    await tb._fb_run("task", "x/y")
    assert captured["path"] == "/freebuff/run"
    assert captured["body"]["auto_commit"] is True
    assert captured["body"]["open_pr"] is True


async def test_embedded_run_bypasses_orchestrator(monkeypatch):
    """In orchestrator mode the embedded run must set the bypass so the agent runs."""
    monkeypatch.setenv("FREEBUFF_REPO_URL", "")  # skip clone path
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_PAT", raising=False)

    import services.workflow_orchestrator as wo
    monkeypatch.setattr(wo, "WORKFLOW_MODE", "orchestrator")

    seen = {}

    async def fake_run(self, **kwargs):
        seen["legacy_inside"] = wo.is_legacy_mode()
        return {"summary": "ok"}

    monkeypatch.setattr("agent.loop.FreeBuffAgent.run", fake_run)
    out = await tb._embedded_run("task", "meta/llama-3.1-8b-instruct")
    assert seen["legacy_inside"] is True          # bypass active during the run
    assert wo._BYPASS.get() is False              # and reset afterwards
    assert out["result"]["summary"] == "ok"


def test_in_web_bot_disabled_without_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    import backend.server as bs
    assert bs._start_in_web_bot_tasks() == []


def test_in_web_bot_respects_run_flag(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("RUN_TELEGRAM_BOT", "false")
    import backend.server as bs
    assert bs._start_in_web_bot_tasks() == []


def test_launcher_sets_embedded_defaults(monkeypatch):
    for k in ("FREEBUFF_EMBEDDED", "AGENCY_WORKFLOW_MODE", "AGENT_AUTO_PR_ENABLED",
              "FREEBUFF_BASE_BRANCH", "FREEBUFF_REPO_URL"):
        monkeypatch.delenv(k, raising=False)
    # Avoid running real git in the launcher's _configure.
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)

    import importlib
    launcher = importlib.import_module("scripts.run_freebuff_bot")
    launcher._configure()

    import os
    assert os.environ["FREEBUFF_EMBEDDED"] == "true"
    assert os.environ["AGENCY_WORKFLOW_MODE"] == "legacy"
    assert os.environ["AGENT_AUTO_PR_ENABLED"] == "true"
    assert os.environ["FREEBUFF_BASE_BRANCH"] == "master"
    assert "github.com" in os.environ["FREEBUFF_REPO_URL"]


def test_launcher_respects_existing_env(monkeypatch):
    monkeypatch.setenv("AGENCY_WORKFLOW_MODE", "orchestrator")
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    import importlib
    launcher = importlib.import_module("scripts.run_freebuff_bot")
    launcher._configure()
    import os
    assert os.environ["AGENCY_WORKFLOW_MODE"] == "orchestrator"  # not overridden
