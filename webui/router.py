from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from webui.providers import ProviderCreate, ProviderManager, ProviderUpdate
from webui.workspaces import WorkspaceCreate, WorkspaceManager, WorkspaceUpdate
from webui.commands import run_command

log = logging.getLogger("qwen-proxy")


def _provider_kind(base_url: str, kind: str) -> str:
    normalized = (kind or "openai_compat").strip().lower()
    if normalized == "openai_compat" and (urlsplit(base_url).hostname or "").lower().endswith("anthropic.com"):
        return "anthropic"
    return normalized


def _provider_headers(base_url: str, api_key: str | None, kind: str) -> dict[str, str]:
    effective_kind = _provider_kind(base_url, kind)
    headers: dict[str, str] = {}
    if effective_kind == "anthropic":
        headers["anthropic-version"] = "2023-06-01"
        if api_key:
            headers["x-api-key"] = api_key
        return headers
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _anthropic_chat_payload(model: str, messages: list[dict[str, Any]], temperature: float) -> dict[str, Any]:
    system_parts: list[str] = []
    anthropic_messages: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        content = message.get("content")
        if not isinstance(content, str):
            continue
        if role == "system":
            system_parts.append(content)
        elif role in {"user", "assistant"}:
            anthropic_messages.append({"role": role, "content": content})
    return {
        "model": model,
        "messages": anthropic_messages or [{"role": "user", "content": ""}],
        "system": "\n\n".join(system_parts) if system_parts else None,
        "max_tokens": 1024,
        "temperature": temperature,
    }


def _anthropic_text(data: dict[str, Any]) -> str:
    return "".join(
        block.get("text", "")
        for block in data.get("content", [])
        if isinstance(block, dict)
    )

def _same_origin(url_a: str, url_b: str) -> bool:
    """Return True when two URLs share the same scheme, host, and port."""
    def _origin(u: str) -> tuple[str, str, int]:
        p = urlsplit(u)
        scheme = p.scheme.lower()
        port = p.port or (443 if scheme == "https" else 80)
        return scheme, (p.hostname or "").lower(), port
    try:
        return _origin(url_a) == _origin(url_b)
    except Exception:
        return False


def _admin_out(admin: Any) -> dict[str, Any]:
    return {
        "username": getattr(admin, "username", "admin"),
        "auth_source": getattr(admin, "auth_source", "unknown"),
    }


class UiChatRequest(BaseModel):
    provider_id: str = Field(default="prov_local", max_length=64)
    model: str | None = Field(default=None, max_length=200)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    messages: list[dict[str, Any]] = Field(default_factory=list)


class UiSearchBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=400)
    limit: int = Field(default=20, ge=1, le=200)


class UiRoutePreviewBody(BaseModel):
    """Body for POST /ui/api/route — preview which model auto-routing would pick."""
    text: str = Field(..., min_length=1, max_length=8000)


class AdminCommandBody(BaseModel):
    workspace_id: str = Field(default="ws_current", max_length=64)
    command: list[str] = Field(..., min_length=1, max_length=32)
    timeout_sec: int = Field(default=60, ge=1, le=600)


class ProviderReorderBody(BaseModel):
    """Drag-and-drop reorder payload — list of provider_ids in the desired top-to-bottom order."""

    provider_ids: list[str] = Field(..., min_length=1, max_length=200)


class BrainPolicyUpdate(BaseModel):
    """Toggle brain provider preference — nvidia (cloud NIM), ollama (local), or colibri (local GLM-5.2)."""

    brain_preference: str = Field(default="nvidia", pattern="^(nvidia|ollama|colibri|auto)$")


def register_webui(
    app: FastAPI,
    *,
    providers: ProviderManager,
    workspaces: WorkspaceManager,
    admin_enabled: bool,
    verify_user: Any,
    get_admin_identity: Any,
) -> None:
    app.state.webui_providers = providers
    app.state.webui_workspaces = workspaces
    app.state.webui_admin_enabled = admin_enabled

    dist = Path(__file__).resolve().parent / "frontend" / "dist"
    index_html = dist / "index.html"

    # Static assets (built by Vite).
    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    router = APIRouter(prefix="/ui/api", tags=["webui"])
    admin_router = APIRouter(prefix="/admin/api", tags=["admin-webui"])

    @router.get("/bootstrap")
    async def bootstrap():
        return {
            "ok": True,
            "admin_enabled": admin_enabled,
            "has_ui_build": index_html.is_file(),
        }

    @router.get("/providers")
    async def list_providers(request: Request, _: Any = Depends(verify_user)):
        mgr: ProviderManager = request.app.state.webui_providers
        return {"providers": [p.model_dump() for p in mgr.list_public()]}

    @router.get("/providers/{provider_id}/models")
    async def provider_models(request: Request, provider_id: str, _: Any = Depends(verify_user)):
        mgr: ProviderManager = request.app.state.webui_providers
        secret = mgr.get_secret(provider_id)
        if not secret:
            raise HTTPException(status_code=404, detail="Unknown provider")
        headers = _provider_headers(secret.base_url, secret.api_key, secret.kind)
        effective_kind = _provider_kind(secret.base_url, secret.kind)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0)) as client:
                resp = await client.get(f"{secret.base_url}/v1/models", headers=headers)
                if resp.status_code == 404 and effective_kind != "anthropic":
                    # Ollama exposes model listing via /api/tags (older or non-OpenAI endpoints).
                    resp = await client.get(f"{secret.base_url}/api/tags", headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail=f"Provider unreachable: {exc}") from exc
        data = resp.json()

        # OpenAI: {"data": [{"id": "..."}]}
        if isinstance(data, dict) and "data" in data:
            models = [m.get("id") for m in (data.get("data") or []) if isinstance(m, dict)]
            return {"provider_id": provider_id, "models": [m for m in models if isinstance(m, str)]}

        # Ollama: {"models": [{"name": "..."}]}
        models = [m.get("name") for m in (data.get("models") or []) if isinstance(m, dict)]
        return {"provider_id": provider_id, "models": [m for m in models if isinstance(m, str)]}

    @router.post("/chat")
    async def ui_chat(request: Request, body: UiChatRequest, auth: Any = Depends(verify_user)):
        mgr: ProviderManager = request.app.state.webui_providers
        secret = mgr.get_secret(body.provider_id)
        if not secret:
            raise HTTPException(status_code=404, detail="Unknown provider")
        effective_kind = _provider_kind(secret.base_url, secret.kind)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        headers.update(_provider_headers(secret.base_url, secret.api_key, secret.kind))
        if not secret.api_key and effective_kind != "anthropic" and _same_origin(secret.base_url, str(request.base_url)):
            user_key = getattr(auth, "key", None)
            if user_key:
                headers["Authorization"] = f"Bearer {user_key}"
        model = body.model or secret.default_model
        if not model:
            raise HTTPException(status_code=400, detail="Missing model (set provider default or pass model)")
        temperature = body.temperature if body.temperature is not None else secret.default_temperature
        payload = (
            _anthropic_chat_payload(model, body.messages, temperature)
            if effective_kind == "anthropic"
            else {
                "model": model,
                "messages": body.messages,
                "temperature": temperature,
                "stream": False,
            }
        )
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
                target_url = (
                    f"{secret.base_url}/v1/messages"
                    if effective_kind == "anthropic"
                    else f"{secret.base_url}/v1/chat/completions"
                )
                resp = await client.post(target_url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail=f"Provider unreachable: {exc}") from exc
        if resp.status_code >= 400:
            # Surface upstream body instead of the generic raise_for_status message.
            detail = resp.text[:2000] or f"Upstream returned {resp.status_code}"
            raise HTTPException(status_code=resp.status_code, detail=detail)
        try:
            data = resp.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=f"Non-JSON upstream response: {exc}") from exc

        if effective_kind == "anthropic":
            content = _anthropic_text(data)
        else:
            choices = data.get("choices") if isinstance(data, dict) else None
            if not isinstance(choices, list) or not choices:
                raise HTTPException(status_code=502, detail="Upstream response missing choices")
            first = choices[0] if isinstance(choices[0], dict) else {}
            msg = first.get("message") if isinstance(first.get("message"), dict) else {}
            content = msg.get("content", "") if isinstance(msg, dict) else ""
            if not isinstance(content, str):
                content = str(content or "")
        return {"model": model, "content": content}

    @router.post("/route")
    async def preview_route(request: Request, body: UiRoutePreviewBody, _: Any = Depends(verify_user)):
        """Return which model the auto-router would pick for *text* (dry-run, no LLM call)."""
        try:
            from router.model_router import get_router
            messages = [{"role": "user", "content": body.text}]
            decision = get_router().route(messages=messages, stream=False)
            return {
                "resolved_model":   decision.resolved_model,
                "task_category":    decision.task_category,
                "selection_source": decision.selection_source,
                "routing_reason":   decision.routing_reason,
            }
        except Exception as exc:
            log.warning("route preview failed: %s", exc)
            raise HTTPException(status_code=503, detail="Internal server error") from exc

    @router.get("/workspaces")
    async def list_workspaces(request: Request, _: Any = Depends(verify_user)):
        mgr: WorkspaceManager = request.app.state.webui_workspaces
        return {"workspaces": [w.model_dump() for w in mgr.list()]}

    @router.get("/workspaces/{workspace_id}/files")
    async def list_files(
        request: Request,
        workspace_id: str,
        path: str = ".",
        limit: int = 200,
        _: Any = Depends(verify_user),
    ):
        mgr: WorkspaceManager = request.app.state.webui_workspaces
        tools = mgr.tools_for(workspace_id)
        return {"workspace_id": workspace_id, "files": tools.list_files(path, limit=limit)}

    @router.get("/workspaces/{workspace_id}/file")
    async def read_file(request: Request, workspace_id: str, path: str, _: Any = Depends(verify_user)):
        mgr: WorkspaceManager = request.app.state.webui_workspaces
        tools = mgr.tools_for(workspace_id)
        return {"workspace_id": workspace_id, "path": path, "content": tools.read_file(path, max_chars=200000)}

    @router.post("/workspaces/{workspace_id}/search")
    async def search(request: Request, workspace_id: str, body: UiSearchBody, _: Any = Depends(verify_user)):
        mgr: WorkspaceManager = request.app.state.webui_workspaces
        tools = mgr.tools_for(workspace_id)
        return {
            "workspace_id": workspace_id,
            "query": body.query,
            "matches": tools.search_code(body.query, limit=body.limit),
        }

    # --- Admin: providers/workspaces CRUD ---

    @admin_router.get("/providers")
    async def admin_list_providers(request: Request, admin: Any = Depends(get_admin_identity)):
        mgr: ProviderManager = request.app.state.webui_providers
        return {"providers": [p.model_dump() for p in mgr.list_admin()], "admin": _admin_out(admin)}

    @admin_router.post("/providers")
    async def admin_create_provider(request: Request, body: ProviderCreate, admin: Any = Depends(get_admin_identity)):
        mgr: ProviderManager = request.app.state.webui_providers
        rec = mgr.create(body)
        return {"provider": rec.model_dump(), "admin": _admin_out(admin)}

    @admin_router.patch("/providers/{provider_id}")
    async def admin_update_provider(
        request: Request,
        provider_id: str,
        body: ProviderUpdate,
        admin: Any = Depends(get_admin_identity),
    ):
        mgr: ProviderManager = request.app.state.webui_providers
        rec = mgr.update(provider_id, body)
        if not rec:
            raise HTTPException(status_code=404, detail="Unknown provider")
        return {"provider": rec.model_dump(), "admin": _admin_out(admin)}

    @admin_router.delete("/providers/{provider_id}")
    async def admin_delete_provider(request: Request, provider_id: str, admin: Any = Depends(get_admin_identity)):
        mgr: ProviderManager = request.app.state.webui_providers
        ok = mgr.delete(provider_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Unknown provider")
        return {"ok": True, "provider_id": provider_id, "admin": _admin_out(admin)}

    @admin_router.get("/bootstrap")
    async def admin_bootstrap(request: Request, admin: Any = Depends(get_admin_identity)):
        """Single-call bootstrap: providers, workspaces, role tags, brain policy.

        Replaces 4 parallel GET requests on admin page load/mutation refresh.
        Cuts 3 network round-trips and avoids redundant admin-auth overhead.
        """
        mgr: ProviderManager = request.app.state.webui_providers
        wsmgr: WorkspaceManager = request.app.state.webui_workspaces
        providers_list = [p.model_dump() for p in mgr.list_admin()]
        workspaces_list = [w.model_dump() for w in wsmgr.list()]

        role_tags: dict = {}
        brain_policy: dict | None = None
        try:
            from packages.ai.brain import get_provider_role_tags as _role_tags, resolve_active_brain, allow_paid_brain, get_brain_preference
            role_tags = await _role_tags()
            brain = await resolve_active_brain()
            brain_policy = {
                "resolution": (
                    {
                        "provider_id": brain.provider_id,
                        "base_url": brain.base_url,
                        "model": brain.model,
                        "role": brain.role,
                        "free_tier": brain.free_tier,
                        "source": brain.source,
                        "priority": brain.priority,
                    }
                    if brain is not None
                    else None
                ),
                "allow_paid_brain": allow_paid_brain(),
                "brain_preference": get_brain_preference(),
                "env_var": "ALLOW_PAID_BRAIN",
                "hint": (
                    "Set ALLOW_PAID_BRAIN=true in the server environment to enable "
                    "paid (Anthropic/Bedrock) providers as the CEO brain."
                ),
            }
        except Exception as exc:
            log.warning("admin_bootstrap: brain_policy unavailable: %s", exc)
        return {
            "providers": providers_list,
            "workspaces": workspaces_list,
            "role_tags": role_tags,
            "brain_policy": brain_policy,
            "admin": _admin_out(admin),
        }

    @admin_router.get("/providers/role-tags")
    async def admin_provider_role_tags(request: Request, admin: Any = Depends(get_admin_identity)):
        """Map provider_id -> {is_brain, role, reason, base_url, name} from the canonical brain resolver.

        Reads from ``brain_policy.get_provider_role_tags`` which queries the
        backend provider store (MongoDB) and the active brain — NOT the webui
        JsonConfigStore. Operators see the same role surface the brain decision
        uses, so the UI cannot disagree with routing. ``base_url`` and ``name``
        are echoed back so the Admin SPA can match role tags to locally-defined
        webui provider records (which use a different provider_id namespace).
        """
        try:
            from packages.ai.brain import get_provider_role_tags as _role_tags
            tags = await _role_tags()
        except Exception as exc:
            log.exception("admin_provider_role_tags: brain_policy call failed: %s", exc)
            raise HTTPException(status_code=503, detail="brain_policy unavailable") from exc
        return {"role_tags": tags, "admin": _admin_out(admin)}

    @admin_router.post("/providers/reorder")
    async def admin_reorder_providers(
        request: Request,
        body: ProviderReorderBody,
        admin: Any = Depends(get_admin_identity),
    ):
        """Set provider priorities by the order of ``provider_ids`` (first = highest).

        Writes the priorities to the webui JsonConfigStore and invalidates the
        brain cache so the next agent run picks up the new order. Returns the
        resulting ordered list so the UI can confirm what was saved.
        """
        mgr: ProviderManager = request.app.state.webui_providers
        ok = mgr.reorder(body.provider_ids)
        providers = sorted(
            [p.model_dump() for p in mgr.list_admin()],
            key=lambda p: p.get("priority", 0),
            reverse=True,
        )
        return {
            "ok": ok,
            "providers": providers,
            "admin": _admin_out(admin),
        }

    @admin_router.get("/policy/brain")
    async def admin_get_brain_policy(request: Request, admin: Any = Depends(get_admin_identity)):
        """Return the currently-resolved brain + the global paid-model policy.

        ``allow_paid_brain`` is a server env var (``ALLOW_PAID_BRAIN``) — read-only
        here so the UI can show the truth. Operators flip it by setting the env
        var on the server (Render / .env) and restarting. The UI is intentionally
        NOT given a write toggle to avoid accidental silent billing on a
        single misclick.

        ``brain_preference`` (``BRAIN_PREFERENCE`` env var) controls whether the
        brain defaults to NVIDIA cloud NIM ("nvidia") or local Ollama ("ollama").
        Toggle via ``PATCH /admin/api/policy/brain`` — no restart required.
        """
        try:
            from packages.ai.brain import allow_paid_brain, get_brain_preference, resolve_active_brain
            brain = await resolve_active_brain()
        except Exception as exc:
            log.exception("admin_get_brain_policy: brain resolution failed: %s", exc)
            raise HTTPException(status_code=503, detail="brain_policy unavailable") from exc
        return {
            "resolution": (
                {
                    "provider_id": brain.provider_id,
                    "base_url": brain.base_url,
                    "model": brain.model,
                    "role": brain.role,
                    "free_tier": brain.free_tier,
                    "source": brain.source,
                    "priority": brain.priority,
                }
                if brain is not None
                else None
            ),
            "allow_paid_brain": allow_paid_brain(),
            "brain_preference": get_brain_preference(),
            "env_var": "ALLOW_PAID_BRAIN",
            "hint": (
                "Set ALLOW_PAID_BRAIN=true in the server environment to enable "
                "paid (Anthropic/Bedrock) providers as the CEO brain. Free-first "
                "is the safe default; changes here WILL incur costs."
            ),
            "admin": _admin_out(admin),
        }

    @admin_router.patch("/policy/brain")
    async def admin_patch_brain_policy(
        request: Request,
        body: BrainPolicyUpdate,
        admin: Any = Depends(get_admin_identity),
    ):
        """Toggle the brain provider preference without restarting the server.

        Sets the in-process ``BRAIN_PREFERENCE`` env var to ``"nvidia"`` or
        ``"ollama"`` and invalidates the brain cache so the next agent run
        picks up the new preference immediately.
        """
        os.environ["BRAIN_PREFERENCE"] = body.brain_preference
        try:
            from packages.ai.brain import invalidate_brain_cache, resolve_active_brain
            invalidate_brain_cache()
            brain = await resolve_active_brain()
        except Exception as exc:
            log.exception("admin_patch_brain_policy: re-resolution failed: %s", exc)
            raise HTTPException(status_code=503, detail="brain_policy unavailable") from exc
        return {
            "brain_preference": body.brain_preference,
            "resolution": {
                "provider_id": brain.provider_id,
                "base_url": brain.base_url,
                "model": brain.model,
                "role": brain.role,
                "free_tier": brain.free_tier,
                "source": brain.source,
                "priority": brain.priority,
            },
            "message": (
                "Brain preference toggled — agents will use "
                + ({"ollama": "local Ollama", "colibri": "local Colibri / GLM-5.2"}.get(body.brain_preference) or "NVIDIA NIM cloud")
                + " on the next run."
            ),
            "admin": _admin_out(admin),
        }

    @admin_router.get("/workspaces")
    async def admin_list_workspaces(request: Request, admin: Any = Depends(get_admin_identity)):
        mgr: WorkspaceManager = request.app.state.webui_workspaces
        return {"workspaces": [w.model_dump() for w in mgr.list()], "admin": _admin_out(admin)}

    # /workspaces/metrics must be registered BEFORE /workspaces/{workspace_id} so FastAPI
    # routes it correctly instead of treating "metrics" as a workspace_id.
    @admin_router.get("/workspaces/metrics")
    async def admin_workspace_metrics(request: Request, admin: Any = Depends(get_admin_identity)):
        """Return aggregate workspace metrics for the admin dashboard."""
        mgr: WorkspaceManager = request.app.state.webui_workspaces
        workspaces = mgr.list()
        return {
            "total": len(workspaces),
            "by_status": {
                "active": sum(1 for w in workspaces if getattr(w, "enabled", True)),
                "disabled": sum(1 for w in workspaces if not getattr(w, "enabled", True)),
            },
            "admin": _admin_out(admin),
        }

    @admin_router.post("/workspaces")
    async def admin_create_workspace(request: Request, body: WorkspaceCreate, admin: Any = Depends(get_admin_identity)):
        mgr: WorkspaceManager = request.app.state.webui_workspaces
        try:
            ws = mgr.create(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Internal server error") from exc
        return {"workspace": ws.model_dump(), "admin": _admin_out(admin)}

    @admin_router.patch("/workspaces/{workspace_id}")
    async def admin_update_workspace(
        request: Request,
        workspace_id: str,
        body: WorkspaceUpdate,
        admin: Any = Depends(get_admin_identity),
    ):
        mgr: WorkspaceManager = request.app.state.webui_workspaces
        ws = mgr.update(workspace_id, body)
        if not ws:
            raise HTTPException(status_code=404, detail="Unknown workspace")
        return {"workspace": ws.model_dump(), "admin": _admin_out(admin)}

    @admin_router.delete("/workspaces/{workspace_id}")
    async def admin_delete_workspace(
        request: Request,
        workspace_id: str,
        admin: Any = Depends(get_admin_identity),
    ):
        mgr: WorkspaceManager = request.app.state.webui_workspaces
        ok = mgr.delete(workspace_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Unknown workspace")
        return {"ok": True, "workspace_id": workspace_id, "admin": _admin_out(admin)}

    @admin_router.post("/workspaces/{workspace_id}/sync")
    async def admin_sync_workspace(request: Request, workspace_id: str, admin: Any = Depends(get_admin_identity)):
        mgr: WorkspaceManager = request.app.state.webui_workspaces
        try:
            result = mgr.sync_git(workspace_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Internal server error") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Internal server error") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail="Internal server error") from exc
        return {"result": result, "admin": _admin_out(admin)}

    @admin_router.post("/commands/run")
    async def admin_run_command(request: Request, body: AdminCommandBody, admin: Any = Depends(get_admin_identity)):
        mgr: WorkspaceManager = request.app.state.webui_workspaces
        ws = mgr.get(body.workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="Unknown workspace")
        try:
            result = run_command(
                command=body.command,
                cwd=Path(ws.path),
                timeout_sec=body.timeout_sec,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Internal server error") from exc
        except subprocess.TimeoutExpired:  # type: ignore[name-defined]
            raise HTTPException(status_code=408, detail="Command timed out")
        return {"result": result, "admin": _admin_out(admin)}

    app.include_router(router)
    app.include_router(admin_router)

    if not index_html.is_file():
        log.warning(
            "Web UI build not found at %s (run `npm ci && npm run build` in webui/frontend/)", dist
        )

    def _serve_index() -> FileResponse:
        if not index_html.is_file():
            raise HTTPException(status_code=503, detail="Web UI not built on server")
        return FileResponse(str(index_html))

    @app.get("/app")
    async def _app_index():
        return _serve_index()

    @app.get("/app/{path:path}")
    async def _app_spa(path: str):
        return _serve_index()

    @app.get("/admin/app")
    async def _admin_app_index():
        return _serve_index()

    @app.get("/admin/app/{path:path}")
    async def _admin_app_spa(path: str):
        return _serve_index()

    @app.get("/")
    async def _root(request: Request):
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return _serve_index()
        return JSONResponse(
            {
                "service": "Qwen3-Coder Authenticated Proxy",
                "ui": "GET / (HTML), /app (HTML), /admin/app (HTML)",
                "endpoints": {
                    "health": "GET  /health          (no auth)",
                    "ollama_api": "ANY  /api/*            (Bearer auth)",
                    "openai_compat": "ANY  /v1/*             (Bearer auth)",
                    "agent_sessions": "POST /agent/sessions   (Bearer auth)",
                    "agent_run": "POST /agent/run        (Bearer auth)",
                    "webui_api": "GET/POST /ui/api/*     (Bearer auth for most routes)",
                },
            }
        )
