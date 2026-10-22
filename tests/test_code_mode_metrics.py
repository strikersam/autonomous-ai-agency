"""Code Mode phase 2 (agent/code_mode_metrics.py): arms, counters, summary, endpoint."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from agent import code_mode_metrics as m
from agent import prompts
from agent.loop import AgentRunner
from packages.config import settings
from packages.config.control_registry import get_control


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    m.reset_store()
    # Hermetic: never reach for a DB collection from these tests.
    monkeypatch.setattr(m._persist, "collection", lambda name: None)
    yield
    m.reset_store()


def _prompt_text() -> str:
    return prompts.build_tool_prompt(goal="g", step={"description": "s"}, observations=[], remaining_calls=3)[0]["content"]


# ── arm assignment ─────────────────────────────────────────────────────────


def test_arm_is_stable_and_holdout_share_matches(monkeypatch):
    monkeypatch.setattr(settings, "agent_code_mode_holdout_percent", 10)
    arms = [m.assign_arm(f"s{i}", i % 7) for i in range(4000)]
    assert arms == [m.assign_arm(f"s{i}", i % 7) for i in range(4000)]
    share = arms.count(m.ARM_HOLDOUT) / len(arms)
    assert 0.07 < share < 0.13
    assert set(arms) == {m.ARM_ON, m.ARM_HOLDOUT}


def test_zero_holdout_puts_every_step_on(monkeypatch):
    monkeypatch.setattr(settings, "agent_code_mode_holdout_percent", 0)
    assert {m.assign_arm(f"s{i}", 1) for i in range(500)} == {m.ARM_ON}


def test_switched_off_is_its_own_arm(monkeypatch):
    monkeypatch.setattr(settings, "agent_code_mode_enabled_raw", "false")
    assert m.assign_arm("s", 1) == m.ARM_OFF


def test_holdout_control_is_live_with_default_10():
    control = get_control("AGENT_CODE_MODE_HOLDOUT_PERCENT")
    assert control is not None and control.default == "10" and control.live is True


def test_holdout_step_does_not_see_run_code():
    token = m.begin_step(m.ARM_HOLDOUT)
    try:
        assert "run_code(" not in _prompt_text()
    finally:
        m.end_step(token, "applied")
    token = m.begin_step(m.ARM_ON)
    try:
        assert "- run_code(code)" in _prompt_text()
    finally:
        m.end_step(token, "applied")


# ── counters + samples ─────────────────────────────────────────────────────


def test_end_step_stores_a_numbers_only_sample():
    token = m.begin_step(m.ARM_ON)
    stats = m.current()
    stats.record_selection([{"role": "system", "content": "x" * 400}, {"role": "user", "content": "y" * 100}])
    stats.record_program(True, 3, None)
    stats.record_program(False, 1, "line 1: syntax error on line 1: invalid syntax")
    sample = m.end_step(token, "applied")
    assert m.current() is None
    assert sample["llm_calls"] == 1 and sample["prompt_chars"] == 500
    assert sample["run_code_programs"] == 2 and sample["run_code_ok"] == 1
    assert sample["run_code_inner_calls"] == 4 and sample["run_code_errors"] == {"syntax": 1}
    assert m.get_store().memory() == [sample]
    assert all(isinstance(v, (int, float, str, dict)) for v in sample.values())


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        ("syntax error on line 2: x", "syntax"),
        ("line 1: Import is not supported in run_code", "unsupported"),
        ("line 1: tools.write_file is not callable from run_code; allowed: x", "tool_not_allowed"),
        ("program timed out after 90s", "timeout"),
        ("line 3: program exceeded 50000 steps", "limit"),
        ("line 1: replace() result would exceed 200000 characters", "limit"),
        ("ValueError: boom", "runtime"),
        (None, "runtime"),
    ],
)
def test_classify_error(error, kind):
    assert m.classify_error(error) == kind


# ── summary + verdict ──────────────────────────────────────────────────────


def _rows(arm: str, n: int, calls: int, chars: int, applied: int) -> list[dict[str, Any]]:
    return [
        {"arm": arm, "llm_calls": calls, "prompt_chars": chars, "wall_s": 1.0,
         "status": "applied" if i < applied else "failed", "selection_errors": 0,
         "run_code_programs": 1 if arm == m.ARM_ON else 0, "run_code_ok": 1 if arm == m.ARM_ON else 0,
         "run_code_inner_calls": 3 if arm == m.ARM_ON else 0, "run_code_errors": {}}
        for i in range(n)
    ]


def test_summary_needs_enough_data_before_a_verdict():
    out = m.summary(_rows(m.ARM_ON, 10, 3, 8000, 10) + _rows(m.ARM_HOLDOUT, 10, 8, 30000, 10))
    assert out["enough_data"] is False and "verdict" not in out
    assert out["delta_on_vs_holdout"]["llm_calls_mean"] == -5


def test_verdict_better_when_calls_and_tokens_drop():
    out = m.summary(_rows(m.ARM_ON, 40, 3, 8000, 36) + _rows(m.ARM_HOLDOUT, 40, 8, 30000, 36))
    assert out["enough_data"] and out["verdict"].startswith("better")
    assert out["run_code"]["ok_rate"] == 1.0 and out["run_code"]["inner_calls_per_program"] == 3


def test_verdict_worse_when_success_drops():
    out = m.summary(_rows(m.ARM_ON, 40, 3, 8000, 20) + _rows(m.ARM_HOLDOUT, 40, 8, 30000, 36))
    assert out["verdict"].startswith("worse")


def test_verdict_no_gain_when_calls_do_not_drop():
    out = m.summary(_rows(m.ARM_ON, 40, 8, 31000, 36) + _rows(m.ARM_HOLDOUT, 40, 8, 30000, 36))
    assert out["verdict"].startswith("no gain")


# ── the real executor loop records into the step ───────────────────────────


def test_execute_step_counts_selections_and_run_code(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("def route():\n    return 1\n")
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    calls = iter([
        {"tool": "run_code", "args": {"code": "result = tools.head_file(path='a.py', lines=1)"}},
        {"tool": "finish", "args": {"reason": "done"}},
    ])

    async def fake_chat_json(self_arg: object, model: str, messages: list) -> dict[str, Any]:
        return next(calls)

    monkeypatch.setattr(AgentRunner, "_chat_json", fake_chat_json)
    token = m.begin_step(m.ARM_ON)
    result = asyncio.run(runner._execute_step(
        goal="g", step={"id": 1, "description": "look", "files": [], "type": "analyze"}, requested_model=None,
    ))
    sample = m.end_step(token, result.get("status"))
    code_obs = [o["result"] for o in result["observations"] if o.get("tool") == "run_code"]
    assert code_obs and json.loads(code_obs[0])["ok"] is True
    assert "def route" in json.loads(code_obs[0])["result"]
    assert sample["llm_calls"] == 2 and sample["prompt_chars"] > 0
    assert sample["run_code_programs"] == 1 and sample["run_code_ok"] == 1


# ── endpoint ───────────────────────────────────────────────────────────────


@pytest.fixture
def metrics_client():
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from backend.code_mode_router import build_code_mode_router

    who: dict[str, dict | None] = {"user": {"email": "a@example.com", "role": "user"}}

    async def fake_user():
        if who["user"] is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return who["user"]

    app = FastAPI()
    app.include_router(build_code_mode_router(fake_user))
    with TestClient(app) as client:
        yield client, who


def test_metrics_endpoint_is_admin_only(metrics_client):
    client, who = metrics_client
    assert client.get("/api/admin/agent/code-mode/metrics").status_code == 403
    who["user"] = None
    assert client.get("/api/admin/agent/code-mode/metrics").status_code == 401


def test_metrics_endpoint_reports_the_arms(metrics_client):
    client, who = metrics_client
    who["user"] = {"email": "ops@example.com", "role": "admin"}
    for row in _rows(m.ARM_ON, 2, 3, 800, 2) + _rows(m.ARM_HOLDOUT, 1, 7, 2000, 1):
        m.get_store().add({**row, "ts": 0.0})
    body = client.get("/api/admin/agent/code-mode/metrics").json()
    assert body["enabled"] is True and body["holdout_percent"] == 10
    assert body["arms"]["on"]["steps"] == 2 and body["arms"]["holdout"]["steps"] == 1
    assert body["delta_on_vs_holdout"]["llm_calls_mean"] == -4
    assert body["enough_data"] is False and body["verdict"] is None


def test_metrics_endpoint_is_mounted_and_authenticated_in_the_backend_app():
    from fastapi.testclient import TestClient

    from backend.server import app

    assert TestClient(app).get("/api/admin/agent/code-mode/metrics").status_code == 401
