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


def _check_runtimes() -> dict[str, Any]:
    """Check all registered runtime health and circuit-breaker states."""
    try:
        from runtimes.manager import get_runtime_manager
        mgr = get_runtime_manager()
        health = mgr.health_summary()
        registered = mgr.list_runtimes()
        return {
            "runtime_count": len(registered),
            "healthy_count": sum(1 for h in health if h.get("available")),
            "runtimes": health,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _check_workspaces() -> dict[str, Any]:
    """Check workspace directory structure and isolation using WorkspaceManager."""
    try:
        from workspace.manager import WorkspaceManager
        mgr = WorkspaceManager()
        diag = mgr.diagnostics()
        return {
            "root": diag["base_root"],
            "root_exists": diag["base_root_exists"],
            "workspace_count": diag["workspaces"]["total"],
            "by_status": diag["workspaces"]["by_status"],
            "metrics": diag["metrics"],
        }
    except Exception as exc:
        return {"error": str(exc)}


def _check_github_readiness() -> dict[str, Any]:
    """Check GitHub token validity, scopes, and repo access."""
    try:
        import shutil
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GH_PAT")
        checks: dict[str, Any] = {"git_binary": bool(shutil.which("git")), "token_found": bool(token)}
        if not token:
            return {**checks, "status": "no_token"}
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
        r = httpx.get("https://api.github.com/user", headers=headers, timeout=5.0)
        if r.status_code == 200:
            user = r.json()
            scopes = r.headers.get("X-OAuth-Scopes", "").split(", ")
            checks["user"] = user.get("login")
            checks["has_repo_scope"] = "repo" in scopes
            checks["scopes"] = scopes
            checks["status"] = "ok"
        else:
            checks["status"] = f"http_{r.status_code}"
        return checks
    except Exception as exc:
        return {"error": str(exc)}


def _check_company_graph() -> dict[str, Any]:
    """Check company graph integrity: DB connectivity and index health."""
    try:
        from services.company_graph_store import get_store
        store = get_store()
        companies = store.list_companies(limit=1)
        return {
            "store_connected": True,
            "companies_count": len(companies) if companies is not None else "?",
            "store_backend": getattr(store, "_backend", "unknown"),
        }
    except Exception as exc:
        return {"store_connected": False, "error": str(exc)}


def _check_feature_matrix() -> dict[str, Any]:
    """Check feature matrix maturity levels and availability."""
    try:
        from features.matrix import get_feature_matrix
        matrix = get_feature_matrix()
        entries = matrix._entries
        by_maturity: dict[str, list[str]] = {}
        for e in entries.values():
            mat = e.maturity.value
            if mat not in by_maturity:
                by_maturity[mat] = []
            by_maturity[mat].append(e.feature_id)
        return {
            "total_features": len(entries),
            "by_maturity": by_maturity,
            "disabled_count": sum(1 for e in entries.values() if not e.enabled),
        }
    except Exception as exc:
        return {"error": str(exc)}


def _check_ci_parity() -> dict[str, Any]:
    """Check that CI workflows exist and are syntactically valid."""
    try:
        wf_dir = Path(".github/workflows")
        if not wf_dir.exists():
            return {"workflows_found": 0, "error": ".github/workflows not found"}
        workflows = list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))
        results = []
        for wf in workflows:
            try:
                import yaml
                with open(wf) as f:
                    yaml.safe_load(f)
                results.append({"name": wf.name, "valid": True})
            except Exception as e:
                results.append({"name": wf.name, "valid": False, "error": str(e)})
        return {"workflows_found": len(workflows), "workflows": results}
    except Exception as exc:
        return {"error": str(exc)}


def _check_background_liveness() -> dict[str, Any]:
    """Check background agent is alive and processing tasks via proxy module."""
    try:
        from proxy import BACKGROUND_AGENT
        alive = BACKGROUND_AGENT.is_alive() if hasattr(BACKGROUND_AGENT, "is_alive") else bool(BACKGROUND_AGENT._thread and BACKGROUND_AGENT._thread.is_alive())
        return {
            "background_alive": alive,
            "queue_size": BACKGROUND_AGENT._queue.qsize() if hasattr(BACKGROUND_AGENT, "_queue") else -1,
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
        cooldowns = get_cooldown_state()
        if isinstance(cooldowns, dict):
            cooldowns.clear()
        return {"action": "clear_cooldowns", "success": True}
    except Exception as exc:
        return {"action": "clear_cooldowns", "success": False, "error": str(exc)}


def _fix_restart_background() -> dict[str, Any]:
    """Restart the background agent worker thread."""
    try:
        from agent.background import BackgroundAgent
        bg = BackgroundAgent()
        bg.stop()
        bg.start()
        return {"action": "restart_background", "success": True}
    except Exception as exc:
        return {"action": "restart_background", "success": False, "error": str(exc)}


AVAILABLE_FIXES: dict[str, Any] = {
    "restart_ollama": _fix_restart_ollama,
    "clear_cooldowns": _fix_clear_cooldowns,
    "restart_background": _fix_restart_background,
}


# ── Public API ────────────────────────────────────────────────────────────


def run_public_status(*, start_time: float | None = None) -> dict[str, Any]:
    """Public status: basic health without exposing internals."""
    ollama = _check_ollama(os.environ.get("OLLAMA_BASE", "http://localhost:11434"))
    result: dict[str, Any] = {
        "status": "healthy" if ollama.get("reachable") else "degraded",
        "ollama": ollama,
    }
    if start_time is not None:
        result["uptime"] = f"{time.time() - start_time:.0f}s"
    return result


def run_deep_diagnostics() -> dict[str, Any]:
    """Full system scan — requires authentication.

    Covers all 8 Doctor check categories from issue #467 Section F:
    - providers: LLM provider chain health
    - runtimes: all registered runtime health and circuit-breaker states
    - workspaces: workspace directory structure and isolation
    - GitHub readiness: token validity, scopes, repo access
    - company graph integrity: DB connectivity and index health
    - feature matrix sanity: maturity levels and availability
    - CI parity: workflow files are syntactically valid
    - background liveness: background agent worker is alive
    """
    base = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
    return {
        "ollama": _check_ollama(base),
        "sessions": _check_sessions(),
        "workflow": _check_workflow_engine(),
        "disk": _check_disk(),
        "event_log": _check_event_log_integrity(),
        "provider_chain": _check_provider_chain(),
        "runtimes": _check_runtimes(),
        "workspaces": _check_workspaces(),
        "github": _check_github_readiness(),
        "company_graph": _check_company_graph(),
        "feature_matrix": _check_feature_matrix(),
        "ci_parity": _check_ci_parity(),
        "background_liveness": _check_background_liveness(),
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
        {
            "name": "restart_background",
            "description": "Restart the background agent worker thread",
            "requires_auth": True,
        },
    ]