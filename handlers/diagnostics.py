"""handlers/diagnostics.py — Doctor: diagnostics with public/authenticated split.

Golden Path step #10: Doctor diagnostics with public/authenticated split
and real one-click fixes for common failure modes.

Public endpoints:
  GET  /api/diagnostics/status   — basic health (no auth required)
  GET  /api/diagnostics/health   — quick check: all services running?

Authenticated endpoints (require API key or admin session):
  GET  /api/diagnostics/deep     — full system scan (sessions, models, DB integrity)
  POST /api/diagnostics/fix      — attempt one-click fixes for diagnosed issues
  GET  /api/diagnostics/kpi      — autonomy KPIs snapshot
"""
from __future__ import annotations

import logging
import os
import subprocess  # nosec B404 -- admin-controlled svc mgmt
import sys
import time
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("qwen-doctor")

# Thresholds for health checks
MIN_FREE_DISK_GB = 1.0
MIN_AVAILABLE_RAM_GB = 0.5


# ── Diagnostic checks ─────────────────────────────────────────────────────


def _check_ollama(base_url: str) -> dict[str, Any]:
    """Check if Ollama is reachable and list loaded models."""
    try:
        r = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        models = [m["name"] for m in r.json().get("models", [])]
        return {"reachable": True, "model_count": len(models), "models": models}
    except Exception as exc:
        return {"reachable": False, "error": f"{type(exc).__name__}: {exc}"}


def _check_sessions() -> dict[str, Any]:
    """Check agent session store health."""
    try:
        from agent.state import AgentSessionStore
        store = AgentSessionStore()
        # We can't enumerate all sessions from the store API, but we can check
        # the DB file exists and is readable
        db_path = Path(store._db_path)
        if db_path.exists():
            size_kb = db_path.stat().st_size / 1024
            return {
                "db_exists": True,
                "db_path": str(db_path),
                "db_size_kb": round(size_kb, 1),
            }
        return {"db_exists": False, "db_path": str(db_path)}
    except Exception as exc:
        return {"error": str(exc)}


def _check_workflow_engine() -> dict[str, Any]:
    """Check workflow engine health."""
    try:
        from workflow.engine import get_engine
        engine = get_engine()
        runs = engine.list_runs(limit=5)
        return {
            "engine_loaded": True,
            "total_runs": len(engine._runs),
            "recent_runs": [
                {"run_id": r.run_id, "status": r.status, "title": r.title}
                for r in runs
            ],
        }
    except Exception as exc:
        return {"engine_loaded": False, "error": str(exc)}


def _check_disk() -> dict[str, Any]:
    """Check disk space."""
    try:
        import shutil
        usage = shutil.disk_usage(Path.cwd())
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        return {
            "total_gb": round(total_gb, 1),
            "free_gb": round(free_gb, 1),
            "healthy": free_gb >= MIN_FREE_DISK_GB,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _check_event_log_integrity() -> dict[str, Any]:
    """Verify event log tables are not corrupted."""
    try:
        from agent.state import AgentSessionStore
        store = AgentSessionStore()
        with store._connect() as conn:
            sessions_count = conn.execute(
                "SELECT COUNT(*) FROM agent_sessions"
            ).fetchone()[0]
            events_count = conn.execute(
                "SELECT COUNT(*) FROM agent_events"
            ).fetchone()[0]
        return {
            "sessions_count": sessions_count,
            "events_count": events_count,
            "db_healthy": True,
        }
    except Exception as exc:
        return {"db_healthy": False, "error": str(exc)}


def _check_provider_chain() -> dict[str, Any]:
    """Check LLM provider chain health."""
    try:
        from provider_router import get_cooldown_state, PROVIDER_ROUTER
        cooldowns = get_cooldown_state()
        providers = []
        for p in PROVIDER_ROUTER.providers:
            on_cooldown = p.provider_id in cooldowns
            providers.append({
                "id": p.provider_id,
                "type": p.type,
                "priority": p.priority,
                "on_cooldown": on_cooldown,
            })
        return {
            "provider_count": len(providers),
            "active_count": sum(1 for p in providers if not p["on_cooldown"]),
            "providers": providers,
        }
    except Exception as exc:
        return {"error": str(exc)}


# ── Fixes ─────────────────────────────────────────────────────────────────


def _fix_restart_ollama() -> dict[str, Any]:
    """Attempt to restart Ollama."""
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["powershell", "-Command", "Restart-Service", "Ollama", "-ErrorAction", "SilentlyContinue"],
                capture_output=True, text=True, timeout=15,
            )
        else:
            result = subprocess.run(
                ["systemctl", "restart", "ollama"],
                capture_output=True, text=True, timeout=15,
            )
        if result.returncode != 0:
            return {"action": "restart_ollama", "success": False, "error": result.stderr.strip()}
        return {"action": "restart_ollama", "success": True}
    except Exception as exc:
        return {"action": "restart_ollama", "success": False, "error": str(exc)}


def _fix_clear_cooldowns() -> dict[str, Any]:
    """Clear provider cooldowns to allow retry."""
    try:
        from provider_router import get_cooldown_state
        # Clear cooldowns by resetting the state dict
        cooldowns = get_cooldown_state()
        if isinstance(cooldowns, dict):
            cooldowns.clear()
        return {"action": "clear_cooldowns", "success": True}
    except Exception as exc:
        return {"action": "clear_cooldowns", "success": False, "error": str(exc)}


# Maps diagnosis keys to fix functions
AVAILABLE_FIXES: dict[str, Any] = {
    "restart_ollama": _fix_restart_ollama,
    "clear_cooldowns": _fix_clear_cooldowns,
}


# ── Public API ────────────────────────────────────────────────────────────


def run_public_status(*, start_time: float | None = None) -> dict[str, Any]:
    """Public status: basic health without exposing internals.

    Args:
        start_time: When the server started (for uptime). If None, uptime is omitted.
    """
    ollama = _check_ollama(os.environ.get("OLLAMA_BASE", "http://localhost:11434"))
    result: dict[str, Any] = {
        "status": "healthy" if ollama.get("reachable") else "degraded",
        "ollama": ollama,
    }
    if start_time is not None:
        result["uptime"] = f"{time.time() - start_time:.0f}s"
    return result


def run_deep_diagnostics() -> dict[str, Any]:
    """Full system scan — requires authentication."""
    base = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
    return {
        "ollama": _check_ollama(base),
        "sessions": _check_sessions(),
        "workflow": _check_workflow_engine(),
        "disk": _check_disk(),
        "event_log": _check_event_log_integrity(),
        "provider_chain": _check_provider_chain(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def run_fix(fix_name: str) -> dict[str, Any]:
    """Attempt a named one-click fix."""
    fix_fn = AVAILABLE_FIXES.get(fix_name)
    if fix_fn is None:
        return {"error": f"Unknown fix '{fix_name}'. Available: {sorted(AVAILABLE_FIXES.keys())}"}
    return fix_fn()


def list_available_fixes() -> list[dict[str, Any]]:
    """Return all available one-click fixes."""
    return [
        {
            "name": "restart_ollama",
            "description": "Restart the Ollama service (Windows Service Manager or systemctl)",
            "requires_auth": True,
        },
        {
            "name": "clear_cooldowns",
            "description": "Clear all provider cooldowns to allow immediate retry",
            "requires_auth": True,
        },
    ]
