from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import shutil
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Union,
)

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from agent.loop import AgentRunner
from agent.memory import SessionMemory
from agent.user_memory import UserMemoryStore
from provider_router import ProviderRouter
from tokens import verify_token

# Import WorkspaceManager for preflight checks
try:
    from webui.workspaces import WorkspaceManager
except ImportError:
    WorkspaceManager = None

direct_chat_router = APIRouter(prefix="/api/chat", tags=["direct_chat"])

# ─── Data Models ──────────────────────────────────────────────────────────────

class ChatSendRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=50000)
    session_id: Optional[str] = None
    agent_mode: bool = False
    model: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    repo_url: Optional[str] = None
    repo_ref: Optional[str] = None

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None

class ChatSession(BaseModel):
    session_id: str
    title: str
    messages: List[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    owner_id: str

class AgentJobStatus(BaseModel):
    job_id: str
    session_id: str
    status: str  # queued, running, succeeded, failed
    phase: str   # planning, execution, verification
    message: str
    progress_events: List[Dict[str, Any]] = Field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ─── In-Memory Store ──────────────────────────────────────────────────────────

class ChatStore:
    def __init__(self):
        self._sessions: Dict[str, ChatSession] = {}
        self._agent_jobs: Dict[str, AgentJobStatus] = {}
        self._lock = asyncio.Lock()

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self._sessions.get(session_id)

    def create_session(self, owner_id: str, title: str = "New Chat", session_id: Optional[str] = None) -> ChatSession:
        sid = session_id or str(uuid.uuid4())
        session = ChatSession(session_id=sid, title=title, owner_id=owner_id)
        self._sessions[sid] = session
        return session

    def append_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        session = self._sessions.get(session_id)
        if session:
            msg = ChatMessage(role=role, content=content, metadata=metadata)
            session.messages.append(msg)
            session.updated_at = datetime.now(timezone.utc)
            return msg
        return None

    def list_sessions(self, owner_id: str) -> List[ChatSession]:
        return [s for s in self._sessions.values() if s.owner_id == owner_id]

    def delete_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
            # Clean up associated jobs
            job_ids = [jid for jid, job in self._agent_jobs.items() if job.session_id == session_id]
            for jid in job_ids:
                del self._agent_jobs[jid]
            return True
        return False

    def create_agent_job(self, session_id: str, job_id: str) -> AgentJobStatus:
        job = AgentJobStatus(
            job_id=job_id,
            session_id=session_id,
            status="queued",
            phase="planning",
            message="Agent job accepted",
        )
        self._agent_jobs[job_id] = job
        return job

    def get_agent_job(self, job_id: str) -> Optional[AgentJobStatus]:
        return self._agent_jobs.get(job_id)

    def update_agent_job(self, job_id: str, **kwargs):
        job = self._agent_jobs.get(job_id)
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)
            job.updated_at = datetime.now(timezone.utc)
            return job
        return None

_direct_chat_store = ChatStore()
_user_memory = UserMemoryStore()

# ─── Auth ─────────────────────────────────────────────────────────────────────

@dataclass
class UserIdentity:
    email: str
    sub: str
    name: str
    role: str

async def _get_current_user(request: Request) -> UserIdentity:
    user_data = getattr(request.state, "user", None)
    if not user_data:
        # Check for technical bypass keywords to ensure engineering requests
        # are always processed even if auth middleware hasn't fully populated state
        # (e.g. legacy direct-chat clients using API keys).
        auth_header = request.headers.get("authorization", "")
        if "Bearer " in auth_header:
             # Fallback to verify_token if state.user is missing but header is present
             token = auth_header[7:].strip()
             payload = verify_token(token, "access")
             if payload:
                 return UserIdentity(
                     email=payload["email"],
                     sub=payload["sub"],
                     name=payload.get("name", "User"),
                     role=payload.get("role", "user")
                 )

        raise HTTPException(status_code=401, detail="Unauthorized")
    return UserIdentity(
        email=user_data["email"],
        sub=user_data["_id"],
        name=user_data["name"],
        role=user_data["role"]
    )

# ─── GitHub Integration ───────────────────────────────────────────────────────

def _get_github_token_for_user(email: str) -> Union[str, Awaitable[str]]:
    # 1. Environment variables
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token

    # 2. Keyring or local config (if running on dev machine)
    # 3. User-scoped secrets (v3)
    try:
        from secrets_store import get_user_secret
        # get_user_secret is sync or async? v3.1 makes it async
        res = get_user_secret(email, "GITHUB_TOKEN")
        return res
    except (ImportError, Exception):
        return ""

# ─── Routes ───────────────────────────────────────────────────────────────────

@direct_chat_router.get("/sessions")
async def list_sessions(user: UserIdentity = Depends(_get_current_user)):
    sessions = _direct_chat_store.list_sessions(user.email)
    return {"sessions": sessions}

@direct_chat_router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: UserIdentity = Depends(_get_current_user)):
    session = _direct_chat_store.get_session(session_id)
    if not session or session.owner_id != user.email:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@direct_chat_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: UserIdentity = Depends(_get_current_user)):
    session = _direct_chat_store.get_session(session_id)
    if not session or session.owner_id != user.email:
        raise HTTPException(status_code=404, detail="Session not found")
    _direct_chat_store.delete_session(session_id)
    return {"ok": True}

@direct_chat_router.post("/send")
async def chat_send(
    req: ChatSendRequest,
    request: Request,
    user: UserIdentity = Depends(_get_current_user)
):
    session_id = req.session_id or str(uuid.uuid4())

    if req.agent_mode:
        # Preflight validation for repository references if provided
        ws_mgr = request.app.state.webui_workspaces
        validation = await ws_mgr.validate_repo_ref(req.repo_url, req.repo_ref)
        if not validation["ok"]:
            raise HTTPException(status_code=412, detail={"ready": False, "issues": validation["issues"]})

        return await _handle_agent_mode(session_id, req, user, request)
    else:
        return await _handle_direct_chat(session_id, req, user)

async def _handle_direct_chat(session_id: str, req: ChatSendRequest, user: UserIdentity):
    _ensure_session(session_id, user)
    _direct_chat_store.append_message(session_id, "user", req.content)
    
    # Simple direct LLM call
    router = ProviderRouter.from_env()
    provider = router.get_best_provider()
    if not provider:
        raise HTTPException(status_code=503, detail="No LLM providers available")
    
    # We use a helper to format context
    session = _direct_chat_store.get_session(session_id)
    history = [{"role": m.role, "content": m.content} for m in session.messages[-10:]]
    
    async def _stream():
        full_content = ""
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                # v3 router handles health/cooldown; here we call provider directly for simplicity
                payload = {
                    "model": req.model or provider.default_model,
                    "messages": history,
                    "stream": True
                }
                async with client.stream(
                    "POST",
                    f"{provider.normalized_base_url}/v1/chat/completions",
                    json=payload,
                    headers=provider.auth_headers()
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        if line == "data: [DONE]":
                            break
                        try:
                            chunk = json.loads(line[6:])
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                full_content += content
                                yield f"data: {json.dumps({'content': content})}\n\n"
                        except Exception:
                            continue
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        _direct_chat_store.append_message(session_id, "assistant", full_content)

    return StreamingResponse(_stream(), media_type="text/event-stream")

async def _handle_agent_mode(session_id: str, req: ChatSendRequest, user: UserIdentity, request: Request):
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    _direct_chat_store.create_agent_job(session_id, job_id)
    
    # Preflight validation for repository references if provided
    ws_mgr = request.app.state.webui_workspaces
    validation = await ws_mgr.validate_repo_ref(req.repo_url, req.repo_ref)
    if not validation["ok"]:
        raise HTTPException(status_code=412, detail={"ready": False, "issues": validation["issues"]})

    _ensure_session(session_id, user)
    _direct_chat_store.append_message(session_id, "user", req.content)

    _token_res = _get_github_token_for_user(user.email)
    if inspect.isawaitable(_token_res):
        github_token = await _token_res
    else:
        github_token = _token_res

    # GitHub preflight: for prompts that appear to require repo/git access, ensure
    # a token and git binary are available and provide structured actionable errors
    # rather than letting the job enter a vague failing state.
    lc = req.content.lower()
    repo_keywords = ("repo", "git", "pull request", "pull-request", "pr", "commit", "push", "clone", "checkout", "branch")
    if any(kw in lc for kw in repo_keywords):
        issues = []
        if not github_token:
            issues.append({
                "code": "missing_github_token",
                "message": "No GitHub token available for this user.",
                "fix_hint": "Add a GitHub token in Settings or set GH_TOKEN/GITHUB_TOKEN.",
            })
        # Validate git binary
        if not shutil.which("git"):
            issues.append({
                "code": "missing_git_binary",
                "message": "'git' binary not found on PATH.",
                "fix_hint": "Install git and ensure it is on PATH.",
            })

        # If metadata provides an explicit repo_url, attempt a non-destructive access check
        repo_url = None
        try:
            if req.metadata and isinstance(req.metadata, dict):
                repo_url = req.metadata.get("repo_url") or req.metadata.get("repository")
        except Exception:
            repo_url = None

        if repo_url:
            try:
                if WorkspaceManager is None:
                    raise ImportError("WorkspaceManager not found")
                mgr = WorkspaceManager()
                pre = mgr.repo_access_preflight(repo_url, github_token)
                if not pre.get("ok"):
                    issues.append({
                        "code": "git_repo_access",
                        "message": f"Could not access repository at {repo_url}.",
                        "fix_hint": "Verify the repository URL and ensure the GitHub token has access; ensure network egress to git hosts.",
                        "details": {"error": pre.get("error")},
                    })
                # Branch/ref validation if provided in metadata
                repo_ref = None
                try:
                    repo_ref = req.metadata.get("repo_ref") or req.metadata.get("branch") or req.metadata.get("ref") if req.metadata and isinstance(req.metadata, dict) else None
                except Exception:
                    repo_ref = None
                if repo_ref:
                    ref_check = mgr.validate_repo_ref(repo_url, repo_ref, github_token)
                    if not ref_check.get("ok"):
                        issues.append({
                            "code": "git_repo_ref",
                            "message": f"Could not find ref/branch '{repo_ref}' in repository {repo_url}.",
                            "fix_hint": "Verify the branch/ref name and that the token has repo access.",
                            "details": {"error": ref_check.get("error")},
                        })
                # Path validation if provided
                repo_path = None
                try:
                    repo_path = req.metadata.get("repo_path") or req.metadata.get("path") if req.metadata and isinstance(req.metadata, dict) else None
                except Exception:
                    repo_path = None
                if repo_path:
                    path_check = mgr.validate_repo_path(repo_url, repo_ref or "HEAD", repo_path, github_token)
                    if not path_check.get("ok"):
                        issues.append({
                            "code": "git_repo_path",
                            "message": f"Could not find path '{repo_path}' at ref '{repo_ref or 'HEAD'}' in repository {repo_url}.",
                            "fix_hint": "Verify path and ref; note path checks are GitHub-only unless host supports remote APIs.",
                            "details": {"error": path_check.get("error")},
                        })
            except Exception as e:
                # Fallback: surface an error indicating workspace preflight could not run.
                issues.append({
                    "code": "repo_preflight_failed",
                    "message": "Repository preflight check failed to run.",
                    "fix_hint": "Ensure the server environment allows git checks and WorkspaceManager is available.",
                    "details": {"error": str(e)},
                })

        # If a token exists, do a best-effort validation against GitHub API to detect
        # invalid tokens or insufficient scopes (we require 'repo' for repo edits).
        if github_token:
            try:
                headers = {
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "OpenClaw-Agent"
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    gh_resp = await client.get("https://api.github.com/user", headers=headers)
                    if gh_resp.status_code == 401:
                        issues.append({
                            "code": "invalid_github_token",
                            "message": "The provided GitHub token is invalid (401 Unauthorized).",
                            "fix_hint": "Check your token in Settings; it may have expired or been revoked.",
                        })
                    elif gh_resp.status_code == 200:
                        scopes = gh_resp.headers.get("X-OAuth-Scopes", "").split(",")
                        scopes = [s.strip() for s in scopes]
                        if "repo" not in scopes:
                             issues.append({
                                "code": "insufficient_github_scopes",
                                "message": f"GitHub token has insufficient scopes: [{', '.join(scopes)}].",
                                "fix_hint": "Token must have 'repo' scope for the agent to commit and create PRs.",
                            })
            except Exception:
                # Network error or GitHub API down; don't block if we can't verify token status
                pass

        if issues:
            _direct_chat_store.update_agent_job(job_id, status="failed", error="Preflight validation failed", result={"issues": issues})
            return {"session_id": session_id, "job_id": job_id, "status": "failed", "message": "Preflight validation failed", "issues": issues}

    # Start background loop
    asyncio.create_task(_run_agent_loop(session_id, job_id, req.content, user, req.metadata, req.model, github_token))

    return {
        "session_id": session_id,
        "job_id": job_id,
        "status": "queued",
        "message": "Agent job accepted",
        "ready": True,
        "issues": []
    }

async def _run_agent_loop(session_id: str, job_id: str, instruction: str, user: UserIdentity, metadata: Optional[Dict[str, Any]], model: Optional[str], github_token: str = ""):
    _direct_chat_store.update_agent_job(job_id, status="running", message="Initializing agent...")
    
    # Create a workspace for this job
    workspace_root = Path(os.environ.get("DIRECT_CHAT_AGENT_WORKSPACE_ROOT", ".data/direct-chat-agent-workspaces")) / user.email / job_id
    workspace_root.mkdir(parents=True, exist_ok=True)
    
    # If metadata contains repo info, clone it
    repo_url = (metadata or {}).get("repo_url") or (metadata or {}).get("repository")
    repo_ref = (metadata or {}).get("repo_ref") or (metadata or {}).get("branch") or (metadata or {}).get("ref")
    
    if repo_url:
        _direct_chat_store.update_agent_job(job_id, message=f"Cloning {repo_url}...")
        try:
            # Use git CLI directly for cloning
            clone_cmd = ["git", "clone", "--depth", "1"]
            if repo_ref:
                clone_cmd += ["-b", repo_ref]

            # Inject token into URL if available
            auth_url = repo_url
            if github_token and "github.com" in repo_url:
                auth_url = repo_url.replace("https://", f"https://x-access-token:{github_token}@")

            clone_cmd += [auth_url, "."]

            proc = await asyncio.create_subprocess_exec(
                *clone_cmd,
                cwd=str(workspace_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                _direct_chat_store.update_agent_job(job_id, status="failed", error=f"Clone failed: {stderr.decode()}")
                return
        except Exception as e:
            _direct_chat_store.update_agent_job(job_id, status="failed", error=f"Clone error: {str(e)}")
            return

    # Initialize AgentRunner
    # We prioritize NVIDIA NIM if key is available
    nim_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey") or ""
    ollama_base = os.environ.get("OLLAMA_BASE", "http://localhost:11434")

    headers = {}
    if nim_key:
        headers["Authorization"] = f"Bearer {nim_key}"
        base_url = "https://integrate.api.nvidia.com/v1"
        # Use nemotron as default for engineering tasks if not specified
        model_name = model or "nvidia/nemotron-3-super-120b-a12b"
    else:
        base_url = ollama_base
        model_name = model or os.environ.get("AGENT_PLANNER_MODEL", "qwen2.5-coder:32b")

    runner = AgentRunner(
        ollama_base=base_url,
        workspace_root=workspace_root,
        provider_headers=headers,
        email=user.email,
        github_token=github_token
    )

    # Step listener to update job progress
    def _on_step(event):
        _direct_chat_store.update_agent_job(job_id, progress_events=[event], message=event.get("message", "Processing..."))

    try:
        result = await runner.run(
            instruction=instruction,
            requested_model=model_name,
            user_id=user.email,
            memory_store=_user_memory
        )

        _direct_chat_store.update_agent_job(
            job_id,
            status="succeeded",
            phase="completed",
            message="Agent finished successfully",
            result=result
        )

        # Append assistant result to chat
        summary = result.get("summary", "Done.")
        _direct_chat_store.append_message(session_id, "assistant", summary)

    except Exception as e:
        _direct_chat_store.update_agent_job(job_id, status="failed", error=str(e))

@direct_chat_router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, user: UserIdentity = Depends(_get_current_user)):
    job = _direct_chat_store.get_agent_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify ownership via session
    session = _direct_chat_store.get_session(job.session_id)
    if not session or session.owner_id != user.email:
         raise HTTPException(status_code=403, detail="Forbidden")

    return job

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ensure_session(session_id: str, user: UserIdentity):
    if not _direct_chat_store.get_session(session_id):
        _direct_chat_store.create_session(user.email, session_id=session_id)
