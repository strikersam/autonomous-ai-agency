"""tests/test_telegram_observe.py

Tests for the read-only "observe from Telegram" commands added to the bot:

  * /autonomy → cmd_autonomy: active brain + loop readiness + dispatch, from
    the un-gated backend endpoint GET /api/autonomy/status.
  * /loops    → cmd_loops: Loop Engineering fleet readiness + costliest loops,
    from GET /api/loops.

Both hit the FastAPI backend (BACKEND_BASE_URL), not the proxy, and need no
auth. Tests stub ``telegram_bot._backend_get`` so there is no HTTP traffic.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.notifications import bot as tb  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def test_cmd_autonomy_formats_brain_and_readiness(monkeypatch):
    async def fake_get(path):
        assert path == "/api/autonomy/status"
        return {
            "brain": {"provider": "cerebras", "model": "qwen-3-coder-480b"},
            "loop_readiness": {"score": 57, "grade": "D", "total_loops": 30, "drift_ok": True},
            "dispatch": {"status": "idle"},
            "missing_secrets": ["GROQ_API_KEY"],
        }

    monkeypatch.setattr(tb, "_backend_get", fake_get)
    out = _run(tb.cmd_autonomy(1))
    assert "cerebras" in out
    assert "qwen-3-coder-480b" in out
    assert "57/100" in out
    assert "grade D" in out
    assert "GROQ_API_KEY" in out


def test_cmd_autonomy_degrades_gracefully(monkeypatch):
    async def boom(path):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(tb, "_backend_get", boom)
    out = _run(tb.cmd_autonomy(1))
    assert "unavailable" in out.lower()
    assert "BACKEND_BASE_URL" in out  # actionable hint


def test_cmd_loops_formats_readiness_and_costliest(monkeypatch):
    async def fake_get(path):
        assert path == "/api/loops"
        return {
            "ok": True,
            "readiness": {
                "score": 57, "grade": "D", "total_loops": 2,
                "self_heal_coverage": 0.5, "by_level": {"L1": 1, "L2": 1, "L3": 0},
                "notes": ["no fully-unattended (L3) loops"],
            },
            "drift": {"ok": True},
            "loops": [
                {"name": "trend-watcher", "cadence": "every 6h", "cost": "high",
                 "self_heal": True, "est_monthly_tokens": 9_000_000},
                {"name": "loop-audit", "cadence": "weekly", "cost": "low",
                 "self_heal": False, "est_monthly_tokens": 1000},
            ],
        }

    monkeypatch.setattr(tb, "_backend_get", fake_get)
    out = _run(tb.cmd_loops(1))
    assert "57/100" in out
    assert "grade D" in out
    assert "trend-watcher" in out          # costliest loop listed first
    assert out.index("trend-watcher") < out.index("loop-audit")
    assert "no fully-unattended" in out    # readiness note surfaced


def test_cmd_loops_reports_registry_error(monkeypatch):
    async def fake_get(path):
        return {"ok": False, "error": "registry.yaml not found"}

    monkeypatch.setattr(tb, "_backend_get", fake_get)
    out = _run(tb.cmd_loops(1))
    assert "registry.yaml not found" in out
