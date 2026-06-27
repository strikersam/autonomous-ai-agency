"""server.py — Main backend FastAPI app: auth, dashboard, company graph, doctor, agents."""
from dotenv import load_dotenv

load_dotenv()

import asyncio
import json
import logging
import os
import re
import secrets
import sys
import uuid
from collections import deque
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Optional, Dict, List, Tuple, Union, Literal

import bcrypt
import html
import httpx
import jwt

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from bson import ObjectId
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from llm_providers import (
    LlmProviderConfig,
    chat_completion_text,
    list_openai_models,
    normalize_base_url,
)
# Motor is used via db.MongoStore when STORAGE_BACKEND=mongo (default)
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

# Feature routers — agents, runtimes, tasks
from agents.api import agent_router
from agents.store import AgentStore, set_agent_store
from agent.scheduler import AgentScheduler, get_scheduler, set_scheduler
from agent.skills import SkillLibrary
from agent.job_manager import AgentJobManager, make_isolated_workspace
from agent.contract import AgentJobRequest, AgentJobSnapshot
from agent.state import AgentSessionStore
from provider_router import (
    CommercialFallbackRequiredError,
    ProviderConfig,
    ProviderFallbackError,
    ProviderRouter,
    extract_openai_text,
)
from langfuse_obs import emit_chat_observation
from runtimes.api import runtime_router
from router import get_router as _get_model_router
from runtimes.manager import get_runtime_manager
from schedules import schedules_router
from tasks.api import task_router
from tasks.store import TaskStore, get_task_store, set_task_store
from setup import setup_router
from activation_api import activation_router
from setup.api import get_wizard_state
from secrets_store import secrets_router, get_secrets_store
from version import __version__, APP_NAME, APP_LABEL, APP_TAGLINE
from social_auth import (
    github_exchange_code,
    github_fetch_user,
    google_exchange_code,
    google_fetch_user,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("llm-wiki")


_ERROR_LOG_BUFFER: deque[dict[str, object]] = deque(maxlen=250)

# Always-on in-memory activity feed. Mongo-backed activity_log is the durable
# store, but it is silently skipped when no DB is available (e.g. SQLite / Render
# without Mongo) — which is why the alerts bell always showed zero. log_activity()
# now also writes here so business events surface regardless of the DB backend.
_ACTIVITY_BUFFER: deque[dict[str, object]] = deque(maxlen=250)


class _InMemoryErrorLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.ERROR:
            return
        _ERROR_LOG_BUFFER.appendleft(
            {
                "category": "error",
                "level": record.levelname.lower(),
                "message": record.getMessage(),
                "logger": record.name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )


def _ensure_error_log_capture() -> None:
    root_logger = logging.getLogger()
    if any(getattr(handler, "_relay_error_buffer", False) for handler in root_logger.handlers):
        return
    handler = _InMemoryErrorLogHandler(level=logging.ERROR)
    handler._relay_error_buffer = True  # type: ignore[attr-defined]
    root_logger.addHandler(handler)


def clear_error_log_buffer() -> None:
    _ERROR_LOG_BUFFER.clear()


_ensure_error_log_capture()

def _scheduler_on_fire(job) -> None:
    """Called by APScheduler when a cron fires. Dispatches to the orchestrator."""
    import asyncio
    from services.workflow_orchestrator import get_workflow_orchestrator, ExecutionRequest
    async def _dispatch():
        try:
            orch = get_workflow_orchestrator()
            req = ExecutionRequest(
                request=job.instruction,
                auto_approve=True,
                user_id="scheduler",
            )
            run = await orch.execute(req)
            log.info("Scheduler fired job %s → run %s", job.job_id, run.run_id)
        except Exception as exc:
            log.error("Scheduler on_fire failed for %s: %s", job.job_id, exc)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_dispatch())
        else:
            loop.run_until_complete(_dispatch())
    except Exception as exc:
        log.error("Scheduler on_fire loop error: %s", exc)

SCHEDULER = AgentScheduler(on_fire=_scheduler_on_fire)
set_scheduler(SCHEDULER)

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "llm_wiki_dashboard")
# Shorter timeout prevents 30-second hangs when MongoDB is unavailable (e.g. in CI / tests).
# Override via MONGO_SELECTION_TIMEOUT_MS env var; default is 2 000 ms.
MONGO_SELECTION_TIMEOUT_MS = int(os.environ.get("MONGO_SELECTION_TIMEOUT_MS", "2000"))
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
ADMIN_EMAIL = os.environ.get("V3_ADMIN_EMAIL") or os.environ.get(
    "ADMIN_EMAIL", "admin@llmrelay.local"
)
ADMIN_PASSWORD = os.environ.get("V3_ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise RuntimeError(
        "ADMIN_PASSWORD must be set in the Render environment variables. "
        "Set ADMIN_PASSWORD (or V3_ADMIN_PASSWORD) and restart the server."
    )
OLLAMA_BASE = (
    os.environ.get("OLLAMA_BASE_URL")
    or os.environ.get("OLLAMA_BASE")
    or "http://localhost:11434"
)
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3-coder:30b")
_LIMITED_CHAT_SESSIONS: dict[str, dict[str, object]] = {}
# Aggregate wall-clock budget for an entire chat Agent-Mode run (plan +
# execute + verify). Caps a hung provider so the chat job fails cleanly
# instead of sitting at phase "planning" forever. Configurable via env.
_AGENT_RUN_BUDGET_SEC = float(os.environ.get("CHAT_AGENT_RUN_BUDGET_SEC", "240"))

_CHAT_AGENT_JOBS = AgentJobManager()
_CHAT_AGENT_WORKSPACE_ROOT = Path(
    os.environ.get("BACKEND_CHAT_AGENT_WORKSPACE_ROOT", ".data/backend-chat-agent-workspaces")
)


def _safe_object_id(value: Optional[str]) -> Optional[ObjectId]:
    if not value:
        return None
    try:
        return ObjectId(value)
    except Exception:
        return None


def _get_limited_chat_session(session_id: str, user_id: str) -> Optional[Dict[str, object]]:
    session = _LIMITED_CHAT_SESSIONS.get(session_id)
    if not session or session.get("user_id") != user_id:
        return None
    return deepcopy(session)


def _save_limited_chat_session(session_id: str, session: dict[str, object]) -> None:
    _LIMITED_CHAT_SESSIONS[session_id] = deepcopy(session)


def _delete_limited_chat_session(session_id: str, user_id: str) -> bool:
    session = _LIMITED_CHAT_SESSIONS.get(session_id)
    if not session or session.get("user_id") != user_id:
        return False
    _LIMITED_CHAT_SESSIONS.pop(session_id, None)
    return True


def _list_limited_chat_sessions(user_id: str) -> list[dict[str, object]]:
    sessions = []
    for session_id, session in _LIMITED_CHAT_SESSIONS.items():
        if session.get("user_id") != user_id:
            continue
        item = deepcopy(session)
        item.setdefault("_id", session_id)
        item.pop("messages", None)
        sessions.append(item)
    sessions.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return sessions


def _new_chat_session_record(
    *,
    session_id: str,
    user_id: str,
    title: str,
    provider_id: Optional[str],
    model: Optional[str],
    temperature: Optional[float],
    messages: Optional[List[Dict]] = None,
) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "_id": session_id,
        "user_id": user_id,
        "title": title,
        "provider_id": provider_id,
        "model": model,
        "temperature": temperature,
        "messages": messages or [],
        "created_at": now,
        "updated_at": now,
    }


async def _persist_chat_session(
    *,
    session_id: str,
    user_id: str,
    storage_mode: str,
    db_session_id: Optional[ObjectId],
    title: str,
    provider_id: Optional[str],
    model: Optional[str],
    temperature: Optional[float],
    messages: list[dict],
    created_at: Optional[str],
) -> None:
    updated_at = datetime.now(timezone.utc).isoformat()
    if storage_mode == "db" and db_session_id is not None:
        await get_db().chat_sessions.update_one(
            {"_id": db_session_id, "user_id": user_id},
            {
                "$set": {
                    "title": title,
                    "messages": messages,
                    "provider_id": provider_id,
                    "model": model,
                    "temperature": temperature,
                    "updated_at": updated_at,
                }
            },
        )
        return

    record = {
        "_id": session_id,
        "user_id": user_id,
        "title": title,
        "provider_id": provider_id,
        "model": model,
        "temperature": temperature,
        "messages": messages,
        "created_at": created_at or updated_at,
        "updated_at": updated_at,
    }
    _save_limited_chat_session(session_id, record)


def _default_agent_role_models() -> dict[str, str]:
    nim_enabled = bool(
        (os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey") or "").strip()
    )
    if nim_enabled:
        return {
            "default": os.environ.get("NVIDIA_DEFAULT_MODEL") or "nvidia/llama-3.3-nemotron-super-49b-v1",
            "planner": os.environ.get("AGENT_PLANNER_MODEL") or "qwen/qwen3-coder-480b-a35b-instruct",
            "executor": os.environ.get("AGENT_EXECUTOR_MODEL") or "nvidia/llama-3.3-nemotron-super-49b-v1",
            "verifier": os.environ.get("AGENT_VERIFIER_MODEL") or "nvidia/llama-3.3-nemotron-super-49b-v1",
            "judge": os.environ.get("AGENT_JUDGE_MODEL") or "deepseek-ai/deepseek-v4-pro",
        }
    return {
        "default": os.environ.get("OLLAMA_MODEL") or "qwen3-coder:30b",
        "planner": os.environ.get("AGENT_PLANNER_MODEL") or "deepseek-r1:32b",
        "executor": os.environ.get("AGENT_EXECUTOR_MODEL") or "qwen3-coder:30b",
        "verifier": os.environ.get("AGENT_VERIFIER_MODEL") or "deepseek-r1:32b",
        "judge": os.environ.get("AGENT_JUDGE_MODEL") or os.environ.get("AGENT_VERIFIER_MODEL") or "deepseek-r1:32b",
    }


async def _resolve_user_agent_role_models(user: dict[str, object]) -> dict[str, str]:
    defaults = _default_agent_role_models()
    user_key = str(user.get("email") or user.get("_id") or "anonymous")
    try:
        state = await get_wizard_state(user_key)
    except Exception:
        return defaults

    step2 = state.step2_model or {}
    step4 = state.step4_agent or {}
    return {
        "default": str(
            step2.get("default_model")
            or step2.get("executor_model")
            or step2.get("coder_model")
            or step4.get("agent_model")
            or defaults["default"]
        ),
        "planner": str(step2.get("planner_model") or defaults["planner"]),
        "executor": str(
            step2.get("executor_model")
            or step2.get("coder_model")
            or step4.get("agent_model")
            or defaults["executor"]
        ),
        "verifier": str(
            step2.get("verifier_model")
            or step2.get("reviewer_model")
            or defaults["verifier"]
        ),
        "judge": str(step2.get("judge_model") or defaults["judge"]),
    }


class AgentStatusEntry(BaseModel):
    id: str
    name: str
    role: str
    status: str
    current_task: Optional[str] = None
    last_active: Optional[str] = None
    tools_used: List[str] = Field(default_factory=list)
    messages_sent: Optional[int] = None


class AgentToolCallEntry(BaseModel):
    id: str
    tool_name: str
    agent: str
    status: str
    input: Optional[Dict[str, object]] = None
    output: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None


class AgentStatusResponse(BaseModel):
    session_id: Optional[str] = None
    has_events: bool = False
    agents: list[AgentStatusEntry] = Field(default_factory=list)
    tool_calls: list[AgentToolCallEntry] = Field(default_factory=list)
    latest_summary: Optional[str] = None
    latest_error: Optional[str] = None
    updated_at: Optional[str] = None


def _get_agent_session_for_user(session_id: str, user_id: str):
    session = AGENT_EVENT_STORE.get(session_id)
    if session and session.owner_id and session.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return session


def _ensure_agent_session_exists(*, session_id: str, user_id: str, title: str) -> None:
    session = _get_agent_session_for_user(session_id, user_id)
    if session is None:
        AGENT_EVENT_STORE.create_with_id(
            session_id=session_id,
            title=title or "Agent Session",
            owner_id=user_id,
        )


def _append_agent_session_message(session_id: str, role: str, content: str) -> None:
    try:
        AGENT_EVENT_STORE.append_message(session_id, role, content)
    except Exception:
        log.debug("agent session message append failed", exc_info=True)


def _truncate_agent_text(value: object, limit: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _extract_agent_tool_calls(session_id: str) -> list[AgentToolCallEntry]:
    session = AGENT_EVENT_STORE.get(session_id)
    if session is None:
        return []
    events = AGENT_EVENT_STORE.get_events(session_id, from_position=0, limit=max(session.event_count, 1) + 25)
    calls: dict[str, AgentToolCallEntry] = {}
    started_at_map: dict[str, datetime] = {}

    for event in events:
        payload = event.payload or {}
        if event.event_type == "tool_call":
            call_id = str(payload.get("call_id") or f"{session_id}:{event.position}")
            calls[call_id] = AgentToolCallEntry(
                id=call_id,
                tool_name=str(payload.get("tool_name") or "tool"),
                agent="implementer",
                status="running",
                input=payload.get("args") if isinstance(payload.get("args"), dict) else None,
                started_at=event.timestamp,
            )
            try:
                started_at_map[call_id] = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
            except Exception:
                pass
            continue

        if event.event_type != "tool_result":
            continue

        call_id = str(payload.get("call_id") or f"{session_id}:{event.position}")
        entry = calls.get(call_id)
        if entry is None:
            entry = AgentToolCallEntry(
                id=call_id,
                tool_name=str(payload.get("tool_name") or "tool"),
                agent="implementer",
                status="running",
            )
            calls[call_id] = entry

        outcome = str(payload.get("status") or "success")
        entry.status = "error" if outcome == "error" else "success"
        entry.completed_at = event.timestamp
        output = _truncate_agent_text(payload.get("output") or "")
        if entry.status == "error":
            entry.error = output or "Tool call failed"
        else:
            entry.output = output

        started_at = started_at_map.get(call_id)
        if started_at is not None:
            try:
                ended_at = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
                entry.duration_ms = max(int((ended_at - started_at).total_seconds() * 1000), 0)
            except Exception:
                pass

    return list(calls.values())


def _build_agent_status_snapshot(session_id: str) -> AgentStatusResponse:
    session = AGENT_EVENT_STORE.get(session_id)
    if session is None:
        return AgentStatusResponse(session_id=session_id)

    events = AGENT_EVENT_STORE.get_events(session_id, from_position=0, limit=max(session.event_count, 1) + 25)
    if not events:
        return AgentStatusResponse(
            session_id=session_id,
            has_events=False,
            updated_at=session.updated_at,
        )

    tool_calls = _extract_agent_tool_calls(session_id)
    running_tools = [call for call in tool_calls if call.status == "running"]
    tool_names = list(dict.fromkeys(call.tool_name for call in tool_calls if call.tool_name))[-4:]

    plan_event = next((event for event in events if event.event_type == "step_start" and "goal" in (event.payload or {})), None)
    current_step_event = None
    completed_steps = 0
    latest_summary = None
    latest_error = None
    judge_event = None

    for event in events:
        payload = event.payload or {}
        if event.event_type == "step_start" and payload.get("step_id") is not None:
            current_step_event = event
        elif event.event_type == "step_complete":
            completed_steps += 1
            current_step_event = None
            if str(payload.get("status") or "") == "failed":
                latest_error = _truncate_agent_text(payload.get("reason") or payload.get("issues") or "Step failed")
        elif event.event_type == "assistant_message":
            if payload.get("summary"):
                latest_summary = _truncate_agent_text(payload.get("summary"))
            if payload.get("judge"):
                judge_event = event
                judge_notes = payload.get("judge") or {}
                if isinstance(judge_notes, dict) and judge_notes.get("verdict") == "BLOCKED":
                    latest_error = _truncate_agent_text(judge_notes.get("notes") or "Judge blocked the run")
        elif event.event_type == "tool_result" and payload.get("status") == "error":
            latest_error = _truncate_agent_text(payload.get("output") or "Tool call failed")

    updated_at = events[-1].timestamp
    planner_status = "done" if plan_event else "idle"
    executor_status = "idle"
    if latest_error:
        executor_status = "error"
    elif current_step_event or running_tools:
        executor_status = "running"
    elif completed_steps > 0:
        executor_status = "done"
    elif plan_event:
        executor_status = "waiting"

    coordinator_status = "running"
    if latest_error:
        coordinator_status = "error"
    elif latest_summary:
        coordinator_status = "done"

    judge_status = "waiting" if latest_summary else "idle"
    if judge_event is not None:
        judge_payload = judge_event.payload.get("judge") if isinstance(judge_event.payload, dict) else {}
        judge_status = "error" if isinstance(judge_payload, dict) and judge_payload.get("verdict") == "BLOCKED" else "done"

    agents = [
        AgentStatusEntry(
            id=f"{session_id}:planner",
            name="Planner",
            role="planner",
            status=planner_status,
            current_task=(
                f"Planned {int((plan_event.payload or {}).get('steps') or 0)} steps"
                if plan_event is not None
                else None
            ),
            last_active=plan_event.timestamp if plan_event is not None else updated_at,
            messages_sent=1 if plan_event is not None else 0,
        ),
        AgentStatusEntry(
            id=f"{session_id}:executor",
            name="Executor",
            role="implementer",
            status=executor_status,
            current_task=(
                str((current_step_event.payload or {}).get("description") or "Running tool calls")
                if current_step_event is not None or running_tools
                else (latest_summary or latest_error)
            ),
            last_active=updated_at,
            tools_used=tool_names,
            messages_sent=completed_steps,
        ),
        AgentStatusEntry(
            id=f"{session_id}:coordinator",
            name="Coordinator",
            role="coordinator",
            status=coordinator_status,
            current_task=latest_summary or latest_error or "Coordinating agent run",
            last_active=updated_at,
            tools_used=tool_names,
            messages_sent=sum(1 for event in events if event.event_type == "assistant_message"),
        ),
        AgentStatusEntry(
            id=f"{session_id}:judge",
            name="Judge",
            role="judge",
            status=judge_status,
            current_task=(
                _truncate_agent_text((judge_event.payload.get("judge") or {}).get("notes") or "Reviewing output")
                if judge_event is not None and isinstance(judge_event.payload, dict)
                else ("Waiting for execution to finish" if latest_summary is None else "Reviewing output")
            ),
            last_active=judge_event.timestamp if judge_event is not None else updated_at,
            messages_sent=1 if judge_event is not None else 0,
        ),
    ]

    return AgentStatusResponse(
        session_id=session_id,
        has_events=True,
        agents=agents,
        tool_calls=tool_calls,
        latest_summary=latest_summary,
        latest_error=latest_error,
        updated_at=updated_at,
    )


def _build_agent_stream_event(
    session_id: str,
    position: int,
    timestamp: str,
    agent: str,
    event_type: str,
    content: str,
    metadata: Optional[Dict[str, object]] = None,
) -> dict[str, object]:
    return {
        "id": f"{session_id}:{position}",
        "timestamp": timestamp,
        "agent": agent,
        "type": event_type,
        "content": content,
        "metadata": metadata or {},
    }


def _normalize_agent_stream_event(session_id: str, event) -> dict[str, object]:
    payload = event.payload or {}
    if event.event_type == "tool_call":
        return _build_agent_stream_event(
            session_id,
            event.position,
            event.timestamp,
            "implementer",
            "tool_call",
            f"Started {payload.get('tool_name') or 'tool'}",
            {
                "call_id": payload.get("call_id"),
                "tool_name": payload.get("tool_name"),
                "args": payload.get("args"),
                "status": payload.get("status"),
                "step_id": payload.get("step_id"),
            },
        )
    if event.event_type == "tool_result":
        status = "error" if payload.get("status") == "error" else "result"
        return _build_agent_stream_event(
            session_id,
            event.position,
            event.timestamp,
            "implementer",
            status,
            f"{payload.get('tool_name') or 'Tool'} {payload.get('status') or 'completed'}",
            {
                "call_id": payload.get("call_id"),
                "tool_name": payload.get("tool_name"),
                "status": payload.get("status"),
                "output": _truncate_agent_text(payload.get("output") or "", 800),
                "step_id": payload.get("step_id"),
            },
        )
    if event.event_type == "step_start":
        if payload.get("goal"):
            return _build_agent_stream_event(
                session_id,
                event.position,
                event.timestamp,
                "planner",
                "status",
                f"Planned {payload.get('steps') or 0} steps for {payload.get('goal')}",
                payload,
            )
        return _build_agent_stream_event(
            session_id,
            event.position,
            event.timestamp,
            "implementer",
            "status",
            str(payload.get("description") or "Started a new step"),
            payload,
        )
    if event.event_type == "step_complete":
        status = "error" if payload.get("status") == "failed" else "result"
        detail = payload.get("description") or payload.get("status") or "Completed step"
        return _build_agent_stream_event(
            session_id,
            event.position,
            event.timestamp,
            "implementer",
            status,
            str(detail),
            payload,
        )
    if event.event_type == "assistant_message":
        if isinstance(payload.get("judge"), dict):
            judge = payload["judge"]
            return _build_agent_stream_event(
                session_id,
                event.position,
                event.timestamp,
                "judge",
                "status",
                f"{judge.get('verdict') or 'Judge'} — {judge.get('notes') or ''}".strip(" —"),
                judge,
            )
        if payload.get("summary"):
            return _build_agent_stream_event(
                session_id,
                event.position,
                event.timestamp,
                "coordinator",
                "result",
                _truncate_agent_text(payload.get("summary"), 800),
                payload,
            )
    if event.event_type == "user_message":
        return _build_agent_stream_event(
            session_id,
            event.position,
            event.timestamp,
            "system",
            "message",
            _truncate_agent_text(payload.get("instruction") or "New request", 300),
            payload,
        )
    return _build_agent_stream_event(
        session_id,
        event.position,
        event.timestamp,
        "system",
        "status",
        _truncate_agent_text(payload or event.event_type, 300),
        payload if isinstance(payload, dict) else {"value": payload},
    )


def _select_auto_skills(content: str, *, limit: int = 5) -> list[dict[str, str]]:
    lower = content.lower()
    queries = ["implementation", "planner", "review"]

    if any(token in lower for token in ("test", "regression", "verify", "failing")):
        queries.extend(["test", "verification"])
    if any(token in lower for token in ("security", "auth", "token", "secret", "permission")):
        queries.extend(["security", "risky", "hardening"])
    if any(token in lower for token in ("docs", "adr", "decision", "readme", "changelog")):
        queries.extend(["docs", "changelog"])
    if any(token in lower for token in ("frontend", "mobile", "ui", "layout", "responsive")):
        queries.extend(["frontend", "design", "performance"])
    if any(token in lower for token in ("commit", "branch", "pull request", "pr")):
        queries.extend(["git", "commit", "review"])

    matches: dict[str, dict[str, str]] = {}
    for query in queries:
        try:
            results = AUTO_SKILL_LIBRARY.search(query)
        except Exception:
            continue
        for skill in results:
            matches.setdefault(
                skill.skill_id,
                {
                    "name": skill.name,
                    "description": skill.description,
                },
            )
            if len(matches) >= limit:
                return list(matches.values())[:limit]
    return list(matches.values())[:limit]


def _build_auto_skill_guidance(content: str) -> tuple[str, list[dict[str, str]]]:
    skills = _select_auto_skills(content)
    if not skills:
        return "", []

    lines = [
        "AUTO-SELECTED SKILLS AND WORKFLOWS:",
        "- Apply these proactively when they improve speed, quality, or safety. The user should not need to request them explicitly.",
        "- For larger tasks, follow the CRISPY working style: scout the context, plan the change, implement narrowly, review the result, and verify with concrete evidence.",
    ]
    for skill in skills:
        lines.append(f"- {skill['name']}: {skill['description']}")
    return "\n".join(lines), skills


def _resolve_ollama_url(url: Optional[str]) -> str:
    """Swap localhost → `ollama` when running inside Docker.

    Inside a container, 127.0.0.1/localhost refers to the container itself,
    not the host running Ollama. Compose usually exposes Ollama at the
    service name "ollama"; respect an explicit override via OLLAMA_HOST_IN_DOCKER.
    """
    if not url:
        return url or "http://localhost:11434"
    # Detect Docker: presence of /.dockerenv is the canonical signal.
    in_docker = Path("/.dockerenv").exists() or os.environ.get(
        "IN_DOCKER", ""
    ).lower() in ("1", "true", "yes")
    if not in_docker:
        return url
    host_alias = os.environ.get("OLLAMA_HOST_IN_DOCKER", "ollama").strip() or "ollama"
    # Only rewrite the host portion, not the whole URL.
    for needle in ("://localhost:", "://127.0.0.1:"):
        if needle in url:
            return url.replace(needle, f"://{host_alias}:", 1)
    return url


HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_TOKEN", "")
HF_BASE_URL = os.environ.get("HF_BASE_URL", "https://router.huggingface.co")
HF_MODEL_ID = os.environ.get("HF_MODEL_ID", "Qwen/Qwen2.5-Coder-7B-Instruct")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
EMERGENT_ANTHROPIC_MODEL = os.environ.get(
    "EMERGENT_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"
)

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "deepseek")
LANGFUSE_PK = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SK = os.environ.get("LANGFUSE_SECRET_KEY", "")
LANGFUSE_BASE = (
    os.environ.get("LANGFUSE_BASE_URL")
    or os.environ.get("LANGFUSE_HOST")
    or os.environ.get("LANGFUSE_URL")
    or "https://cloud.langfuse.com"
)
AGENT_EVENT_STORE = AgentSessionStore()
AUTO_SKILL_LIBRARY = SkillLibrary()
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")
NGROK_DOMAIN = os.environ.get("NGROK_DOMAIN", "")


def _langfuse_credentials() -> tuple[str, str, str]:
    public_key = (os.environ.get("LANGFUSE_PUBLIC_KEY") or "").strip()
    secret_key = (os.environ.get("LANGFUSE_SECRET_KEY") or "").strip()
    base_url = (
        os.environ.get("LANGFUSE_BASE_URL")
        or os.environ.get("LANGFUSE_HOST")
        or os.environ.get("LANGFUSE_URL")
        or "https://cloud.langfuse.com"
    ).strip().rstrip("/")
    return public_key, secret_key, base_url
NGROK_TOKEN = os.environ.get("NGROK_AUTH_TOKEN", "") or os.environ.get("NGROK_AUTHTOKEN", "")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY", "")
TOGETHER_BASE_URL = "https://api.together.xyz/v1"

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = "https://api.minimax.chat/v1"
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
MOONSHOT_API_KEY = os.environ.get("MOONSHOT_API_KEY", "")
MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

OLLAMA_WINDOWS_SERVER = os.environ.get("OLLAMA_WINDOWS_SERVER", "").strip().rstrip("/")
OLLAMA_WINDOWS_MODEL = os.environ.get("OLLAMA_WINDOWS_MODEL", OLLAMA_MODEL)

# GitHub OAuth App credentials (optional — enables the one-click "Connect with GitHub"
# flow; without these the fallback PAT input is shown instead).
# Register an OAuth App at https://github.com/settings/developers
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
# Set this to the full callback URL registered in your OAuth App, e.g.
# https://my-backend.onrender.com/api/github/oauth/callback
GITHUB_CALLBACK_URL = os.environ.get("GITHUB_CALLBACK_URL", "")

# Imported early so /api/skills/discover can reference the registries list
try:
    from agent.skill_registry import GITHUB_REGISTRIES
except ImportError:
    log.warning("Could not import GITHUB_REGISTRIES — skill discover endpoint will show no registries")
    GITHUB_REGISTRIES = []  # type: ignore[assignment]


# ── Dashboard hot-path helpers ─────────────────────────────────────────────────
import asyncio as _asyncio
import time as _time

_DASHBOARD_CACHE: dict = {}


async def _cached(key: str, *, ttl_s: float, producer) -> object:
    """Single-flight TTL cache. Concurrent callers wait for the first producer."""
    now = _time.monotonic()
    entry = _DASHBOARD_CACHE.get(key)
    if entry and "event" not in entry and entry.get("expires_at", 0) > now:
        return entry["value"]
    if entry and "event" in entry:
        await entry["event"].wait()
        e2 = _DASHBOARD_CACHE.get(key, {})
        if "event" not in e2:
            return e2.get("value")
    evt = _asyncio.Event()
    _DASHBOARD_CACHE[key] = {"expires_at": now + ttl_s, "event": evt, "value": None}
    try:
        value = await producer()
        _DASHBOARD_CACHE[key] = {"expires_at": now + ttl_s, "value": value}
        return value
    finally:
        evt.set()


async def _fast_count(collection) -> int:
    """Count without materialising rows — prefers estimated_document_count."""
    try:
        return await collection.estimated_document_count()
    except AttributeError:
        return await collection.count_documents({})

# ─── Model Catalog ────────────────────────────────────────────────────────────────
# Best-in-class models per provider, tagged by role and tier.
# role: planner = strong reasoning; executor = instruction-following/coding; verifier = critical eval

PREDEFINED_MODELS: dict[str, list[dict]] = {
    "openrouter": [
        {
            "id": "deepseek/deepseek-r1",
            "name": "DeepSeek R1",
            "role": ["planner", "verifier"],
            "tier": "flagship",
        },
        {
            "id": "qwen/qwen3-235b-a22b",
            "name": "Qwen3 235B A22B",
            "role": ["executor"],
            "tier": "flagship",
        },
        {
            "id": "google/gemini-2.5-pro-preview",
            "name": "Gemini 2.5 Pro",
            "role": ["planner", "executor"],
            "tier": "flagship",
        },
        {
            "id": "anthropic/claude-opus-4",
            "name": "Claude Opus 4",
            "role": ["planner", "verifier"],
            "tier": "flagship",
        },
        {
            "id": "meta-llama/llama-4-maverick",
            "name": "Llama 4 Maverick",
            "role": ["executor"],
            "tier": "fast",
        },
        {
            "id": "qwen/qwen3-30b-a3b",
            "name": "Qwen3 30B A3B",
            "role": ["executor"],
            "tier": "fast",
        },
        {
            "id": "deepseek/deepseek-r1-distill-qwen-32b",
            "name": "DeepSeek R1 Distill 32B",
            "role": ["planner"],
            "tier": "balanced",
        },
        {
            "id": "mistralai/mistral-small-3.2-24b-instruct",
            "name": "Mistral Small 3.2 24B",
            "role": ["executor"],
            "tier": "fast",
        },
    ],
    "huggingface": [
        {
            "id": "Qwen/QwQ-32B",
            "name": "QwQ 32B",
            "role": ["planner", "verifier"],
            "tier": "flagship",
        },
        {
            "id": "deepseek-ai/DeepSeek-R1",
            "name": "DeepSeek R1",
            "role": ["planner", "verifier"],
            "tier": "flagship",
        },
        {
            "id": "Qwen/Qwen2.5-72B-Instruct",
            "name": "Qwen2.5 72B Instruct",
            "role": ["executor"],
            "tier": "flagship",
        },
        {
            "id": "Qwen/Qwen2.5-Coder-32B-Instruct",
            "name": "Qwen2.5-Coder 32B",
            "role": ["executor"],
            "tier": "balanced",
        },
        {
            "id": "meta-llama/Llama-3.3-70B-Instruct",
            "name": "Llama 3.3 70B",
            "role": ["executor"],
            "tier": "balanced",
        },
        {
            "id": "mistralai/Mistral-7B-Instruct-v0.3",
            "name": "Mistral 7B v0.3",
            "role": ["executor"],
            "tier": "fast",
        },
    ],
    "ollama": [
        {
            "id": "deepseek-r1:671b",
            "name": "DeepSeek R1 671B",
            "role": ["planner", "verifier"],
            "tier": "flagship",
        },
        {
            "id": "deepseek-r1:32b",
            "name": "DeepSeek R1 32B",
            "role": ["planner", "verifier"],
            "tier": "flagship",
        },
        {
            "id": "qwen3-coder:30b",
            "name": "Qwen3-Coder 30B",
            "role": ["executor"],
            "tier": "flagship",
        },
        {
            "id": "qwen3:14b",
            "name": "Qwen3 14B",
            "role": ["executor"],
            "tier": "balanced",
        },
        {
            "id": "llama3.3:70b",
            "name": "Llama 3.3 70B",
            "role": ["executor"],
            "tier": "flagship",
        },
        {
            "id": "deepseek-r1:14b",
            "name": "DeepSeek R1 14B",
            "role": ["planner"],
            "tier": "balanced",
        },
        {
            "id": "qwen2.5-coder:14b",
            "name": "Qwen2.5-Coder 14B",
            "role": ["executor"],
            "tier": "balanced",
        },
        {
            "id": "llama3.2:3b",
            "name": "Llama 3.2 3B",
            "role": ["executor"],
            "tier": "fast",
        },
    ],
    "together": [
        {
            "id": "deepseek-ai/DeepSeek-R1",
            "name": "DeepSeek R1",
            "role": ["planner", "verifier"],
            "tier": "flagship",
        },
        {
            "id": "Qwen/Qwen3-235B-A22B",
            "name": "Qwen3 235B A22B",
            "role": ["executor"],
            "tier": "flagship",
        },
        {
            "id": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
            "name": "Llama 4 Maverick",
            "role": ["executor"],
            "tier": "fast",
        },
        {
            "id": "Qwen/Qwen2.5-72B-Instruct-Turbo",
            "name": "Qwen2.5 72B Turbo",
            "role": ["executor"],
            "tier": "balanced",
        },
        {
            "id": "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
            "name": "DeepSeek R1 Distill 32B",
            "role": ["planner"],
            "tier": "balanced",
        },
    ],
    "deepseek": [
        {
            "id": "deepseek-chat",
            "name": "DeepSeek-V3",
            "role": ["executor"],
            "tier": "flagship",
        },
        {
            "id": "deepseek-reasoner",
            "name": "DeepSeek-R1",
            "role": ["planner", "verifier"],
            "tier": "flagship",
        },
    ],
    "zhipu": [
        {
            "id": "glm-5.2",
            "name": "GLM-4.5 Air",
            "role": ["planner", "executor", "verifier"],
            "tier": "balanced",
        },
    ],
    "dashscope": [
        {
            "id": "qwen3-coder-30b-a3b",
            "name": "Qwen3-Coder-30B-A3B",
            "role": ["planner", "executor", "verifier"],
            "tier": "balanced",
        },
        {
            "id": "qwen3.5-397b-a17b",
            "name": "Qwen3.5 397B A17B",
            "role": ["executor"],
            "tier": "flagship",
        },
    ],
    "minimax": [
        {
            "id": "mimo-v2-flash",
            "name": "MiMo-V2-Flash",
            "role": ["planner", "executor", "verifier"],
            "tier": "balanced",
        },
    ],
    "google": [
        {
            "id": "gemma-4",
            "name": "Gemma 4",
            "role": ["planner", "executor", "verifier"],
            "tier": "balanced",
        },
    ],
    "moonshot": [
        {
            "id": "kimi-k2.6",
            "name": "Kimi-K2.6",
            "role": ["planner", "executor", "verifier"],
            "tier": "flagship",
        },
    ],
}

# Which model handles each agent role per provider type.
# Planner/Verifier → strong reasoning model; Executor → best instruction-following model.
AGENT_ROLE_MODELS: dict[str, dict[str, str]] = {
    "openrouter": {
        "planner": "deepseek/deepseek-r1",
        "executor": "qwen/qwen3-235b-a22b",
        "verifier": "deepseek/deepseek-r1",
    },
    "huggingface": {
        "planner": "Qwen/QwQ-32B",
        "executor": "Qwen/Qwen2.5-72B-Instruct",
        "verifier": "deepseek-ai/DeepSeek-R1",
    },
    "ollama": {
        "planner": "deepseek-r1:671b",
        "executor": "qwen3-coder:30b",
        "verifier": "deepseek-r1:671b",
    },
    "together": {
        "planner": "deepseek-ai/DeepSeek-R1",
        "executor": "Qwen/Qwen3-235B-A22B",
        "verifier": "deepseek-ai/DeepSeek-R1",
    },
    "deepseek": {
        "planner": "deepseek-reasoner",
        "executor": "deepseek-chat",
        "verifier": "deepseek-reasoner",
    },
    "zhipu": {
        "planner": "glm-5.2",
        "executor": "glm-5.2",
        "verifier": "glm-5.2",
    },
    "dashscope": {
        "planner": "qwen3-coder-30b-a3b",
        "executor": "qwen3.5-397b-a17b",
        "verifier": "qwen3-coder-30b-a3b",
    },
    "minimax": {
        "planner": "mimo-v2-flash",
        "executor": "mimo-v2-flash",
        "verifier": "mimo-v2-flash",
    },
    "google": {
        "planner": "gemma-4",
        "executor": "gemma-4",
        "verifier": "gemma-4",
    },
    "moonshot": {
        "planner": "kimi-k2.6",
        "executor": "kimi-k2.6",
        "verifier": "kimi-k2.6",
    },
}

# ── Social Auth Config ───────────────────────────────────────────────────────
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
SESSION_SECRET = os.environ.get("SESSION_SECRET", JWT_SECRET)
# Base URL of this server — used for OAuth callback URIs.
# Must match exactly what is registered in GitHub/Google OAuth App settings.
# Example: https://myserver.com  (no trailing slash)
OAUTH_REDIRECT_BASE = os.environ.get("OAUTH_REDIRECT_BASE", "").rstrip("/")

# ─── Auth Helpers ───────────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "iat": now,
            "jti": secrets.token_hex(8),
            "exp": now + timedelta(hours=24),
            "type": "access",
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def create_refresh_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "iat": now,
            "jti": secrets.token_hex(8),
            "exp": now + timedelta(days=7),
            "type": "refresh",
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def _token_response(*, uid: str, email: str, name: str, role: str, access: str, refresh: str) -> dict[str, Any]:
    return {
        "_id": uid,
        "id": uid,
        "email": email,
        "name": name,
        "role": role,
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": 24 * 60 * 60,
    }


async def get_optional_user(request: Request) -> Optional[dict]:
    """Get user if authenticated, otherwise return None (for public endpoints)."""
    token = None
    auth = request.headers.get("Authorization", "")
    x_api_key = request.headers.get("x-api-key", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    elif x_api_key:
        token = x_api_key
    elif request.url.path in {"/api/agent/status", "/api/agent/stream"}:
        token = request.query_params.get("access_token")
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        try:
            user = await get_db().users.find_one({"_id": ObjectId(payload["sub"])})
        except Exception:
            user = None
        # When using SQLite (STORAGE_BACKEND=sqlite), user _id is a plain
        # string (UUID), not a Mongo ObjectId. Retry with the raw string.
        if user is None:
            try:
                user = await get_db().users.find_one({"_id": payload["sub"]})
            except Exception:
                user = None
        # Last-resort DB fallback for CI/limited mode — only for admin.
        if user is None and payload.get("email") == ADMIN_EMAIL:
            user = {
                "_id": payload["sub"],
                "email": ADMIN_EMAIL,
                "name": "Admin",
                "role": "admin",
            }
        if not user:
            return None
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
        return None


async def get_current_user(request: Request) -> dict:
    user = await get_optional_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def _telegram_bot_supervisor() -> None:
    """Run the FreeBuff Telegram bot, restarting it on unexpected exit."""
    import asyncio as _asyncio

    from telegram_bot import run_bot
    while True:
        try:
            await run_bot()
            log.warning("Telegram bot exited (likely misconfig); retrying in 30s.")
        except _asyncio.CancelledError:
            raise
        except Exception as exc:  # never let the bot kill the web process
            log.exception("Telegram bot crashed: %s — restarting in 30s", exc)
        await _asyncio.sleep(30)


async def _keepalive_self_ping() -> None:
    """Ping our own public URL so a free-tier web service doesn't sleep.

    Render free web services sleep after ~15 min without *inbound* traffic; the
    bot's outbound long-poll does not count. Pinging RENDER_EXTERNAL_URL keeps
    the service awake so the bot keeps receiving. Opt out with BOT_KEEPALIVE=false.
    """
    import asyncio as _asyncio

    base = (os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("SELF_BOOTSTRAP_URL") or "").rstrip("/")
    if not base:
        return
    url = f"{base}/api/ping"
    import httpx as _httpx
    while True:
        await _asyncio.sleep(600)  # every 10 minutes
        try:
            async with _httpx.AsyncClient(timeout=20.0) as client:
                await client.get(url)
        except _asyncio.CancelledError:
            raise
        except Exception as exc:
            log.debug("keepalive self-ping failed (non-fatal): %s", exc)


def _start_in_web_bot_tasks() -> list:
    """Start the Telegram bot (and keep-alive) inside the web process when enabled.

    Enabled when TELEGRAM_BOT_TOKEN is set and RUN_TELEGRAM_BOT is truthy
    (default true). Returns the created asyncio tasks so the caller can cancel
    them on shutdown.
    """
    import asyncio as _asyncio

    tasks: list = []
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        return tasks
    if os.environ.get("RUN_TELEGRAM_BOT", "true").strip().lower() not in {"1", "true", "yes"}:
        log.info("RUN_TELEGRAM_BOT is disabled — not starting the in-web Telegram bot.")
        return tasks

    # FreeBuff embedded defaults so the bot runs the agent in-process (no proxy)
    # and opens draft PRs. Only set when the operator hasn't overridden them.
    os.environ.setdefault("FREEBUFF_EMBEDDED", "true")
    os.environ.setdefault("AGENT_AUTO_PR_ENABLED", "true")
    os.environ.setdefault("FREEBUFF_BASE_BRANCH", "master")
    os.environ.setdefault("FREEBUFF_REPO_URL", "https://github.com/strikersam/local-llm-server")

    try:
        tasks.append(_asyncio.create_task(_telegram_bot_supervisor()))
        log.info("FreeBuff Telegram bot starting inside web process (embedded mode).")
    except Exception as exc:
        log.warning("Could not start in-web Telegram bot: %s", exc)
        return tasks

    if os.environ.get("BOT_KEEPALIVE", "true").strip().lower() in {"1", "true", "yes"}:
        tasks.append(_asyncio.create_task(_keepalive_self_ping()))

    return tasks




async def _startup_reliability_hooks() -> None:
    """#522 + #505: Reliability startup — schedule hydration, orchestrator restore, queue + supervisor start."""
    # Rehydrate persisted schedules so company cadences survive redeploys.
    try:
        hydrated = await SCHEDULER.hydrate()
        if hydrated:
            log.info("Startup: hydrated %d scheduled job(s) from durable store", hydrated)
    except Exception:
        log.warning("Startup: scheduler hydration failed (non-fatal)")

    # Restore in-flight orchestrator runs from checkpoint store.
    try:
        from services.workflow_orchestrator import get_workflow_orchestrator
        orchestrator = get_workflow_orchestrator()
        restored = await orchestrator.restore_in_flight()
        if restored:
            log.info("Startup: restored %d in-flight orchestration run(s)", restored)
    except Exception:
        log.debug("Startup: orchestrator checkpoint restore skipped")

    # Start the orchestrator FIFO queue and deterministic supervisor.
    try:
        from services.orchestrator_queue import start_orchestrator_queue
        await start_orchestrator_queue()
        log.info("Startup: orchestrator queue started")
    except Exception:
        log.debug("Startup: orchestrator queue start skipped")

    try:
        from services.orchestrator_supervisor import start_orchestrator_supervisor
        await start_orchestrator_supervisor()
        log.info("Startup: orchestrator supervisor started")
    except Exception:
        log.debug("Startup: orchestrator supervisor start skipped")

    # Register the ECC harness adapter.
    try:
        from agents.harness_adapter import get_harness_adapter
        adapter = get_harness_adapter()
        adapter.register_active("claude_code")
        adapter.register_active("cursor")
        adapter.register_active("telegram")
        log.info("Startup: ECC harness adapter registered (%d active)", len(adapter.active_harness_ids))
    except Exception:
        log.debug("Startup: harness adapter registration skipped")


@asynccontextmanager
async def lifespan(app_: "FastAPI"):
    from services.background import start_background_services, run_background_in_web

    from services.background import BackgroundServices
    bg: Optional[BackgroundServices] = None
    try:
        await ensure_bootstrap()
        log.info("LLM Relay Platform started — provider=%s", LLM_PROVIDER)
    except Exception as exc:
        log.warning("MongoDB bootstrap deferred (no DB connection): %s", exc)
        log.info(
            "LLM Relay Platform started in limited mode — set MONGO_URL to enable full features"
        )

    if run_background_in_web():
        bg = await start_background_services(
            workspace_root=ROOT_DIR,
            task_store=get_task_store(),
            scheduler=SCHEDULER,
        )
    else:
        log.info(
            "RUN_BACKGROUND_IN_WEB=false — background services skipped "
            "(expected: dedicated worker process is running)"
        )

    # FreeBuff Telegram bot — optionally run inside this web process so a single
    # free-tier service can host both the API and the phone-control bot.
    extra_tasks = _start_in_web_bot_tasks()

    # #522 + #505: Reliability startup hooks
    await _startup_reliability_hooks()

    # N5: Surface SERVICE_TOKEN misconfiguration at startup so the operator
    # sees the gap in the backend logs (not just when /setbrain fails at
    # runtime). Best-effort — never blocks startup.
    try:
        from services.service_token import is_service_token_configured
        if not is_service_token_configured():
            log.warning(
                "SERVICE_TOKEN not set — Telegram mutating control "
                "(/setbrain + /merge) will refuse with 503. "
                "Generate with: python -c \"import secrets; print('st_' + secrets.token_urlsafe(32))\" "
                "and set on BOTH the backend AND the Telegram bot."
            )
    except Exception:  # pragma: no cover - defensive
        pass

    # Warm the app-settings cache so the (sync) onboarding-gate default read is
    # correct from the first request. Best-effort — never blocks startup.
    try:
        from app_settings import refresh_cache
        await refresh_cache()
    except Exception as exc:  # noqa: BLE001
        log.warning("app_settings cache warm failed: %s", exc)

    yield

    for _t in extra_tasks:
        _t.cancel()
    if bg is not None:
        await bg.stop()


app = FastAPI(title=f"{APP_LABEL} — {APP_TAGLINE}", version=__version__, lifespan=lifespan)


frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
_raw_cors_origins = os.environ.get("CORS_ORIGINS", "*").strip()
# Default CORS origins: GitHub Pages + wildcard for development
_default_cors = [
    "https://strikersam.github.io",
    "https://*.github.io",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8001",
]
CORS_ORIGINS = [
    origin.strip() for origin in _raw_cors_origins.split(",") if origin.strip()
] or _default_cors

# ─── Social Login (GitHub & Google) ───────────────────────────────────────────


async def _store_login_state(state: str, provider: str) -> None:
    """Persist an OAuth *login* state server-side in the shared oauth_states store.

    Session cookies do NOT reliably survive the OAuth round-trip in this
    deployment: the frontend is on Cloudflare while the backend is on Render,
    and Render's free tier rotates the in-process SESSION_SECRET on every cold
    start (when JWT_SECRET is unset). A server-side state row — the same
    mechanism the GitHub repo-connect flow already uses — is provider- and
    instance-agnostic. The collection has a 10-minute TTL index, so stale rows
    are dropped automatically.
    """
    await get_db().oauth_states.insert_one(
        {
            "state": state,
            "flow_type": "login",
            "provider": provider,
            "created_at": datetime.now(timezone.utc),
        }
    )


def _valid_login_state(doc: Optional[dict], provider: str) -> bool:
    """Return True if a fetched oauth_states doc is a valid, unexpired login state."""
    if not doc or doc.get("flow_type") != "login" or doc.get("provider") != provider:
        return False
    created = doc.get("created_at")
    if isinstance(created, datetime):
        # MongoDB (motor) returns naive UTC datetimes by default, so normalise to
        # tz-aware before comparing — otherwise "offset-naive vs offset-aware"
        # raises TypeError and the callback 500s after the state check passes.
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        # Defensive expiry check for backends without a TTL index (e.g. SQLite).
        if (datetime.now(timezone.utc) - created).total_seconds() > 600:
            return False
    return True


@app.get("/api/auth/github/login")
async def github_login(request: Request):
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GitHub login not configured")
    state = secrets.token_urlsafe(32)
    await _store_login_state(state, "github")
    redirect_uri = (
        f"{OAUTH_REDIRECT_BASE}/api/auth/github/callback"
        if OAUTH_REDIRECT_BASE
        else str(request.url_for("github_callback"))
    )
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}&state={state}&scope=user:email"
        f"&redirect_uri={redirect_uri}"
    )
    return RedirectResponse(url)


@app.get("/api/auth/github/callback")
async def github_callback(request: Request, code: str = None, state: str = None):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    # Login flow: state was stored server-side in oauth_states by
    # /api/auth/github/login.
    state_doc = await get_db().oauth_states.find_one({"state": state})
    if not _valid_login_state(state_doc, provider="github"):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    # State validated — consume it so it cannot be replayed.
    await get_db().oauth_states.delete_one({"state": state})

    try:
        # 1. Exchange code for token (canonical helper)
        access_token = await github_exchange_code(code)
        if not access_token:
            raise HTTPException(status_code=400, detail="GitHub token exchange failed")

        # 2. Fetch user profile (canonical helper — returns email, name, avatar, login)
        gh_user = await github_fetch_user(access_token)
        if not gh_user:
            raise HTTPException(status_code=502, detail="GitHub OAuth request failed")
        email = gh_user["email"]
    except HTTPException:
        raise
    except Exception as exc:
        log.error("GitHub OAuth login error: %s", exc)
        raise HTTPException(status_code=502, detail="GitHub OAuth request failed")

    if not email:
        raise HTTPException(
            status_code=400, detail="Could not retrieve email from GitHub"
        )

    # 3. Find or create user
    user = await get_db().users.find_one({"email": email.lower()})
    # Extract raw numeric GitHub ID from the canonical user_id (format: "gh_<id>")
    uid_str = gh_user["user_id"][3:] if gh_user["user_id"].startswith("gh_") else gh_user["user_id"]
    now = datetime.now(timezone.utc).isoformat()

    if not user:
        # Automatic registration
        new_user = {
            "email": email.lower(),
            "name": gh_user["name"],
            "avatar_url": gh_user["avatar_url"],
            "provider": "github",
            "provider_user_id": uid_str,
            "role": "user",
            "created_at": now,
            "last_login": now,
        }
        result = await get_db().users.insert_one(new_user)
        user_id = str(result.inserted_id)
        await log_activity(
            "auth", f"New user {email} registered via GitHub", user_id=user_id
        )
    else:
        # Update existing user with social info if missing or just update last_login
        user_id = str(user["_id"])
        await get_db().users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "last_login": now,
                    "provider": user.get("provider", "github"),
                    "provider_user_id": user.get("provider_user_id", uid_str),
                    "avatar_url": user.get("avatar_url")
                    or gh_user["avatar_url"],
                }
            },
        )
        await log_activity(
            "auth", f"User {email} logged in via GitHub", user_id=user_id
        )

    # 5. Generate tokens and redirect to frontend
    access = create_access_token(user_id, email)
    refresh = create_refresh_token(user_id)
    return RedirectResponse(
        f"{frontend_url}/auth/callback?access_token={access}&refresh_token={refresh}"
    )


@app.get("/api/auth/github/repo-access")
async def github_repo_access(request: Request, user: dict = Depends(get_current_user)):
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GitHub login not configured")
    state = secrets.token_urlsafe(32)
    request.session["repo_oauth_state"] = state
    # We request 'repo' scope for read/write access to repositories
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}&state={state}&scope=repo,user:email"
        f"&redirect_uri={request.url_for('github_repo_callback')}"
    )
    return RedirectResponse(url)


@app.get("/api/auth/github/repo-callback")
async def github_repo_callback(request: Request, code: str = None, state: str = None):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    if state != request.session.pop("repo_oauth_state", None):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    try:
        # 1. Exchange code for token (canonical helper)
        access_token = await github_exchange_code(code)
        if not access_token:
            raise HTTPException(status_code=400, detail="GitHub token exchange failed")

        # 2. Fetch user profile (canonical helper — returns email, name, login)
        gh_user = await github_fetch_user(access_token)
        if not gh_user:
            raise HTTPException(status_code=502, detail="GitHub OAuth request failed")
        email = gh_user["email"]
    except HTTPException:
        raise
    except Exception as exc:
        log.error("GitHub OAuth repo-callback error: %s", exc)
        raise HTTPException(status_code=502, detail="GitHub OAuth request failed")

    if not email:
        raise HTTPException(
            status_code=400, detail="Could not retrieve email from GitHub"
        )

    # 3. Update the user with the new token
        # Note: We associate the token with the authenticated user.
        # Ideally, we should check if the GitHub email matches the logged-in user email.
        # For simplicity in this local tool, we just update the user.
        await get_db().users.update_one(
            {"email": email.lower()},
            {
                "$set": {
                    "github_repo_token": access_token,
                    "github_login": gh_user["login"],
                    "github_updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        await log_activity(
            "auth",
            f"User {email} granted GitHub repo access",
            meta={"github_login": gh_user["login"]},
        )

        return RedirectResponse(f"{frontend_url}/settings?github_authorized=true")


@app.get("/api/github/repos")
async def github_list_repos(user: dict = Depends(get_current_user)):
    token = user.get("github_repo_token")
    # Also check github_settings collection (set by popup OAuth flow)
    if not token:
        doc = await get_db().github_settings.find_one({"user_id": user["_id"]})
        if doc:
            token = doc.get("token")
    if not token:
        return {"repos": [], "authorized": False, "message": "No GitHub token connected. Go to GitHub screen to connect one."}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                "https://api.github.com/user/repos?per_page=100&sort=updated",
                headers={"Authorization": f"token {token}"},
            )
            if resp.status_code == 401:
                return {
                    "repos": [],
                    "authorized": False,
                    "error": "Token revoked or expired",
                }
            resp.raise_for_status()
            repos = resp.json()
            return {
                "repos": [
                    {
                        "id": r["id"],
                        "full_name": r["full_name"],
                        "name": r["name"],
                        "private": r["private"],
                        "url": r["html_url"],
                        "description": r["description"],
                    }
                    for r in repos
                ],
                "authorized": True,
            }
        except Exception:
            return {"repos": [], "authorized": True, "error": "Failed to fetch repositories"}


class AuthorizeReposBody(BaseModel):
    repo_names: list[str]


@app.post("/api/github/authorize-repos")
async def github_authorize_repos(
    body: AuthorizeReposBody, user: dict = Depends(get_current_user)
):
    await get_db().users.update_one(
        {"_id": ObjectId(user["_id"])}, {"$set": {"authorized_repos": body.repo_names}}
    )
    await log_activity(
        "auth", f"User updated authorized repos: {len(body.repo_names)} repos"
    )
    return {"ok": True}




# ─── ECC Harness Adapter API ──────────────────────────────────────────────

@app.get("/api/harness/catalog")
async def harness_catalog():
    """Return the full ECC harness catalog with capabilities.

    Public — no auth required (descriptive metadata only)."""
    from agents.harness_adapter import HARNESS_CATALOG, get_harness_adapter
    adapter = get_harness_adapter()
    active_ids = set(adapter.active_harness_ids)
    return {
        "harnesses": [
            {
                "harness_id": h.harness_id,
                "display_name": h.display_name,
                "supports": h.supports,
                "default_model": h.default_model,
                "is_active": h.harness_id in active_ids,
            }
            for h in sorted(HARNESS_CATALOG.values(), key=lambda x: x.display_name)
        ],
        "active_count": len(active_ids),
    }


@app.get("/api/harness/active")
async def harness_active(user: dict = Depends(get_current_user)):
    """Return the currently active ECC harnesses with session metrics.

    Authenticated — harness metrics may be user-specific in future."""
    from agents.harness_adapter import get_harness_adapter
    from services.harness_registry import get_harness_registry
    adapter = get_harness_adapter()
    registry = get_harness_registry()
    return {
        "adapter": adapter.as_dict(),
        "registry": registry.as_dict(),
    }


class HarnessSessionBody(BaseModel):
    harness_id: str
    session_id: str
    model: str | None = None


@app.post("/api/harness/session/start")
async def harness_session_start(
    body: HarnessSessionBody,
    user: dict = Depends(get_current_user),
):
    """Register a new harness session (called by the orchestrator on execute)."""
    from services.harness_registry import get_harness_registry
    registry = get_harness_registry()
    record = registry.register_session(body.harness_id, body.session_id, body.model)
    return record.model_dump()


class HarnessSessionCloseBody(BaseModel):
    session_id: str
    tasks_completed: int = 0
    success: bool = True
    errors: list[str] = Field(default_factory=list)


@app.post("/api/harness/session/close")
async def harness_session_close(
    body: HarnessSessionCloseBody,
    user: dict = Depends(get_current_user),
):
    """Close a harness session and aggregate its metrics."""
    from services.harness_registry import get_harness_registry
    registry = get_harness_registry()
    registry.close_session(
        body.session_id,
        tasks_completed=body.tasks_completed,
        success=body.success,
        errors=body.errors,
    )
    return {"ok": True}

@app.get("/api/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    """Return the current user's profile from the Bearer JWT.

    Called by the frontend AuthContext.checkAuth() after login (both
    email/password and social OAuth flows) to validate the stored token
    and hydrate the user object. Previously this endpoint only existed in
    the dead social_auth.py module, breaking social login callbacks.
    """
    return {
        "_id": user.get("_id", ""),
        "id": user.get("_id", ""),
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "role": user.get("role", "user"),
        "avatar_url": user.get("avatar_url", ""),
    }


@app.get("/api/github/status")
async def github_status(user: dict = Depends(get_current_user)):
    oauth_enabled = bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET)
    # Token may live in the user doc (set by redirect/PAT flow) or in
    # github_settings (set by popup OAuth).  Check both so older accounts work.
    token = user.get("github_repo_token")
    gh_login = user.get("github_login")
    if not token:
        doc = await get_db().github_settings.find_one({"user_id": user["_id"]})
        if doc:
            token = doc.get("token")
            gh_login = gh_login or doc.get("github_login")
    return {
        "connected": bool(token),
        "oauth_enabled": oauth_enabled,
        "login": gh_login,  # used by main GitHub Integration section
        "github_login": gh_login,  # used by GitHubAccessSection
        "authorized_repos": user.get("authorized_repos", []),
    }


@app.get("/api/auth/google/login")
async def google_login(request: Request):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google login not configured")
    state = secrets.token_urlsafe(32)
    await _store_login_state(state, "google")
    # Use OAUTH_REDIRECT_BASE so the redirect_uri matches what is registered in Google Console.
    # Falls back to url_for only in local dev where no proxy is involved.
    redirect_uri = (
        f"{OAUTH_REDIRECT_BASE}/api/auth/google/callback"
        if OAUTH_REDIRECT_BASE
        else str(request.url_for("google_callback"))
    )
    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}&response_type=code&scope=openid%20email%20profile"
        f"&redirect_uri={redirect_uri}&state={state}"
    )
    return RedirectResponse(url)


@app.get("/api/auth/google/callback")
async def google_callback(request: Request, code: str = None, state: str = None):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    # State was stored server-side in oauth_states by /api/auth/google/login.
    state_doc = await get_db().oauth_states.find_one({"state": state})
    if not _valid_login_state(state_doc, provider="google"):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    # State validated — consume it so it cannot be replayed.
    await get_db().oauth_states.delete_one({"state": state})

    # redirect_uri must be identical to the one used in /api/auth/google/login
    redirect_uri = (
        f"{OAUTH_REDIRECT_BASE}/api/auth/google/callback"
        if OAUTH_REDIRECT_BASE
        else str(request.url_for("google_callback"))
    )

    try:
        # 1. Exchange code for token (canonical helper)
        access_token = await google_exchange_code(code, redirect_uri=redirect_uri)
        if not access_token:
            raise HTTPException(status_code=400, detail="Google token exchange failed")

        # 2. Fetch user profile (canonical helper — returns email, name, avatar)
        g_user = await google_fetch_user(access_token)
        if not g_user:
            raise HTTPException(status_code=502, detail="Google OAuth request failed")
        email = g_user["email"]
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Google OAuth login error: %s", exc)
        raise HTTPException(status_code=502, detail="Google OAuth request failed")

    if not email:
        raise HTTPException(
            status_code=400, detail="Could not retrieve email from Google"
        )

    # 3. Find or create user
    user = await get_db().users.find_one({"email": email.lower()})
    # Extract raw Google sub ID from the canonical user_id (format: "goog_<id>")
    uid_str = g_user["user_id"][5:] if g_user["user_id"].startswith("goog_") else g_user["user_id"]
    now = datetime.now(timezone.utc).isoformat()

    if not user:
        new_user = {
            "email": email.lower(),
            "name": g_user["name"],
            "avatar_url": g_user["avatar_url"],
            "provider": "google",
            "provider_user_id": uid_str,
            "role": "user",
            "created_at": now,
            "last_login": now,
        }
        result = await get_db().users.insert_one(new_user)
        user_id = str(result.inserted_id)
        await log_activity(
            "auth", f"New user {email} registered via Google", user_id=user_id
        )
    else:
        user_id = str(user["_id"])
        await get_db().users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "last_login": now,
                    "provider": user.get("provider", "google"),
                    "provider_user_id": user.get("provider_user_id", uid_str),
                    "avatar_url": user.get("avatar_url") or g_user["avatar_url"],
                }
            },
        )
        await log_activity(
            "auth", f"User {email} logged in via Google", user_id=user_id
        )

    # 4. Generate tokens and redirect to frontend
    access = create_access_token(user_id, email)
    refresh = create_refresh_token(user_id)
    return RedirectResponse(
        f"{frontend_url}/auth/callback?access_token={access}&refresh_token={refresh}"
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="llm_relay_session",
    max_age=3600,  # 1 hour for OAuth state
)

# Storage backend — delegates to either MongoStore (default) or SQLiteStore.
# Switch with: STORAGE_BACKEND=sqlite  (no MongoDB required)
# All 112+ call sites use get_db() unchanged.
from db import get_store as _get_store


def get_db():
    """Return the active storage backend (Mongo or SQLite).

    Lazy-initialised singleton.  Set ``STORAGE_BACKEND=sqlite`` to use the
    zero-dependency SQLite backend (ideal for development and CI).
    """
    return _get_store()


class JWTUserStateMiddleware(BaseHTTPMiddleware):
    """Populate request.state.user from a valid Bearer JWT.

    Task and agent routers read request.state.user directly (rather than
    using Depends(get_current_user)), so this middleware bridges the gap.
    """

    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
            try:
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                if payload.get("type") == "access":
                    user = None
                    try:
                        user = await get_db().users.find_one({"_id": ObjectId(payload["sub"])})
                    except Exception:
                        user = None
                    # SQLite backend stores _id as string, not ObjectId.
                    if user is None:
                        try:
                            user = await get_db().users.find_one({"_id": payload["sub"]})
                        except Exception:
                            user = None
                    if not user and payload.get("email") == ADMIN_EMAIL:
                        user = {
                            "_id": payload["sub"],
                            "email": ADMIN_EMAIL,
                            "name": "Admin",
                            "role": "admin",
                        }
                    if user:
                        user["_id"] = str(user["_id"])
                        user.pop("password_hash", None)
                        request.state.user = user
            except Exception:
                pass
        return await call_next(request)


app.add_middleware(JWTUserStateMiddleware)

_BOOTSTRAP_DONE = False
_BOOTSTRAP_LOCK = asyncio.Lock()


async def ensure_bootstrap() -> None:
    """Idempotent bootstrap for indexes + seeded admin/providers.

    FastAPI startup hooks can be skipped in some dev/prod entrypoints; this keeps
    the service usable even if the ASGI server doesn't run startup events.
    """
    global _BOOTSTRAP_DONE
    if _BOOTSTRAP_DONE:
        return
    try:
        async with _BOOTSTRAP_LOCK:
            if _BOOTSTRAP_DONE:
                return
            await get_db().users.create_index("email", unique=True)
            await get_db().wiki_pages.create_index("slug", unique=True)
            await get_db().wiki_pages.create_index([("title", "text"), ("content", "text")])
            await get_db().sources.create_index("created_at")
            await get_db().activity_log.create_index("created_at")
            await get_db().chat_sessions.create_index("user_id")
            await get_db().providers.create_index("provider_id", unique=True)
            await get_db().api_keys.create_index("key_id", unique=True)
            await get_db().github_settings.create_index("user_id", unique=True)
            # oauth_states has a 10-minute TTL — MongoDB drops stale records automatically
            await get_db().oauth_states.create_index("created_at", expireAfterSeconds=600)
            # Indexes for feature routers
            await get_db().agent_definitions.create_index("agent_id", unique=True)
            await get_db().agent_definitions.create_index("owner_id")
            await get_db().tasks.create_index("task_id", unique=True)
            await get_db().tasks.create_index("owner_id")
            await get_db().tasks.create_index("status")
            # Wire feature stores to the shared MongoDB connection
            set_agent_store(AgentStore(db=get_db()))
            set_task_store(TaskStore(db=get_db()))
            await seed_admin()
            await seed_default_agents()
            await seed_default_providers()
            await _sync_ollama_model()
            _BOOTSTRAP_DONE = True
    except Exception as exc:
        log.warning("MongoDB bootstrap failed (running in limited mode): %s", exc)
        _BOOTSTRAP_DONE = True  # Mark as "attempted" to prevent repeated timeouts
        raise


# Startup is handled by the lifespan context manager defined above.


async def _sync_ollama_model() -> None:
    """Auto-detect the best available Ollama model and update ollama-local in the DB.

    Runs after seed_default_providers so the provider always points at an
    actually-installed model.  If the configured model IS installed we leave it
    alone; if not, we pick the first (largest) installed model instead.
    Prefers larger / more capable model names (gemma4, qwen3, llama3, deepseek)
    over tiny fallbacks like tinyllama.
    """
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            if r.status_code != 200:
                return
            installed = [m["name"] for m in r.json().get("models", [])]
    except Exception as exc:
        log.debug("_sync_ollama_model: Ollama unreachable — %s", exc)
        return

    if not installed:
        return

    prov = await get_db().providers.find_one({"provider_id": "ollama-local"})
    current = (prov or {}).get("default_model", "")

    # If the currently configured model is already installed, nothing to do.
    if current in installed:
        return

    # Prefer larger / more capable models by keyword heuristic.
    _PREFER = ("qwen3", "gemma4", "gemma-4", "llama3", "deepseek", "mistral", "mixtral")
    preferred = [m for m in installed for kw in _PREFER if kw in m.lower()]
    best = preferred[0] if preferred else installed[0]

    await get_db().providers.update_one(
        {"provider_id": "ollama-local"},
        {"$set": {"default_model": best}},
    )
    log.info(
        "Auto-selected Ollama model: %s (configured model %r not installed; available: %s)",
        best,
        current,
        installed,
    )


async def seed_admin():
    existing = await get_db().users.find_one({"email": ADMIN_EMAIL})
    if existing is None:
        await get_db().users.insert_one(
            {
                "email": ADMIN_EMAIL,
                "password_hash": hash_password(ADMIN_PASSWORD),
                "name": "Admin",
                "role": "admin",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        log.info("Admin user seeded: %s", ADMIN_EMAIL)
    elif ADMIN_PASSWORD and not verify_password(
        ADMIN_PASSWORD, existing["password_hash"]
    ):
        # Sync DB password from the effective admin password env var on restart so the
        # configured credential always works. Operators change this via .env
        # or the Render dashboard — not by editing the DB directly.
        await get_db().users.update_one(
            {"email": ADMIN_EMAIL},
            {"$set": {"password_hash": hash_password(ADMIN_PASSWORD)}},
        )
        log.info(
            "Admin password synced from effective admin password env var for %s",
            ADMIN_EMAIL,
        )


async def seed_default_agents() -> None:
    """Seed the five built-in CRISPY agent profiles if they don't exist yet.

    These are public (workspace-visible) and owned by the admin account so every
    user can see and use them immediately without manual setup.
    """
    from agents.profiles import load_all_profiles
    from agents.store import AgentDefinition, get_agent_store

    _TASK_TYPES: dict[str, list[str]] = {
        "scout": ["research", "code_review", "general"],
        "architect": ["planning", "design", "general"],
        "coder": ["code_generation", "repo_editing", "tool_use"],
        "reviewer": ["code_review", "general"],
        "verifier": ["shell_exec", "tool_use"],
    }
    _COST_POLICY: dict[str, str] = {
        "scout": "local_only",
        "architect": "local_only",
        "coder": "local_only",
        "reviewer": "local_only",
        "verifier": "local_only",
    }

    store = get_agent_store()
    profiles = load_all_profiles()

    for role, profile in profiles.items():
        # Idempotency: skip if an agent with this role tag already exists
        existing = await get_db().agent_definitions.find_one({"tags": f"crispy:{role}"})
        if existing:
            continue

        agent = AgentDefinition(
            owner_id=ADMIN_EMAIL,
            name=profile.name,
            description=f"CRISPY {profile.name} — {profile.label}",
            model=profile.model,
            system_prompt=profile.system_prompt,
            is_public=True,
            cost_policy=_COST_POLICY.get(role, "local_only"),
            task_types=_TASK_TYPES.get(role, ["general"]),
            tags=["crispy", f"crispy:{role}", "built-in"],
        )
        await store.create(agent)
        log.info("Seeded CRISPY agent: %s (%s)", profile.name, profile.model)


async def seed_default_providers():
    _nvidia_key = (
        os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey") or ""
    ).strip()
    _nvidia_base = (
        os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com"
    ).rstrip("/").removesuffix("/v1")
    # Seed from the single source of truth so the seeded provider record never
    # drifts from DEFAULT_FREE_NVIDIA_MODEL / the tests (a hardcoded `...49b-v1`
    # here lagged the `...49b-v1.5` default and broke the brain/provider tests
    # under MongoDB, where the seeded record persists and is read back).
    from brain_policy import DEFAULT_FREE_NVIDIA_MODEL
    _nvidia_model = (
        os.environ.get("NVIDIA_DEFAULT_MODEL") or DEFAULT_FREE_NVIDIA_MODEL
    )
    defaults = [
        {
            "provider_id": "anthropic-claude",
            "name": "Claude (Sonnet 4.6)",
            "type": "anthropic",
            "base_url": "https://api.anthropic.com",
            "api_key": ANTHROPIC_API_KEY,
            "default_model": "claude-sonnet-4-6",
            "is_default": False,
            "priority": -50,
            "status": "configured" if ANTHROPIC_API_KEY else "unconfigured",
        },
        {
            "provider_id": "nvidia-nim",
            "name": "Nvidia NIM (Free)",
            "type": "openai-compatible",
            "base_url": _nvidia_base,
            "api_key": _nvidia_key,
            "default_model": _nvidia_model,
            "is_default": LLM_PROVIDER == "nvidia-nim",
            "priority": -10,
            "status": "configured" if _nvidia_key else "unconfigured",
        },
        {
            "provider_id": "ollama-local",
            "name": "Ollama (Local)",
            "type": "ollama",
            "base_url": _resolve_ollama_url(OLLAMA_BASE),
            "api_key": "",
            "default_model": OLLAMA_MODEL,
            "is_default": LLM_PROVIDER == "ollama",
            "priority": 0,
            "status": "configured",
        },
        {
            "provider_id": "huggingface-serverless",
            "name": "Hugging Face (Serverless)",
            "type": "huggingface",
            "base_url": HF_BASE_URL,
            "api_key": HF_TOKEN,
            "default_model": HF_MODEL_ID,
            "is_default": LLM_PROVIDER == "huggingface",
            "priority": 10,
            "status": "configured",
        },
        {
            "provider_id": "openrouter",
            "name": "OpenRouter",
            "type": "openai-compatible",
            "base_url": OPENROUTER_BASE_URL,
            "api_key": OPENROUTER_API_KEY,
            "default_model": "qwen/qwen3-235b-a22b",
            "is_default": LLM_PROVIDER == "openrouter",
            "priority": 30,
            "status": "configured" if OPENROUTER_API_KEY else "unconfigured",
        },
        {
            "provider_id": "together-ai",
            "name": "Together AI",
            "type": "openai-compatible",
            "base_url": TOGETHER_BASE_URL,
            "api_key": TOGETHER_API_KEY,
            "default_model": "Qwen/Qwen3-235B-A22B",
            "is_default": LLM_PROVIDER == "together",
            "priority": 35,
            "status": "configured" if TOGETHER_API_KEY else "unconfigured",
        },
        {
            "provider_id": "deepseek",
            "name": "DeepSeek API",
            "type": "openai-compatible",
            "base_url": DEEPSEEK_BASE_URL,
            "api_key": DEEPSEEK_API_KEY,
            "default_model": "deepseek-reasoner",
            "is_default": LLM_PROVIDER == "deepseek",
            "priority": 20,
            "status": "configured" if DEEPSEEK_API_KEY else "unconfigured",
        },
        {
            "provider_id": "zhipu",
            "name": "Zhipu AI (GLM)",
            "type": "openai-compatible",
            "base_url": ZHIPU_BASE_URL,
            "api_key": ZHIPU_API_KEY,
            "default_model": "glm-5.2",
            "is_default": LLM_PROVIDER == "zhipu",
            "priority": 60,
            "status": "configured" if ZHIPU_API_KEY else "unconfigured",
        },
        {
            "provider_id": "dashscope",
            "name": "AliCloud DashScope",
            "type": "openai-compatible",
            "base_url": DASHSCOPE_BASE_URL,
            "api_key": DASHSCOPE_API_KEY,
            "default_model": "qwen3.5-397b-a17b",
            "is_default": LLM_PROVIDER == "dashscope",
            "priority": 65,
            "status": "configured" if DASHSCOPE_API_KEY else "unconfigured",
        },
        {
            "provider_id": "minimax",
            "name": "MiniMax",
            "type": "openai-compatible",
            "base_url": MINIMAX_BASE_URL,
            "api_key": MINIMAX_API_KEY,
            "default_model": "mimo-v2-flash",
            "is_default": LLM_PROVIDER == "minimax",
            "priority": 70,
            "status": "configured" if MINIMAX_API_KEY else "unconfigured",
        },
        {
            "provider_id": "google-gemini",
            "name": "Google Gemini (OpenAI compat)",
            "type": "openai-compatible",
            "base_url": GOOGLE_BASE_URL,
            "api_key": GOOGLE_API_KEY,
            "default_model": "gemma-4",
            "is_default": LLM_PROVIDER == "google",
            "priority": 75,
            "status": "configured" if GOOGLE_API_KEY else "unconfigured",
        },
        {
            "provider_id": "moonshot",
            "name": "Moonshot AI (Kimi)",
            "type": "openai-compatible",
            "base_url": MOONSHOT_BASE_URL,
            "api_key": MOONSHOT_API_KEY,
            "default_model": "kimi-k2.6",
            "is_default": LLM_PROVIDER == "moonshot",
            "priority": 10,
            "status": "configured" if MOONSHOT_API_KEY else "unconfigured",
        },
        {
            "provider_id": "kimi-web-bridge",
            "name": "Kimi Web Bridge (free, no API key)",
            "type": "openai-compatible",
            "base_url": os.environ.get("KIMI_BRIDGE_URL", "http://localhost:8011/v1"),
            "api_key": os.environ.get("KIMI_BRIDGE_TOKEN", "")
            if os.environ.get("KIMI_BRIDGE_ENABLED", "").strip().lower()
            in {"true", "1", "yes"}
            else "",
            "default_model": os.environ.get("KIMI_BRIDGE_MODEL", "kimi-k2.6"),
            "is_default": False,
            # Free tier — preferred over paid escalation when enabled.
            "priority": int(os.environ.get("KIMI_BRIDGE_PRIORITY", "5") or "5"),
            "tier": "free_cloud",
            "status": "configured"
            if os.environ.get("KIMI_BRIDGE_ENABLED", "").strip().lower()
            in {"true", "1", "yes"}
            else "unconfigured",
        },
        {
            "provider_id": "anthropic-universal",
            "name": "Anthropic (Universal Key)",
            "type": "emergent-anthropic",
            "base_url": "emergent://anthropic",
            "api_key": EMERGENT_LLM_KEY,
            "default_model": EMERGENT_ANTHROPIC_MODEL,
            "is_default": False,
            "priority": 55,
            "status": "configured" if EMERGENT_LLM_KEY else "unconfigured",
        },
        {
            "provider_id": "anthropic",
            "name": "Anthropic Claude (Direct API)",
            "type": "anthropic",
            "base_url": ANTHROPIC_BASE_URL,
            "api_key": ANTHROPIC_API_KEY,
            "default_model": ANTHROPIC_MODEL,
            "is_default": False,
            "priority": 50,
            "status": "configured" if ANTHROPIC_API_KEY else "unconfigured",
        },
        {
            "provider_id": "ollama-windows-server",
            "name": "Ollama (Windows Server)",
            "type": "ollama",
            "base_url": OLLAMA_WINDOWS_SERVER,  # empty string → excluded by filter
            "api_key": "",
            "default_model": OLLAMA_WINDOWS_MODEL,
            "is_default": False,
            "priority": 5,
            "status": "configured" if OLLAMA_WINDOWS_SERVER else "unconfigured",
        },
    ]
    for p in defaults:
        existing = await get_db().providers.find_one({"provider_id": p["provider_id"]})
        if not existing:
            p["created_at"] = datetime.now(timezone.utc).isoformat()
            await get_db().providers.insert_one(p)
        else:
            # Always sync env-var-backed fields so .env changes take effect
            # without requiring a manual DB wipe.
            update: dict = {}
            if p.get("api_key") and existing.get("api_key") != p["api_key"]:
                update["api_key"] = p["api_key"]
            if p.get("base_url") and existing.get("base_url") != p["base_url"]:
                update["base_url"] = p["base_url"]
            # Sync default_model so changing OLLAMA_MODEL / DEEPSEEK_MODEL etc in .env
            # is immediately reflected without a DB wipe.
            if (
                p.get("default_model")
                and existing.get("default_model") != p["default_model"]
            ):
                update["default_model"] = p["default_model"]
            # Re-sync status when an api_key is now present but status was "unconfigured"
            new_status = p.get("status", "")
            if new_status and new_status != existing.get("status", ""):
                update["status"] = new_status
            # Sync priority so the fallback ordering is always correct
            new_priority = p.get("priority")
            if new_priority is not None and existing.get("priority") != new_priority:
                update["priority"] = new_priority
            if update:
                await get_db().providers.update_one(
                    {"provider_id": p["provider_id"]}, {"$set": update}
                )
                log.info(
                    "Synced env-var fields for provider %s: %s",
                    p["provider_id"],
                    list(update.keys()),
                )


def _builtin_provider_records() -> list[dict]:
    """Return a minimal set of built-in provider records without touching MongoDB.

    This is an intentional SUBSET covering the entries that are always present
    regardless of operator configuration. It is used as a limited-mode fallback 
    when MongoDB is unreachable — not as the authoritative full catalog.
    """
    return [
        {
            "provider_id": "anthropic-claude",
            "name": "Claude (Sonnet 4.6)",
            "type": "anthropic",
            "base_url": "https://api.anthropic.com",
            "api_key": ANTHROPIC_API_KEY,
            "default_model": "claude-sonnet-4-6",
            "is_default": False,
            "priority": -50,
            "status": "configured" if ANTHROPIC_API_KEY else "unconfigured",
        },
        {
            "provider_id": "ollama-local",
            "name": "Ollama (Local)",
            "type": "ollama",
            "base_url": _resolve_ollama_url(OLLAMA_BASE),
            "api_key": "",
            "default_model": OLLAMA_MODEL,
            "is_default": LLM_PROVIDER == "ollama",
            "priority": 0,
            "status": "configured",
        },
        {
            "provider_id": "anthropic-universal",
            "name": "Anthropic (Universal Key)",
            "type": "emergent-anthropic",
            "base_url": "emergent://anthropic",
            "api_key": EMERGENT_LLM_KEY,
            "default_model": EMERGENT_ANTHROPIC_MODEL,
            "is_default": False,
            "priority": 55,
            "status": "configured" if EMERGENT_LLM_KEY else "unconfigured",
        },
        {
            "provider_id": "anthropic",
            "name": "Anthropic Claude (Direct API)",
            "type": "anthropic",
            "base_url": ANTHROPIC_BASE_URL,
            "api_key": ANTHROPIC_API_KEY,
            "default_model": ANTHROPIC_MODEL,
            "is_default": False,
            "priority": 50,
            "status": "configured" if ANTHROPIC_API_KEY else "unconfigured",
        },
    ]


# ─── Multi-Agent Orchestration ────────────────────────────────────────────────
# Implements the Planner → Executor → Verifier three-role loop described in the
# project README and ADR-003. Applies Anthropic's context efficiency principles:
#   • Observation masking: truncate old tool outputs to ≤300 chars
#   • Context compaction: LLM-summarize history when > COMPACT_THRESHOLD messages
#   • Condensed sub-agent summaries: each role returns a ≤500-char synthesis

_COMPLEX_KEYWORDS = {
    "write",
    "create",
    "build",
    "generate",
    "analyze",
    "implement",
    "refactor",
    "design",
    "plan",
    "research",
    "compare",
    "summarize",
    "explain in detail",
    "step by step",
    "walk me through",
    "how would you",
    "what are all",
    # GitHub / repo operations — always need the agent tools
    "github",
    "repository",
    "repo",
    "commit",
    "push",
    "pull request",
    "branch",
    "add changes",
    "make changes",
    "edit code",
    "edit file",
    "connect to my",
    "open pr",
    "open a pr",
    "merge",
    "clone",
}
_COMPLEX_WORD_THRESHOLD = 25
_COMPACT_THRESHOLD = 16
_DIRECT_CHAT_REPO_ACTION_KEYWORDS = {
    "repository",
    "repo",
    "open a pr",
    "open pr",
    "pull request",
    "branch",
    "run tests",
    "merge strategy",
    "multi-file",
    "multiple files",
    "docker image",
    "production app",
    "regressions",
}
_DIRECT_CHAT_GITHUB_ACTION_KEYWORDS = {
    "github",
    "pull request",
    "open pr",
    "open a pr",
    "branch",
    "commit changes",
    "push",
    "clone",
}
_DIRECT_CHAT_WORKSPACE_ACTION_KEYWORDS = {
    "repository",
    "repo",
    "workspace",
    "codebase",
    "multi-file",
    "multiple files",
    "edit code",
    "edit file",
    "exact file edits",
    "tests to add",
    "merge strategy",
}
_DIRECT_CHAT_RUNTIME_ACTION_KEYWORDS = {
    "docker",
    "dockerfile",
    "container",
    "runtime",
    "run tests",
    "build image",
    "install dependency",
    "copy package",
    "start server",
}
_DIRECT_CHAT_EXPLANATION_PREFIXES = (
    "explain",
    "why",
    "how do",
    "how does",
    "what is",
    "what are",
    "walk me through",
    "help me understand",
)
_DIRECT_CHAT_EXECUTION_SIGNALS = (
    "fix ",
    "edit ",
    "update ",
    "change the code",
    "apply the fix",
    "make the fix",
    "run tests",
    "run the tests",
    "commit the changes",
    "push the",
    "merge the",
    "add a regression test",
    "add tests",
)
_DIRECT_CHAT_RECURRING_KEYWORDS = (
    "every day",
    "daily",
    "every morning",
    "every night",
    "every week",
    "weekly",
    "every month",
    "monthly",
    "every hour",
    "hourly",
    "cron",
    "schedule this",
    "scheduled",
    "automatically",
)


def _classify_complexity(content: str) -> str:
    """Return 'complex' if the message warrants multi-agent orchestration, else 'simple'."""
    lower = content.lower()
    word_count = len(content.split())
    has_keyword = any(kw in lower for kw in _COMPLEX_KEYWORDS)
    return (
        "complex"
        if (word_count >= _COMPLEX_WORD_THRESHOLD or has_keyword)
        else "simple"
    )


def _requires_agent_mode_for_safe_repo_help(content: str) -> bool:
    lower = content.lower()
    hits = sum(keyword in lower for keyword in _DIRECT_CHAT_REPO_ACTION_KEYWORDS)
    requests_edits = any(
        phrase in lower
        for phrase in (
            "exact file edits",
            "change two files",
            "fix plan",
            "commit message",
            "tests to add",
        )
    )
    return hits >= 2 or (hits >= 1 and requests_edits)


def _direct_chat_agent_handoff(
    content: str, *, github_connected: bool
) -> Optional[Dict[str, object]]:
    lower = content.lower()
    stripped = lower.strip()
    reason_codes: list[str] = []
    reasons: list[str] = []

    if any(keyword in lower for keyword in _DIRECT_CHAT_GITHUB_ACTION_KEYWORDS):
        reason_codes.append("github")
        reasons.append("GitHub branch / PR actions")

    if any(keyword in lower for keyword in _DIRECT_CHAT_WORKSPACE_ACTION_KEYWORDS):
        reason_codes.append("workspace")
        reasons.append("repository / file changes")

    if any(keyword in lower for keyword in _DIRECT_CHAT_RUNTIME_ACTION_KEYWORDS):
        reason_codes.append("runtime")
        reasons.append("workspace or container execution")

    asks_for_concrete_changes = any(
        phrase in lower
        for phrase in (
            "exact file edits",
            "tests to add",
            "commit message",
            "apply the fix",
            "make the fix",
            "change the code",
            "open a pr",
            "open pr",
            "run tests",
            "merge strategy",
        )
    )
    asks_for_explanation = any(
        stripped.startswith(prefix) for prefix in _DIRECT_CHAT_EXPLANATION_PREFIXES
    )
    has_execution_signal = any(signal in lower for signal in _DIRECT_CHAT_EXECUTION_SIGNALS)

    if not reason_codes:
        return None

    if asks_for_explanation and not has_execution_signal:
        return None

    if len(reason_codes) == 1 and not asks_for_concrete_changes:
        return None

    workflow_suggestions = [_build_direct_chat_task_suggestion(content, reason_codes)]
    schedule_suggestion = _build_direct_chat_schedule_suggestion(content, reason_codes)
    if schedule_suggestion is not None:
        workflow_suggestions.append(schedule_suggestion)

    return {
        "type": "agent_handoff",
        "recommended_mode": "agent",
        "reason_codes": reason_codes,
        "reasons": reasons,
        "retryable_prompt": content,
        "workflow_suggestions": workflow_suggestions,
        "github_connected": github_connected,
        "settings_route": (
            "/settings"
            if ("github" in reason_codes and not github_connected)
            else None
        ),
    }


def _derive_work_item_title(content: str, *, fallback: str) -> str:
    text = re.sub(r"\s+", " ", content).strip()
    for delimiter in ("\n", ".", "?", "!"):
        if delimiter in text:
            text = text.split(delimiter, 1)[0].strip()
            break
    if not text:
        return fallback
    if len(text) > 72:
        trimmed = text[:72].rsplit(" ", 1)[0].strip()
        text = f"{trimmed or text[:72].strip()}…"
    return text[0].upper() + text[1:]


def _infer_task_priority(content: str) -> str:
    lower = content.lower()
    if any(keyword in lower for keyword in ("urgent", "sev1", "critical", "outage")):
        return "urgent"
    if any(keyword in lower for keyword in ("production", "regression", "broken", "fix")):
        return "high"
    return "medium"


def _infer_schedule_cron(content: str) -> tuple[str, str]:
    lower = content.lower()
    if "every hour" in lower or "hourly" in lower:
        return "0 * * * *", "Hourly"
    if "every week" in lower or "weekly" in lower:
        return "0 9 * * 1", "Weekly"
    if "every month" in lower or "monthly" in lower:
        return "0 9 1 * *", "Monthly"
    return "0 9 * * *", "Daily"


def _looks_like_recurring_automation(content: str) -> bool:
    lower = content.lower()
    return any(keyword in lower for keyword in _DIRECT_CHAT_RECURRING_KEYWORDS)


def _build_direct_chat_tags(reason_codes: list[str]) -> list[str]:
    tags: list[str] = []
    mapping = {
        "github": "github",
        "workspace": "workspace",
        "runtime": "runtime",
    }
    for code in reason_codes:
        tag = mapping.get(code)
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def _build_direct_chat_task_suggestion(
    content: str, reason_codes: list[str]
) -> dict[str, object]:
    title = _derive_work_item_title(content, fallback="Follow up on direct chat request")
    task_type = "general"
    if "github" in reason_codes or "workspace" in reason_codes:
        task_type = "repository_change"
    elif "runtime" in reason_codes:
        task_type = "runtime_change"
    return {
        "kind": "task",
        "label": "Create Task",
        "route": "/tasks",
        "payload": {
            "title": title,
            "description": "Created from a Direct Chat handoff so the work can be tracked in the task board.",
            "prompt": content,
            "priority": _infer_task_priority(content),
            "task_type": task_type,
            "requires_approval": "github" in reason_codes,
            "tags": _build_direct_chat_tags(reason_codes),
        },
    }


def _build_direct_chat_schedule_suggestion(
    content: str, reason_codes: list[str]
) -> Optional[Dict[str, object]]:
    if not _looks_like_recurring_automation(content):
        return None
    cron, cadence = _infer_schedule_cron(content)
    title = _derive_work_item_title(content, fallback="Recurring agent workflow")
    return {
        "kind": "schedule",
        "label": "Create Schedule",
        "route": "/schedules",
        "payload": {
            "name": f"{cadence}: {title}",
            "cron": cron,
            "instruction": content,
            "approval_gate": "github" in reason_codes,
            "tags": _build_direct_chat_tags(reason_codes),
        },
    }


def _mask_observations(messages: list[dict], max_chars: int = 300) -> list[dict]:
    """Truncate tool/observation content in older messages to prevent context bloat."""
    result = []
    for i, m in enumerate(messages):
        if i < len(messages) - 4 and m.get("role") == "assistant":
            content = m.get("content", "")
            if len(content) > max_chars:
                m = {**m, "content": content[:max_chars] + " … [truncated]"}
        result.append(m)
    return result


def _sanitize_chat_messages(messages: list[dict]) -> list[dict[str, str]]:
    sanitized: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "").strip()
        content = message.get("content")
        if not role or content is None:
            continue
        normalized: dict[str, str] = {"role": role, "content": str(content)}
        name = message.get("name")
        if name:
            normalized["name"] = str(name)
        sanitized.append(normalized)
    return sanitized


async def _compact_context(
    messages: list[dict],
    provider_cfg: "LlmProviderConfig",
    model: Optional[str],
) -> list[dict]:
    """Summarize older messages when history grows beyond COMPACT_THRESHOLD."""
    if len(messages) <= _COMPACT_THRESHOLD:
        return messages

    # Keep the last 6 messages verbatim; summarize the rest.
    to_summarize = messages[:-6]
    recent = messages[-6:]

    summary_prompt = [
        {
            "role": "system",
            "content": (
                "You are a context compactor. Summarize the conversation below "
                "in ≤500 words, preserving all decisions, facts, and code snippets. "
                "Output ONLY the summary — no preamble."
            ),
        },
        {
            "role": "user",
            "content": "\n\n".join(
                f"[{m['role'].upper()}] {m['content']}" for m in to_summarize
            ),
        },
    ]
    try:
        summary = await chat_completion_text(
            provider_cfg, messages=summary_prompt, model=model, temperature=0.1
        )
        compacted = [
            {"role": "system", "content": f"[Conversation summary]\n{summary}"}
        ]
    except Exception:
        # If compaction fails, just drop old messages rather than crashing.
        compacted = [
            {"role": "system", "content": "[Earlier context omitted for brevity]"}
        ]

    return compacted + recent


async def _agent_provider_failure_response(instruction: str, exc: Exception) -> str:
    """Fall back to a direct LLM call when the agent loop cannot reach any provider.

    Tries call_llm() with a simple conversational prompt. If that also fails, returns
    an actionable error message explaining what went wrong and how to fix it.
    """
    log.warning("Agent provider failure — attempting direct-chat fallback: %s", exc)
    try:
        direct_response = await call_llm(
            messages=[{"role": "user", "content": instruction}],
            allow_commercial_fallback_once=True,
        )
        return (
            f"{direct_response}\n\n"
            "_(Answered in direct-chat mode — the agent infrastructure is currently unavailable.)_"
        )
    except Exception as fallback_exc:
        log.warning("Direct-chat fallback also failed: %s", fallback_exc)

    failure_detail = str(exc)
    providers_hint = ""
    if "401" in failure_detail:
        providers_hint = (
            "One or more API keys returned **401 Unauthorized**. "
            "Update them at **Providers → API Key**.\n"
        )
    if "All connection attempts failed" in failure_detail or "Connection refused" in failure_detail:
        providers_hint += (
            "Ollama appears to be offline. "
            "Start it with `ollama serve` or check **Providers → Test**.\n"
        )
    return (
        "⚠️ **All LLM providers failed** — the agent couldn't start.\n\n"
        + (providers_hint or "")
        + "\n**To fix:**\n"
        "• Open **Providers** and click **Test** next to each provider.\n"
        "• Replace any provider showing 401 with a valid API key.\n"
        "• If using Ollama, make sure it is running and reachable.\n"
        "• Add a free fallback such as OpenRouter or DeepSeek.\n\n"
        f"_Technical detail: {failure_detail[:300]}_"
    )


async def _run_agent_loop(
    instruction: str,
    session_messages: list[dict],
    wiki_index: str,
    provider: dict,
    session_id: Optional[str] = None,
    requested_model: Optional[str] = None,
    model_overrides: Optional[Dict[str, str]] = None,
    github_token: Optional[str] = None,
    provider_chain: Optional[List[ProviderConfig]] = None,
    allow_commercial_fallback: bool = True,
    workspace_root: Optional[Union[str, Path]] = None,
    context: Optional[Dict] = None,
) -> str:
    try:
        from agent.loop import AgentRunner
        from agent.user_memory import UserMemoryStore
    except ImportError as exc:
        return (
            "⚠️ The agent run failed before it could use any tools.\n\n"
            f"Error: {exc}\n\n"
            "Troubleshooting:\n"
            "• Check that the selected LLM provider is reachable (Providers page → Test).\n"
            "• If using Ollama in Docker, ensure OLLAMA_BASE_URL points to the container hostname"
            " (e.g. http://ollama:11434).\n"
            "• For GitHub operations, verify a token is connected at Settings → GitHub and"
            " Agent Mode (⚡) is ON."
        )

    # Use a workspace root defined by either environment or a default.
    workspace_root = Path(workspace_root or Path(__file__).resolve().parent)

    headers = (
        {"Authorization": f"Bearer {provider.get('api_key')}"}
        if provider.get("api_key")
        else None
    )
    runner = AgentRunner(
        ollama_base=_resolve_ollama_url(provider.get("base_url") or OLLAMA_BASE),
        workspace_root=workspace_root,
        provider_headers=headers,
        provider_temperature=0.3,  # default for agent
        session_store=AGENT_EVENT_STORE,
        github_token=github_token,
    )

    github_status = (
        "GitHub token connected — you can list repos, read files, create branches, "
        "commit changes, and open pull requests via the github_* tools."
        if github_token
        else "GitHub not connected — if the user asks for GitHub operations, tell them to add a token at Settings → GitHub."
    )
    auto_skill_guidance, auto_skills = _build_auto_skill_guidance(instruction)
    if session_id and auto_skills:
        try:
            AGENT_EVENT_STORE.append_event(
                session_id,
                "skill_context",
                {"skills": auto_skills},
            )
        except Exception:
            log.debug("skill guidance event append failed", exc_info=True)

    agent_instruction = (
        "CONTEXT: You are a powerful AI coding agent with multi-step reasoning and full tool access.\n\n"
        "CAPABILITIES:\n"
        "- Read, search, and edit files in the local workspace\n"
        "- Read files from GitHub repositories, create branches, commit changes, open PRs\n"
        "- Save and recall user preferences across sessions\n"
        "- Access the wiki knowledge base and create/edit wiki pages\n\n"
        f"GITHUB STATUS: {github_status}\n\n"
        + (f"{auto_skill_guidance}\n\n" if auto_skill_guidance else "")
        + f"WIKI INDEX (current pages):\n{wiki_index}\n\n"
        + ("USER CONTEXT:\n" + "\n".join(f"  {k}: {v}" for k, v in context.items()) + "\n\n" if context else "")
        + f"TASK: {instruction}"
    )

    try:
        if session_id:
            _append_agent_session_message(session_id, "user", instruction)
        # Live Agent Mode is a deliberate, user-invoked execution path. Set the
        # orchestrator bypass token so the AgentRunner.run() deprecation guard
        # (active under the default AGENCY_WORKFLOW_MODE=orchestrator) doesn't
        # block it — the guard exists to catch *unintended* parallel callers,
        # not the explicit chat Agent Mode toggle.
        import services.workflow_orchestrator as _wo
        _bypass_token = _wo._BYPASS.set(True)
        try:
            # Overall wall-clock budget for the entire agent run (plan +
            # execute + verify). Without this, a hung provider connection
            # leaves the chat job stuck at phase "planning" indefinitely
            # because runner.run() makes several sequential LLM calls each
            # with a 300s httpx read timeout and no aggregate cap.
            result = await asyncio.wait_for(
                runner.run(
                    instruction=agent_instruction,
                    history=session_messages,
                    requested_model=requested_model,
                    auto_commit=True,
                    max_steps=8,
                    memory_store=UserMemoryStore(),
                    session_id=session_id,
                ),
                timeout=_AGENT_RUN_BUDGET_SEC,
            )
        except asyncio.TimeoutError:
            log.warning(
                "Agent run exceeded %ss budget (session=%s) — returning timeout response",
                _AGENT_RUN_BUDGET_SEC, session_id,
            )
            return (
                "\u26a0\ufe0f The agent run timed out before completing.\n\n"
                "The selected provider took too long to respond (no result within "
                f"{int(_AGENT_RUN_BUDGET_SEC)}s). This usually means the LLM endpoint "
                "is overloaded, unreachable, or the model is too slow.\n\n"
                "**Try:**\n"
                "\u2022 Re-run the request (transient provider slowness is common).\n"
                "\u2022 Switch to a faster provider/model in Providers.\n"
                "\u2022 For Ollama, confirm the model is pulled and `ollama serve` is responsive.\n"
            )
        finally:
            _wo._BYPASS.reset(_bypass_token)
        if session_id:
            AGENT_EVENT_STORE.update_result(
                session_id,
                result.get("plan") or {"goal": instruction, "steps": []},
                result,
            )
            _append_agent_session_message(session_id, "assistant", str(result.get("summary") or ""))
        return result["summary"]
    except CommercialFallbackRequiredError:
        raise
    except ProviderFallbackError as exc:
        log.error("AgentRunner provider fallback exhausted: %s", exc)
        return await _agent_provider_failure_response(instruction, exc)
    except Exception as exc:
        log.error("AgentRunner failed: %s", exc)
        exc_str = str(exc)
        if "All configured LLM providers failed" in exc_str or exc_str.startswith("planning:"):
            return await _agent_provider_failure_response(instruction, exc)
        return (
            f"⚠️ Agent error: {exc}\n\n"
            "**Troubleshooting:**\n"
            "• Verify your configured provider is reachable and has valid credentials (Providers → Test).\n"
            "• If using Ollama, ensure it is running (`ollama serve`) and the model is pulled.\n"
            "• If using NVIDIA NIM, verify your NVIDIA_API_KEY is valid and has credits remaining.\n"
            "• For GitHub operations, connect a token at Settings → GitHub.\n"
            "• Check the server logs for the full traceback.\n"
        )


# ─── Activity Logging ──────────────────────────────────────────────────────────


async def log_activity(
    category: str, message: str, user_id: str = None, meta: dict = None
):
    entry = {
        "category": category,
        "message": message,
        "user_id": user_id,
        "meta": meta or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Always record to the in-memory feed so the alerts bell works even without a DB.
    _ACTIVITY_BUFFER.appendleft(dict(entry))
    try:
        await get_db().activity_log.insert_one(dict(entry))
    except Exception as exc:
        log.warning("Activity log DB write skipped (DB unavailable): %s", exc)


# ─── Auth Endpoints ─────────────────────────────────────────────────────────────


class LoginBody(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
async def login(body: LoginBody):
    try:
        await ensure_bootstrap()
        email = body.email.strip().lower()
        user = await get_db().users.find_one({"email": email})
    except Exception as exc:
        log.warning("DB query failed during login (limited mode): %s", exc)
        # Fallback to env-based admin
        if body.email.strip().lower() == ADMIN_EMAIL.lower() and verify_password(
            body.password, hash_password(ADMIN_PASSWORD)
        ):
            uid = "admin_user_001"
            access = create_access_token(uid, ADMIN_EMAIL)
            refresh = create_refresh_token(uid)
            return _token_response(
                uid=uid,
                email=ADMIN_EMAIL,
                name="Admin",
                role="admin",
                access=access,
                refresh=refresh,
            )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    uid = str(user["_id"])
    access = create_access_token(uid, email)
    refresh = create_refresh_token(uid)
    try:
        await log_activity("auth", f"User {email} logged in", user_id=uid)
    except Exception:
        pass  # Ignore activity log failures in limited mode
    return _token_response(
        uid=uid,
        email=user["email"],
        name=user.get("name", ""),
        role=user.get("role", "user"),
        access=access,
        refresh=refresh,
    )


@app.post("/api/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    response = JSONResponse({
        "ok": True,
        "status": "logged out",
        "email": user.get("email", ""),
    })
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return response


@app.get("/api/auth/me")
async def me(user: dict = Depends(get_current_user)):
    result = dict(user)
    if "id" not in result and result.get("_id"):
        result["id"] = result["_id"]
    return result


@app.post("/api/auth/refresh")
async def refresh_token(request: Request):
    body = await request.json()
    token = body.get("refresh_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        try:
            user = await get_db().users.find_one({"_id": ObjectId(payload["sub"])})
        except Exception:
            if payload.get("sub") == "admin_user_001":
                user = {
                    "_id": "admin_user_001",
                    "email": ADMIN_EMAIL,
                }
            else:
                user = None
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        uid = str(user["_id"])
        access = create_access_token(uid, user["email"])
        return {"access_token": access}
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")


# ─── LLM Engine ─────────────────────────────────────────────────────────────────


async def get_active_provider():
    try:
        prov = await get_db().providers.find_one({"is_default": True})
        if not prov:
            prov = await get_db().providers.find_one({})
        return prov
    except Exception:
        return None


def _fallback_local_provider_record() -> Dict[str, Union[str, int]]:
    return {
        "provider_id": "ollama-local",
        "name": "Ollama (Local)",
        "type": "ollama",
        "base_url": _resolve_ollama_url(OLLAMA_BASE),
        "api_key": "",
        "default_model": OLLAMA_MODEL,
        "priority": 0,
    }


def _nvidia_nim_provider_record() -> Optional[Dict]:
    """Return a provider record for Nvidia NIM if the API key is set in env."""
    key = (
        os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey") or ""
    ).strip()
    if not key:
        return None
    base = (
        os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com"
    ).rstrip("/").removesuffix("/v1")
    model = (
        os.environ.get("NVIDIA_DEFAULT_MODEL") or "nvidia/llama-3.3-nemotron-super-49b-v1"
    )
    return {
        "provider_id": "nvidia-nim",
        "name": "Nvidia NIM (Free)",
        "type": "openai-compatible",
        "base_url": base,
        "api_key": key,
        "default_model": model,
        "status": "configured",
        "priority": -10,
    }


async def _list_configured_provider_records() -> list[dict]:
    try:
        records = await get_db().providers.find({}).to_list(length=200)
    except Exception:
        records = _builtin_provider_records()
    filtered: list[dict] = []
    for record in records:
        base_url = str(record.get("base_url") or "").strip()
        status = str(record.get("status") or "").strip().lower()
        provider_type = str(record.get("type") or "").strip().lower()
        has_key = bool(str(record.get("api_key") or "").strip())
        if not base_url:
            continue
        if provider_type == "ollama" or status == "configured" or has_key:
            filtered.append(record)
    # Nvidia NIM from env participates like any other record — priority governs.
    # (Previously it was unconditionally prepended, which made UI ordering a lie:
    # a user-promoted provider could never outrank it. See #524.)
    nim = _nvidia_nim_provider_record()
    if nim and not any(r.get("provider_id") == "nvidia-nim" for r in filtered):
        filtered.append(nim)
    def _record_priority(r: dict) -> int:
        try:
            return int(float(r.get("priority")))
        except (TypeError, ValueError):
            return 100

    filtered.sort(
        key=lambda r: (_record_priority(r), str(r.get("provider_id") or ""))
    )
    return filtered or [_fallback_local_provider_record()]


async def _get_provider_policy() -> dict:
    """Read the durable provider policy from DB, falling back to a safe default.

    Returns a dict with at least {'allow_paid': bool}. Never raises.
    Failsafe: returns allow_paid=False when the DB is unreachable or env
    ALLOW_PAID_BRAIN=true overrides it.
    """
    from brain_policy import allow_paid_brain as _env_allow_paid
    # Env var takes precedence over DB (operator kill-switch).
    if _env_allow_paid():
        return {"allow_paid": True, "surfaces": {}}
    try:
        doc = await get_db().providers.find_one({"provider_id": "provider_policy"})
        if doc:
            return {"allow_paid": bool(doc.get("allow_paid", False)), "surfaces": {}}
    except Exception:
        pass
    return {"allow_paid": False, "surfaces": {}}


# Per-surface routing knobs exposed by the Providers screen. "auto" = let the
# router decide; operators can pin a surface to a specific provider class.
_POLICY_SURFACES: tuple[str, ...] = (
    "brain", "ceo", "chat", "task", "sdlc", "scanner", "context", "review",
)


class ProviderPolicyUpdate(BaseModel):
    """Editable subset of the durable provider policy (paid-provider kill switch)."""

    allow_paid: bool = Field(
        default=False,
        description="When false, paid providers (Anthropic) are NEVER auto-selected",
    )
    surfaces: dict[str, str] = Field(
        default_factory=lambda: {s: "auto" for s in _POLICY_SURFACES},
        description="Per-surface routing override; 'auto' lets the router decide",
    )


async def _set_provider_policy(update: ProviderPolicyUpdate) -> dict:
    """Persist the durable provider policy and return the new state."""
    now = datetime.now(timezone.utc).isoformat()
    await get_db().providers.update_one(
        {"provider_id": "provider_policy"},
        {"$set": {
            "allow_paid": update.allow_paid,
            "surfaces": update.surfaces,
            "updated_at": now,
        }},
        upsert=True,
    )
    return {"allow_paid": update.allow_paid, "surfaces": update.surfaces}


# ─── Brain config (DB-persisted, UI-switchable) ─────────────────────────────
# PR #824 follow-up: implements docs/plans/db-brain-switcher.md.
# The agency's "brain" (provider + planner/executor/verifier/judge models)
# can be changed from the admin UI in one click, persisted in the DB, with
# no redeploy. The store lives in services/brain_config_store.py and the
# liveness prober in services/brain_liveness.py.
#
# Hard constraints (from the plan):
#   1. Never land on a dead model — PATCH probes each changed model before
#      saving and refuses (422) any that 404/410.
#   2. Always keep the known-good ``nvidia/llama-3.3-nemotron-super-49b-v1``
#      as the safe default.
#   3. Admin-gated — reuse the existing ``get_current_user`` dependency +
#      ``_is_admin`` check from ``backend.company_api``.
#   4. Never log key values; the response shape includes only
#      ``key_present`` flags, never the keys themselves.

from services.brain_config_store import (  # noqa: E402 — late import to avoid cycle
    BrainConfigPatch,
    PROVIDER_KEY_ENV,
    PROVIDER_PRESETS,
    PROVIDER_DEFAULT_BASE_URL,
    get_brain_config,
    get_brain_config_store,
    invalidate_brain_config_cache,
    provider_api_key,
    provider_base_url,
    provider_key_present,
    refresh_brain_config_cache,
    set_brain_config as _set_brain_config,
)
from services.brain_liveness import probe_model_liveness  # noqa: E402


def _require_admin(user: dict) -> None:
    """Raise 403 unless *user* has the admin role.

    Reuses ``backend.company_api._is_admin`` so the brain endpoints honour
    the same role-tag convention as the rest of the admin surface.
    """
    from backend.company_api import _is_admin
    if not _is_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Admin role required to view or change the brain config",
        )


def _brain_provider_status() -> list[dict]:
    """Return per-provider metadata for the GET endpoint.

    Surfaces ``key_present`` (bool) and the env-var name the operator would
    need to set if the key is missing. Never includes the key itself.
    """
    out: list[dict] = []
    for provider in ("cerebras", "groq", "nvidia", "ollama"):
        out.append({
            "provider_id": provider,
            "key_present": provider_key_present(provider),
            "key_env_var": PROVIDER_KEY_ENV.get(provider),
            "base_url": provider_base_url(provider),
            "presets": PROVIDER_PRESETS.get(provider, {}),
        })
    return out

@app.post("/api/admin/seed")
async def admin_seed() -> dict[str, object]:
    """Idempotent admin re-seed endpoint. Only available when TESTING=true."""
    if not os.environ.get("TESTING"):
        raise HTTPException(status_code=404, detail="Not found")
    await seed_admin()
    return {"ok": True}


@app.get("/admin/api/policy/brain")
async def get_brain_policy_route(user: dict = Depends(get_current_user)):
    """Return the active brain config + per-provider key-present flags.

    The response shape:
      ``{config: BrainConfig, providers: [...], last_probe: {...}|null}``

    Never includes API keys — only ``key_present`` booleans so the UI can
    disable the "Apply" button when the chosen provider's key is missing.
    """
    _require_admin(user)
    cfg = await refresh_brain_config_cache()
    return {
        "config": cfg.model_dump(mode="json"),
        "providers": _brain_provider_status(),
        "safe_default": {
            "primary_provider": "nvidia",
            "model": "nvidia/llama-3.3-nemotron-super-49b-v1",
        },
    }


async def _user_or_service_token(
    request: Request,
    user: dict | None = Depends(get_optional_user),
) -> dict:
    """N5 dual-auth dependency: accept EITHER a user session OR a service token.

    Used by mutating endpoints that the dashboard (user session) and the
    Telegram bot (service token) both need to call. The bot doesn't carry a
    user session, so we can't just gate on ``Depends(get_current_user)`` —
    we need to short-circuit to the service-token path when the
    ``X-Service-Token`` header is present.

    Resolution order:
      1. If ``X-Service-Token`` header is present → verify it (fail-closed).
         Returns ``{"actor": "service:telegram", "_service_token_auth": True}``
         on success.
      2. Otherwise → require a user session. If ``get_optional_user``
         returned None, raise 401. The handler is responsible for the
         ``_require_admin(user)`` check.

    Test fixtures that override ``get_current_user`` continue to work
    because ``get_optional_user`` is the function they should override for
    service-token-aware endpoints. Existing tests that override
    ``get_current_user`` will see the override propagate via FastAPI's
    dependency injection — ``get_optional_user`` calls
    ``get_current_user`` indirectly via the request, but the test fixture
    overrides at the dependency-injection layer so the override fires.

    Raises:
        HTTPException 503 — service token not configured (misconfiguration).
        HTTPException 401 — service token wrong, OR no user session.
        HTTPException 403 — handled by the caller via _require_admin.
    """
    from services.service_token import is_service_token_configured, verify_service_token
    if request.headers.get("X-Service-Token"):
        if not is_service_token_configured():
            raise HTTPException(
                status_code=503,
                detail="Service token not configured — set SERVICE_TOKEN to enable Telegram mutating control.",
            )
        if not verify_service_token(request.headers.get("X-Service-Token")):
            raise HTTPException(status_code=401, detail="Invalid X-Service-Token header.")
        return {"actor": "service:telegram", "_service_token_auth": True}
    # No service-token header → require a user session.
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@app.patch("/admin/api/policy/brain")
async def patch_brain_policy_route(
    patch: BrainConfigPatch,
    request: Request,
    user: dict = Depends(_user_or_service_token),
):
    """Apply a partial brain config update.

    Hard constraint: every changed model id is **probed for liveness before
    save**. If any probe returns non-2xx (410/404/5xx/etc.) the entire
    PATCH is rejected with HTTP 422 and a probe report — the persisted
    config is unchanged so the agent loop keeps running on the last-known
    good brain. The plan calls this the "never land on a dead model" guard.

    Returns the applied config + the probe report so the UI can show a
    green check on each role model.

    Auth (N5 — mutating Telegram control): the ``_user_or_service_token``
    dependency accepts EITHER a user session (the dashboard's existing
    flow) OR a service token (the Telegram bot's ``/setbrain`` command).
    The service-token path is logged with ``actor='service:telegram'`` so
    the operator can audit who switched the brain. The user-session path
    still requires the admin role (unchanged).
    """
    # ── N5: dual auth resolution ─────────────────────────────────────────────
    if user.get("_service_token_auth"):
        actor = "service:telegram"
    else:
        _require_admin(user)
        actor = str(user.get("email") or user.get("_id") or "admin")

    # 1. Build the list of (role, model, provider) tuples to probe.
    # Only probe fields the PATCH actually changes — if the operator only
    # touched ``executor_model``, we don't re-probe planner/verifier/judge.
    current = await get_brain_config()
    new_provider = patch.primary_provider or current.primary_provider
    # The Ollama base URL is UI-configurable. Probe (and later persist) against
    # the URL being set in this PATCH if supplied, else the currently-saved one,
    # so a brand-new tunnel URL is validated against itself before it's stored.
    probe_ollama_base: str | None = None
    if new_provider == "ollama":
        probe_ollama_base = (
            patch.ollama_base_url
            if patch.ollama_base_url is not None
            else (current.ollama_base_url or None)
        ) or None
    fields_to_probe: list[tuple[str, str]] = []
    if patch.planner_model is not None:
        fields_to_probe.append(("planner", patch.planner_model))
    if patch.executor_model is not None:
        fields_to_probe.append(("executor", patch.executor_model))
    if patch.verifier_model is not None:
        fields_to_probe.append(("verifier", patch.verifier_model))
    if patch.judge_model is not None:
        fields_to_probe.append(("judge", patch.judge_model))

    # If the operator only changed the Ollama tunnel URL (no model fields),
    # still validate it by probing the current executor model against the new
    # URL — otherwise a typo'd/dead tunnel could be persisted unchecked.
    if (
        new_provider == "ollama"
        and patch.ollama_base_url is not None
        and patch.ollama_base_url != (current.ollama_base_url or "")
        and not fields_to_probe
    ):
        fields_to_probe.append(("executor", current.executor_model))

    # 2. Probe each (provider, model) pair. Provider keys must be present
    #    (or it must be Ollama) — otherwise the probe short-circuits with
    #    a clear reason instead of firing a doomed HTTP request.
    probe_report: list[dict] = []
    failures: list[dict] = []
    for role, model in fields_to_probe:
        result = await probe_model_liveness(new_provider, model, base_url=probe_ollama_base)
        entry = {
            "role": role,
            "provider": new_provider,
            "model": model,
            "live": result.live,
            "status_code": result.status_code,
            "reason": result.reason,
            "elapsed_ms": result.elapsed_ms,
        }
        probe_report.append(entry)
        if not result.live:
            failures.append(entry)

    if failures:
        # Refuse to persist — return 422 with the full probe report so the
        # UI can highlight which role model failed and why.
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Refusing to persist a dead model (liveness probe failed)",
                "failures": failures,
                "probe_report": probe_report,
            },
        )

    # 3. All probes green — persist. ``set_brain_config`` invalidates the
    #    brain_policy cache too so the next agent run picks up the change.
    applied = await _set_brain_config(patch, actor=actor)
    log.info(
        "Brain config updated by %s: provider=%s planner=%s executor=%s verifier=%s judge=%s",
        actor, applied.primary_provider,
        applied.planner_model, applied.executor_model,
        applied.verifier_model, applied.judge_model,
    )
    return {
        "config": applied.model_dump(mode="json"),
        "probe_report": probe_report,
    }


class BrainTestRequest(BaseModel):
    """Body for POST /admin/api/policy/brain/test — probe without saving."""

    provider: str
    model: str
    # Optional Ollama base URL to test a typed-but-unsaved tunnel before Apply.
    base_url: str | None = None


@app.post("/admin/api/policy/brain/test")
async def test_brain_model_route(
    body: BrainTestRequest,
    user: dict = Depends(get_current_user),
):
    """Probe a ``(provider, model)`` pair without persisting.

    Powers the UI "Test" button next to each model field. Returns the same
    :class:`ProbeResult` shape the PATCH endpoint produces so the UI can
    reuse the same render code. ``base_url`` lets the Brain card validate a
    new Ollama tunnel URL before it's saved.
    """
    _require_admin(user)
    result = await probe_model_liveness(body.provider, body.model, base_url=body.base_url)
    return {
        "provider": result.provider,
        "model": result.model,
        "live": result.live,
        "status_code": result.status_code,
        "reason": result.reason,
        "elapsed_ms": result.elapsed_ms,
    }


# ── N5: mutating Telegram control — service-token-gated PR merge ─────────────
# Roadmap item N5: the operator must be able to merge an approved PR from the
# phone (the ``/merge <pr>`` Telegram command). This endpoint is gated by the
# service token (services.service_token.require_service_token) — NOT by user
# auth — because the Telegram bot doesn't carry a user session.
#
# Safety invariants (the bot enforces these client-side too, but the backend
# is the source of truth):
#   1. The PR must be mergeable (mergeable_state == 'clean' or 'unstable').
#   2. The PR must NOT be a draft.
#   3. The PR's CI must be green (all required checks passed).
#   4. The merge method is 'squash' (keeps master linear; matches the existing
#      auto-merge.yml convention for agency PRs).
#   5. Every merge is logged with actor='service:telegram' + the PR number +
#      sha, so the operator can audit who merged what.

class PRMergeRequest(BaseModel):
    """Body for POST /admin/api/prs/{number}/merge — service-token-gated."""
    # Optional: the SHA the caller expects to be merging. If set and the
    # actual head SHA differs, the merge is rejected with 409 Conflict —
    # prevents a stale "merge this" command from merging a different commit
    # than the one the operator reviewed.
    expected_sha: str | None = Field(default=None, max_length=64)
    # Optional: merge method override ('squash' | 'merge' | 'rebase').
    # Defaults to 'squash' (matches auto-merge.yml convention).
    merge_method: str | None = Field(default=None, pattern=r"^(squash|merge|rebase)$")


@app.post("/admin/api/prs/{number}/merge")
async def merge_pr_route(
    number: int,
    body: PRMergeRequest,
    request: Request,
):
    """Merge a PR via the GitHub API. Service-token-gated (N5).

    Returns the merge commit SHA + the PR's new state. The endpoint refuses
    to merge a draft, a PR with failing CI, or a PR whose head SHA doesn't
    match ``expected_sha`` (when provided).
    """
    from services.service_token import is_service_token_configured, verify_service_token

    # ── Auth (service token only — no user-session fallback for /merge) ──────
    # /setbrain accepts either path because the dashboard also uses it. /merge
    # is Telegram-only — the dashboard already has a "Merge" button via the
    # GitHub UI, so we don't need a user-session path here. Fail-closed if
    # the service token isn't configured.
    if not is_service_token_configured():
        raise HTTPException(
            status_code=503,
            detail="Service token not configured — set SERVICE_TOKEN to enable Telegram mutating control.",
        )
    if not verify_service_token(request.headers.get("X-Service-Token")):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Service-Token header.")

    token = (
        os.environ.get("GH_PAT")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
    )
    if not token:
        raise HTTPException(
            status_code=503,
            detail="Backend has no GH_PAT configured — cannot call GitHub merge API.",
        )

    repo = os.environ.get("GITHUB_REPOSITORY") or "strikersam/autonomous-ai-agency"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }
    import urllib.request as _urllib_request
    import urllib.error as _urllib_error

    # 1. Fetch the PR to verify mergeability + CI state.
    try:
        pr_req = _urllib_request.Request(
            f"https://api.github.com/repos/{repo}/pulls/{number}",
            headers=headers,
        )
        with _urllib_request.urlopen(pr_req, timeout=30) as resp:
            pr_data = json.loads(resp.read().decode())
    except _urllib_error.HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(status_code=404, detail=f"PR #{number} not found in {repo}.")
        raise HTTPException(status_code=502, detail=f"GitHub API error: HTTP {exc.code}")

    if pr_data.get("draft"):
        raise HTTPException(status_code=422, detail=f"PR #{number} is a draft — refusing to merge.")
    if pr_data.get("mergeable_state") not in ("clean", "unstable"):
        # 'dirty' / 'blocked' / 'behind' / 'unknown' all refuse — the operator
        # needs to resolve conflicts or wait for CI before retrying.
        raise HTTPException(
            status_code=422,
            detail=(
                f"PR #{number} is not mergeable "
                f"(mergeable_state={pr_data.get('mergeable_state')!r}) — "
                "resolve conflicts / wait for CI and retry."
            ),
        )

    head_sha = pr_data.get("head", {}).get("sha", "")
    if body.expected_sha and body.expected_sha != head_sha:
        raise HTTPException(
            status_code=409,
            detail=(
                f"PR #{number} head SHA is {head_sha[:8]}, "
                f"but expected_sha was {body.expected_sha[:8]}. "
                "Refusing to merge a commit you didn't review."
            ),
        )

    # 2. Verify CI is green (all required checks passed). The bot enforces
    #    this client-side too, but the backend is the source of truth.
    check_req = _urllib_request.Request(
        f"https://api.github.com/repos/{repo}/commits/{head_sha}/check-runs?per_page=100",
        headers=headers,
    )
    try:
        with _urllib_request.urlopen(check_req, timeout=30) as resp:
            check_data = json.loads(resp.read().decode())
    except _urllib_error.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"GitHub check-runs API error: HTTP {exc.code}")

    check_runs = check_data.get("check_runs", [])
    incomplete = [cr for cr in check_runs if cr.get("status") != "completed"]
    if incomplete:
        raise HTTPException(
            status_code=422,
            detail=(
                f"PR #{number} has {len(incomplete)} incomplete check(s) — "
                "wait for CI to finish and retry."
            ),
        )
    failed = [
        cr for cr in check_runs
        if cr.get("conclusion") not in ("success", "skipped", "neutral")
    ]
    if failed:
        names = [cr.get("name", "?") for cr in failed[:5]]
        raise HTTPException(
            status_code=422,
            detail=(
                f"PR #{number} has {len(failed)} failed check(s): {names}. "
                "Refusing to merge a red PR."
            ),
        )

    # 3. All guards passed — merge via the GitHub API.
    method = body.merge_method or "squash"
    merge_payload = {
        "commit_title": pr_data.get("title", f"Merge PR #{number}"),
        "merge_method": method,
    }
    merge_req = _urllib_request.Request(
        f"https://api.github.com/repos/{repo}/pulls/{number}/merge",
        data=json.dumps(merge_payload).encode(),
        method="PUT",
        headers=headers,
    )
    try:
        with _urllib_request.urlopen(merge_req, timeout=30) as resp:
            merge_result = json.loads(resp.read().decode())
    except _urllib_error.HTTPError as exc:
        # The GitHub merge endpoint returns 409 if the PR is not mergeable
        # for a reason the API didn't surface earlier (e.g. branch protection).
        detail_body = exc.read().decode()[:200] if exc.fp else ""
        raise HTTPException(
            status_code=502,
            detail=f"GitHub merge API error: HTTP {exc.code} — {detail_body}",
        )

    merge_sha = merge_result.get("sha")
    # 4. Log the action for audit. The bot also echoes this back to Telegram
    #    for confirmation (the roadmap's "every mutating action is logged to
    #    the decision log and echoed back to Telegram for confirmation").
    log.info(
        "service-token: MERGE pr=#%d repo=%s method=%s sha=%s actor=service:telegram",
        number, repo, method, (merge_sha or "")[:8],
    )
    return {
        "merged": True,
        "pr_number": number,
        "merge_sha": merge_sha,
        "method": method,
        "actor": "service:telegram",
    }


def _chat_provider_policy(
    *, allow_commercial_fallback_once: bool = False
) -> dict[str, bool]:
    policy = get_runtime_manager().get_policy()
    never_paid = bool(policy.get("never_use_paid_providers", True))
    require_approval = bool(policy.get("require_approval_before_paid_escalation", True))
    return {
        "never_use_paid_providers": never_paid,
        "require_approval_before_paid_escalation": require_approval,
        "allow_commercial_fallback": (not never_paid)
        and (allow_commercial_fallback_once or not require_approval),
    }


async def _build_provider_router(
    *,
    primary_provider_id: Optional[str],
    allow_commercial_fallback_once: bool = False,
) -> tuple[ProviderRouter, dict[str, bool], dict]:
    records = await _list_configured_provider_records()
    policy = _chat_provider_policy(
        allow_commercial_fallback_once=allow_commercial_fallback_once
    )
    router = ProviderRouter.from_provider_records(
        records,
        primary_provider_id=primary_provider_id,
        include_commercial=not policy["never_use_paid_providers"],
    )
    primary = (
        next(
            (
                record
                for record in records
                if record.get("provider_id") == router.providers[0].provider_id
            ),
            _fallback_local_provider_record(),
        )
        if router.providers
        else _fallback_local_provider_record()
    )
    return router, policy, primary


async def call_llm(
    messages: list[dict],
    *,
    model: Optional[str] = None,
    temperature: float = 0.3,
    provider_id: Optional[str] = None,
    allow_commercial_fallback_once: bool = False,
    max_retries: int = 2,
    provider_timeout_sec: float = 300.0,
    observation: Optional[Dict[str, object]] = None,
) -> str:
    provider = (
        await get_db().providers.find_one({"provider_id": provider_id})
        if provider_id
        else await get_active_provider()
    )
    if not provider:
        provider = _fallback_local_provider_record()
    provider_type = str(provider.get("type") or "openai-compatible")
    started_at = datetime.now(timezone.utc)
    try:
        router, policy, primary_provider = await _build_provider_router(
            primary_provider_id=str(provider.get("provider_id") or "") or None,
            allow_commercial_fallback_once=allow_commercial_fallback_once,
        )
        result = await router.chat_completion(
            {
                "model": model
                or primary_provider.get("default_model")
                or provider.get("default_model")
                or OLLAMA_MODEL,
                "messages": messages,
                "temperature": temperature,
                "stream": False,
            },
            max_retries=max_retries,
            provider_timeout_sec=provider_timeout_sec,
            allow_commercial_fallback=policy["allow_commercial_fallback"],
        )
        response_payload = result.response.json()
        response_text = extract_openai_text(response_payload)
        if observation:
            try:
                usage = response_payload.get("usage") if isinstance(response_payload, dict) else {}
                usage = usage if isinstance(usage, dict) else {}
                emit_chat_observation(
                    email=str(observation.get("email") or "unknown"),
                    department=str(observation.get("department") or "general"),
                    key_id=str(observation.get("key_id")) if observation.get("key_id") else None,
                    model=result.model or response_payload.get("model") or model or OLLAMA_MODEL,
                    messages=messages,
                    output_text=response_text,
                    prompt_tokens=int(usage.get("prompt_tokens") or 0),
                    completion_tokens=int(usage.get("completion_tokens") or 0),
                    latency_ms=max(0, int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)),
                    routing_meta={
                        "provider_id": result.provider.provider_id,
                        "provider_type": result.provider.type,
                        "attempt_count": len(result.attempts),
                    },
                    task_name=str(observation.get("task_name") or "chat completion"),
                )
            except Exception as exc:
                log.warning("Langfuse emit failed for hosted chat: %s", exc)
        return response_text
    except CommercialFallbackRequiredError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "approval_required": True,
                "commercial_candidates": exc.candidates,
            },
        ) from exc
    except ProviderFallbackError as exc:
        log.error("LLM provider fallback exhausted: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        # Surface helpful provider-specific guidance.
        status = exc.response.status_code
        detail = (
            f"LLM call failed ({provider_type}, HTTP {status}): {exc.response.text}"
        )
        if status in (401, 403) and provider_type in (
            "huggingface",
            "openai-compatible",
        ):
            detail = (
                f"{detail}\n\n"
                "This provider requires an API token. Set it in Providers → API Key "
                "or via HF_TOKEN / HUGGINGFACE_API_TOKEN for the default Hugging Face provider."
            )
        raise HTTPException(status_code=502, detail=detail) from exc
    except Exception as exc:
        log.error("LLM call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}") from exc


# ─── Chat Sessions ──────────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    content: str
    session_id: Optional[str] = None
    model: Optional[str] = None
    provider_id: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    agent_mode: bool = (
        False  # When True, forces multi-agent orchestration regardless of complexity
    )
    allow_commercial_fallback_once: bool = False
    context: Optional[Dict] = None  # Company/repo/systems context from frontend chips


_DIRECT_CHAT_PROVIDER_TIMEOUT_SEC = 20.0
_DIRECT_CHAT_MAX_RETRIES = 0


async def _persist_agent_chat_response(
    *,
    session_id: str,
    user_id: str,
    storage_mode: str,
    db_session_id: Optional[ObjectId],
    title: str,
    provider_id: Optional[str],
    model: Optional[str],
    temperature: Optional[float],
    messages: list[dict],
    created_at: Optional[str],
    response_text: str,
) -> None:
    final_messages = list(messages) + [{"role": "assistant", "content": response_text}]
    await _persist_chat_session(
        session_id=session_id,
        user_id=user_id,
        storage_mode=storage_mode,
        db_session_id=db_session_id,
        title=title,
        provider_id=provider_id,
        model=model,
        temperature=temperature,
        messages=final_messages,
        created_at=created_at,
    )


async def _agent_timeout_fallback_response(
    *,
    content: str,
    provider_id: Optional[str],
    model: Optional[str],
    provider_default_model: Optional[str],
    temperature: float,
    session_model: Optional[str],
    allow_commercial_fallback_once: bool,
    observation: Optional[Dict[str, object]] = None,
) -> str:
    fallback_messages = [
        {
            "role": "system",
            "content": (
                "You are recovering from an agent-mode timeout. The tool-using agent "
                "did not finish before the hosted request deadline. Provide the most "
                "useful possible advisory answer without claiming any files were changed. "
                "For code-edit tasks, include likely root cause, exact proposed edits, "
                "tests to add, and a conventional commit message when relevant."
            ),
        },
        {"role": "user", "content": content},
    ]
    candidate_models: list[Optional[str]] = []
    for candidate in (model, provider_default_model, session_model, None):
        if candidate not in candidate_models:
            candidate_models.append(candidate)

    last_exc: Optional[Exception] = None
    recovered: Optional[str] = None
    for candidate in candidate_models:
        try:
            recovered = await asyncio.wait_for(
                call_llm(
                    fallback_messages,
                    model=candidate,
                    temperature=temperature,
                    provider_id=provider_id,
                    allow_commercial_fallback_once=allow_commercial_fallback_once,
                    observation=observation,
                ),
                timeout=15,
            )
            break
        except Exception as exc:
            last_exc = exc
            continue

    if recovered is None:
        assert last_exc is not None
        raise last_exc

    return (
        "⚠️ Agent Mode timed out before tool execution completed. "
        "Here is a direct recovery answer without repository side effects:\n\n"
        f"{recovered}"
    )


def _chat_error_detail_text(detail: object) -> str:
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        nested_detail = detail.get("detail")
        if isinstance(nested_detail, str) and nested_detail.strip():
            return nested_detail.strip()
    if isinstance(detail, str):
        return detail.strip()
    return str(detail).strip()


def _direct_chat_recovery_attempts(
    *, provider_id: Optional[str], requested_model: Optional[str]
) -> list[tuple[Optional[str], Optional[str]]]:
    attempts: list[tuple[Optional[str], Optional[str]]] = []
    if requested_model:
        attempts.append((provider_id, None))
    attempts.append((None, None))

    deduped: list[tuple[Optional[str], Optional[str]]] = []
    for candidate in attempts:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


async def _recover_direct_chat_response(
    *,
    llm_messages: list[dict],
    provider_id: Optional[str],
    requested_model: Optional[str],
    session_model: Optional[str],
    temperature: float,
    allow_commercial_fallback_once: bool,
    failure_detail: str,
    observation: Optional[Dict[str, object]] = None,
) -> str:
    recovery_model = requested_model or session_model
    log.warning("Direct chat primary attempt failed: %s", failure_detail)

    for recovery_provider_id, recovery_requested_model in _direct_chat_recovery_attempts(
        provider_id=provider_id,
        requested_model=recovery_model,
    ):
        log.info(
            "Attempting direct-chat recovery with provider=%s model=%s",
            recovery_provider_id or "auto",
            recovery_requested_model or "provider-default",
        )
        try:
            recovered = await call_llm(
                llm_messages,
                model=recovery_requested_model,
                temperature=temperature,
                provider_id=recovery_provider_id,
                allow_commercial_fallback_once=allow_commercial_fallback_once,
                max_retries=_DIRECT_CHAT_MAX_RETRIES,
                provider_timeout_sec=_DIRECT_CHAT_PROVIDER_TIMEOUT_SEC,
                observation=observation,
            )
            return (
                "⚠️ The selected provider or model did not answer reliably, so I "
                "recovered this reply using the next healthy fallback:\n\n"
                f"{recovered}"
            )
        except HTTPException as exc:
            if (
                exc.status_code == 409
                and isinstance(exc.detail, dict)
                and exc.detail.get("approval_required")
            ):
                raise
            log.warning(
                "Direct-chat recovery attempt failed with HTTP %s: %s",
                exc.status_code,
                _chat_error_detail_text(exc.detail),
            )
            continue
        except Exception as exc:
            log.warning("Direct-chat recovery attempt failed: %s", exc)
            continue

    return (
        "⚠️ Direct chat could not reach a healthy LLM provider, so I did not "
        "fabricate an answer.\n\n"
        f"Last failure: {failure_detail}\n\n"
        "Next steps:\n"
        "• Open Providers and run Test on the configured backends.\n"
        "• If a specific model was selected, switch back to the provider default model.\n"
        "• Retry once the healthy provider indicator is green."
    )


@app.post("/api/chat/send")
async def chat_send(body: ChatMessage, user: dict = Depends(get_current_user)):
    uid = user["_id"]
    sid = body.session_id
    _db_limited = False
    session_storage = "db"
    db_session_id = _safe_object_id(sid)
    if not sid:
        try:
            active = await get_active_provider()
            default_pid = active.get("provider_id") if active else "ollama-local"
            result = await get_db().chat_sessions.insert_one(
                {
                    "user_id": uid,
                    "title": body.content[:60],
                    "provider_id": body.provider_id or default_pid,
                    "model": body.model or None,
                    "temperature": body.temperature
                    if body.temperature is not None
                    else None,
                    "messages": [],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            sid = str(result.inserted_id)
            db_session_id = _safe_object_id(sid)
        except Exception:
            sid = str(uuid.uuid4())
            _db_limited = True
            session_storage = "fallback"
            db_session_id = None
    try:
        session = (
            await get_db().chat_sessions.find_one({"_id": db_session_id, "user_id": uid})
            if (not _db_limited and db_session_id is not None)
            else None
        )
    except Exception:
        session = None
        _db_limited = True
        session_storage = "fallback"
    if not session:
        fallback_session = _get_limited_chat_session(sid, uid) if sid else None
        if fallback_session is not None:
            session = fallback_session
            session_storage = "fallback"
        elif not _db_limited and db_session_id is not None:
            raise HTTPException(status_code=404, detail="Session not found")
        else:
            session_storage = "fallback"
            session = _new_chat_session_record(
                session_id=sid,
                user_id=uid,
                title=body.content[:60],
                provider_id=body.provider_id,
                model=body.model,
                temperature=body.temperature,
                messages=[],
            )
    if not session and not _db_limited:
        raise HTTPException(status_code=404, detail="Session not found")
    session = session or {}
    messages = session.get("messages", [])
    messages.append({"role": "user", "content": body.content})
    model_messages = _sanitize_chat_messages(messages)

    wiki_pages = []
    try:
        async for page in get_db().wiki_pages.find({}, {"_id": 0, "slug": 1, "title": 1}).limit(50):
            wiki_pages.append(f"- {page['title']} ({page['slug']})")
    except Exception:
        pass
    wiki_index = "\n".join(wiki_pages) if wiki_pages else "(empty wiki)"

    provider_id = body.provider_id or session.get("provider_id")
    provider_hint_id = body.provider_id or None
    temperature = (
        body.temperature
        if body.temperature is not None
        else (session.get("temperature") or 0.3)
    )
    assistant_meta: Optional[Dict[str, object]] = None
    observation_payload = {
        "email": user.get("email") or ADMIN_EMAIL,
        "department": user.get("department") or "general",
        "key_id": user.get("key_id"),
        "task_name": "direct chat",
    }

    # Respect the chat toggle strictly: direct chat stays on the fast LLM path
    # unless the caller explicitly enables Agent Mode.
    use_agent = body.agent_mode

    # Hard timeouts so a stuck/thinking model never silently hangs the request.
    _AGENT_TIMEOUT_SEC = 45  # stay below hosted edge timeouts; recover with direct answer
    _LLM_TIMEOUT_SEC = 120  # 2 minutes for simple LLM calls

    if use_agent:
        _ensure_agent_session_exists(
            session_id=sid,
            user_id=str(uid),
            title=str(session.get("title") or body.content[:60]),
        )
        await _persist_chat_session(
            session_id=sid,
            user_id=uid,
            storage_mode=session_storage,
            db_session_id=db_session_id,
            title=str(session.get("title") or body.content[:60]),
            provider_id=provider_id,
            model=body.model or session.get("model"),
            temperature=temperature,
            messages=messages,
            created_at=session.get("created_at"),
        )

        role_models = await _resolve_user_agent_role_models(user)
        try:
            router, policy, primary_provider = await _build_provider_router(
                primary_provider_id=provider_hint_id,
                allow_commercial_fallback_once=body.allow_commercial_fallback_once,
            )
        except CommercialFallbackRequiredError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "approval_required": True,
                    "commercial_candidates": exc.candidates,
                    "session_id": sid,
                },
            ) from exc

        requested_agent_model = (
            body.model
            or session.get("model")
            or (primary_provider.get("default_model") if provider_hint_id else role_models["executor"])
            or primary_provider.get("default_model")
        )

        _job_req = AgentJobRequest(
            session_id=sid,
            owner_id=str(uid),
            instruction=body.content,
            requested_model=requested_agent_model,
            provider_id=primary_provider.get("provider_id"),
            runtime_id="internal_agent",
            allow_commercial_fallback=policy.get("allow_commercial_fallback", True),
        )
        job = _CHAT_AGENT_JOBS.create_job(
            session_id=_job_req.session_id,
            owner_id=_job_req.owner_id,
            instruction=_job_req.instruction,
            requested_model=_job_req.requested_model,
            provider_id=_job_req.provider_id,
            runtime_id=_job_req.runtime_id,
        )
        workspace_root = make_isolated_workspace(_CHAT_AGENT_WORKSPACE_ROOT, sid, job.job_id)
        job.workspace_path = str(workspace_root)

        async def _run_agent_job(heartbeat):
            heartbeat("planning", f"Planner model: {role_models['planner']}")
            response_text = await _run_agent_loop(
                instruction=body.content,
                session_messages=model_messages[:-1],
                wiki_index=wiki_index,
                provider=primary_provider,
                session_id=sid,
                requested_model=requested_agent_model,
                model_overrides=role_models,
                github_token=user.get("github_repo_token"),
                provider_chain=router.providers[1:],
                allow_commercial_fallback=policy["allow_commercial_fallback"],
                workspace_root=workspace_root,
                context=body.context,
            )
            heartbeat("verification", f"Judge model: {role_models['judge']}")
            await _persist_agent_chat_response(
                session_id=sid,
                user_id=uid,
                storage_mode=session_storage,
                db_session_id=db_session_id,
                title=str(session.get("title") or body.content[:60]),
                provider_id=provider_id,
                model=body.model or session.get("model") or requested_agent_model,
                temperature=temperature,
                messages=messages,
                created_at=session.get("created_at"),
                response_text=response_text,
            )
            return {
                "session_id": sid,
                "response": response_text,
                "runtime": {
                    "provider_id": primary_provider.get("provider_id"),
                    "workspace_path": str(workspace_root),
                    "requested_model": requested_agent_model,
                    "role_models": role_models,
                },
            }

        _CHAT_AGENT_JOBS.start_job(job.job_id, _run_agent_job)
        return JSONResponse(
            status_code=202,
            content={
                "session_id": sid,
                "job_id": job.job_id,
                "status": job.status,
                "phase": job.phase,
                "message": "Agent workflow queued. Poll the job endpoint for progress.",
            },
        )

    if not use_agent:
        github_connected = bool(user.get("github_repo_token"))
        assistant_meta = _direct_chat_agent_handoff(
            body.content,
            github_connected=github_connected,
        )
        if assistant_meta is not None:
            reason_text = ", ".join(assistant_meta.get("reasons", []))
            settings_hint = (
                " Connect GitHub in Settings first if you want repo access there."
                if assistant_meta.get("settings_route")
                else ""
            )
            response_text = (
                "This request needs Agent Mode because it involves "
                f"{reason_text}. In direct chat, I can explain patterns, but I should not "
                "invent repo-specific edits, GitHub actions, or workspace/container steps "
                "without tool access. Toggle Agent Mode (⚡) and retry this same prompt, "
                f"or paste the relevant files instead.{settings_hint}"
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": response_text,
                    "assistant_meta": assistant_meta,
                }
            )
            try:
                await _persist_chat_session(
                    session_id=sid,
                    user_id=uid,
                    storage_mode=session_storage,
                    db_session_id=db_session_id,
                    title=str(session.get("title") or body.content[:60]),
                    provider_id=provider_id,
                    model=body.model or session.get("model"),
                    temperature=temperature,
                    messages=messages,
                    created_at=session.get("created_at"),
                )
            except Exception:
                pass
            return {
                "session_id": sid,
                "response": response_text,
                "assistant_meta": assistant_meta,
                "message_count": len(messages),
            }

        github_hint = (
            " You also have GitHub repository access via the connected token — "
            "to perform repo operations (read files, commit, open PRs), the user must enable Agent Mode (the ⚡ toggle)."
            if github_connected
            else " GitHub repo access is not connected. If the user wants you to interact with a repository, "
            "ask them to go to Settings → GitHub and connect their account, then enable Agent Mode."
        )
        system_msg = {
            "role": "system",
            "content": (
                "You are an AI assistant with access to a persistent knowledge wiki and, when Agent Mode is on, "
                "GitHub repository tools (read files, create branches, commit changes, open pull requests). "
                f"Current wiki pages:\n{wiki_index}\n"
                "Use [[Page Title]] notation for wiki references. Be concise and helpful."
                + github_hint
            ),
        }
        # Compact context if history is long.
        history_for_llm = model_messages[-20:]
        if len(messages) > _COMPACT_THRESHOLD:
            provider = (
                await get_db().providers.find_one({"provider_id": provider_id})
                if provider_id
                else await get_active_provider()
            )
            if provider:
                cfg = LlmProviderConfig(
                    type=str(provider.get("type") or "openai-compatible"),
                    base_url=normalize_base_url(
                        str(provider.get("base_url") or OLLAMA_BASE)
                    ),
                    api_key=(str(provider.get("api_key") or "").strip() or None),
                    default_model=(
                        str(provider.get("default_model") or "").strip() or None
                    ),
                )
                history_for_llm = await _compact_context(
                    model_messages, cfg, body.model or session.get("model")
                )
        llm_messages = [system_msg] + history_for_llm

        # Phase 2 — ModelRouter model hint: classify the instruction and resolve
        # the best local model name.  Only overrides when the caller did not
        # explicitly request a model.  Failures are non-fatal; fall through to
        # whatever the provider default is.
        _direct_chat_model = body.model or session.get("model")
        if not _direct_chat_model:
            try:
                _routing = _get_model_router().route(
                    messages=[{"role": "user", "content": body.content}],
                    requested_model=provider_hint_id or None,
                )
                if _routing.resolved_model:
                    _direct_chat_model = _routing.resolved_model
                    log.debug(
                        "ModelRouter resolved %r (source=%s, task=%s) for direct chat",
                        _direct_chat_model,
                        _routing.selection_source,
                        _routing.task_type,
                    )
            except Exception as _mr_exc:
                log.debug("ModelRouter skipped: %s", _mr_exc)

        try:
            response_text = await asyncio.wait_for(
                call_llm(
                    llm_messages,
                    model=_direct_chat_model,
                    temperature=float(temperature),
                    provider_id=provider_hint_id,
                    allow_commercial_fallback_once=body.allow_commercial_fallback_once,
                    max_retries=_DIRECT_CHAT_MAX_RETRIES,
                    provider_timeout_sec=_DIRECT_CHAT_PROVIDER_TIMEOUT_SEC,
                    observation=observation_payload,
                ),
                timeout=_LLM_TIMEOUT_SEC,
            )
        except HTTPException as exc:
            if (
                exc.status_code == 409
                and isinstance(exc.detail, dict)
                and exc.detail.get("approval_required")
            ):
                detail = dict(exc.detail)
                detail.setdefault("session_id", sid)
                raise HTTPException(status_code=409, detail=detail) from exc
            try:
                response_text = await _recover_direct_chat_response(
                    llm_messages=llm_messages,
                    provider_id=provider_hint_id,
                    requested_model=_direct_chat_model,
                    session_model=session.get("model"),
                    temperature=float(temperature),
                    allow_commercial_fallback_once=body.allow_commercial_fallback_once,
                    failure_detail=_chat_error_detail_text(exc.detail),
                    observation=observation_payload,
                )
            except HTTPException as recovery_exc:
                if (
                    recovery_exc.status_code == 409
                    and isinstance(recovery_exc.detail, dict)
                    and recovery_exc.detail.get("approval_required")
                ):
                    detail = dict(recovery_exc.detail)
                    detail.setdefault("session_id", sid)
                    raise HTTPException(status_code=409, detail=detail) from recovery_exc
                raise
        except asyncio.TimeoutError:
            log.warning("LLM call timed out after %ds", _LLM_TIMEOUT_SEC)
            try:
                response_text = await _recover_direct_chat_response(
                    llm_messages=llm_messages,
                    provider_id=provider_hint_id,
                    requested_model=_direct_chat_model,
                    session_model=session.get("model"),
                    temperature=float(temperature),
                    allow_commercial_fallback_once=body.allow_commercial_fallback_once,
                    failure_detail=(
                        f"The initial direct-chat request exceeded {_LLM_TIMEOUT_SEC} seconds."
                    ),
                    observation=observation_payload,
                )
            except HTTPException as recovery_exc:
                if (
                    recovery_exc.status_code == 409
                    and isinstance(recovery_exc.detail, dict)
                    and recovery_exc.detail.get("approval_required")
                ):
                    detail = dict(recovery_exc.detail)
                    detail.setdefault("session_id", sid)
                    raise HTTPException(status_code=409, detail=detail) from recovery_exc
                raise

    assistant_message = {"role": "assistant", "content": response_text}
    if assistant_meta is not None:
        assistant_message["assistant_meta"] = assistant_meta
    messages.append(assistant_message)
    try:
        await _persist_chat_session(
            session_id=sid,
            user_id=uid,
            storage_mode=session_storage,
            db_session_id=db_session_id,
            title=str(session.get("title") or body.content[:60]),
            provider_id=provider_id,
            model=body.model or session.get("model"),
            temperature=temperature,
            messages=messages,
            created_at=session.get("created_at"),
        )
        await log_activity(
            "chat", f"Chat in session {sid[:8]}...", user_id=uid, meta={"session_id": sid}
        )
    except Exception:
        pass  # limited mode: session persistence is best-effort
    return {
        "session_id": sid,
        "response": response_text,
        "assistant_meta": assistant_meta,
        "message_count": len(messages),
    }


@app.get("/api/chat/agent-jobs/{job_id}")
async def get_chat_agent_job(job_id: str, user: dict = Depends(get_current_user)):
    job = _CHAT_AGENT_JOBS.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Agent job not found")
    if job.owner_id and job.owner_id != str(user.get("_id")):
        raise HTTPException(status_code=403, detail="Forbidden")
    return AgentJobSnapshot.from_agent_job(job).model_dump()


@app.post("/api/chat/agent-jobs/{job_id}/cancel")
async def cancel_chat_agent_job(job_id: str, user: dict = Depends(get_current_user)):
    job = _CHAT_AGENT_JOBS.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Agent job not found")
    if job.owner_id and job.owner_id != str(user.get("_id")):
        raise HTTPException(status_code=403, detail="Forbidden")
    cancelled = _CHAT_AGENT_JOBS.cancel_job(job_id)
    assert cancelled is not None
    return AgentJobSnapshot.from_agent_job(cancelled).model_dump()




# ── Agent HITL resume ─────────────────────────────────────────────────────────

class _ResumeRequest(BaseModel):
    action: Literal["approve", "deny", "input"] = "approve"
    input: str = ""


@app.post("/api/chat/resume/{session_id}")
async def resume_agent_chat_job(
    session_id: str,
    body: _ResumeRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """Resume a paused agent job for *session_id*.

    When the agent loop reaches a human-in-the-loop checkpoint (phase
    ``needs_approval`` or ``needs_input``) the frontend calls this endpoint
    with the user's decision.  Three actions are supported:

    * ``approve`` — allow the agent to continue (optionally with *input*).
    * ``deny``    — cancel the job; the user can send a new message.
    * ``input``   — provide a freeform text answer to a question the agent asked.
    """
    uid = str(user.get("_id", ""))
    # Find the most recent non-terminal job for this session that the caller owns.
    jobs = [
        j for j in _CHAT_AGENT_JOBS.list_jobs(session_id=session_id)
        if (j.owner_id is None or j.owner_id == uid)
        and j.status in {"queued", "running"}
    ]
    job = max(jobs, key=lambda j: j.created_at, default=None)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="No active agent job found for this session. "
                   "The job may have already completed or been cancelled.",
        )

    action = (body.action or "approve").lower().strip()

    if action == "deny":
        cancelled = _CHAT_AGENT_JOBS.cancel_job(job.job_id)
        if cancelled is None:
            raise HTTPException(status_code=409, detail="Job could not be cancelled.")
        return AgentJobSnapshot.from_agent_job(cancelled).model_dump()

    # approve / input — record the human decision as a progress event so the
    # polling client can observe it, then mark the job as continuing.
    # Full HITL wiring (waking a suspended coroutine) is Phase 3;
    # for now we surface the decision in the job's progress_events so the
    # frontend can display it and move on.
    job.progress_events.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "resuming",
        "message": f"Human decision: {action}"
                   + (f" — {body.input[:200]}" if body.input else ""),
    })
    job.phase = "resuming"
    return AgentJobSnapshot.from_agent_job(job).model_dump()


@app.get("/api/chat/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    sessions = []
    try:
        async for s in (
            get_db().chat_sessions.find({"user_id": user["_id"]}, {"messages": 0})
            .sort("updated_at", -1)
            .limit(50)
        ):
            s["_id"] = str(s["_id"])
            sessions.append(s)
    except Exception:
        pass
    sessions.extend(_list_limited_chat_sessions(user["_id"]))
    sessions.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    sessions = sessions[:50]
    return {"sessions": sessions}


@app.get("/api/chat/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)):
    db_session_id = _safe_object_id(session_id)
    session = None
    if db_session_id is not None:
        try:
            session = await get_db().chat_sessions.find_one(
                {"_id": db_session_id, "user_id": user["_id"]}
            )
        except Exception:
            session = None
    if not session:
        session = _get_limited_chat_session(session_id, user["_id"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session["_id"] = str(session.get("_id") or session_id)
    return session


@app.delete("/api/chat/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    db_session_id = _safe_object_id(session_id)
    deleted = False
    if db_session_id is not None:
        try:
            result = await get_db().chat_sessions.delete_one(
                {"_id": db_session_id, "user_id": user["_id"]}
            )
            deleted = result.deleted_count > 0
        except Exception:
            deleted = False
    if _delete_limited_chat_session(session_id, user["_id"]):
        deleted = True
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@app.get("/api/agent/status", response_model=AgentStatusResponse)
@app.get("/api/chat/agent-status", response_model=AgentStatusResponse)
async def get_agent_status(
    session_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    if not session_id:
        return AgentStatusResponse()

    _get_agent_session_for_user(session_id, str(user["_id"]))
    return _build_agent_status_snapshot(session_id)


@app.get("/api/agent/stream")
async def stream_agent_activity(
    session_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    if session_id:
        _get_agent_session_for_user(session_id, str(user["_id"]))

    async def event_stream():
        cursor = 0
        while True:
            if not session_id:
                yield ": waiting\n\n"
                await asyncio.sleep(1.0)
                continue

            session = AGENT_EVENT_STORE.get(session_id)
            if session is None:
                yield ": pending\n\n"
                await asyncio.sleep(1.0)
                continue

            events = AGENT_EVENT_STORE.get_events(
                session_id,
                from_position=cursor,
                limit=100,
            )
            if events:
                for event in events:
                    cursor = event.position + 1
                    payload = json.dumps(_normalize_agent_stream_event(session_id, event))
                    yield f"data: {payload}\n\n"
                continue

            yield ": keepalive\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Wiki Pages ─────────────────────────────────────────────────────────────────


class WikiPageCreate(BaseModel):
    title: str
    content: str = ""
    tags: list[str] = []


class WikiPageUpdate(BaseModel):
    title: str = None
    content: str = None
    tags: list[str] = None


def slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-")


@app.get("/api/wiki/pages")
async def list_wiki_pages(q: str = None, user: dict = Depends(get_current_user)):
    query = {"$text": {"$search": q}} if q else {}
    pages = []
    async for p in (
        get_db().wiki_pages.find(query, {"content": 0}).sort("updated_at", -1).limit(200)
    ):
        p["_id"] = str(p["_id"])
        pages.append(p)
    return {"pages": pages}


@app.get("/api/wiki/pages/{slug}")
async def get_wiki_page(slug: str, user: dict = Depends(get_current_user)):
    page = await get_db().wiki_pages.find_one({"slug": slug})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    page["_id"] = str(page["_id"])
    return page


@app.post("/api/wiki/pages")
async def create_wiki_page(
    body: WikiPageCreate, user: dict = Depends(get_current_user)
):
    slug = slugify(body.title)
    if await get_db().wiki_pages.find_one({"slug": slug}):
        raise HTTPException(
            status_code=409, detail="Page with this title already exists"
        )
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "title": body.title,
        "slug": slug,
        "content": body.content,
        "tags": body.tags,
        "source_count": 0,
        "created_at": now,
        "updated_at": now,
        "created_by": user["_id"],
    }
    result = await get_db().wiki_pages.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    await log_activity("wiki", f"Created page: {body.title}", user_id=user["_id"])
    return doc


@app.put("/api/wiki/pages/{slug}")
async def update_wiki_page(
    slug: str, body: WikiPageUpdate, user: dict = Depends(get_current_user)
):
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if body.title is not None:
        updates["title"] = body.title
    if body.content is not None:
        updates["content"] = body.content
    if body.tags is not None:
        updates["tags"] = body.tags
    result = await get_db().wiki_pages.update_one({"slug": slug}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Page not found")
    page = await get_db().wiki_pages.find_one({"slug": slug})
    page["_id"] = str(page["_id"])
    await log_activity("wiki", f"Updated page: {slug}", user_id=user["_id"])
    return page


@app.delete("/api/wiki/pages/{slug}")
async def delete_wiki_page(slug: str, user: dict = Depends(get_current_user)):
    result = await get_db().wiki_pages.delete_one({"slug": slug})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Page not found")
    await log_activity("wiki", f"Deleted page: {slug}", user_id=user["_id"])
    return {"ok": True}


@app.post("/api/wiki/lint")
async def lint_wiki(user: dict = Depends(get_current_user)):
    pages = []
    async for p in get_db().wiki_pages.find(
        {}, {"_id": 0, "title": 1, "slug": 1, "content": 1, "tags": 1}
    ):
        pages.append(p)
    if not pages:
        return {"issues": [], "summary": "Wiki is empty. Add some pages first."}
    page_list = "\n".join(
        [
            f"- {p['title']} (/{p['slug']}): {len(p.get('content', ''))} chars, tags: {p.get('tags', [])}"
            for p in pages
        ]
    )
    result = await call_llm(
        [
            {
                "role": "system",
                "content": "Analyze wiki structure. Return JSON with 'issues' (array of {type, severity, page, description}) and 'summary' (string).",
            },
            {"role": "user", "content": f"Wiki pages:\n{page_list}"},
        ]
    )
    try:
        json_match = re.search(r"\{.*\}", result, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            return parsed
    except Exception:
        pass
    return {"issues": [], "summary": result}


# ─── Source Ingestion ───────────────────────────────────────────────────────────


@app.post("/api/sources/ingest")
async def ingest_source(
    user: dict = Depends(get_current_user),
    file: UploadFile = File(None),
    url: str = Form(None),
    title: str = Form(None),
    content_text: str = Form(None),
):
    if not file and not url and not content_text:
        raise HTTPException(
            status_code=400, detail="Provide a file, URL, or text content"
        )
    raw_content, source_type, source_name = "", "text", title or "Untitled Source"
    if file:
        raw_content = (await file.read()).decode("utf-8", errors="replace")
        source_name = title or file.filename or "Uploaded File"
        source_type = "file"
    elif url:
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                resp = await c.get(url, follow_redirects=True)
                raw_content = resp.text[:50000]
            source_name = title or url
            source_type = "url"
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")
    elif content_text:
        raw_content = content_text
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "title": source_name,
        "type": source_type,
        "url": url,
        "raw_content": raw_content[:100000],
        "status": "pending",
        "summary": None,
        "created_at": now,
        "created_by": user["_id"],
    }
    result = await get_db().sources.insert_one(doc)
    source_id = str(result.inserted_id)
    try:
        summary = await call_llm(
            [
                {
                    "role": "system",
                    "content": "Summarize this source in 2-3 paragraphs. Extract key concepts. Format as markdown.",
                },
                {"role": "user", "content": raw_content[:8000]},
            ]
        )
        await get_db().sources.update_one(
            {"_id": ObjectId(source_id)},
            {"$set": {"status": "processed", "summary": summary}},
        )
        await log_activity(
            "ingest",
            f"Ingested: {source_name}",
            user_id=user["_id"],
            meta={"source_id": source_id},
        )
    except Exception as e:
        await get_db().sources.update_one(
            {"_id": ObjectId(source_id)},
            {"$set": {"status": "failed", "summary": f"Processing failed: {e}"}},
        )
    doc["_id"] = source_id
    return doc


@app.get("/api/sources")
async def list_sources(user: dict = Depends(get_current_user)):
    sources = []
    async for s in (
        get_db().sources.find({}, {"raw_content": 0}).sort("created_at", -1).limit(100)
    ):
        s["_id"] = str(s["_id"])
        sources.append(s)
    return {"sources": sources}


@app.get("/api/sources/{source_id}")
async def get_source(source_id: str, user: dict = Depends(get_current_user)):
    source = await get_db().sources.find_one({"_id": ObjectId(source_id)})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source["_id"] = str(source["_id"])
    return source


@app.delete("/api/sources/{source_id}")
async def delete_source(source_id: str, user: dict = Depends(get_current_user)):
    await get_db().sources.delete_one({"_id": ObjectId(source_id)})
    return {"ok": True}


# ─── Activity & Stats ──────────────────────────────────────────────────────────


@app.get("/api/activity")
async def _get_activity_impl(limit: int = 50) -> dict[str, Any]:
    logs = []
    try:
        async for entry in get_db().activity_log.find({}).sort("created_at", -1).limit(limit):
            entry["_id"] = str(entry["_id"])
            logs.append(entry)
    except Exception as exc:
        log.debug("Activity query unavailable: %s", exc)
    # Merge the always-on in-memory feeds so alerts work without a DB and reflect
    # recent business events (task failures, quick-notes, onboarding, etc.).
    if _ACTIVITY_BUFFER:
        logs.extend(list(_ACTIVITY_BUFFER)[:limit])
    if _ERROR_LOG_BUFFER:
        logs.extend(list(_ERROR_LOG_BUFFER)[:limit])
    logs.sort(
        key=lambda entry: str(
            entry.get("created_at") or entry.get("timestamp") or entry.get("time") or ""
        ),
        reverse=True,
    )
    # De-duplicate entries that exist in both Mongo and the in-memory buffer
    # (same event written to both by log_activity).
    deduped: list = []
    seen: set = set()
    for entry in logs:
        key = (
            str(entry.get("created_at") or entry.get("timestamp") or ""),
            str(entry.get("message") or ""),
            str(entry.get("category") or entry.get("level") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    logs = deduped[:limit]
    
    
    # Derive live platform alerts on read (no storage — restart/wipe-proof):
    # failed orchestrator runs, runs awaiting approval, and an empty scheduler.
    try:
        from services.workflow_orchestrator import get_workflow_orchestrator
        for run in (await get_workflow_orchestrator().list_runs(limit=25)) or []:
            rid = run.get("run_id", "?")
            status = run.get("status")
            ts = run.get("started_at") or ""
            if status == "failed":
                logs.insert(0, {
                    "id": f"alert-run-{rid}", "type": "error", "severity": "error",
                    "title": f"Run failed: {rid}",
                    "message": str(run.get("error") or "Execution failed")[:160],
                    "created_at": ts,
                })
            elif status == "awaiting_approval":
                logs.insert(0, {
                    "id": f"alert-approval-{rid}", "type": "approval", "severity": "warning",
                    "title": f"Run awaiting approval: {rid}",
                    "message": str(run.get("request") or "")[:160],
                    "created_at": ts,
                })
    except Exception as exc:  # never break the feed
        log.debug("Activity: orchestrator alert derivation unavailable: %s", exc)
    
    
    try:
        from agent.scheduler import get_scheduler
        jobs = get_scheduler().list()
        if not jobs:
            logs.insert(0, {
                "id": "alert-schedules-empty", "type": "infra", "severity": "error",
                "title": "No schedules registered — possible wipe after restart",
                "message": "All scheduler jobs are missing. Recreate supervisor cadences (see GitHub issue #504 / epic).",
                "created_at": "",
            })
    except Exception as exc:
        log.debug("Activity: scheduler alert derivation unavailable: %s", exc)
    
    
    logs = logs[:limit]
    # Return all key names AlertsBell reads: logs, events, activity, items, activities
    return {"logs": logs, "events": logs, "activity": logs, "items": logs, "activities": logs}


async def get_activity(limit: int = 50, user: dict = Depends(get_current_user)):
    return await _cached(f"activity:{limit}", ttl_s=3, producer=lambda: _get_activity_impl(limit))

@app.get("/api/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    return await _cached("dashboard:stats", ttl_s=10, producer=_produce_stats)


async def _produce_stats() -> dict[str, object]:
    wiki_count = await _fast_count(get_db().wiki_pages)
    source_count = await _fast_count(get_db().sources)
    session_count = await _fast_count(get_db().chat_sessions)
    log_count = await _fast_count(get_db().activity_log)
    provider_count = await _fast_count(get_db().providers)
    key_count = await _fast_count(get_db().api_keys)
    recent_pages: list[dict[str, object]] = []
    async for p in (
        get_db().wiki_pages.find({}, {"_id": 0, "title": 1, "slug": 1, "updated_at": 1})
        .sort("updated_at", -1)
        .limit(5)
    ):
        recent_pages.append(p)
    active_provider = await get_active_provider()
    return {
        "wiki_pages": wiki_count,
        "sources": source_count,
        "chat_sessions": session_count,
        "activity_entries": log_count,
        "providers": provider_count,
        "api_keys": key_count,
        "recent_pages": recent_pages,
        "llm_provider": active_provider.get("name", "None")
        if active_provider
        else "None",
        "ngrok_domain": NGROK_DOMAIN,
        "langfuse_configured": bool(LANGFUSE_PK and LANGFUSE_SK),
    }


# ─── Providers CRUD ─────────────────────────────────────────────────────────────


class ProviderCreate(BaseModel):
    provider_id: str
    name: str
    type: str = "openai-compatible"
    base_url: str
    api_key: str = ""
    default_model: str = ""
    is_default: bool = False


class ProviderUpdate(BaseModel):
    name: str = None
    base_url: str = None
    api_key: str = None
    default_model: str = None
    is_default: bool = None
    priority: int = Field(default=None, ge=-100, le=1000)



# BUG-19 fix: Provider policy endpoints (paid-provider kill switch)
@app.get("/api/providers/policy")
async def get_provider_policy_route(user: dict = Depends(get_current_user)):
    """Return the provider policy (paid-provider kill switch state)."""
    return await _get_provider_policy()


@app.put("/api/providers/policy")
async def update_provider_policy_route(
    update: ProviderPolicyUpdate,
    user: dict = Depends(get_current_user),
):
    """Update the provider policy (paid-provider kill switch)."""
    result = await _set_provider_policy(update)
    log.info(
        "Provider policy updated by %s: allow_paid=%s",
        user.get("email", "unknown"),
        update.allow_paid,
    )
    return result


@app.get("/api/providers")
async def list_providers(user: dict = Depends(get_current_user)):
    providers = []
    try:
        async for p in get_db().providers.find({}).sort("created_at", 1):
            p["_id"] = str(p["_id"])
            if p.get("api_key"):
                p["api_key_masked"] = (
                    p["api_key"][:8] + "..." + p["api_key"][-4:]
                    if len(p["api_key"]) > 12
                    else "***"
                )
            else:
                p["api_key_masked"] = ""
            p.pop("api_key", None)
            providers.append(p)
    except Exception:
        # Limited mode: MongoDB unavailable — return built-in defaults
        for p in _builtin_provider_records():
            p = dict(p)
            p.pop("api_key", None)
            p["api_key_masked"] = ""
            providers.append(p)
    return {"providers": providers}


@app.post("/api/providers")
async def create_provider(body: ProviderCreate, user: dict = Depends(get_current_user)):
    if await get_db().providers.find_one({"provider_id": body.provider_id}):
        raise HTTPException(status_code=409, detail="Provider ID already exists")
    if body.is_default:
        await get_db().providers.update_many({}, {"$set": {"is_default": False}})
    doc = body.dict()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    doc["status"] = "configured"
    await get_db().providers.insert_one(doc)
    await log_activity("provider", f"Added provider: {body.name}", user_id=user["_id"])
    return {"ok": True, "provider_id": body.provider_id}


@app.put("/api/providers/{provider_id}")
async def update_provider(
    provider_id: str, body: ProviderUpdate, user: dict = Depends(get_current_user)
):
    updates = {}
    for k, v in body.model_dump(exclude_none=True).items():
        updates[k] = v
    if body.is_default:
        await get_db().providers.update_many(
            {"provider_id": {"$ne": provider_id}}, {"$set": {"is_default": False}}
        )
    if updates:
        result = await get_db().providers.update_one(
            {"provider_id": provider_id}, {"$set": updates}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Provider not found")
    await log_activity(
        "provider", f"Updated provider: {provider_id}", user_id=user["_id"]
    )
    return {"ok": True}


@app.delete("/api/providers/{provider_id}")
async def delete_provider(provider_id: str, user: dict = Depends(get_current_user)):
    result = await get_db().providers.delete_one({"provider_id": provider_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Provider not found")
    await log_activity(
        "provider", f"Deleted provider: {provider_id}", user_id=user["_id"]
    )
    return {"ok": True}


@app.post("/api/providers/{provider_id}/test")
async def test_provider(provider_id: str, user: dict = Depends(get_current_user)):
    prov = await get_db().providers.find_one({"provider_id": provider_id})
    if not prov:
        raise HTTPException(status_code=404, detail="Provider not found")
    try:
        if prov["type"] == "ollama":
            resolved_base = _resolve_ollama_url(
                prov.get("base_url") or OLLAMA_BASE
            ).rstrip("/")
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{resolved_base}/api/tags")
                models = [m["name"] for m in r.json().get("models", [])]
            await get_db().providers.update_one(
                {"provider_id": provider_id}, {"$set": {"status": "online"}}
            )
            return {"ok": True, "models": models}
        else:
            cfg = LlmProviderConfig(
                type=str(prov.get("type") or "openai-compatible"),
                base_url=normalize_base_url(str(prov.get("base_url") or "")),
                api_key=(str(prov.get("api_key") or "").strip() or None),
                default_model=(str(prov.get("default_model") or "").strip() or None),
            )
            models = await list_openai_models(cfg)
            await get_db().providers.update_one(
                {"provider_id": provider_id}, {"$set": {"status": "online"}}
            )
            return {"ok": True, "models": models}
    except Exception as e:
        await get_db().providers.update_one(
            {"provider_id": provider_id}, {"$set": {"status": "error"}}
        )
        return {"ok": False, "error": "Provider test failed. Check API key and base URL in Providers settings."}


@app.get("/api/providers/{provider_id}/models")
async def provider_models(provider_id: str, user: dict = Depends(get_current_user)):
    prov = await get_db().providers.find_one({"provider_id": provider_id})
    if not prov:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Determine provider type key for catalog lookup.
    ptype = str(prov.get("type") or "openai-compatible")
    # Map provider_id to catalog key (e.g. "openrouter" → "openrouter", "together-ai" → "together")
    catalog_key = (
        provider_id
        if provider_id in PREDEFINED_MODELS
        else {
            "ollama-local": "ollama",
            "huggingface-serverless": "huggingface",
            "together-ai": "together",
        }.get(provider_id, ptype)
    )
    predefined = [m["id"] for m in PREDEFINED_MODELS.get(catalog_key, [])]

    if ptype == "ollama":
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{prov['base_url']}/api/tags")
                r.raise_for_status()
                live_models = [m["name"] for m in r.json().get("models", [])]
        except Exception:
            live_models = []
        # Merge: live models first, then predefined not already present
        seen = set(live_models)
        merged = live_models + [m for m in predefined if m not in seen]
        return {"provider_id": provider_id, "models": merged}

    cfg = LlmProviderConfig(
        type=ptype,
        base_url=normalize_base_url(str(prov.get("base_url") or "")),
        api_key=(str(prov.get("api_key") or "").strip() or None),
        default_model=(str(prov.get("default_model") or "").strip() or None),
    )
    try:
        live_models = await list_openai_models(cfg)
    except Exception:
        live_models = []

    # Always surface predefined models even if the live /v1/models call fails or returns nothing
    seen = set(live_models)
    merged = live_models + [m for m in predefined if m not in seen]
    if not merged and cfg.default_model:
        merged = [cfg.default_model]
    return {"provider_id": provider_id, "models": merged}


# ─── Models Hub ─────────────────────────────────────────────────────────────────


@app.get("/api/models/catalog")
async def models_catalog(user: dict = Depends(get_current_user)):
    """Return the full predefined model catalog with role/tier metadata."""
    return {"catalog": PREDEFINED_MODELS, "agent_role_models": AGENT_ROLE_MODELS}


@app.get("/api/models")
async def list_models(user: dict = Depends(get_current_user)):
    models = []
    # Try Ollama
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{OLLAMA_BASE}/api/tags")
            if r.status_code == 200:
                for m in r.json().get("models", []):
                    models.append(
                        {
                            "name": m["name"],
                            "size": m.get("size", 0),
                            "modified_at": m.get("modified_at", ""),
                            "source": "ollama-local",
                            "details": m.get("details", {}),
                        }
                    )
    except Exception:
        pass
    # Add cloud model references from providers
    async for prov in get_db().providers.find({"type": {"$ne": "ollama"}}):
        if prov.get("default_model"):
            models.append(
                {
                    "name": prov["default_model"],
                    "size": 0,
                    "modified_at": "",
                    "source": prov["provider_id"],
                    "details": {"provider": prov["name"]},
                }
            )
    return {"models": models}


class ModelPullRequest(BaseModel):
    name: str


@app.post("/api/models/pull")
async def pull_model(body: ModelPullRequest, user: dict = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=600) as c:
            r = await c.post(
                f"{OLLAMA_BASE}/api/pull", json={"name": body.name, "stream": False}
            )
            r.raise_for_status()
        await log_activity("models", f"Pulled model: {body.name}", user_id=user["_id"])
        return {"ok": True, "model": body.name}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Pull failed: {e}")


@app.delete("/api/models/{model_name}")
async def delete_model(model_name: str, user: dict = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.delete(f"{OLLAMA_BASE}/api/delete", json={"name": model_name})
            r.raise_for_status()
        await log_activity(
            "models", f"Deleted model: {model_name}", user_id=user["_id"]
        )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Delete failed: {e}")






# ─── Skills Registry & Recommendations ──────────────────────────────────────────
# Exposes the dynamic skill registry over HTTP so the frontend and agents can
# discover, search, and get context-aware recommendations.

try:
    from agent.skill_registry import SkillRegistry as _SkillRegistry, set_skill_registry
    _SKILL_REGISTRY = _SkillRegistry(
        github_token=(
            os.environ.get("GH_TOKEN")  # render.yaml / preflight use GH_TOKEN
            or os.environ.get("GITHUB_TOKEN")
            or os.environ.get("GH_PAT")
            or os.environ.get("GITHUB_ACCESS_TOKEN")
        )
    )
    set_skill_registry(_SKILL_REGISTRY)
except Exception as _sr_err:
    log.warning("Could not initialise SkillRegistry: %s", _sr_err)
    _SKILL_REGISTRY = None  # type: ignore[assignment]


@app.get("/api/skills")
async def list_skills(
    source: str | None = None,
    query: str | None = None,
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    """List all indexed skills, optionally filtered by source and/or query."""
    if _SKILL_REGISTRY is None:
        return {"skills": [], "total": 0}
    skills = _SKILL_REGISTRY.search(query) if query else _SKILL_REGISTRY.list(source=source)
    return {"skills": [s.as_dict() for s in skills[:limit]], "total": len(skills)}


@app.get("/api/skills/discover")
async def discover_remote_skills(user: dict = Depends(get_current_user)) -> dict[str, object]:
    """Preview what skills are available from remote GitHub registries without adding them."""
    if _SKILL_REGISTRY is None:
        return {"registries": [], "total": 0}
    await _SKILL_REGISTRY.refresh_remote()
    registries = {}
    for reg in GITHUB_REGISTRIES:
        rid = reg["id"]
        registries[rid] = {"id": rid, "owner": reg["owner"], "repo": reg["repo"],
                           "structure": reg.get("structure", "subdirs"), "skill_count": 0, "skills": []}
    for skill in _SKILL_REGISTRY.list():
        if skill.source.startswith("github:") and skill.registry_id in registries:
            registries[skill.registry_id]["skill_count"] += 1
            registries[skill.registry_id]["skills"].append({
                "skill_id": skill.skill_id, "name": skill.name,
                "description": (skill.description or "")[:120],
                "tags": skill.tags[:5], "tech_relevance": skill.tech_relevance[:5], "url": skill.url})
    result = sorted(registries.values(), key=lambda r: r["skill_count"], reverse=True)
    return {"registries": result, "total": sum(r["skill_count"] for r in result)}


@app.post("/api/skills/refresh")
async def refresh_skills(user: dict = Depends(get_current_user)):
    """Trigger a remote registry refresh (fetches from GitHub registries)."""
    if _SKILL_REGISTRY is None:
        return {"ok": False, "message": "SkillRegistry not available"}
    added = await _SKILL_REGISTRY.refresh_remote()
    total = len(_SKILL_REGISTRY.list())
    return {"ok": True, "new_skills": added, "total": total}


class SkillRecommendRequest(BaseModel):
    tech_stack: list[str] = []
    workflow_types: list[str] = []
    query: str | None = None
    limit: int = 10


@app.post("/api/skills/recommend")
async def recommend_skills(body: SkillRecommendRequest, user: dict = Depends(get_current_user)):
    """
    Return context-aware skill recommendations.
    Pass tech_stack (from scanner) and/or workflow_types (from active workflows)
    to get ranked, reason-annotated results.
    """
    if _SKILL_REGISTRY is None:
        return {"recommendations": []}
    recs = _SKILL_REGISTRY.recommend(
        tech_stack=body.tech_stack,
        workflow_types=body.workflow_types,
        query=body.query,
        limit=body.limit,
    )
    return {"recommendations": recs}


@app.get("/api/skills/recommend/auto")
async def auto_recommend_skills(
    company_id: str | None = None,
    limit: int = 10,
    user: dict = Depends(get_current_user),
):
    """
    Auto-recommend skills by reading the company's scan results and active
    workflows from the database — no client-side params needed.
    """
    if _SKILL_REGISTRY is None:
        return {"recommendations": [], "tech_stack": [], "workflow_types": []}

    tech_stack: list[str] = []
    workflow_types: list[str] = []
    uid = str(user.get("_id", user.get("id", "")))

    # Resolve company_id — use provided or fall back to user's only company
    cid = company_id
    if not cid:
        co = await get_db().companies.find_one({"user_id": uid})
        if co:
            cid = str(co["_id"])

    if cid:
        from bson import ObjectId as _ObjId
        try:
            co_doc = await get_db().companies.find_one({"_id": _ObjId(cid), "user_id": uid})
            if co_doc:
                # Pull tech stack from latest scan
                scan = await get_db().website_scans.find_one(
                    {"company_id": cid, "status": "success"},
                    sort=[("completed_at", -1)],
                )
                if scan:
                    detected = scan.get("detected_systems") or {}
                    for cat in ("frameworks", "cms", "databases", "payment", "analytics", "hosting"):
                        tech_stack.extend(detected.get(cat, []))
                    tech_stack.extend(scan.get("technologies", []))
                # Repo scan
                repo_scan = await get_db().repo_scans.find_one(
                    {"company_id": cid},
                    sort=[("completed_at", -1)],
                )
                if repo_scan:
                    inferred = repo_scan.get("inferred_stack") or {}
                    for cat in ("frameworks", "languages", "databases"):
                        tech_stack.extend(inferred.get(cat, []))
                # Active workflows
                async for wf in get_db().workflows.find(
                    {"company_id": cid, "is_active": True}
                ):
                    name = (wf.get("name") or "").lower()
                    triggers = wf.get("triggers") or []
                    workflow_types.append(name)
                    workflow_types.extend(triggers)
        except Exception as exc:
            log.debug("auto_recommend: error reading company data: %s", exc)

    tech_stack = list(dict.fromkeys(t for t in tech_stack if t))[:20]
    workflow_types = list(dict.fromkeys(w for w in workflow_types if w))[:10]

    recs = _SKILL_REGISTRY.recommend(
        tech_stack=tech_stack,
        workflow_types=workflow_types,
        limit=limit,
    )
    return {
        "recommendations": recs,
        "tech_stack": tech_stack,
        "workflow_types": workflow_types,
    }


@app.get("/api/skills/{skill_id:path}")
async def get_skill(skill_id: str, user: dict = Depends(get_current_user)):
    """Return full details for one skill by ID."""
    if _SKILL_REGISTRY is None:
        raise HTTPException(status_code=503, detail="SkillRegistry not available")
    skill = _SKILL_REGISTRY.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {**skill.as_dict(), "content": skill.raw_content}

# ─── MCP Server Configuration ───────────────────────────────────────────────────
# Stores user-configured MCP server records in the database.
# Status is *not* polled server-side (MCP servers run on the user's machine);
# the frontend sets status when it attempts a connection test.

class McpServerBody(BaseModel):
    name: str
    cmd: str
    desc: str = ""
    status: str = "idle"
    tools: int = 0


@app.get("/api/mcp/servers")
async def list_mcp_servers(user: dict = Depends(get_current_user)):
    """Return all MCP server configurations for this user."""
    uid = str(user.get("_id", user.get("id", "")))
    servers: list[dict] = []
    async for s in get_db().mcp_servers.find({"user_id": uid}).sort("created_at", 1):
        s["id"] = str(s.pop("_id"))
        servers.append(s)
    return {"servers": servers}


@app.post("/api/mcp/servers")
async def create_mcp_server(body: McpServerBody, user: dict = Depends(get_current_user)):
    """Add a new MCP server configuration."""
    uid = str(user.get("_id", user.get("id", "")))
    doc = {
        "user_id": uid,
        "name": body.name,
        "cmd": body.cmd,
        "desc": body.desc,
        "status": body.status,
        "tools": body.tools,
        "created_at": datetime.now(timezone.utc),
    }
    result = await get_db().mcp_servers.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@app.patch("/api/mcp/servers/{server_id}")
async def update_mcp_server(server_id: str, body: dict, user: dict = Depends(get_current_user)):
    """Update status/tools/name on an MCP server."""
    uid = str(user.get("_id", user.get("id", "")))
    from bson import ObjectId as _ObjId
    try:
        oid = _ObjId(server_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid server ID")
    allowed = {k: v for k, v in body.items() if k in ("name", "cmd", "desc", "status", "tools")}
    if not allowed:
        raise HTTPException(status_code=400, detail="No updatable fields provided")
    result = await get_db().mcp_servers.update_one(
        {"_id": oid, "user_id": uid}, {"$set": allowed}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Server not found")
    return {"ok": True}


@app.delete("/api/mcp/servers/{server_id}")
async def delete_mcp_server(server_id: str, user: dict = Depends(get_current_user)):
    """Remove an MCP server configuration."""
    uid = str(user.get("_id", user.get("id", "")))
    from bson import ObjectId as _ObjId
    try:
        oid = _ObjId(server_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid server ID")
    result = await get_db().mcp_servers.delete_one({"_id": oid, "user_id": uid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Server not found")
    return {"ok": True}

# ─── API Keys Management ───────────────────────────────────────────────────────


class ApiKeyCreate(BaseModel):
    email: str
    department: str = "general"
    label: str = ""


@app.get("/api/keys")
async def list_api_keys(user: dict = Depends(get_current_user)):
    keys = []
    async for k in get_db().api_keys.find({}, {"secret_hash": 0}).sort("created_at", -1):
        k["_id"] = str(k["_id"])
        keys.append(k)
    return {"keys": keys}


@app.post("/api/keys")
async def create_api_key(body: ApiKeyCreate, user: dict = Depends(get_current_user)):
    plain = "sk-wiki-" + secrets.token_urlsafe(32)
    key_id = "key_" + secrets.token_hex(4)
    hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
    doc = {
        "key_id": key_id,
        "email": body.email,
        "department": body.department,
        "label": body.label,
        "secret_hash": hashed,
        "prefix": plain[:12] + "...",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user["_id"],
    }
    await get_db().api_keys.insert_one(doc)
    await log_activity("keys", f"Created API key for {body.email}", user_id=user["_id"])
    return {"key_id": key_id, "api_key": plain, "email": body.email}


@app.delete("/api/keys/{key_id}")
async def delete_api_key(key_id: str, user: dict = Depends(get_current_user)):
    result = await get_db().api_keys.delete_one({"key_id": key_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Key not found")
    await log_activity("keys", f"Revoked API key: {key_id}", user_id=user["_id"])
    return {"ok": True}


# ─── Observability (Langfuse) ───────────────────────────────────────────────────


def _period_cutoff(period: str) -> datetime:
    now = datetime.now(timezone.utc)
    if period == "day":
        return now - timedelta(days=1)
    if period == "week":
        return now - timedelta(days=7)
    if period == "month":
        return now - timedelta(days=30)
    return datetime.fromtimestamp(0, tz=timezone.utc)


async def _load_local_metrics_since(cutoff: datetime) -> list[dict]:
    docs: list[dict] = []
    try:
        cursor = get_db().local_metrics.find({"timestamp": {"$gte": cutoff}}).sort("timestamp", 1)
        async for doc in cursor:
            docs.append(doc)
    except Exception:
        return []
    return docs


def _to_dt(value: object) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return None


@app.get("/api/observability/savings")
async def observability_savings(
    period: str = "month",
    bucket: str = "day",
    user: dict = Depends(get_current_user),
):
    cutoff = _period_cutoff(period)
    docs = await _load_local_metrics_since(cutoff)
    user_role = str(user.get("role", "user"))
    user_email = user.get("email")
    if user_role not in {"admin", "power_user"} and user_email:
        docs = [doc for doc in docs if doc.get("email") == user_email]

    total_saved = round(sum(float(doc.get("cost_usd") or 0.0) for doc in docs), 4)
    total_tokens = sum(int(doc.get("prompt_tokens") or 0) + int(doc.get("completion_tokens") or 0) for doc in docs)
    total_requests = len(docs)

    bucket_map: dict[str, dict] = {}
    for doc in docs:
        ts = _to_dt(doc.get("timestamp"))
        if ts is None:
            continue
        if bucket == "hour":
            stamp = ts.replace(minute=0, second=0, microsecond=0)
            label = stamp.strftime("%m-%d %H:00")
        else:
            stamp = ts.replace(hour=0, minute=0, second=0, microsecond=0)
            label = stamp.strftime("%m-%d")
        key = stamp.isoformat()
        entry = bucket_map.setdefault(
            key,
            {
                "timestamp": int(stamp.timestamp()),
                "date": label,
                "label": label,
                "saved_usd": 0.0,
                "savings_usd": 0.0,
                "tokens": 0,
                "requests": 0,
            },
        )
        saved = float(doc.get("cost_usd") or 0.0)
        entry["saved_usd"] += saved
        entry["savings_usd"] += saved
        entry["tokens"] += int(doc.get("prompt_tokens") or 0) + int(doc.get("completion_tokens") or 0)
        entry["requests"] += 1

    buckets = list(bucket_map.values())
    for entry in buckets:
        entry["saved_usd"] = round(entry["saved_usd"], 4)
        entry["savings_usd"] = round(entry["savings_usd"], 4)
    buckets.sort(key=lambda entry: entry["timestamp"])

    today_cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_saved = round(
        sum(float(doc.get("cost_usd") or 0.0) for doc in docs if (_to_dt(doc.get("timestamp")) or today_cutoff) >= today_cutoff),
        4,
    )

    user_rollup: dict[str, dict] = {}
    for doc in docs:
        email = str(doc.get("email") or "unknown")
        row = user_rollup.setdefault(
            email,
            {"user": email, "saved_usd": 0.0, "local_requests": 0, "cloud_requests": 0},
        )
        row["saved_usd"] += float(doc.get("cost_usd") or 0.0)
        row["local_requests"] += 1
    by_user = []
    for row in user_rollup.values():
        total_user_requests = row["local_requests"] + row["cloud_requests"]
        row["saved_usd"] = round(row["saved_usd"], 4)
        row["local_pct"] = round((row["local_requests"] / total_user_requests) * 100) if total_user_requests else 0
        by_user.append(row)
    by_user.sort(key=lambda row: row["saved_usd"], reverse=True)

    summary = {
        "period": period,
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "total_infra_cost_usd": 0.0,
        "total_commercial_eq_usd": total_saved,
        "total_savings_usd": total_saved,
    }
    return {
        "summary": summary,
        "time_series": buckets,
        "total_saved_usd": total_saved,
        "period_saved_usd": total_saved,
        "today_saved_usd": today_saved,
        "buckets": buckets,
        "by_user": by_user,
    }


@app.get("/api/observability/usage")
async def observability_usage(period: str = "month", user: dict = Depends(get_current_user)):
    cutoff = _period_cutoff(period)
    docs = await _load_local_metrics_since(cutoff)
    user_role = str(user.get("role", "user"))
    user_email = user.get("email")
    if user_role not in {"admin", "power_user"} and user_email:
        docs = [doc for doc in docs if doc.get("email") == user_email]

    by_model: dict[str, dict] = {}
    for doc in docs:
        model = str(doc.get("model") or "unknown")
        row = by_model.setdefault(model, {"requests": 0, "tokens": 0, "savings_usd": 0.0})
        row["requests"] += 1
        row["tokens"] += int(doc.get("prompt_tokens") or 0) + int(doc.get("completion_tokens") or 0)
        row["savings_usd"] += float(doc.get("cost_usd") or 0.0)
    for row in by_model.values():
        row["savings_usd"] = round(row["savings_usd"], 4)

    requests_24h = 0
    try:
        day_cutoff = _period_cutoff("day")
        requests_24h = len([doc for doc in await _load_local_metrics_since(day_cutoff) if user_role in {"admin", "power_user"} or doc.get("email") == user_email])
    except Exception:
        requests_24h = len(docs)

    total_requests = len(docs)
    return {
        "period": period,
        "total_requests": total_requests,
        "requests_24h": requests_24h,
        "total_tokens": sum(row["tokens"] for row in by_model.values()),
        "local_ratio": 1.0 if total_requests else 0.0,
        "escalations": 0,
        "by_model": by_model,
    }


@app.get("/api/observability/status")
async def observability_status(user: dict = Depends(get_current_user)):
    langfuse_pk, langfuse_sk, langfuse_base = _langfuse_credentials()
    configured = bool(langfuse_pk and langfuse_sk)
    status = {
        "configured": configured,
        "base_url": langfuse_base,
        "public_key_prefix": langfuse_pk[:12] + "..." if langfuse_pk else "",
    }
    if configured:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(
                    f"{langfuse_base}/api/public/health",
                    auth=(langfuse_pk, langfuse_sk),
                )
                if r.status_code == 200:
                    status["connected"] = True
                    status["message"] = "Langfuse connected"
                else:
                    status["connected"] = False
                    status["message"] = f"HTTP {r.status_code}"
        except Exception as e:
            status["connected"] = False
            status["message"] = str(e)
    else:
        status["connected"] = False
        status["message"] = (
            "Not configured — set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY"
        )
    return status


@app.get("/api/observability/dashboard-url")
async def observability_dashboard(user: dict = Depends(get_current_user)):
    langfuse_pk, _, langfuse_base = _langfuse_credentials()
    return {"url": langfuse_base, "configured": bool(langfuse_pk)}


@app.get("/api/observability/metrics")
async def observability_metrics(user: dict = Depends(get_current_user)):
    """Fetch basic usage metrics from the local_metrics collection."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)

    # 24h Aggregation
    pipeline = [
        {"$match": {"timestamp": {"$gte": day_ago}}},
        {
            "$group": {
                "_id": None,
                "total_requests": {"$sum": 1},
                "total_tokens": {
                    "$sum": {"$add": ["$prompt_tokens", "$completion_tokens"]}
                },
                "total_savings_usd": {"$sum": "$cost_usd"},
            }
        },
    ]
    cursor = get_db().local_metrics.aggregate(pipeline)
    agg = await cursor.to_list(length=1)
    summary = (
        agg[0]
        if agg
        else {"total_requests": 0, "total_tokens": 0, "total_savings_usd": 0}
    )
    summary.pop("_id", None)

    # Recent activity
    recent = []
    async for m in get_db().local_metrics.find({}).sort("timestamp", -1).limit(10):
        m["_id"] = str(m["_id"])
        m["timestamp"] = m["timestamp"].isoformat()
        recent.append(m)

    return {"summary_24h": summary, "recent_traces": recent}




@app.get("/api/observability/traces")
async def observability_traces(
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
):
    """Return paginated LLM traces from the local_metrics collection.

    Each trace includes model, provider, token counts, latency, and timestamp.
    Falls back to an empty list when Langfuse is not configured (local-only mode).
    """
    traces: list[dict] = []
    try:
        cursor = (
            get_db()
            .local_metrics.find({})
            .sort("timestamp", -1)
            .skip(offset)
            .limit(max(1, min(limit, 200)))
        )
        async for m in cursor:
            m["_id"] = str(m["_id"])
            if hasattr(m.get("timestamp"), "isoformat"):
                m["timestamp"] = m["timestamp"].isoformat()
            traces.append(m)
    except Exception as exc:
        log.warning("observability_traces: DB query failed: %s", exc)

    return {"traces": traces, "offset": offset, "limit": limit, "total": len(traces)}

# ─── System / Platform Info ─────────────────────────────────────────────────────


@app.get("/api/platform")
async def platform_info(user: dict = Depends(get_current_user)):
    return {
        "name": APP_NAME,
        "version": __version__,
        "ngrok_domain": NGROK_DOMAIN,
        "ngrok_configured": bool(NGROK_TOKEN),
        "langfuse_configured": bool(LANGFUSE_PK and LANGFUSE_SK),
        "langfuse_url": LANGFUSE_BASE,
        "ollama_base": OLLAMA_BASE,
        "github_repo": "https://github.com/strikersam/local-llm-server",
    }


@app.get("/api/ping")
async def ping() -> dict[str, object]:
    """Lightweight liveness probe — no external I/O."""
    return {"status": "ok", "pong": True}


@app.get("/api/kpi/public")
async def get_public_kpis() -> dict:
    """Public, read-only autonomy KPIs — no authentication required.

    Surfaces the aggregate autonomy counters from agent/kpi.py so the public
    site / public Doctor view can show a live read-only KPI strip (brief #6).
    Only non-sensitive process-wide counts are exposed — no user, company, repo,
    or task identifiers. Counters are cumulative since process start
    (``uptime_seconds`` gives the window); fields that are not yet instrumented
    are reported honestly rather than fabricated.
    """
    import datetime

    try:
        from agent.kpi import get_tracker
        snapshot = get_tracker().snapshot().as_dict()
    except Exception:  # pragma: no cover - defensive
        log.exception("Public KPI snapshot unavailable")
        return {
            "available": False,
            "error": "KPI service temporarily unavailable",
            "run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    derived = {
        "plans_started": snapshot.get("total_plans", 0),
        "steps_applied": snapshot.get("steps_applied", 0),
        "steps_failed": snapshot.get("steps_failed", 0),
        "prs_opened": snapshot.get("prs_created", 0),
        "commits_made": snapshot.get("commits_made", 0),
        "approval_gates_passed": snapshot.get("approval_gates_passed", 0),
        "approval_gates_rejected": snapshot.get("approval_gates_rejected", 0),
        "safety_blocks": snapshot.get("safety_blocks", 0),
        # Not yet instrumented in agent/kpi.py — surfaced as null, not faked, so the
        # public view never overstates autonomy. (brief: regression-after-auto-merge)
        "regressions_after_auto_merge": None,
    }
    return {
        "available": True,
        "window": "cumulative-since-process-start",
        "uptime_seconds": snapshot.get("uptime_seconds", 0),
        "metrics": snapshot,
        "summary": derived,
        "run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


# ── Autonomy status cache (non-blocking) ──────────────────────────────────────
# The CEO cycle + task execution can take 60-120s (NVIDIA NIM call).
# /api/autonomy/status must return immediately, so the CEO + dispatch
# run as a background task and the result is cached here. The cache is
# refreshed on every hit if the previous background task has completed.
_autonomy_ceo_cache: dict[str, object] = {"triggered": False}
_autonomy_dispatch_cache: dict[str, object] = {"ran": False}
_autonomy_bg_task: asyncio.Task | None = None
_autonomy_bg_last_run: float = 0.0

async def _autonomy_bg_cycle():
    """Background CEO cycle + task dispatch. Runs fire-and-forget."""
    global _autonomy_ceo_cache, _autonomy_dispatch_cache, _autonomy_bg_last_run
    try:
        import datetime
        # ── CEO agency: force-start + fire cycle ──
        ceo_status: dict[str, object] = {"triggered": False}
        try:
            from agent.scheduler import get_scheduler
            from tasks.automation import TaskAutomationService
            from tasks.store import get_task_store
            sched = get_scheduler()
            if sched._on_fire is None:
                task_automation = TaskAutomationService(store=get_task_store())
                sched.set_on_fire(task_automation.handle_scheduled_job)
                try:
                    import asyncio as _aio_loop
                    sched.attach_main_loop(_aio_loop.get_running_loop())
                except Exception:
                    pass
                ceo_status["scheduler_wired"] = True
        except Exception as exc:
            ceo_status["scheduler_wire_error"] = str(exc)[:100]

        try:
            from agent.agency import Agency, get_agency, set_agency, _gh_token, _gh_repo
            ceo_status["gh_token_set"] = bool(_gh_token())
            ceo_status["gh_repo"] = _gh_repo() or "MISSING"
            agency = get_agency()
            if agency is None or not agency._running:
                agency = Agency()
                try:
                    import asyncio as _aio
                    agency.attach_main_loop(_aio.get_running_loop())
                except Exception:
                    pass
                set_agency(agency)
                agency.start()
                ceo_status["started"] = True
            if agency is not None and agency._running:
                import asyncio as _asyncio
                result = await _asyncio.wait_for(agency.run_cycle(), timeout=60.0)
                ceo_status["triggered"] = True
                ceo_status["directives_issued"] = result.directives_issued
                ceo_status["cycle_id"] = result.cycle_id
                ceo_status["ceo_assessment"] = result.ceo_assessment[:200]
                ceo_status["quick_notes_seen"] = result.improvement_issues_seen
                try:
                    qn = agency._last_quick_notes
                    ceo_status["quick_notes_actionable"] = len(qn.get("actionable", []))
                    ceo_status["quick_notes_exhausted_closed"] = qn.get("exhausted_closed", 0)
                except Exception:
                    pass
                try:
                    import agent.agency as _ag
                    ceo_status["gh_api_status"] = _ag._last_gh_fetch_status
                    ceo_status["gh_api_count"] = _ag._last_gh_fetch_count
                    ceo_status["gh_api_error"] = _ag._last_gh_fetch_error[:100] if _ag._last_gh_fetch_error else ""
                except Exception:
                    pass
                ceo_status["cycle_id"] = result.cycle_id
        except Exception as exc:
            ceo_status["error"] = str(exc)[:200]
        _autonomy_ceo_cache = ceo_status

        # ── Task dispatch ──
        dispatch_status: dict[str, object] = {"ran": False}
        if os.environ.get("SELF_BOOTSTRAP_ENABLED", "true").strip().lower() in ("true", "1", "yes"):
            import asyncio as _aio_wait
            await _aio_wait.sleep(1.0)
            try:
                from tasks.store import get_task_store
                from tasks.service import TaskExecutionCoordinator
                store = get_task_store()
                pending = await store.list_pending(limit=1)
                if not pending:
                    try:
                        from tasks.models import Task
                        from tasks.service import TaskWorkflowService
                        import agent.agency as _ag
                        import httpx
                        token = _ag._gh_token()
                        repo = _ag._gh_repo()
                        if token and repo:
                            async with httpx.AsyncClient(timeout=15) as client:
                                resp = await client.get(
                                    f"https://api.github.com/repos/{repo}/issues",
                                    params={"state": "open", "per_page": "50", "sort": "created", "direction": "asc"},
                                    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                                )
                                if resp.status_code == 200:
                                    all_issues = [i for i in resp.json() if "pull_request" not in i]
                                    actionable = [
                                        i for i in all_issues
                                        if "quick-note:exhausted" not in [lb.get("name","") for lb in i.get("labels", [])]
                                    ]
                                    if actionable:
                                        issue = actionable[0]
                                        is_qn = "quick-note" in [lb.get("name","") for lb in issue.get("labels", [])]
                                        prefix = "quick-note" if is_qn else "issue"
                                        task = Task(
                                            owner_id="system",
                                            title=f"{prefix} #{issue['number']}: {issue['title'][:50]}",
                                            description=f"Implement GitHub issue #{issue['number']}: {issue['title']}",
                                            prompt=(issue.get("body") or "")[:2000],
                                            task_type="quick_note" if is_qn else "issue",
                                            tags=[lb["name"] for lb in issue.get("labels", [])] + ["needs-implementation"],
                                            source="ceo_direct",
                                            pending_agent_run=True,
                                        )
                                        wf = TaskWorkflowService(store=store)
                                        await wf.create_task(task, actor="system:ceo_direct")
                                        dispatch_status["direct_task_created"] = task.task_id
                                        dispatch_status["direct_issue_number"] = issue["number"]
                                        import asyncio as _aio_sync
                                        await _aio_sync.sleep(0.5)
                                        pending = await store.list_pending(limit=1)
                    except Exception as exc:
                        dispatch_status["direct_task_error"] = str(exc)[:100]
                if pending:
                    task_id = pending[0].task_id
                    dispatch_status["task_id"] = task_id
                    dispatch_status["task_title"] = pending[0].title[:60]
                    dispatch_status["pending_agent_run"] = pending[0].pending_agent_run
                    try:
                        from tasks.service import _brain_is_configured
                        dispatch_status["brain_configured"] = await _brain_is_configured()
                    except Exception as exc:
                        dispatch_status["brain_configured"] = f"error: {exc}"[:100]
                    try:
                        from runtimes.base import TaskSpec
                        from runtimes.adapters.internal_agent import InternalAgentAdapter
                        import services.workflow_orchestrator as _wo
                        task = pending[0]
                        task.status = "in_progress"
                        task.pending_agent_run = False
                        await store.update(task)
                        spec = TaskSpec(
                            task_id=task_id,
                            instruction=task.prompt or task.title,
                            task_type=task.task_type or "general",
                            workspace_path=str(ROOT_DIR),
                            context={"owner_id": task.owner_id, "title": task.title},
                        )
                        _bypass_token = _wo._BYPASS.set(True)
                        try:
                            adapter = InternalAgentAdapter({"workspace_root": str(ROOT_DIR)})
                            import asyncio as _aio2
                            result, decision = await _aio2.wait_for(
                                adapter.execute(spec), timeout=30.0
                            )
                        finally:
                            _wo._BYPASS.reset(_bypass_token)
                        task.result = result.output
                        task.status = "done" if result.success else "failed"
                        task.error_message = None if result.success else "Execution failed"
                        await store.update(task)
                        dispatch_status["ran"] = True
                        dispatch_status["result_status"] = task.status
                        dispatch_status["result_error"] = (task.error_message or "")[:100]
                    except Exception as exc:
                        dispatch_status["ran"] = False
                        dispatch_status["error"] = str(exc)[:200]
                        try:
                            task = await store.get(task_id)
                            if task:
                                task.status = "failed"
                                task.error_message = str(exc)[:500]
                                await store.update(task)
                        except Exception:
                            pass
                else:
                    dispatch_status["pending_count"] = 0
            except Exception as exc:
                dispatch_status["error"] = str(exc)[:200]
        _autonomy_dispatch_cache = dispatch_status
        _autonomy_bg_last_run = time.time()
    except Exception as exc:
        log.warning("Autonomy background cycle error: %s", exc)


@app.get("/api/autonomy/status")
async def autonomy_status() -> dict[str, object]:
    """Public autonomy readiness probe — no authentication required.

    A live deploy that is missing its brain key (``NVIDIA_API_KEY``) leaves
    every agent task with no LLM to reason with, which otherwise manifests as
    "nothing happens" with no visible cause. This probe makes that state
    explicit so a misconfigured deploy is diagnosable from the outside.

    The shape is a stable contract (see ``tests/test_autonomy_status.py``):
    ``brain`` (resolution + configured flag), ``loops`` (per-loop running
    state), ``loops_running`` (any loop alive), ``missing_secrets`` (env vars
    the operator still needs to set), and ``status`` — one of ``no_brain``,
    ``idle``, ``partial``, or ``autonomous``.
    """
    import datetime
    import importlib

    # ── Brain resolution (read env fresh; never the cached resolver, so this
    #    probe reflects the live environment rather than a startup snapshot). ──
    brain: dict[str, object]
    missing_secrets: list[str] = []
    try:
        from brain_policy import resolve_free_nvidia_brain
        nvidia = resolve_free_nvidia_brain()
    except Exception:  # pragma: no cover - defensive
        log.exception("autonomy_status: NVIDIA brain resolution failed")
        nvidia = None

    if nvidia is not None:
        nv_base, _nv_headers, nv_model = nvidia
        brain = {
            "configured": True,
            "provider": "nvidia-nim",
            "model": nv_model,
            "base_url": nv_base,
        }
    else:
        # No NVIDIA brain — check whether a local Ollama brain is configured
        # instead (laptop/desktop usage via BRAIN_PREFERENCE=ollama or a plain
        # OLLAMA_BASE). Only fall through to "no_brain" when neither is set.
        ollama_base = (
            os.environ.get("OLLAMA_BASE", "").strip()
            or os.environ.get("OLLAMA_BASE_URL", "").strip()
        )
        if ollama_base:
            brain = {
                "configured": True,
                "provider": "ollama",
                "model": OLLAMA_MODEL,
                "base_url": ollama_base,
            }
        else:
            brain = {
                "configured": False,
                "provider": None,
                "model": None,
                "base_url": None,
            }
            missing_secrets.append("NVIDIA_API_KEY")

    # ── Autonomy loops: report each engine's live running state. Under a bare
    #    TestClient (no lifespan startup) none are bootstrapped, so they read
    #    as not-running rather than erroring. ──
    loop_specs = (
        ("log_monitor", "agent.log_monitor", "get_log_monitor"),
        ("self_healing", "agent.self_healing", "get_self_healing_agent"),
        ("improvement_loop", "agent.improvement_loop", "get_improvement_loop"),
        ("trend_watcher", "agent.trend_watcher", "get_trend_watcher"),
    )
    loops: dict[str, bool] = {}
    for name, module_path, getter_name in loop_specs:
        running = False
        try:
            getter = getattr(importlib.import_module(module_path), getter_name)
            inst = getter()
            if inst is not None:
                # Engines that expose a `_running` flag report it; those that
                # don't (presence == running) default to True when bootstrapped.
                running = bool(getattr(inst, "_running", True))
        except Exception:  # pragma: no cover - defensive
            running = False
        loops[name] = running

    running_count = sum(1 for v in loops.values() if v)
    if not brain["configured"]:
        status = "no_brain"
    elif running_count == 0:
        status = "idle"
    elif running_count == len(loops):
        status = "autonomous"
    else:
        status = "partial"

    # ── Self-bootstrap status: shows whether the platform has onboarded itself
    #    as a company. Without this, "0 companies" on /api/doctor/public is
    #    opaque — the operator can't tell if self-bootstrap hasn't run yet,
    #    failed silently, or is still in progress.
    #
    #    Also TRIGGERS ensure_self_company() if no company exists yet — this
    #    runs on the request's event loop (the FastAPI main loop), so it
    #    safely touches Motor/aiosqlite clients. On Render free tier, the
    #    CEO agency thread can't reliably dispatch because the event loop
    #    stops pumping between requests. This probe ensures the self-bootstrap
    #    runs every time someone checks the status. ──
    self_bootstrap_status: dict[str, object] = {"enabled": False}
    try:
        from services.self_bootstrap import self_bootstrap_enabled, SELF_WEBSITE_URL, SELF_REPO_URL
        self_bootstrap_status["enabled"] = self_bootstrap_enabled()
        self_bootstrap_status["website_url"] = SELF_WEBSITE_URL
        self_bootstrap_status["repo_url"] = SELF_REPO_URL
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        # If self-bootstrap is enabled AND no company exists yet, try to
        # ensure the company exists. This runs on the request's event loop
        # (the FastAPI main loop), so it safely touches Motor/aiosqlite
        # clients. On Render free tier, the CEO agency thread can't reliably
        # dispatch because the event loop stops pumping between requests.
        # Skip in tests (SELF_BOOTSTRAP_ENABLED=false) to avoid interfering
        # with E2E/unit tests.
        from services.self_bootstrap import _find_self_company
        existing = await _find_self_company()
        if existing is None and self_bootstrap_status.get("enabled"):
            # No company yet — trigger ensure_self_company() on this
            # request's event loop. Idempotent: subsequent calls no-op.
            from services.self_bootstrap import ensure_self_company
            bootstrap_result = await ensure_self_company()
            self_bootstrap_status["last_result"] = bootstrap_result.get("status")
            # Re-read after bootstrap
            existing = await _find_self_company()
        if existing is not None:
            self_bootstrap_status["company_id"] = existing.id
            self_bootstrap_status["onboarding_status"] = existing.onboarding_status
            self_bootstrap_status["domain"] = existing.domain
        else:
            self_bootstrap_status["company_id"] = None
            self_bootstrap_status["onboarding_status"] = "not_started"
    except Exception as exc:  # pragma: no cover - defensive
        self_bootstrap_status["error"] = str(exc)

    # ── CEO agency: trigger a cycle on every status check ─────────────────
    #    On Render free tier, the CEO agency thread gets killed when the
    #    instance spins down between requests. The 5-min tick never fires.
    #    Triggering run_cycle() here ensures the CEO dispatches quick-note
    #    issues every time someone checks the status. The cycle is
    #    idempotent (deduplicates directives) and runs on the request's
    #    event loop, so it safely touches Motor/aiosqlite clients.
    # Return cached CEO + dispatch results (populated by background task)
    ceo_status = dict(_autonomy_ceo_cache)
    dispatch_status = dict(_autonomy_dispatch_cache)

    # Fire background CEO + dispatch cycle if not already running and
    # at least 30 seconds since last run
    import time as _time_mod
    global _autonomy_bg_task
    if (_autonomy_bg_task is None or _autonomy_bg_task.done()) and        (_time_mod.time() - _autonomy_bg_last_run > 30):
        try:
            _autonomy_bg_task = asyncio.create_task(_autonomy_bg_cycle())
        except Exception:
            pass

    # ── Company count:# ── Company count: mirrors the /api/doctor/public storage check so the
    #    autonomy probe is self-contained. Uses the safe list helper so a
    #    stale row with an invalid onboarding_status doesn't crash the probe. ──
    company_count = 0
    try:
        from services.self_bootstrap import _list_companies_safe
        companies = await _list_companies_safe()
        company_count = len(companies)
    except Exception:  # pragma: no cover - defensive
        pass

    # ── Loop fleet readiness: a legible, scored view of the whole autonomous
    #    loop fleet (Loop Engineering's loop-audit). Defensive — a missing or
    #    malformed registry must never break this contract, so failures degrade
    #    to None rather than raising. ──
    loop_readiness_summary: dict[str, object] | None = None
    try:
        from agent.loop_registry import load_registry_sync, loop_readiness, audit_drift
        _registry = load_registry_sync()
        _report = loop_readiness(_registry)
        _drift = audit_drift(_registry)
        loop_readiness_summary = {
            "score": _report.score,
            "grade": _report.grade,
            "total_loops": _report.total_loops,
            "by_level": _report.by_level,
            "self_heal_coverage": _report.self_heal_coverage,
            "dimensions": _report.dimensions,
            "drift_ok": _drift.ok,
            "est_monthly_tokens": _registry.estimate_monthly_tokens(),
        }
    except Exception:  # pragma: no cover - defensive
        log.exception("autonomy_status: loop readiness computation failed")

    # ── CRISPY run-history (N4 — burn-in evidence for EXPERIMENTAL → stable) ──
    # The roadmap demands data-backed promotion of crispy_workflow, not a flag
    # flip. Surface the run-history metric so the operator (and the autonomy
    # UI) can see whether the burn-in criteria are met. Defensive — never
    # break /api/autonomy/status if the engine isn't initialized.
    crispy_run_history: dict[str, object] | None = None
    try:
        from workflow.engine import get_engine as _get_crispy_engine
        _crispy_engine = _get_crispy_engine()
        crispy_run_history = _crispy_engine.crispy_run_history()
    except Exception:  # pragma: no cover - defensive
        log.debug("autonomy_status: crispy run-history unavailable", exc_info=True)

    return {
        "status": status,
        "brain": brain,
        "loops": loops,
        "loops_running": running_count > 0,
        "loop_readiness": loop_readiness_summary,
        "crispy_run_history": crispy_run_history,
        "missing_secrets": missing_secrets,
        "self_bootstrap": self_bootstrap_status,
        "ceo": ceo_status,
        "dispatch": dispatch_status,
        "company_count": company_count,
        "run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@app.get("/api/loops")
async def loops_overview() -> dict[str, object]:
    """Full Loop Engineering fleet view for the UI: the catalogued loops plus
    the loop-audit readiness score, loop-cost estimate, and drift status.

    Powers the Loops screen. Read-only and defensive — a missing/malformed
    ``loops/registry.yaml`` degrades to an empty fleet with an error note
    rather than raising, so the screen never hard-crashes.
    """
    try:
        from agent.loop_registry import load_registry_sync, loop_readiness, audit_drift
        registry = await asyncio.to_thread(load_registry_sync)
        report = loop_readiness(registry)
        drift = audit_drift(registry)
        loops = [
            {
                "id": l.id,
                "name": l.name,
                "pattern": l.pattern,
                "level": l.level,
                "trigger": l.trigger,
                "cadence": l.cadence,
                "runs_per_day": l.runs_per_day,
                "cost": l.cost,
                "source": l.source,
                "self_heal": l.self_heal,
                "gate": l.gate,
                "purpose": l.purpose,
                "est_monthly_tokens": l.estimate_monthly_tokens(),
            }
            for l in registry.loops
        ]
        return {
            "ok": True,
            "readiness": {
                "score": report.score,
                "grade": report.grade,
                "total_loops": report.total_loops,
                "by_level": report.by_level,
                "self_heal_coverage": report.self_heal_coverage,
                "gated_risky_coverage": report.gated_risky_coverage,
                "dimensions": report.dimensions,
                "notes": report.notes,
            },
            "drift": {
                "ok": drift.ok,
                "missing_from_registry": drift.missing_from_registry,
                "stale_sources": drift.stale_sources,
            },
            "est_monthly_tokens": registry.estimate_monthly_tokens(),
            "loops": loops,
        }
    except Exception as exc:  # pragma: no cover - defensive
        log.exception("loops_overview: failed to build loop fleet view")
        return {
            "ok": False,
            "error": str(exc),
            "readiness": None,
            "drift": None,
            "est_monthly_tokens": 0,
            "loops": [],
        }


@app.get("/api/autonomy/tick")
async def autonomy_tick() -> dict[str, object]:
    """Execute ONE pending task synchronously. Called by the cron workflow every 2 min.

    This is the agency's execution heartbeat. It:
    1. Fires the CEO cycle (background — fast)
    2. Picks up the oldest pending task
    3. Executes it via InternalAgentAdapter (NVIDIA NIM) with a 20s timeout
    4. Returns the result

    Unlike /api/autonomy/status, this endpoint BLOCKS until the task
    completes (or times out at 20s). The cron workflow is designed to
    wait for this.
    """
    import datetime
    result: dict[str, object] = {
        "run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ceo": {},
        "dispatch": {},
    }

    # 1. Fire CEO cycle in background (non-blocking)
    try:
        from agent.agency import Agency, get_agency, set_agency, _gh_token, _gh_repo
        # Wire scheduler on_fire if not done
        try:
            from agent.scheduler import get_scheduler
            from tasks.automation import TaskAutomationService
            from tasks.store import get_task_store
            sched = get_scheduler()
            if sched._on_fire is None:
                task_automation = TaskAutomationService(store=get_task_store())
                sched.set_on_fire(task_automation.handle_scheduled_job)
                try:
                    import asyncio as _aio_loop
                    sched.attach_main_loop(_aio_loop.get_running_loop())
                except Exception:
                    pass
        except Exception:
            pass

        agency = get_agency()
        if agency is None or not agency._running:
            agency = Agency()
            try:
                import asyncio as _aio
                agency.attach_main_loop(_aio.get_running_loop())
            except Exception:
                pass
            set_agency(agency)
            agency.start()

        if agency is not None and agency._running:
            try:
                import asyncio as _asyncio
                ceo_result = await _asyncio.wait_for(agency.run_cycle(), timeout=float(os.environ.get("AGENCY_CEO_TIMEOUT_SEC", "10")))
                result["ceo"] = {
                    "triggered": True,
                    "directives_issued": ceo_result.directives_issued,
                    "gh_api_count": None,
                }
                try:
                    import agent.agency as _ag
                    result["ceo"]["gh_api_count"] = _ag._last_gh_fetch_count
                    result["ceo"]["gh_api_status"] = _ag._last_gh_fetch_status
                except Exception:
                    pass
            except asyncio.TimeoutError:
                result["ceo"] = {"triggered": True, "error": "CEO cycle timed out (15s)"}
            except Exception as exc:
                result["ceo"] = {"triggered": False, "error": str(exc)[:200]}
    except Exception as exc:
        result["ceo"] = {"error": str(exc)[:200]}

    # 1.5. Requeue blocked tasks (from previous model failures)
    # Old tasks that were blocked because of the dead 120b model or asyncio
    # bug need to be requeued so they can execute with the new models.
    requeued = 0
    try:
        from tasks.store import get_task_store
        from tasks.models import TaskStatus
        store = get_task_store()
        blocked = await store.list_blocked(limit=5)
        for task in blocked:
            task.status = TaskStatus.TODO
            task.pending_agent_run = True
            task.auto_retry_count = 0
            task.error_message = None
            task.review_reason = None
            task.add_log(
                "Requeued from BLOCKED — model/asyncio fix deployed",
                event_type="auto_retry_reset",
                actor="system:tick_requeue",
                task_status=TaskStatus.TODO,
            )
            await store.update(task)
            requeued += 1
        if requeued:
            log.info("Tick: requeued %d blocked tasks", requeued)
    except Exception as exc:
        result["requeue_error"] = str(exc)[:100]
    result["requeued"] = requeued

    # 2. Pick up the oldest pending task and execute it synchronously
    if os.environ.get("SELF_BOOTSTRAP_ENABLED", "true").strip().lower() not in ("true", "1", "yes"):
        result["dispatch"] = {"skipped": "SELF_BOOTSTRAP_ENABLED=false"}
        return result

    try:
        from tasks.store import get_task_store
        store = get_task_store()
        pending = await store.list_pending(limit=1)

        # If no pending tasks, create one from the oldest GitHub issue
        if not pending:
            try:
                from tasks.models import Task
                from tasks.service import TaskWorkflowService
                import agent.agency as _ag
                import httpx
                token = _ag._gh_token()
                repo = _ag._gh_repo()
                if token and repo:
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.get(
                            f"https://api.github.com/repos/{repo}/issues",
                            params={"state": "open", "per_page": "5", "sort": "created", "direction": "asc"},
                            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                        )
                        if resp.status_code == 200:
                            all_issues = [i for i in resp.json() if "pull_request" not in i]
                            actionable = [i for i in all_issues if "quick-note:exhausted" not in [lb.get("name","") for lb in i.get("labels", [])]]
                            if actionable:
                                issue = actionable[0]
                                is_qn = "quick-note" in [lb.get("name","") for lb in issue.get("labels", [])]
                                prefix = "quick-note" if is_qn else "issue"
                                task = Task(
                                    owner_id="system",
                                    title=f"{prefix} #{issue['number']}: {issue['title'][:50]}",
                                    description=f"Implement GitHub issue #{issue['number']}: {issue['title']}",
                                    prompt=(issue.get("body") or "")[:2000],
                                    task_type="quick_note" if is_qn else "issue",
                                    tags=[lb["name"] for lb in issue.get("labels", [])] + ["needs-implementation"],
                                    source="ceo_direct",
                                    pending_agent_run=True,
                                )
                                wf = TaskWorkflowService(store=store)
                                await wf.create_task(task, actor="system:ceo_direct")
                                result["dispatch"]["direct_issue_number"] = issue["number"]
                                result["dispatch"]["direct_task_created"] = task.task_id
                                await asyncio.sleep(0.3)
                                pending = await store.list_pending(limit=1)
            except Exception as exc:
                result["dispatch"]["direct_task_error"] = str(exc)[:100]

        # Execute the pending task synchronously with a 20s timeout
        if pending:
            task_id = pending[0].task_id
            result["dispatch"]["task_id"] = task_id
            result["dispatch"]["task_title"] = pending[0].title[:60]

            try:
                from runtimes.base import TaskSpec
                from runtimes.adapters.internal_agent import InternalAgentAdapter
                import services.workflow_orchestrator as _wo
                task = pending[0]
                task.status = "in_progress"
                task.pending_agent_run = False
                await store.update(task)

                spec = TaskSpec(
                    task_id=task_id,
                    instruction=task.prompt or task.title,
                    task_type=task.task_type or "general",
                    workspace_path=str(ROOT_DIR),
                    context={"owner_id": task.owner_id, "title": task.title},
                )
                _bypass_token = _wo._BYPASS.set(True)
                try:
                    adapter = InternalAgentAdapter({"workspace_root": str(ROOT_DIR)})
                    exec_result, decision = await asyncio.wait_for(
                        adapter.execute(spec), timeout=float(os.environ.get("AGENCY_TASK_TIMEOUT_SEC", "40"))
                    )
                    task.result = exec_result.output
                    task.status = "done" if exec_result.success else "failed"
                    task.error_message = None if exec_result.success else "Execution failed"
                    await store.update(task)
                    result["dispatch"]["ran"] = True
                    result["dispatch"]["result_status"] = task.status
                    result["dispatch"]["result_error"] = (task.error_message or "")[:100]
                except asyncio.TimeoutError:
                    result["dispatch"]["ran"] = False
                    result["dispatch"]["result_status"] = "timeout"
                    result["dispatch"]["error"] = "Task timed out (20s) — will retry next cycle"
                    task.status = "todo"
                    task.pending_agent_run = True
                    await store.update(task)
                finally:
                    _wo._BYPASS.reset(_bypass_token)
            except Exception as exc:
                result["dispatch"]["ran"] = False
                result["dispatch"]["error"] = str(exc)[:200]
                try:
                    task = await store.get(task_id)
                    if task:
                        task.status = "failed"
                        task.error_message = str(exc)[:500]
                        await store.update(task)
                except Exception:
                    pass
        else:
            result["dispatch"]["pending_count"] = 0
            result["dispatch"]["ran"] = False
    except Exception as exc:
        result["dispatch"]["error"] = str(exc)[:200]

    return result


@app.post("/api/webhooks/github")
async def github_webhook(request: Request) -> dict[str, object]:
    """Public GitHub webhook sink → autonomous issue intake (Charter G3).

    HMAC-verified against ``GITHUB_WEBHOOK_SECRET``: with no secret configured
    the route refuses (503) rather than accepting unauthenticated payloads;
    unsigned or tampered payloads are rejected (401). Valid ``issues`` events
    are turned into board tasks via :func:`tasks.issue_intake.intake_issue`.
    This is a thin shell — all logic lives in that module so it stays
    unit-testable without HTTP.
    """
    secret = (os.environ.get("GITHUB_WEBHOOK_SECRET") or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="GITHUB_WEBHOOK_SECRET not configured")

    raw = await request.body()
    from tasks.issue_intake import intake_issue, verify_signature

    if not verify_signature(secret, raw, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    event = request.headers.get("X-GitHub-Event", "")
    if event == "ping":
        return {"ok": True, "pong": True}
    if event != "issues":
        return {"ok": True, "skipped": f"unhandled event: {event}"}

    try:
        payload = json.loads(raw or b"{}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid JSON payload") from exc

    try:
        task = await intake_issue(payload)
    except Exception as exc:  # pragma: no cover - defensive
        log.exception("github_webhook: issue intake failed")
        raise HTTPException(status_code=500, detail="issue intake failed") from exc

    if task is None:
        return {"ok": True, "intake": "skipped"}
    return {"ok": True, "intake": "created", "task_id": task.task_id}


@app.get("/api/status")
async def system_status(user: dict = Depends(get_current_user)) -> dict[str, object]:
    """Authenticated system status summary for the Doctor screen."""
    try:
        await get_db().command("ping")
        storage_ok = True
    except Exception:
        storage_ok = False
    return {
        "status": "ok" if storage_ok else "degraded",
        "storage": storage_ok,
        "provider": LLM_PROVIDER,
    }


@app.get("/api/health")
async def health():
    try:
        await get_db().command("ping")
        mongo_ok = True
    except Exception:
        mongo_ok = False
    return {"status": "ok" if mongo_ok else "degraded", "mongo": mongo_ok}


_last_cron_tick_at: Optional[datetime] = None


@app.post("/api/scheduler/tick")
async def scheduler_tick(request: Request):
    """Called by Cloudflare Cron every minute. Protected by CRON_SECRET header."""
    cron_secret = os.environ.get("CRON_SECRET", "")
    incoming = request.headers.get("x-cron-secret", "")
    if cron_secret and incoming != cron_secret:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Invalid cron secret")
    global _last_cron_tick_at
    _last_cron_tick_at = datetime.now(timezone.utc)
    scheduler = get_scheduler()
    fired = []
    try:
        jobs = scheduler.list()
        now = datetime.now(timezone.utc)
        for job in jobs:
            next_run = getattr(job, "next_run_time", None)
            if next_run is None:
                continue
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)
            if next_run <= now:
                try:
                    scheduler.trigger(job.job_id)
                    fired.append(job.job_id)
                except Exception as exc:
                    log.warning("tick: failed to trigger %s: %s", job.job_id, exc)
    except Exception as exc:
        log.error("scheduler_tick error: %s", exc)
    return {"ok": True, "fired": fired, "total_jobs": len(scheduler.list())}



class SchedulerTickLastResponse(BaseModel):
    """Public keepalive-monitoring response for GET /api/scheduler/tick/last.

    Intentionally public — no auth required.  Monitoring tools and the
    Cloudflare Worker itself call this endpoint to confirm the cron
    ``scheduled()`` handler is successfully reaching the Render backend.
    """
    last_tick_at: Optional[str] = Field(default=None, description="ISO 8601 timestamp of last tick, or null")
    seconds_since_last_tick: Optional[float] = Field(default=None, description="Elapsed seconds since last tick, or null")
    stale: bool = Field(default=True, description="True when >120s since last tick")
    message: str = Field(default="No tick received yet since server start", description="Human-readable status")


@app.get("/api/scheduler/tick/last", response_model=SchedulerTickLastResponse)
async def scheduler_tick_last() -> SchedulerTickLastResponse:
    """Return the last Cloudflare Cron tick timestamp for keepalive monitoring.

    Public — no auth required. Monitoring tools and the Cloudflare Worker itself
    can call this to confirm the cron is successfully reaching the backend.
    Returns nulls when the server has just started and no tick has arrived yet.
    """
    tick_at = _last_cron_tick_at
    if tick_at is None:
        return SchedulerTickLastResponse(
            last_tick_at=None,
            seconds_since_last_tick=None,
            stale=True,
            message="No tick received yet since server start",
        )
    now = datetime.now(timezone.utc)
    delta = (now - tick_at).total_seconds()
    stale = delta > 120
    return SchedulerTickLastResponse(
        last_tick_at=tick_at.isoformat(),
        seconds_since_last_tick=round(delta, 1),
        stale=stale,
        message=(
            "Keepalive is healthy" if not stale
            else f"No tick received in {round(delta)}s — keepalive may be down"
        ),
    )

@app.post("/api/scheduler/force-cleanup")
async def scheduler_force_cleanup(user: dict = Depends(get_current_user)):
    """Force-dedup and clean stale schedules from the durable store.

    Admin-only endpoint. Calls AgentScheduler.force_cleanup() which reads
    all persisted schedules, deduplicates by name, and removes stale run-once
    jobs that have already fired. Returns counts of what was cleaned.
    """
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    try:
        sched = get_scheduler()
        summary = await sched.force_cleanup()
        return {"ok": True, **summary}
    except Exception as exc:
        log.warning("Force-cleanup failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


    active = await get_active_provider()
    active_type = str((active or {}).get("type", "ollama")).lower()
    active_base = str((active or {}).get("base_url", OLLAMA_BASE))
    ollama_relevant = (
        active_type in ("ollama", "")
        or "localhost:11434" in active_base
        or "11434" in active_base
    )

    ollama_ok: Optional[bool] = None
    if ollama_relevant:
        ollama_ok = False
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                r = await c.get(f"{active_base.rstrip('/')}/api/tags")
                ollama_ok = r.status_code == 200
        except Exception:
            pass

    return {
        "status": "ok" if mongo_ok else "degraded",
        "mongo": mongo_ok,
        "ollama": ollama_ok,
        "ollama_relevant": ollama_relevant,
        "provider": LLM_PROVIDER,
    }


# ─── Quick Notes (FAB + iPhone Shortcut) ────────────────────────────────────────
# Mirrors the proxy.py /v1/quick-notes endpoints so the dashboard FAB can
# reach them via REACT_APP_BACKEND_URL (backend server), not the proxy port.

try:
    from agent.quick_note import QuickNoteQueue as _QuickNoteQueue
    _QUICK_NOTE_QUEUE: _QuickNoteQueue | None = _QuickNoteQueue()
except Exception:
    _QUICK_NOTE_QUEUE = None


class _QuickNoteBody(BaseModel):
    url: str = Field(default="", max_length=2000)
    instruction: str = Field(default="", max_length=2000)


@app.post("/v1/quick-notes")
async def quick_notes_submit(
    body: _QuickNoteBody,
    user: dict = Depends(get_current_user),
) -> dict[str, object]:
    """Submit a quick-note URL or instruction from the dashboard FAB."""
    url = body.url.strip()
    instruction = body.instruction.strip()

    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN", "")
    gh_repo = os.environ.get("GITHUB_REPOSITORY", "")

    title = f"quick-note: {url[:80]}" if url else f"quick-note: {instruction[:80]}"
    issue_body = url
    if instruction:
        issue_body += f"\nTask: {instruction}"

    # Always turn the quick-note into a real Task so the agency actually picks it up.
    # Previously notes were only filed as a GitHub issue or parked in a local queue
    # processed by a `claude` CLI that isn't present in production — so they "stayed
    # there forever". Creating a Task routes the note through the working dispatcher →
    # agents (which propose a PR), which is what the operator actually wants.
    quick_note_task_id = None
    try:
        from tasks.service import TaskWorkflowService
        from tasks.models import Task as _QNTask

        owner_id = str(
            user.get("_id") or user.get("id") or user.get("sub")
            or user.get("email") or "system"
        )
        note_instruction = instruction or (
            f"Review this resource and take any useful action for the company/repo, "
            f"then open a PR with your proposal: {url}" if url else ""
        )
        if note_instruction:
            _qn_wf = TaskWorkflowService(store=get_task_store())
            _qn_task = _QNTask(
                owner_id=owner_id,
                title=title[:512],
                description=issue_body[:32000],
                prompt=note_instruction[:32000],
                task_type="quick_note",
                tags=["quick-note"],
                source="quick-note",
            )
            await _qn_wf.create_task(_qn_task, actor=f"user:{owner_id}")
            quick_note_task_id = _qn_task.task_id
            log.info("Quick-note converted to task %s", quick_note_task_id)
            await log_activity(
                "quick_note",
                f"Quick-note queued for the agency as task {quick_note_task_id}: {title[:80]}",
                user_id=owner_id,
                meta={"task_id": quick_note_task_id},
            )
    except Exception:
        log.exception("Quick-note → task conversion failed")

    if gh_token and gh_repo and url:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"https://api.github.com/repos/{gh_repo}/issues",
                    json={"title": title, "body": issue_body, "labels": ["quick-note"]},
                    headers={
                        "Authorization": f"Bearer {gh_token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
            if resp.status_code == 201:
                issue_data = resp.json()
                return {
                    "status": "created",
                    "channel": "github",
                    "issue_number": issue_data["number"],
                    "issue_url": issue_data.get("html_url", ""),
                    "task_id": quick_note_task_id,
                }
            log.warning("Quick-note GitHub issue creation failed (%d)", resp.status_code)
        except Exception:
            log.exception("Quick-note GitHub issue creation error")

    if _QUICK_NOTE_QUEUE is not None:
        note = _QUICK_NOTE_QUEUE.add(url or instruction)
        return {
            "status": "queued",
            "channel": "local",
            "note_id": note.note_id,
            "task_id": quick_note_task_id,
        }
    return {
        "status": "queued",
        "channel": "local",
        "note_id": None,
        "task_id": quick_note_task_id,
    }


@app.get("/v1/quick-notes")
async def quick_notes_list(user: dict = Depends(get_current_user)) -> dict[str, object]:
    """List queued quick-notes."""
    if _QUICK_NOTE_QUEUE is None:
        return {"notes": [], "count": 0}
    notes = _QUICK_NOTE_QUEUE.list_all()
    return {"notes": [n.as_dict() for n in notes], "count": len(notes)}


# ─── GitHub Integration ─────────────────────────────────────────────────────────
# All GitHub API calls are proxied through the backend so the PAT never
# leaves the server. The token is stored per-user in get_db().github_settings.

GITHUB_API = "https://api.github.com"


async def _get_github_token(user_id: str) -> Optional[str]:
    doc = await get_db().github_settings.find_one({"user_id": user_id})
    return doc.get("token") if doc else None


def _gh_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


class GitHubTokenBody(BaseModel):
    token: str = Field(..., min_length=1, max_length=500)


# ── OAuth flow ─────────────────────────────────────────────────────────────────


@app.post("/api/github/oauth/start")
async def github_oauth_start(
    user: dict = Depends(get_current_user), redirect: bool = False
):
    """Create a time-limited OAuth state and return the GitHub authorization URL.

    When redirect=true the callback will issue a full-page redirect back to the
    settings page instead of using postMessage — required for mobile browsers that
    block popup windows.
    """
    if not GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=501,
            detail="GitHub OAuth not configured on this server. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET, then restart.",
        )
    state = secrets.token_urlsafe(32)
    await get_db().oauth_states.insert_one(
        {
            "state": state,
            "user_id": user["_id"],
            "flow_type": "repo",
            "redirect": redirect,
            "created_at": datetime.now(timezone.utc),
        }
    )
    # No redirect_uri — GitHub will use the single registered callback URL
    # (/api/auth/github/callback), which handles both login and repo-connect flows.
    qs = f"client_id={GITHUB_CLIENT_ID}&scope=repo&state={state}"
    return {"url": f"https://github.com/login/oauth/authorize?{qs}"}


def _oauth_popup_html(
    success: bool, login: str = "", error_msg: str = ""
) -> HTMLResponse:
    """Tiny HTML page that fires postMessage to the opener then self-closes."""
    if success:
        payload = json.dumps({"type": "github_oauth", "success": True, "login": login})
        body = "<p style='font-family:monospace;padding:2rem'>GitHub connected! Closing…</p>"
    else:
        escaped = html.escape(error_msg)
        payload = json.dumps(
            {"type": "github_oauth", "success": False, "error": escaped}
        )
        body = f"<p style='font-family:monospace;padding:2rem;color:red'>Error: {escaped}</p>"
    # Use the known frontend origin so the browser only delivers the message there,
    # not to arbitrary openers (prevents cross-origin message interception).
    target_origin = json.dumps(frontend_url)
    js = f"try{{window.opener&&window.opener.postMessage({payload},{target_origin})}}catch(e){{}}window.close();"
    return HTMLResponse(
        f"<!doctype html><html><body>{body}<script>{js}</script></body></html>"
    )


@app.get("/api/github/oauth/callback")
async def github_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    """GitHub redirects here after the user authorises (or denies) the OAuth App."""

    # Helper that respects redirect mode for error responses.
    async def _error(msg: str, redirect_mode: bool = False) -> HTMLResponse:
        if redirect_mode:
            from urllib.parse import quote

            return RedirectResponse(
                f"{frontend_url}/settings?github_error={quote(msg)}"
            )
        return _oauth_popup_html(False, error_msg=msg)

    if error or not code or not state:
        return await _error(error_description or error or "Authorization denied")

    state_doc = await get_db().oauth_states.find_one({"state": state})
    if not state_doc:
        return await _error("OAuth state expired or invalid — please try again.")

    is_redirect: bool = state_doc.get("redirect", False)
    user_id: str = state_doc["user_id"]
    await get_db().oauth_states.delete_one({"state": state})

    # Exchange the temporary code for a long-lived access token.
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                json={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": code,
                },
            )
        r.raise_for_status()
        token_data = r.json()
    except Exception as exc:
        log.error("GitHub token exchange failed: %s", exc)
        return await _error(
            "Token exchange with GitHub failed. Check server logs.", is_redirect
        )

    access_token = token_data.get("access_token")
    if not access_token:
        err = (
            token_data.get("error_description")
            or token_data.get("error")
            or "No token returned"
        )
        return await _error(err, is_redirect)

    # Fetch the GitHub user to confirm the token works.
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{GITHUB_API}/user", headers=_gh_headers(access_token))
        r.raise_for_status()
        gh_user = r.json()
    except Exception as exc:
        log.error("GitHub /user fetch failed after token exchange: %s", exc)
        return await _error(
            "Could not fetch GitHub user info after authorisation.", is_redirect
        )

    login: str = gh_user.get("login", "")

    await get_db().github_settings.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "token": access_token,
                "github_login": login,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    await log_activity("github", f"GitHub OAuth connected — @{login}", user_id=user_id)
    if state_doc.get("redirect"):
        return RedirectResponse(f"{frontend_url}/settings?github_authorized=true")
    return _oauth_popup_html(True, login=login)


@app.put("/api/github/token")
async def set_github_token(
    body: GitHubTokenBody, user: dict = Depends(get_current_user)
):
    uid = user["_id"]
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{GITHUB_API}/user", headers=_gh_headers(body.token))
        if r.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"GitHub token rejected (HTTP {r.status_code}). Check the token has repo scope.",
            )
        gh_user = r.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=400, detail=f"GitHub token validation failed: {exc}"
        ) from exc
    now_iso = datetime.now(timezone.utc).isoformat()
    gh_login = gh_user.get("login", "")
    await get_db().github_settings.update_one(
        {"user_id": uid},
        {
            "$set": {
                "user_id": uid,
                "token": body.token,
                "github_login": gh_login,
                "updated_at": now_iso,
            }
        },
        upsert=True,
    )
    # Sync to user document so the agent runner can read it directly
    await get_db().users.update_one(
        {"_id": ObjectId(uid)},
        {
            "$set": {
                "github_repo_token": body.token,
                "github_login": gh_login,
                "github_updated_at": now_iso,
            }
        },
    )
    await log_activity("github", f"GitHub token connected for @{gh_login}", user_id=uid)
    return {"ok": True, "login": gh_login}


@app.delete("/api/github/token")
async def delete_github_token(user: dict = Depends(get_current_user)):
    await get_db().github_settings.delete_one({"user_id": user["_id"]})
    # Clear from user document too
    await get_db().users.update_one(
        {"_id": ObjectId(user["_id"])},
        {
            "$unset": {
                "github_repo_token": "",
                "github_login": "",
                "github_updated_at": "",
            }
        },
    )
    return {"ok": True}


@app.get("/api/github/repos")
async def list_github_repos(
    user: dict = Depends(get_current_user),
    q: str = "",
    page: int = 1,
):
    token = await _get_github_token(user["_id"])
    if not token:
        raise HTTPException(
            status_code=400,
            detail="GitHub not connected. Add a token in Settings → GitHub.",
        )
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            if q:
                doc = await get_db().github_settings.find_one({"user_id": user["_id"]})
                login = doc.get("github_login", "") if doc else ""
                r = await c.get(
                    f"{GITHUB_API}/search/repositories",
                    headers=_gh_headers(token),
                    params={"q": f"{q} user:{login}" if login else q, "per_page": 30},
                )
            else:
                r = await c.get(
                    f"{GITHUB_API}/user/repos",
                    headers=_gh_headers(token),
                    params={
                        "per_page": 30,
                        "page": page,
                        "sort": "updated",
                        "affiliation": "owner,collaborator",
                    },
                )
        r.raise_for_status()
        raw = r.json().get("items", r.json()) if q else r.json()
        repos = [
            {
                "full_name": repo["full_name"],
                "name": repo["name"],
                "owner": repo["owner"]["login"],
                "description": repo.get("description") or "",
                "private": repo.get("private", False),
                "default_branch": repo.get("default_branch", "main"),
                "updated_at": repo.get("updated_at", ""),
                "language": repo.get("language") or "",
                "stars": repo.get("stargazers_count", 0),
            }
            for repo in (raw if isinstance(raw, list) else [])
        ]
        return {"repos": repos}
    except httpx.HTTPStatusError as exc:
        log.error(
            "GitHub API %s error: %s", exc.response.status_code, exc.response.text
        )
        raise HTTPException(
            status_code=exc.response.status_code, detail="GitHub API error"
        ) from exc


@app.get("/api/github/repos/{owner}/{repo}/branches")
async def list_github_branches(
    owner: str, repo: str, user: dict = Depends(get_current_user)
):
    token = await _get_github_token(user["_id"])
    if not token:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/branches",
                headers=_gh_headers(token),
                params={"per_page": 50},
            )
        r.raise_for_status()
        return {"branches": [b["name"] for b in r.json()]}
    except httpx.HTTPStatusError as exc:
        log.error(
            "GitHub API %s error: %s", exc.response.status_code, exc.response.text
        )
        raise HTTPException(
            status_code=exc.response.status_code, detail="GitHub API error"
        ) from exc


@app.get("/api/github/repos/{owner}/{repo}/tree")
async def get_github_tree(
    owner: str,
    repo: str,
    ref: str = "HEAD",
    path: str = "",
    user: dict = Depends(get_current_user),
):
    token = await _get_github_token(user["_id"])
    if not token:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
                headers=_gh_headers(token),
                params={"ref": ref},
            )
        r.raise_for_status()
        raw = r.json()
        items = raw if isinstance(raw, list) else [raw]
        return {
            "path": path,
            "items": [
                {
                    "name": i["name"],
                    "path": i["path"],
                    "type": i["type"],
                    "size": i.get("size", 0),
                    "sha": i.get("sha", ""),
                }
                for i in items
            ],
        }
    except httpx.HTTPStatusError as exc:
        log.error(
            "GitHub API %s error: %s", exc.response.status_code, exc.response.text
        )
        raise HTTPException(
            status_code=exc.response.status_code, detail="GitHub API error"
        ) from exc


@app.get("/api/github/repos/{owner}/{repo}/file")
async def read_github_file(
    owner: str,
    repo: str,
    path: str,
    ref: str = "HEAD",
    user: dict = Depends(get_current_user),
):
    token = await _get_github_token(user["_id"])
    if not token:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    import base64 as _b64

    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
                headers=_gh_headers(token),
                params={"ref": ref},
            )
        r.raise_for_status()
        data = r.json()
        content = _b64.b64decode(data.get("content", "").replace("\n", "")).decode(
            "utf-8", errors="replace"
        )
        return {
            "path": path,
            "content": content,
            "sha": data.get("sha", ""),
            "size": data.get("size", 0),
        }
    except httpx.HTTPStatusError as exc:
        log.error(
            "GitHub API %s error: %s", exc.response.status_code, exc.response.text
        )
        raise HTTPException(
            status_code=exc.response.status_code, detail="GitHub API error"
        ) from exc


class GitHubFileWrite(BaseModel):
    path: str = Field(..., min_length=1, max_length=2000)
    content: str
    message: str = Field(..., min_length=1, max_length=1000)
    sha: Optional[str] = None  # required for updates, omit for new files
    branch: str = Field(default="main", min_length=1, max_length=200)


@app.put("/api/github/repos/{owner}/{repo}/file")
async def write_github_file(
    owner: str,
    repo: str,
    body: GitHubFileWrite,
    user: dict = Depends(get_current_user),
):
    token = await _get_github_token(user["_id"])
    if not token:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    import base64 as _b64

    try:
        content_b64 = _b64.b64encode(body.content.encode("utf-8")).decode("ascii")
        payload: dict = {
            "message": body.message,
            "content": content_b64,
            "branch": body.branch,
        }
        if body.sha:
            payload["sha"] = body.sha
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.put(
                f"{GITHUB_API}/repos/{owner}/{repo}/contents/{body.path}",
                headers=_gh_headers(token),
                json=payload,
            )
        r.raise_for_status()
        data = r.json()
        commit_sha = data.get("commit", {}).get("sha", "")
        file_sha = data.get("content", {}).get("sha", "")
        await log_activity(
            "github",
            f"Committed {body.path} to {owner}/{repo}@{body.branch}",
            user_id=user["_id"],
            meta={
                "repo": f"{owner}/{repo}",
                "path": body.path,
                "commit_sha": commit_sha,
            },
        )
        return {"ok": True, "commit_sha": commit_sha, "file_sha": file_sha}
    except httpx.HTTPStatusError as exc:
        log.error(
            "GitHub API %s error: %s", exc.response.status_code, exc.response.text
        )
        raise HTTPException(
            status_code=exc.response.status_code, detail="GitHub API error"
        ) from exc


@app.get("/api/github/repos/{owner}/{repo}/pulls")
async def list_github_pulls(
    owner: str,
    repo: str,
    state: str = "open",
    user: dict = Depends(get_current_user),
):
    token = await _get_github_token(user["_id"])
    if not token:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
                headers=_gh_headers(token),
                params={"state": state, "per_page": 30},
            )
        r.raise_for_status()
        pulls = [
            {
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "user": pr["user"]["login"],
                "head": pr["head"]["ref"],
                "base": pr["base"]["ref"],
                "created_at": pr["created_at"],
                "html_url": pr["html_url"],
            }
            for pr in r.json()
        ]
        return {"pulls": pulls}
    except httpx.HTTPStatusError as exc:
        log.error(
            "GitHub API %s error: %s", exc.response.status_code, exc.response.text
        )
        raise HTTPException(
            status_code=exc.response.status_code, detail="GitHub API error"
        ) from exc


class GitHubPRCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    body: str = ""
    head: str = Field(..., min_length=1, max_length=200)
    base: str = Field(default="main", min_length=1, max_length=200)


@app.post("/api/github/repos/{owner}/{repo}/pulls")
async def create_github_pr(
    owner: str,
    repo: str,
    body: GitHubPRCreate,
    user: dict = Depends(get_current_user),
):
    token = await _get_github_token(user["_id"])
    if not token:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
                headers=_gh_headers(token),
                json={
                    "title": body.title,
                    "body": body.body,
                    "head": body.head,
                    "base": body.base,
                },
            )
        r.raise_for_status()
        pr = r.json()
        await log_activity(
            "github",
            f"Created PR #{pr['number']} in {owner}/{repo}",
            user_id=user["_id"],
        )
        return {
            "ok": True,
            "number": pr["number"],
            "html_url": pr["html_url"],
            "title": pr["title"],
        }
    except httpx.HTTPStatusError as exc:
        log.error(
            "GitHub API %s error: %s", exc.response.status_code, exc.response.text
        )
        raise HTTPException(
            status_code=exc.response.status_code, detail="GitHub API error"
        ) from exc


# ─── Legacy scheduler compatibility (pre-Control Plane frontend builds) ─────


class LegacyScheduleJobRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    cron: str = Field(..., min_length=9, max_length=100)
    instruction: str = Field(..., min_length=1, max_length=4000)
    agent_id: Optional[str] = Field(default=None, max_length=64)
    runtime_id: Optional[str] = Field(default=None, max_length=64)
    model: Optional[str] = Field(default=None, max_length=200)
    task_type: str = Field(default="scheduled", max_length=64)
    requires_approval: bool = False
    tags: list[str] = Field(default_factory=list)


class LegacyScheduleToggleRequest(BaseModel):
    status: str = Field(..., pattern="^(active|paused)$")


@app.post("/agent/scheduler/jobs")
async def legacy_scheduler_create(
    body: LegacyScheduleJobRequest, user: dict = Depends(get_current_user)
):
    job = get_scheduler().create(
        name=body.name,
        cron=body.cron,
        instruction=body.instruction,
        agent_id=body.agent_id,
        runtime_id=body.runtime_id,
        model=body.model,
        task_type=body.task_type,
        requires_approval=body.requires_approval,
        tags=body.tags,
    )
    return job.as_dict()


@app.get("/agent/scheduler/jobs")
async def legacy_scheduler_list(user: dict = Depends(get_current_user)):
    return {"jobs": [job.as_dict() for job in get_scheduler().list()]}


@app.get("/agent/scheduler/jobs/{job_id}")
async def legacy_scheduler_get(job_id: str, user: dict = Depends(get_current_user)):
    job = get_scheduler().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.as_dict()


@app.post("/agent/scheduler/jobs/{job_id}/trigger")
async def legacy_scheduler_trigger(job_id: str, user: dict = Depends(get_current_user)):
    try:
        return get_scheduler().trigger(job_id).as_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@app.delete("/agent/scheduler/jobs/{job_id}")
async def legacy_scheduler_delete(job_id: str, user: dict = Depends(get_current_user)):
    return {"deleted": get_scheduler().delete(job_id)}


@app.patch("/agent/scheduler/jobs/{job_id}")
async def legacy_scheduler_toggle(
    job_id: str, body: LegacyScheduleToggleRequest, user: dict = Depends(get_current_user)
):
    try:
        return get_scheduler().toggle(job_id, enabled=(body.status == "active")).as_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc




# ─── Doctor / System Health endpoint ────────────────────────────────────────────

class _DoctorCheck(BaseModel):
    id: str
    category: str
    label: str
    status: Literal["pass", "warn", "fail"]
    detail: str
    action: Optional[dict] = None
    explanation: Optional[str] = None


class _DoctorReport(BaseModel):
    ready: bool
    summary: str
    checks: list[_DoctorCheck] = []
    run_at: str


@app.get("/api/doctor", response_model=_DoctorReport)
async def get_doctor_report(user: Optional[dict] = Depends(get_optional_user)) -> _DoctorReport:
    """Consolidated system health report: preflight checks + runtime health.

    Returns a structured list of named checks (pass / warn / fail) sourced from:
    - DirectChatDoctor: git binary, GitHub token, GitHub API access
    - RuntimeManager: each registered runtime's circuit-breaker state
    - Internal probes: Ollama reachability, Langfuse configuration
    """
    from agent.doctor import DirectChatDoctor
    import datetime

    github_token = (
        (user or {}).get("github_repo_token")
        or os.environ.get("GH_PAT") 
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
    )
    doctor = DirectChatDoctor(github_token=github_token)

    checks: list[_DoctorCheck] = []

    # ── 1. Preflight report from agent.doctor ────────────────────────────────
    try:
        preflight = await doctor.check_all()
        if not preflight.issues:
            checks.append(_DoctorCheck(
                id="preflight",
                category="Setup",
                label="Preflight checks",
                status="pass",
                detail="git binary found, GitHub token valid and repo accessible.",
            ))
        else:
            for issue in preflight.issues:
                checks.append(_DoctorCheck(
                    id=issue.code,
                    category="Setup",
                    label=issue.message[:80],
                    status="fail",
                    detail=issue.message,
                    action={"label": "Fix", "hint": issue.fix_hint},
                    explanation=issue.fix_hint,
                ))
    except Exception as exc:
        checks.append(_DoctorCheck(
            id="preflight_error",
            category="Setup",
            label="Preflight check failed",
            status="warn",
            detail=f"Could not run preflight checks: {exc}",
        ))

    # ── 2. Runtime health (from RuntimeManager cache — non-blocking) ─────────
    try:
        mgr = get_runtime_manager()
        for rt in mgr.list_runtimes():
            rid = rt["runtime_id"]
            available = rt.get("available", False)
            health = rt.get("health") or {}
            circuit_open = (health.get("circuit_open") is True)
            detail_parts = []
            if health.get("details"):
                for k, v in health["details"].items():
                    detail_parts.append(f"{k}: {v}")
            detail = health.get("error") or (", ".join(detail_parts) if detail_parts else ("Healthy" if available else "Unavailable"))
            checks.append(_DoctorCheck(
                id=f"runtime_{rid}",
                category="Runtime",
                label=f"Runtime: {rid}",
                # Sidecar runtimes (hermes/goose/aider/...) are optional beta
                # features — their absence must not flip Doctor to not-ready.
                # Only the internal agent runtime is required in the default path.
                status="pass" if available else (
                    "fail" if rid == "internal_agent" else "warn"
                ),
                detail=str(detail)[:200],
                action={"label": "Check health", "href": f"/runtimes/{rid}/health"} if not available else None,
                explanation="Circuit breaker is OPEN — runtime failed 3+ consecutive health checks." if circuit_open else None,
            ))
    except Exception as exc:
        checks.append(_DoctorCheck(
            id="runtime_error",
            category="Runtime",
            label="Runtime health unavailable",
            status="warn",
            detail=f"Could not query RuntimeManager: {exc}",
        ))

    # ── 3. Langfuse configuration ─────────────────────────────────────────────
    langfuse_pk = os.environ.get("LANGFUSE_PUBLIC_KEY") or os.environ.get("LANGFUSE_PK")
    langfuse_sk = os.environ.get("LANGFUSE_SECRET_KEY") or os.environ.get("LANGFUSE_SK")
    checks.append(_DoctorCheck(
        id="langfuse",
        category="Observability",
        label="Langfuse tracing",
        status="pass" if (langfuse_pk and langfuse_sk) else "warn",
        detail="Langfuse keys configured — traces will be emitted." if (langfuse_pk and langfuse_sk)
               else "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set — tracing disabled.",
        action=None if (langfuse_pk and langfuse_sk) else {"label": "Configure", "hint": "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in environment."},
        explanation=None if (langfuse_pk and langfuse_sk) else "Without Langfuse, LLM call traces are not stored. Set the keys and restart to enable observability.",
    ))

    # ── 4. Ollama reachability (quick probe via RuntimeManager health cache) ──
    try:
        mgr = get_runtime_manager()
        internal_health = mgr.get_runtime("internal_agent")
        if internal_health:
            available = internal_health.get("health", {}).get("available", False)
            provider = (internal_health.get("health", {}).get("details") or {}).get("provider", "unknown")
            checks.append(_DoctorCheck(
                id="llm_provider",
                category="Models",
                label=f"LLM provider ({provider})",
                status="pass" if available else "fail",
                detail=f"Provider '{provider}' is {'reachable' if available else 'unreachable'}.",
                action=None if available else {"label": "Check config", "hint": "Set NVIDIA_API_KEY or ensure Ollama is running on OLLAMA_BASE."},
            ))
    except Exception:
        pass

    ready = all(c.status != "fail" for c in checks)
    fail_count = sum(1 for c in checks if c.status == "fail")
    warn_count = sum(1 for c in checks if c.status == "warn")
    pass_count = sum(1 for c in checks if c.status == "pass")

    if ready and warn_count == 0:
        summary = f"All {pass_count} checks passing — system healthy."
    elif ready:
        summary = f"{pass_count} passing, {warn_count} warning(s) — review recommended."
    else:
        summary = f"{fail_count} check(s) failing — action required."

    return _DoctorReport(
        ready=ready,
        summary=summary,
        checks=checks,
        run_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )


@app.get("/api/doctor/public", response_model=_DoctorReport)
async def get_public_doctor() -> _DoctorReport:
    """Public Doctor endpoint — no authentication required.

    Returns system-level diagnostics only (git, storage, provider health).
    No user-specific checks (GitHub token, workspace, repo access).
    """
    import datetime
    import shutil

    checks: list[_DoctorCheck] = []

    # 1. Git binary
    git_ok = bool(shutil.which("git"))
    checks.append(_DoctorCheck(
        id="git_binary",
        category="Setup",
        label="Git binary",
        status="pass" if git_ok else "fail",
        detail="git found on PATH" if git_ok else "git not found on PATH",
        explanation="Install git for repository operations" if not git_ok else None,
    ))

    # 2. Storage backend
    try:
        from db import get_store
        store = get_store()
        # NOTE: don't duck-type with hasattr() — MongoStore.__getattr__ proxies
        # any attribute to a Motor *collection*, so store.count_companies is a
        # collection named "count_companies", not a method (TypeError at call).
        count = await store.companies.count_documents({})
        checks.append(_DoctorCheck(
            id="storage",
            category="Storage",
            label="Storage backend",
            status="pass",
            detail=f"Connected ({count} companies)",
        ))
    except Exception as exc:
        checks.append(_DoctorCheck(
            id="storage",
            category="Storage",
            label="Storage backend",
            status="fail",
            detail=f"Unavailable: {exc}",
        ))

    # 3. Provider health (Ollama reachability)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        ollama_ok = False
    checks.append(_DoctorCheck(
        id="ollama",
        category="Provider",
        label="Ollama provider",
        status="pass" if ollama_ok else "warn",
        detail="Ollama reachable" if ollama_ok else "Ollama unreachable — start with ollama serve",
        explanation="Ollama is the local LLM engine. Ensure it is running." if not ollama_ok else None,
    ))

    # 4. Runtime health
    try:
        mgr = get_runtime_manager()
        runtimes = mgr.list_runtimes()
        running = sum(1 for rt in runtimes if rt.get("available", False))
        checks.append(_DoctorCheck(
            id="runtimes",
            category="Runtime",
            label="Agent runtimes",
            status="pass" if running > 0 else "warn",
            detail=f"{running}/{len(runtimes)} runtimes available" if runtimes else "No runtimes registered",
        ))
    except Exception as exc:
        checks.append(_DoctorCheck(
            id="runtimes",
            category="Runtime",
            label="Agent runtimes",
            status="warn",
            detail=f"Could not query: {exc}",
        ))

    # 5. Feature gate status
    workflow_mode = os.environ.get("AGENCY_WORKFLOW_MODE", "orchestrator")
    checks.append(_DoctorCheck(
        id="workflow_mode",
        category="Feature",
        label="Workflow mode",
        status="pass" if workflow_mode == "orchestrator" else "warn",
        detail=f"Golden path enforced ({workflow_mode})" if workflow_mode == "orchestrator" else f"Legacy mode ({workflow_mode})",
        explanation="Set AGENCY_WORKFLOW_MODE=orchestrator for the production-grade golden path." if workflow_mode != "orchestrator" else None,
    ))

    fail_count = sum(1 for c in checks if c.status == "fail")
    pass_count = sum(1 for c in checks if c.status == "pass")
    ready = fail_count == 0
    summary = f"{pass_count}/{len(checks)} checks passing — {'healthy' if ready else 'action required'}"

    return _DoctorReport(
        ready=ready,
        summary=summary,
        checks=checks,
        run_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )


@app.get("/api/doctor/diagnostics", response_model=_DoctorReport)
async def get_doctor_diagnostics(
    user: dict = Depends(get_current_user),
) -> _DoctorReport:
    """Authenticated Doctor endpoint — full diagnostics.

    Returns all system-level checks plus user-specific diagnostics:
    GitHub token, workspace integrity, company graph health.
    Requires authentication.
    """
    from agent.doctor import DirectChatDoctor
    import datetime

    # User-specific diagnostics: use ONLY the caller's own GitHub token, never
    # the server-wide env fallback — otherwise a user with no GitHub connection
    # would falsely report healthy against the host's token.
    github_token = user.get("github_repo_token")
    doctor = DirectChatDoctor(github_token=github_token)

    checks: list[_DoctorCheck] = []

    # 1. Preflight (GitHub token, git binary, repo access)
    try:
        preflight = await doctor.check_all()
        if not preflight.issues:
            checks.append(_DoctorCheck(
                id="preflight",
                category="Setup",
                label="Git & GitHub setup",
                status="pass",
                detail="git found, GitHub token valid, repo accessible",
            ))
        else:
            for issue in preflight.issues:
                checks.append(_DoctorCheck(
                    id=issue.code,
                    category="Setup",
                    label=issue.message[:80],
                    status="fail",
                    detail=issue.message,
                    explanation=issue.fix_hint,
                ))
    except Exception as exc:
        checks.append(_DoctorCheck(
            id="preflight_error",
            category="Setup",
            label="Preflight checks",
            status="warn",
            detail=f"Could not run: {exc}",
        ))

    # 2. Company graph integrity
    try:
        # Use the same resolver as company creation so a user whose companies
        # are owned by `_id` (not email) is matched correctly.
        user_id = _wfo_resolve_user_id(user)
        store = get_company_graph_store()
        # list_companies returns a plain List[Company] (not a (list, total) tuple).
        companies = await store.list_companies(owner_id=user_id, limit=10)
        checks.append(_DoctorCheck(
            id="company_graph",
            category="Company",
            label="Company Graph",
            status="pass" if companies else "warn",
            detail=f"{len(companies)} company(s) onboarded" if companies else "No companies onboarded yet",
            explanation="Create a company via the Onboarding flow to start using the platform." if not companies else None,
        ))
    except Exception as exc:
        checks.append(_DoctorCheck(
            id="company_graph",
            category="Company",
            label="Company Graph",
            status="warn",
            detail=f"Could not query: {exc}",
        ))

    # 3. Workspace integrity
    workspace_root = os.environ.get("WORKSPACE_ROOT", str(ROOT_DIR))
    workspace_exists = Path(workspace_root).exists()
    checks.append(_DoctorCheck(
        id="workspace",
        category="Workspace",
        label="Workspace",
        status="pass" if workspace_exists else "fail",
        detail=f"Workspace at {workspace_root}" if workspace_exists else f"Workspace not found: {workspace_root}",
    ))

    # 4. Skill library health
    try:
        from agent.skills import SkillLibrary
        lib = SkillLibrary()
        skill_count = len(lib.list())
        checks.append(_DoctorCheck(
            id="skills",
            category="Skills",
            label="Skill Library",
            status="pass" if skill_count > 0 else "warn",
            detail=f"{skill_count} skills loaded",
        ))
    except Exception:
        checks.append(_DoctorCheck(
            id="skills",
            category="Skills",
            label="Skill Library",
            status="warn",
            detail="Skill library unavailable",
        ))

    # 4b. Skill registry ("skills repos") connectivity — this is what the operator
    # means by "skills repo connected": the GitHub-backed SkillRegistry that pulls
    # skills from the configured registries (anthropics/skills, this repo, etc.).
    try:
        from agent.skill_registry import (
            GITHUB_REGISTRIES,
            get_skill_registry_safe,
        )

        registry = get_skill_registry_safe()
        if registry is None:
            checks.append(_DoctorCheck(
                id="skill_registry",
                category="Skills",
                label="Skills Repos",
                status="fail",
                detail="Skill registry not initialised — skills repos are not connected.",
                explanation="Set GITHUB_TOKEN so the server can fetch the configured "
                "skill registries, then restart. Local .claude/skills still load without it.",
            ))
        else:
            all_skills = registry.list()
            local_n = sum(1 for s in all_skills if s.source == "local")
            remote_sources = {
                s.source for s in all_skills if s.source.startswith("github:")
            }
            n_registries = len(GITHUB_REGISTRIES)
            if remote_sources:
                checks.append(_DoctorCheck(
                    id="skill_registry",
                    category="Skills",
                    label="Skills Repos",
                    status="pass",
                    detail=f"Connected: {len(remote_sources)}/{n_registries} skill "
                    f"repos, {len(all_skills)} skills ({local_n} local).",
                ))
            else:
                checks.append(_DoctorCheck(
                    id="skill_registry",
                    category="Skills",
                    label="Skills Repos",
                    status="warn",
                    detail=f"{local_n} local skills loaded; {n_registries} remote skill "
                    "repos configured but none fetched yet.",
                    explanation="Remote skill repos load asynchronously and need network "
                    "(and GITHUB_TOKEN to avoid rate limits). They will appear after the "
                    "first refresh.",
                ))
    except Exception as exc:
        log.exception("Skill registry check failed")
        checks.append(_DoctorCheck(
            id="skill_registry",
            category="Skills",
            label="Skills Repos",
            status="warn",
            detail="Skill registry check failed",
        ))

    # 5. Workflow orchestrator status
    try:
        from services.workflow_orchestrator import get_workflow_orchestrator
        orchestrator = get_workflow_orchestrator()
        # Scope run visibility to the caller (admins see all) so diagnostics
        # never leak other tenants' recent activity.
        owner_id = None if _wfo_is_admin(user) else _wfo_resolve_user_id(user)
        runs = orchestrator.list_runs(limit=5, owner_id=owner_id)
        checks.append(_DoctorCheck(
            id="orchestrator",
            category="Workflow",
            label="Workflow Orchestrator",
            status="pass",
            detail=f"Active ({len(runs)} recent runs)",
        ))
    except Exception as exc:
        checks.append(_DoctorCheck(
            id="orchestrator",
            category="Workflow",
            label="Workflow Orchestrator",
            status="warn",
            detail=f"Not available: {exc}",
        ))

    # 6. Service token (N5 — mutating Telegram control readiness).
    # The /setbrain + /merge Telegram commands require SERVICE_TOKEN to be set
    # identically on the backend AND the bot. A 'warn' here (not 'fail')
    # because the rest of the agency works fine without it — only the
    # mutating Telegram commands are gated. Surfaces as a Doctor screen row
    # so the operator can see the gap before trying /setbrain from the phone.
    try:
        from services.service_token import is_service_token_configured
        if is_service_token_configured():
            checks.append(_DoctorCheck(
                id="service_token",
                category="Setup",
                label="Service Token (Telegram mutating control)",
                status="pass",
                detail="SERVICE_TOKEN configured — /setbrain + /merge are available.",
            ))
        else:
            checks.append(_DoctorCheck(
                id="service_token",
                category="Setup",
                label="Service Token (Telegram mutating control)",
                status="warn",
                detail="SERVICE_TOKEN not set — /setbrain + /merge will refuse with 503.",
                explanation=(
                    "Set SERVICE_TOKEN in the backend env (and identically on the "
                    "Telegram bot) to enable mutating Telegram control. "
                    "Generate with: python -c \"import secrets; print('st_' + secrets.token_urlsafe(32))\". "
                    "See services/service_token.py for the security model."
                ),
            ))
    except Exception as exc:  # pragma: no cover - defensive
        checks.append(_DoctorCheck(
            id="service_token",
            category="Setup",
            label="Service Token (Telegram mutating control)",
            status="warn",
            detail=f"Could not check: {exc}",
        ))

    fail_count = sum(1 for c in checks if c.status == "fail")
    pass_count = sum(1 for c in checks if c.status == "pass")
    ready = fail_count == 0
    summary = f"{pass_count}/{len(checks)} checks passing — {'healthy' if ready else 'action required'}"

    return _DoctorReport(
        ready=ready,
        summary=summary,
        checks=checks,
        run_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )



# ─── Feature Routers ────────────────────────────────────────────────────────────
app.include_router(agent_router)
app.include_router(runtime_router)
app.include_router(task_router)
app.include_router(schedules_router, dependencies=[Depends(get_current_user)])
app.include_router(setup_router)
app.include_router(activation_router)
app.include_router(secrets_router)

# Portfolio + Agile board API (powers the v5 PortfolioScreen)
from agents.portfolio_api import portfolio_router
app.include_router(portfolio_router)

try:
    from agents.agile_api import agile_router
    app.include_router(agile_router)
    log.info("Agile sprints API mounted at /api/agile")
except Exception as _agile_err:
    log.warning("Agile API not mounted: %s", _agile_err, exc_info=True)

# v4 Dashboard API - powers the Continuous Improvement Dashboard at
# autonomous-ai-agency.strikersam.workers.dev
from backend.v4_api import v4_router
app.include_router(v4_router)
log.info("v4 Dashboard API mounted at /v4")

# Company Graph API
from services.company_graph_store import get_company_graph_store
import backend.company_api as company_api_module
app.include_router(company_api_module.router)

# SEO / GEO / AIO Audit API (issue #533)
try:
    import backend.seo_api as seo_api_module
    app.include_router(seo_api_module.router)
except Exception as _seo_err:  # noqa: BLE001 - SEO API must not block startup
    log.warning("SEO audit API not mounted: %s", _seo_err, exc_info=True)

# Workflow Orchestrator API --- canonical execution backbone
from services.workflow_orchestrator import (
    ExecutionRequest,
    get_workflow_orchestrator,
)


from backend.company_api import _resolve_user_id as _wfo_resolve_user_id
from backend.company_api import _is_admin as _wfo_is_admin
from backend.company_api import get_company_access as _wfo_company_access


def _wfo_owned_run_or_404(orchestrator, run_id: str, user: dict):
    """Fetch a run, enforcing per-user ownership (admins bypass).

    Returns 404 — not 403 — when a non-admin requests a run they don't own,
    so run IDs can't be enumerated across tenants (IDOR-safe).
    """
    run = orchestrator.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if not _wfo_is_admin(user):
        if run.user_id != _wfo_resolve_user_id(user):
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


@app.post("/api/workflow/orchestrator/execute")
async def workflow_orchestrator_execute(
    body: ExecutionRequest,
    user: dict = Depends(get_current_user),
):
    """Execute work through the 11-phase golden path."""
    orchestrator = get_workflow_orchestrator()
    is_admin = _wfo_is_admin(user)

    # If a company is targeted, the caller must have access to it — otherwise a
    # user could run/approve a workflow against another tenant's company and read
    # its graph snapshot back via bound_context (cross-tenant leak).
    if body.company_id:
        await _wfo_company_access(body.company_id, user)

    # auto_approve bypasses the HITL ApprovalGate and is for trusted/internal
    # callers only.  Never honor it from a non-admin, user-facing request.
    if not is_admin:
        body.auto_approve = False

    # Stamp the run with a stable, auth-method-agnostic owner id so it can be
    # scoped on list/get/approve.  Same resolver as the company endpoints.
    body.user_id = _wfo_resolve_user_id(user)
    # Execution must act with the CALLER's GitHub permissions, never the
    # server-wide service-account token.
    body.github_token = user.get("github_repo_token")
    run = await orchestrator.execute(body)
    return {"status": run.status, "run": run.as_dict()}


@app.post("/api/workflow/orchestrator/approve/{run_id}")
async def workflow_orchestrator_approve(
    run_id: str,
    user: dict = Depends(get_current_user),
):
    """Approve a run paused at the ApprovalGate and resume execution."""
    orchestrator = get_workflow_orchestrator()
    # Ownership check first — a user may only approve their own runs (admin: any).
    _wfo_owned_run_or_404(orchestrator, run_id, user)
    # Attribute the approval to the authenticated user — never an arbitrary
    # client-supplied string (audit-log integrity).
    approved_by = _wfo_resolve_user_id(user)
    try:
        # #522: approve_async enqueues the run via the FIFO queue instead of
        # blocking inline. Returns 202 immediately; the run executes
        # asynchronously when a concurrency slot opens.
        run = await orchestrator.approve_async(run_id, approved_by=approved_by)
        status_code = 202 if run.status == "queued" else 200
        return JSONResponse(
            {"status": run.status, "run": run.as_dict()},
            status_code=status_code,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))




@app.get("/api/workflow/orchestrator/status")
async def workflow_orchestrator_status(
    user: dict = Depends(get_current_user),
):
    """Return orchestrator queue depth, active runs, and supervisor state (#522)."""
    orchestrator = get_workflow_orchestrator()
    owner_id = None if _wfo_is_admin(user) else _wfo_resolve_user_id(user)
    runs = orchestrator.list_runs(limit=200, owner_id=owner_id)

    queue_status = {"max_concurrent": 2, "active": 0, "queued": 0}
    try:
        from services.orchestrator_queue import get_orchestrator_queue
        q = get_orchestrator_queue()
        queue_status = q.status()
    except Exception:
        pass

    supervisor_state = {}
    try:
        from services.orchestrator_supervisor import get_orchestrator_supervisor
        sv = get_orchestrator_supervisor()
        st = sv.state
        supervisor_state = {
            "running": st.running,
            "ticks": st.ticks,
            "stalled_recovered": st.stalled_recovered,
            "failed_retried": st.failed_retried,
            "alerts_emitted": st.alerts_emitted,
        }
    except Exception:
        pass

    return {
        "runs": len(runs),
        "by_status": {
            "pending": sum(1 for r in runs if r.get("status") == "pending"),
            "running": sum(1 for r in runs if r.get("status") == "running"),
            "awaiting_approval": sum(1 for r in runs if r.get("status") == "awaiting_approval"),
            "queued": sum(1 for r in runs if r.get("status") == "queued"),
            "done": sum(1 for r in runs if r.get("status") == "done"),
            "failed": sum(1 for r in runs if r.get("status") == "failed"),
        },
        "queue": queue_status,
        "supervisor": supervisor_state,
    }

@app.get("/api/workflow/orchestrator/runs")
async def workflow_orchestrator_list_runs(
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    """List recent workflow orchestrator runs.

    Non-admin users see only their own runs; admins see every run.
    """
    orchestrator = get_workflow_orchestrator()
    owner_id = None if _wfo_is_admin(user) else _wfo_resolve_user_id(user)
    return {
        "runs": orchestrator.list_runs(limit=limit, owner_id=owner_id),
        "scoped_to_user": owner_id is not None,
    }


@app.get("/api/workflow/orchestrator/runs/{run_id}")
async def workflow_orchestrator_get_run(
    run_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a single workflow orchestrator run by ID (owner or admin only)."""
    orchestrator = get_workflow_orchestrator()
    run = _wfo_owned_run_or_404(orchestrator, run_id, user)
    return {"run": run.as_dict()}

# Initialise the secrets store with our MongoDB handle so it persists to the
# same database as the rest of the app.
get_secrets_store(db=get_db())

# ─── Mount MCP server in-process ────────────────────────────────────────────
# Serves at /mcp-internal so MCP_SERVER_BASE_URL can point at this service's
# own external URL without needing a separate container or paid disk.
try:
    from mcp_server.server import app as _mcp_app
    app.mount("/mcp-internal", _mcp_app)
    log.info("MCP server mounted at /mcp-internal")
except Exception as _mcp_err:
    log.warning("MCP server not mounted: %s", _mcp_err)

# ─── Serve React Frontend (Replit compatibility) ────────────────────────────────
# Mount the built React app and serve index.html for unknown routes (SPA routing)

# Path prefixes (NO leading slash — FastAPI's {full_path:path} converter strips
# it) that belong to the API/auth surface and must NEVER fall through to the SPA
# catch-all. Without this guard, an anonymous GET to an orphan route under any of
# these (e.g. /v1/models, /admin/keys, /telegram/webhook) returned 200 with the
# React index.html instead of 401/404 JSON. Kept at module scope so tests and
# downstream code can reference it regardless of whether the build dir exists.
SPA_PROTECTED_PREFIXES: tuple[str, ...] = (
    "api/",
    "v1/",
    "v2/",
    "agent/",
    "admin/",
    "workflow/",
    "runtimes/",
    "ui/",
    "telegram/",
    "mcp-internal/",
)

_FRONTEND_BUILD = Path(__file__).resolve().parent.parent / "frontend" / "build"

if _FRONTEND_BUILD.exists():
    app.mount(
        "/static", StaticFiles(directory=str(_FRONTEND_BUILD / "static")), name="static"
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # API/auth paths that reached the catch-all have no upstream handler —
        # return 404 JSON rather than leaking the SPA shell to a protected route.
        if any(full_path.startswith(p) for p in SPA_PROTECTED_PREFIXES):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        index = _FRONTEND_BUILD / "index.html"
        if index.exists():
            return HTMLResponse(index.read_text())
        return JSONResponse({"detail": "Frontend not built"}, status_code=404)

# Force rebuild Thu Jun 25 14:08:14 UTC 2026
# Force rebuild Thu Jun 25 14:22:25 UTC 2026
