"""services/hermes_server.py — the agency's OWN Hermes runtime server.

This is *our* Hermes server, not an external NousResearch deployment. It speaks
the exact HTTP API that ``runtimes/adapters/hermes.py`` already calls
(``GET /health`` + ``POST /tasks``) and executes every task through our own
``InternalAgentAdapter`` — i.e. on the agency's configured brain (Cerebras /
Groq / NIM / Ollama). So "turning Hermes on" needs no third-party service: run
this app (locally, in docker-compose, or as a sidecar), point ``HERMES_BASE_URL``
at it, and the Hermes runtime lights up.

Run it:
    uvicorn services.hermes_server:app --host 0.0.0.0 --port 8100

Then set ``HERMES_BASE_URL=http://<host>:8100`` on the backend and the Doctor /
Runtimes page will report Hermes as available.

Design notes
------------
* Synchronous execution: ``/tasks`` runs the task to completion and returns the
  result inline (``status="done"``). The adapter also supports an async
  ``queued``/``running`` + poll flow, but we keep it simple and synchronous —
  the adapter handles either shape.
* The response keys (``success`` / ``output`` / ``artifacts`` / ``status``) are
  exactly the ones ``HermesAdapter.execute`` reads back, so no translation layer
  is needed on the client side.
* Never logs secrets. The optional bearer check uses ``HERMES_API_KEY`` only to
  gate access when the operator sets one.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

log = logging.getLogger("hermes-server")

app = FastAPI(title="Agency Hermes", version="1.0.0")


class TaskIn(BaseModel):
    """Body for POST /tasks — mirrors the payload HermesAdapter.execute sends."""

    task_id: str | None = None
    instruction: str
    task_type: str = "code_review"
    timeout_sec: int = 600
    context: dict[str, Any] | None = None
    workspace_path: str | None = None
    model: str | None = None
    tool_allowlist: list[str] | None = None
    # The adapter may also send a kimi_bridge config for browser tasks; accept
    # and ignore it here (InternalAgentAdapter resolves its own provider).
    kimi_bridge: dict[str, Any] | None = None


def _check_auth(authorization: str | None) -> None:
    """Optional bearer gate. Only enforced when HERMES_API_KEY is configured."""
    expected = (os.environ.get("HERMES_API_KEY") or "").strip()
    if not expected:
        return  # open by default (local/sidecar use)
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid Hermes API key")


@app.get("/health")
async def health() -> dict[str, Any]:
    """Liveness probe the HermesAdapter.health_check() calls.

    Returns 200 + JSON. ``version`` is surfaced by the adapter into RuntimeHealth.
    """
    return {
        "status": "ok",
        "runtime": "hermes",
        "ours": True,          # this is the agency's own Hermes, not NousResearch
        "version": app.version,
    }


def _resolve_model_preference(requested: str | None) -> str | None:
    """Pick the model for a Hermes run: the caller's choice, else the coder.

    This is what makes routing a task to Hermes different from internal_agent.
    Hermes executes *through* ``InternalAgentAdapter``, so on the same model it
    is byte-for-byte what the fallback would have done plus an HTTP hop, and
    ``RUNTIME_CODE_GENERATION=hermes`` would buy nothing. Preferring the
    coding specialist is the difference.

    ``resolve_coding_model_preference`` is reused rather than reimplemented (one
    source of truth), and returns ``None`` unless the coding brain is enabled and
    the active provider can serve it — so a deployment that has not opted in is
    unchanged. A resolver failure is never fatal: a model preference is an
    optimisation, not a precondition for running the task.
    """
    if requested:
        return requested
    try:
        from packages.ai.brain_config import resolve_coding_model_preference
        return resolve_coding_model_preference()
    except Exception as exc:  # noqa: BLE001 — never fail a task over a preference
        log.debug("hermes_server: coding-model preference unavailable: %s", exc)
        return None


@app.post("/tasks")
async def run_task(
    body: TaskIn,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Execute a task synchronously via the InternalAgentAdapter (our brain).

    Response keys match what ``HermesAdapter.execute`` reads back.
    """
    _check_auth(authorization)

    # Local imports: the adapter/agent stack is heavy, so resolve per-request.
    from runtimes.adapters.internal_agent import InternalAgentAdapter
    from runtimes.base import TaskSpec

    task_id = body.task_id or str(uuid.uuid4())
    spec = TaskSpec(
        task_id=task_id,
        instruction=body.instruction,
        task_type=body.task_type or "code_review",
        workspace_path=body.workspace_path,
        model_preference=_resolve_model_preference(body.model),
        timeout_sec=int(body.timeout_sec or 600),
        context=body.context or {},
        tool_allowlist=body.tool_allowlist,
    )

    t0 = time.monotonic()
    # This Hermes server IS a sanctioned autonomous execution endpoint — it exists
    # solely to run the internal agent for the HermesAdapter. It reaches the
    # adapter over an HTTP hop (the adapter POSTs to this in-process server on
    # :8100), and a ContextVar does not cross that boundary: the orchestrator
    # ``_BYPASS`` set by the calling coordinator lives in the caller's context,
    # not in this request handler's. Without re-establishing it here, every task
    # routed through the Hermes runtime hits AgentRunner.run()'s orchestrator-mode
    # block and fails 100% of the time. Set it locally around the execute() call,
    # exactly as the other sanctioned callers (tasks/service.py, ceo_dispatcher,
    # direct_chat) do, and always reset it in ``finally`` so it never leaks.
    from services import workflow_orchestrator as _wo
    _bypass_token = _wo._BYPASS.set(True)
    try:
        result = await InternalAgentAdapter().execute(spec)
    except Exception as exc:  # noqa: BLE001 — surface as a failed task, never 500-crash
        log.exception("hermes_server: task %s failed", task_id)
        return {
            "task_id": task_id,
            "status": "failed",
            "success": False,
            "output": f"Hermes task failed: {exc}",
            "artifacts": [],
            "elapsed_ms": int((time.monotonic() - t0) * 1000),
        }
    finally:
        _wo._BYPASS.reset(_bypass_token)

    return {
        "task_id": task_id,
        "status": "done" if result.success else "failed",
        "success": bool(result.success),
        "output": result.output or "",
        "artifacts": list(getattr(result, "artifacts", []) or []),
        "model_used": getattr(result, "model_used", None),
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
    }
