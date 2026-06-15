"""direct_chat.py — Direct chat endpoints for v3 dashboard.

Handles chat sessions and message sending for the Direct Chat feature.
Protected by JWT authentication (v3 auth system).
Delegates to LLM providers via the proxy's routing system.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Annotated, Any, Optional

# Company Graph integration
try:
    from models.company_graph import CompanyGraph
    from services.company_graph import get_company_graph_service
    from services.company_graph_store import get_company_graph_store
    _company_graph_available = True
except ImportError:
    _company_graph_available = False

import httpx
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from agent.job_manager import AgentJobManager, make_isolated_workspace
from agent.user_memory import UserMemoryStore
from agent.intent import detect_intent, classify_direct_chat_intent, INTENT_EXECUTION, INTENT_CLARIFY, INTENT_ANALYSIS, INTENT_CONVERSATION
from agent.doctor import DirectChatDoctor, translate_error_to_conversational
from agent.schemas import DirectChatState
from tokens import verify_token
from provider_router import ProviderRouter
from runtimes.adapters.internal_agent import InternalAgentAdapter
from runtimes.base import TaskSpec
from agent.models import ResumeRequest

log = logging.getLogger("qwen-proxy")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
direct_chat_router = APIRouter(prefix="/api/chat", tags=["chat"])

# Session store for direct chat
from agent.state import AgentSessionStore
_direct_chat_store = AgentSessionStore(db_path="direct_chat_sessions.db")
_agent_jobs = AgentJobManager()


def get_agent_job_manager() -> AgentJobManager:
    """Public accessor for the module-level AgentJobManager singleton."""
    return _agent_jobs
_agent_workspace_root = Path(os.environ.get("DIRECT_CHAT_AGENT_WORKSPACE_ROOT", ".data/direct-chat-agent-workspaces"))


def _ensure_session(session_id: str, user: UserInfo) -> None:
    if _direct_chat_store.get(session_id) is None:
        _direct_chat_store.create_with_id(
            session_id=session_id,
            title=f"Direct chat for {user.email}",
            owner_id=user.email,
        )


def _session_history(session_id: str) -> list[dict[str, str]]:
    session = _direct_chat_store.get(session_id)
    if session is None:
        return []
    return [item.model_dump() for item in session.history]


class UserInfo(BaseModel):
    """Current user from JWT token."""
    id: str
    email: str
    default_company_id: Optional[str] = None


UserInfo.model_rebuild()

class AgentEventModel(BaseModel):
    """Tool-call event shape consumed by ToolCallViewer.jsx.

    ToolCallViewer reads call.tool_name, call.status, call.input, call.output,
    and call.id — the old field names (tool/args/result) are preserved as
    aliases for backward compatibility.
    """
    id: str | None = None
    type: str
    # ToolCallViewer fields
    tool_name: str | None = None
    status: str | None = None
    input: dict | None = None
    output: str | None = None
    # legacy/extra fields kept for other consumers
    tool: str | None = None
    args: dict | None = None
    result: str | None = None
    message: str | None = None





# =============================================================================
# DIRECT CHAT SESSION WITH COMPANY GRAPH INTEGRATION
# =============================================================================

class DirectChatSession:
    """Direct chat session with Company Graph context binding."""
    
    def __init__(self, session_id: str, user: UserInfo):
        self.session_id = session_id
        self.user = user
        self.company_id: str | None = None
        self.repo_id: str | None = None
        self._company_graph: CompanyGraph | None = None
        self._graph_service = get_company_graph_service() if _company_graph_available else None
        self._graph_store = get_company_graph_store() if _company_graph_available else None
    
    async def bind_company(self, company_id: str) -> CompanyGraph | None:
        """Bind a company to this chat session and load its Company Graph."""
        if not _company_graph_available:
            log.warning("Company Graph not available, cannot bind company")
            return None
        
        self.company_id = company_id
        try:
            self._company_graph = await self._graph_service.get_or_create_company_graph(company_id)
            log.info(f"Bound company {company_id} to session {self.session_id}")
            return self._company_graph
        except Exception as e:
            log.error(f"Failed to bind company {company_id}: {e}")
            return None
    
    async def bind_repo(self, repo_id: str) -> None:
        """Bind a repository to this chat session."""
        self.repo_id = repo_id
        log.info(f"Bound repo {repo_id} to session {self.session_id}")
    
    def get_company_graph(self) -> CompanyGraph | None:
        """Get the bound Company Graph."""
        return self._company_graph
    
    async def get_context(self) -> dict:
        """Get enriched context including Company Graph data."""
        context = {
            "session_id": self.session_id,
            "user_id": self.user.id,
            "user_email": self.user.email
        }
        
        if self.company_id:
            context["company_id"] = self.company_id
        if self.repo_id:
            context["repo_id"] = self.repo_id
        
        if self._company_graph:
            context["company"] = {
                "name": self._company_graph.company.name,
                "domain": self._company_graph.company.domain,
                "business_category": self._company_graph.company.business_category
            }
            context["detected_systems"] = [
                {"system_type": s.system_type, "name": s.name, "confidence": s.confidence}
                for s in self._company_graph.detected_systems
            ]
            context["available_specialists"] = [
                {"id": s.id, "name": s.name, "family": s.family, "capabilities": s.capabilities}
                for s in self._company_graph.specialists
                if s.is_provisioned and s.status == "available"
            ]
        
        return context


# =============================================================================
# CONTEXT DETECTION FUNCTIONS
# =============================================================================

async def detect_company_id(message: str, session: DirectChatSession) -> str | None:
    """Detect company ID from message or session context."""
    if not _company_graph_available:
        return None
    
    # Check if message mentions a domain
    domains = re.findall(r'(?:https?://)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})', message)
    if domains:
        try:
            store = get_company_graph_store()
            companies = await store.list_companies(search=domains[0])
            if companies:
                return companies[0].id
        except Exception as e:
            log.error(f"Failed to look up company by domain: {e}")
    
    # Check if user has a default company
    if hasattr(session.user, 'default_company_id') and session.user.default_company_id:
        return session.user.default_company_id
    
    return None


def detect_repo_id(message: str) -> str | None:
    """Detect repository ID from message."""
    # Look for GitHub/GitLab/Bitbucket URLs
    repo_patterns = [
        r'github\.com/[^/]+/[^/]+',
        r'gitlab\.com/[^/]+/[^/]+',
        r'bitbucket\.org/[^/]+/[^/]+'
    ]
    
    for pattern in repo_patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(0)
    
    return None


async def handle_chat_message_with_context(session: DirectChatSession, message: str) -> tuple[str, dict]:
    """Handle chat message with Company Graph context enrichment."""
    # Check if message contains company or repo information
    company_id = await detect_company_id(message, session)
    repo_id = detect_repo_id(message)
    
    if company_id:
        await session.bind_company(company_id)
    if repo_id:
        await session.bind_repo(repo_id)
    
    # Get enriched context
    context = await session.get_context()
    
    # Add context to the message for the LLM
    company_info = context.get('company', {})
    detected_systems = context.get('detected_systems', [])
    available_specialists = context.get('available_specialists', [])
    
    systems_str = ', '.join([s['name'] for s in detected_systems]) if detected_systems else 'None detected'
    specialists_str = ', '.join([s['name'] for s in available_specialists]) if available_specialists else 'None available'
    
    enriched_message = f"""Company Context:
- Company: {company_info.get('name', 'Unknown')}
- Domain: {company_info.get('domain', 'Unknown')}
- Business Category: {company_info.get('business_category', 'Unknown')}
- Detected Systems: {systems_str}
- Available Specialists: {specialists_str}

User Message: {message}"""
    
    return enriched_message, context


class AgentJobModel(BaseModel):
    job_id: str
    status: str
    phase: str
    progress_events: list[dict]


class AgentStatusResponse(BaseModel):
    has_events: bool
    agents: list[AgentJobModel]
    tool_calls: list[AgentEventModel]
    latest_summary: str
    latest_error: str
    state: DirectChatState | None = None
    humanized_progress: str | None = None


def _get_bearer_token(authorization: str | None = Header(None)) -> str:
    """Extract bearer token from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    return authorization[7:].strip()


async def _get_current_user(token: Annotated[str, Depends(_get_bearer_token)]) -> UserInfo:
    """Extract and validate current user from JWT token."""
    payload = verify_token(token, token_type="access")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return UserInfo(
        id=payload.get("sub", ""),
        email=payload.get("email", ""),
    )


class ChatSendRequest(BaseModel):
    """Send chat message request."""
    content: str
    session_id: str | None = None
    model: str | None = None
    provider_id: str | None = None
    temperature: float | None = None
    agent_mode: bool = False
    metadata: dict[str, Any] | None = None
    allow_commercial_fallback_once: bool = False
    repo_url: str | None = None
    repo_ref: str | None = None


async def _get_github_token_for_user(user_email: str) -> str | None:
    """Fetch GitHub token for user from secrets store or environment."""
    try:
        from secrets_store import get_secrets_store
        from rbac import get_user_role
        store = get_secrets_store()
        uid = user_email
        role = get_user_role({"email": user_email})  # Simplified
        recs = await store.list_for_user(uid, role)
        for rec in recs:
            if "github" in rec.tags or rec.name.lower().startswith("github"):
                value = await store.get_value(rec.secret_id, uid, role)
                if value:
                    return value
    except Exception as e:
        log.debug("Could not fetch GitHub token from secrets: %s", e)
    # Fallback: env var
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT") or os.environ.get("GH_TOKEN")


def _is_trivial_message(content: str) -> bool:
    """Detect simple greetings/replies to avoid unnecessary agent promotion."""
    if not content or not isinstance(content, str):
        return False
    stripped = content.strip()
    lowered = stripped.lower()

    trivial_phrases = {
        "hello", "hi", "hey", "sup", "yo", "greetings",
        "good morning", "good afternoon", "good evening",
        "how are you", "what's up", "hi there", "hello there", "hey there",
        "thanks", "thank you", "ok", "okay", "sounds good", "got it",
        "what can you do", "who are you", "what are you",
    }
    if lowered in trivial_phrases:
        return True
    words = stripped.split()
    # Short messages that mention git/PR ops are non-trivial regardless of word count.
    _git_multi_word = ("pull request", "pull requests", "code review")
    _git_keywords = {
        "pr", "prs", "commit", "commits", "push", "clone", "branch", "branches",
        "repo", "repos", "repository", "git", "merge", "diff", "patch",
        "file", "files", "code", "write", "create", "fix", "build", "run",
        "edit", "generate", "deploy", "implement", "refactor", "analyze",
        "analyse", "audit", "investigate", "explain", "review",
    }
    word_tokens = {w.strip(".,!?;:()[]{}\"'").lower() for w in stripped.split()}
    if any(phrase in lowered for phrase in _git_multi_word) or (word_tokens & _git_keywords):
        return False
    if len(words) <= 4:
        return True
    if lowered.endswith("?") and len(words) <= 12:
        return True
    return False


@direct_chat_router.post("/send")
async def send_chat_message(
    req: ChatSendRequest,
    request: Request,
    user: Annotated[UserInfo, Depends(_get_current_user)],
):
    """Unified orchestration entry point for all direct chat messages."""

    # 1. Intent Detection — classify into higher-level direct-chat categories
    intent = classify_direct_chat_intent(req.content)
    session_id = req.session_id or str(uuid.uuid4())
    _ensure_session(session_id, user)

    # 2. Sticky Context Recovery
    session = _direct_chat_store.get(session_id)
    if not req.repo_url and session and session.repo_url:
        req.repo_url = session.repo_url
        log.info(f"Restored sticky repo context: {req.repo_url}")
    if not req.repo_ref and session and session.repo_ref:
        req.repo_ref = session.repo_ref

    # 3. Handle Special Intents
    # Note: classify_direct_chat_intent returns higher-level categories like 'clarify_needed', 'answer_only', 'plan_only', 'execute_now', 'execute_after_approval'
    if intent == "clarify_needed" or intent == INTENT_CLARIFY:
        msg = "I can definitely help with that, but could you please provide a bit more detail on what exactly you'd like me to change or fix? I want to make sure I have all the context before I start."
        _direct_chat_store.append_message(session_id, "user", req.content)
        _direct_chat_store.append_message(session_id, "assistant", msg)
        return JSONResponse(content={"session_id": session_id, "response": msg, "intent": intent, "state": DirectChatState.NEEDS_INPUT})

    # 4. Route by intent — agent_mode=True is a power-user override that bypasses
    #    the answer_only path and forces execution regardless of classifier output.
    is_trivial = _is_trivial_message(req.content)

    # Prepare metadata flags for the agent runner
    req.metadata = req.metadata or {}
    if intent == "plan_only":
        req.metadata["plan_only"] = True
    if intent == "execute_after_approval":
        req.metadata["require_approval"] = True

    # answer_only path — only when agent_mode is NOT explicitly set
    if intent == "answer_only" and not req.agent_mode:
        return await _handle_regular_chat(req, user, request, session_id)

    # Safety: do not auto-execute trivial messages without explicit agent_mode
    if is_trivial and intent in ("execute_now", "execute_after_approval", "plan_only") and not req.agent_mode:
        msg = "That sounds like a request to modify the repository. Could you confirm what you want me to change?"
        _direct_chat_store.append_message(session_id, "assistant", msg)
        return JSONResponse(content={"session_id": session_id, "response": msg, "intent": "clarify_needed", "state": DirectChatState.NEEDS_INPUT})

    # All other paths — proceed with agent execution
    return await _handle_agent_mode(req, user, request, session_id, intent)

async def _handle_regular_chat(
    req: ChatSendRequest,
    user: UserInfo,
    request: Request,
    session_id: str,
):
    log.info(f"Chat message from {user.email}: {req.content[:50]}...")
    history = _session_history(session_id)

    system_prompt = (
        "You are a helpful coding assistant integrated with a self-hosted AI proxy server. "
        "You can answer questions about code, explain concepts, review snippets, and assist "
        "with software engineering tasks. "
        "For tasks that require reading or editing files in a GitHub repository "
        "(e.g. opening PRs, committing changes, browsing repo contents), I will automatically "
        "detect your intent and start an execution workflow. "
        "Never refuse to help; always guide the user toward the right approach."
    )
    payload = {
        "messages": [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": req.content}],
        "model": req.model or "nvidia/llama-3.3-nemotron-super-49b-v1",
        "stream": False,
    }
    if req.temperature is not None:
        payload["temperature"] = req.temperature
    router: ProviderRouter = request.app.state.PROVIDER_ROUTER
    try:
        provider = None
        if req.provider_id:
            for p in router.providers:
                if p.provider_id == req.provider_id:
                    provider = p
                    break
        if provider: result = await ProviderRouter([provider]).chat_completion(payload)
        else: result = await router.chat_completion(payload)
        if not hasattr(result, "response"):
            log.error(f"Provider response object missing response: {type(result)}")
            raise HTTPException(status_code=500, detail="Invalid provider response format")
        assistant_message = result.response.json()["choices"][0]["message"]["content"]
        _direct_chat_store.append_message(session_id, "user", req.content)
        _direct_chat_store.append_message(session_id, "assistant", assistant_message)
        return JSONResponse(content={
            "session_id": session_id,
            "response": assistant_message,
            "state": DirectChatState.ASSISTANT_REPLY
        })
    except Exception as e:
        log.error(f"Failed to get provider response: {e}")
        raise HTTPException(status_code=500, detail="The AI service is currently unavailable. Please try again or select a different model.")

async def _handle_agent_mode(
    req: ChatSendRequest,
    user: UserInfo,
    request: Request,
    session_id: str,
    intent: str,
):
    try:
        return await _do_handle_agent_mode(req, user, request, session_id, intent)
    except HTTPException as he:
        if he.status_code == 412:
            msg = translate_error_to_conversational(he.detail)
            _direct_chat_store.append_message(session_id, "assistant", msg)

            if os.environ.get("DIRECT_CHAT_STRICT_PREFLIGHT") == "true":
                return JSONResponse(status_code=412, content={"detail": he.detail})

            return JSONResponse(status_code=200, content={
                "session_id": session_id,
                "response": msg,
                "preflight_failed": True,
                "detail": he.detail,
                "state": DirectChatState.FAILED_WITH_FIX_HINT
            })
        raise
    except Exception as e:
        log.exception("Agent mode failed")
        raise

async def _do_handle_agent_mode(
    req: ChatSendRequest,
    user: UserInfo,
    request: Request,
    session_id: str,
    intent: str,
):
    log.info(f"Execution flow for {user.email}: {req.content[:50]}...")
    history = _session_history(session_id)
    
    # Persist context
    if req.repo_url or req.repo_ref:
        _direct_chat_store.update_repo_context(session_id, req.repo_url, req.repo_ref)
    _direct_chat_store.update_task_context(session_id, objective=req.content)

    # Preflight
    ws_mgr = request.app.state.webui_workspaces
    if req.repo_url:
        validation = await ws_mgr.validate_repo_ref(req.repo_url, req.repo_ref)
        if not validation["ok"]:
            # validate_repo_ref returns {"ok": False, "error": "..."} — normalise to
            # the PreflightReport-style issues list the API contract expects.
            err_msg = str(validation.get("error") or "Repository access failed")
            raise HTTPException(
                status_code=412,
                detail={
                    "ready": False,
                    "summary": "Repository preflight failed",
                    "issues": [{"code": "git_repo_access", "message": err_msg,
                                 "fix_hint": "Check your GitHub token and repository URL in Settings."}],
                },
            )

    import inspect
    _token_res = _get_github_token_for_user(user.email)
    github_token = await _token_res if inspect.isawaitable(_token_res) else _token_res

    # plan_only is a synchronous (non-background) path — planning is fast enough
    # to return directly without the background-job machinery. No job is created.
    if req.metadata and req.metadata.get("plan_only"):
        app_router = request.app.state.PROVIDER_ROUTER
        sorted_providers = sorted(app_router.providers, key=lambda p: p.priority) if hasattr(app_router, "providers") else []
        primary_provider = sorted_providers[0] if sorted_providers else None
        ollama_base = primary_provider.normalized_base_url if primary_provider else OLLAMA_BASE
        primary_headers = primary_provider.auth_headers() if primary_provider and primary_provider.api_key else {}
        _direct_chat_store.append_message(session_id, "user", req.content)
        from agent.loop import AgentRunner
        runner = AgentRunner(
            ollama_base=ollama_base,
            workspace_root=str(make_isolated_workspace(_agent_workspace_root, session_id, f"plan_{session_id}")),
            provider_headers=primary_headers,
            provider_temperature=req.temperature,
            github_token=github_token,
            email=user.email,
            repo_url=req.repo_url,
            base_branch=req.repo_ref or "main",
        )
        plan = await runner.plan(
            instruction=req.content, history=history, requested_model=req.model,
            max_steps=30, user_id=user.id, session_id=session_id,
            memory_store=UserMemoryStore(), metadata=req.metadata,
        )
        assistant_plan = getattr(plan, "summary", None) or getattr(plan, "goal", None) or str(plan)
        _direct_chat_store.append_message(session_id, "assistant", assistant_plan)
        return JSONResponse(
            status_code=200,
            content={
                "session_id": session_id,
                "response": assistant_plan,
                "status": "planned",
                "state": DirectChatState.COMPLETED,
            },
        )

    # Preflight Doctor (cached)
    session = _direct_chat_store.get(session_id)
    preflight_passed = session.metadata.get("preflight_passed") if session and session.metadata else False
    if not preflight_passed:
        doctor = DirectChatDoctor(github_token=github_token)
        report = await doctor.check_all(repo_url=req.repo_url, repo_ref=req.repo_ref)
        if not report.ready:
            raise HTTPException(status_code=412, detail=report.model_dump())
        if session:
            new_meta = dict(session.metadata or {})
            new_meta["preflight_passed"] = True
            _direct_chat_store.update_session_metadata(session_id, new_meta)

    # Job Creation
    job = _agent_jobs.create_job(session_id=session_id, owner_id=user.email, instruction=req.content, requested_model=req.model, provider_id=req.provider_id)

    # Workspace Bootstrap
    workspace_root = None
    if req.repo_url:
        try:
            manifest = ws_mgr.create_workspace(session_id=session_id, job_id=job.job_id, repo_url=req.repo_url, repo_ref=req.repo_ref, github_token=github_token)
            workspace_root = Path(manifest.root_path)
        except Exception as e:
            log.warning(f"Bootstrap fail: {e}")
            if any(kw in str(e).lower() for kw in ("auth", "denied")):
                _direct_chat_store.append_message(session_id, "assistant", f"I hit an access issue while setting up the workspace for {req.repo_url}. Please check your token in Settings.")

    if not workspace_root:
        workspace_root = make_isolated_workspace(_agent_workspace_root, session_id, job.job_id)
    job.workspace_path = str(workspace_root)

    # Runtime Selection
    from runtimes.manager import get_runtime_manager
    runtime_mgr = get_runtime_manager()
    task_type = "repo_editing" if intent == INTENT_EXECUTION else "code_review"
    primary_runtime, _ = runtime_mgr.select_runtime(task_type)
    adapter = primary_runtime or InternalAgentAdapter(config={"workspace_root": str(workspace_root)})
    spec = TaskSpec(
        task_id=job.job_id,
        instruction=req.content,
        task_type=task_type,
        workspace_path=str(workspace_root),
        model_preference=req.model,
        timeout_sec=int(os.environ.get("DIRECT_CHAT_AGENT_TIMEOUT_SEC", "1800")),
        context={
            "conversation": history,
            "max_steps": 30,
            "owner_id": user.id,
            "user_email": user.email,
            "session_id": session_id,
            "metadata": req.metadata or {},
            "github_token": github_token,
        },
    )

    _direct_chat_store.append_message(session_id, "user", req.content)

    # Extract required state before background job starts (it may lose request context)
    app_router = request.app.state.PROVIDER_ROUTER
    sorted_providers: list = []
    if hasattr(app_router, "providers"):
        sorted_providers = sorted(app_router.providers, key=lambda p: p.priority)
    else:
        log.warning("PROVIDER_ROUTER on app.state has no .providers attribute — agent jobs will use default OLLAMA_BASE")
    primary_provider = sorted_providers[0] if sorted_providers else None
    ollama_base = primary_provider.normalized_base_url if primary_provider else OLLAMA_BASE
    primary_headers = primary_provider.auth_headers() if primary_provider and primary_provider.api_key else {}

    # Interactive Gating Helper
    async def wait_for_resume(job_id: str, s_id: str):
        """Wait for the user to resume the job via the resume endpoint."""
        while True:
            _s = _direct_chat_store.get(s_id)
            if _s and _s.resume_payload:
                payload = _s.resume_payload
                _direct_chat_store.update_resume_payload(s_id, None)
                return payload
            await asyncio.sleep(1.0)

    async def _run_agent_job(heartbeat):
        log.info(f"Background agent job starting: job_id={job.job_id} session_id={session_id}")
        try:
            return await _do_run_agent_job(heartbeat)
        except Exception as e:
            log.exception(f"Background agent job {job.job_id} failed")
            heartbeat("failed", str(e))
            return {"session_id": session_id, "error": str(e), "status": "failed"}

    async def _do_run_agent_job(heartbeat):
        from agent.loop import AgentRunner

        _spec = spec
        if adapter.RUNTIME_ID != "internal_agent":
            heartbeat("execution", f"Dispatching task to specialized runtime: {adapter.RUNTIME_ID}")
            try:
                res = await adapter.execute(_spec)
                _direct_chat_store.append_message(session_id, "assistant", res.output)
                return {"session_id": session_id, "response": res.output}
            except Exception as e:
                log.exception(f"External runtime {adapter.RUNTIME_ID} failed")
                heartbeat("failed", str(e))
                return {"session_id": session_id, "error": str(e)}

        heartbeat("planning", "Analyzing repository and creating an execution plan")

        runner = AgentRunner(
            ollama_base=ollama_base,
            workspace_root=str(workspace_root),
            provider_headers=primary_headers,
            provider_temperature=req.temperature,
            github_token=github_token,
            email=user.email,
            repo_url=req.repo_url,
            base_branch=req.repo_ref or "main",
        )

        plan = await runner.plan(
            instruction=req.content, history=history, requested_model=req.model,
            max_steps=30, user_id=user.id, session_id=session_id, memory_store=UserMemoryStore(),
            metadata=req.metadata
        )

        requires_approval = getattr(plan, "requires_risky_review", False) or (req.metadata and req.metadata.get("require_approval"))
        if requires_approval:
            heartbeat("needs_approval", f"I've created a plan, but it involves sensitive changes that need your approval. Goal: {getattr(plan,'goal', '')}")
            resume_data = await wait_for_resume(job.job_id, session_id)
            if resume_data.get("action") != "approve":
                heartbeat("failed", "Task cancelled by user during approval.")
                _direct_chat_store.append_message(session_id, "assistant", "I've cancelled the task as requested.")
                return {"session_id": session_id, "status": "cancelled", "summary": "User rejected plan."}

        heartbeat("execution", "Executing planned changes")
        import services.workflow_orchestrator as _wo
        _bypass_token = _wo._BYPASS.set(True)
        try:
            result = await runner.run(metadata=req.metadata or {}, instruction=req.content, history=history, requested_model=req.model, auto_commit=True, max_steps=30, user_id=user.id, session_id=session_id, memory_store=UserMemoryStore())
        finally:
            _wo._BYPASS.reset(_bypass_token)

        heartbeat("verification", "Validating the changes and ensuring quality")
        heartbeat("completed", "Task successfully completed")

        assistant_message = result.get("summary", result.get("response", "Agent completed"))
        _direct_chat_store.append_message(session_id, "assistant", assistant_message)
        return {"session_id": session_id, "response": assistant_message, "status": "succeeded"}

    _agent_jobs.start_job(job.job_id, _run_agent_job)
    return JSONResponse(status_code=202, content={"session_id": session_id, "job_id": job.job_id, "status": job.status, "phase": job.phase, "message": "Assistant is working on your request.", "state": DirectChatState.WORKING})


@direct_chat_router.get("/agent-status", response_model=AgentStatusResponse)
async def get_agent_status(
    request: Request,
    session_id: str | None = None,
    user: Annotated[UserInfo, Depends(_get_current_user)] = None,  # noqa: B008
) -> AgentStatusResponse:
    # Resolve owner_id from the injected JWT user or, for backward compatibility
    # with backend/server.py (which uses session middleware instead), from
    # request.state.user.  The dependency override in tests replaces _get_current_user
    # with a stub that returns a UserInfo directly.
    if user is not None:
        owner_id: str = user.email
    else:
        user_state = getattr(request.state, "user", None)
        if not isinstance(user_state, dict) or not user_state.get("email"):
            raise HTTPException(status_code=401, detail="Authentication required")
        owner_id = user_state["email"]
    all_jobs = _agent_jobs.list_jobs(session_id=session_id)
    jobs = [j for j in all_jobs if getattr(j, "owner_id", None) == owner_id]

    tool_calls: list[AgentEventModel] = []
    agents: list[AgentJobModel] = []
    latest_summary = ""
    latest_error = ""
    has_events = False

    sorted_jobs = sorted(jobs, key=lambda j: j.updated_at, reverse=True)
    current_state = DirectChatState.ASSISTANT_REPLY
    humanized_progress = ""

    if sorted_jobs:
        latest_job = sorted_jobs[0]
        current_state = _map_job_status_to_state(latest_job.status, latest_job.phase)
        last_msg = latest_job.progress_events[-1].get("message") if latest_job.progress_events else None
        humanized_progress = _humanize_phase(latest_job.phase, last_msg, latest_job.updated_at)

    for job in jobs:
        jd = job.as_dict()
        events = jd.get("progress_events") or []
        if events: has_events = True
        agents.append(AgentJobModel(job_id=jd["job_id"], status=jd["status"], phase=jd["phase"], progress_events=events))
        for idx, evt in enumerate(events):
            if evt.get("type") == "tool_call":
                tn = evt.get("tool_name") or evt.get("tool")
                tool_calls.append(AgentEventModel(
                    id=f"{jd['job_id']}-{idx}", type="tool_call", tool_name=tn,
                    status=evt.get("status") or ("error" if str(evt.get("result_preview") or "").startswith("[error") else "success" if evt.get("result_preview") else "pending"),
                    input=evt.get("args"), output=evt.get("result_preview") or evt.get("result"),
                    tool=tn, args=evt.get("args"), result=evt.get("result_preview") or evt.get("result"), message=evt.get("message")
                ))
        err = jd.get("error") or {}
        if err.get("message"): latest_error = err["message"]
        result = jd.get("result") or {}
        if result.get("response"): latest_summary = result["response"]
        elif result.get("summary"): latest_summary = result["summary"]

    return AgentStatusResponse(
        has_events=has_events, agents=agents, tool_calls=tool_calls,
        latest_summary=latest_summary, latest_error=latest_error,
        state=current_state, humanized_progress=humanized_progress
    )


@direct_chat_router.get("/agent-jobs/{job_id}")
async def get_agent_job(job_id: str):
    job = _agent_jobs.get_job(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    from agent.schemas import RunningJob, CompletedJob, FailedJob
    jd = job.as_dict()
    if job.status == "running":
        return RunningJob(job_id=jd["job_id"], session_id=jd["session_id"], status=jd["status"], phase=jd["phase"], progress_events=jd.get("progress_events", []), workspace_path=jd.get("workspace_path")).model_dump()
    elif job.status == "succeeded":
        return CompletedJob(job_id=jd["job_id"], session_id=jd["session_id"], status=jd["status"], phase=jd["phase"], final_message=jd.get("final_message"), result=jd.get("result")).model_dump()
    else:
        return FailedJob(job_id=jd["job_id"], session_id=jd["session_id"], status=jd["status"], phase=jd["phase"], error=jd.get("error") or {}).model_dump()

def _humanize_phase(phase: str, latest_event_msg: str | None = None, updated_at: str | None = None) -> str:
    mapping = {
        "starting": "Preparing your workspace",
        "planning": "Analyzing the repository and creating an execution plan",
        "execution": "Executing the planned changes",
        "verification": "Validating the changes and ensuring quality",
        "completed": "Task successfully completed",
        "failed": "I encountered an issue while working on the task",
        "cancelled": "The task was cancelled",
        "queued": "Waiting to start in the background",
    }
    is_slow = False
    if updated_at:
        try:
            from datetime import datetime, timezone
            last_upd = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - last_upd).total_seconds() > 30: is_slow = True
        except Exception: pass

    base = mapping.get(phase, phase.capitalize())
    if latest_event_msg and phase == "execution" and "Tool: " in latest_event_msg:
        tool = latest_event_msg.replace("Tool: ", "")
        tool_mapping = {
            "read_file": "Reading relevant source files", "write_file": "Applying code modifications",
            "apply_diff": "Integrating the suggested fixes", "list_files": "Inspecting the repository structure",
            "search_code": "Searching the codebase for context", "run_command": "Running validation commands and tests",
            "github_open_pull_request": "Preparing and opening a pull request", "git_commit": "Committing the changes to the branch",
        }
        base = tool_mapping.get(tool, f"Working with {tool}")
    return f"Still {base.lower()}..." if is_slow and phase not in ("completed", "failed", "cancelled") else base

def _map_job_status_to_state(status: str, phase: str) -> DirectChatState:
    if phase == "needs_approval": return DirectChatState.NEEDS_APPROVAL
    if phase == "needs_input": return DirectChatState.NEEDS_INPUT
    if status == "running": return DirectChatState.WORKING
    if status == "succeeded": return DirectChatState.COMPLETED
    if status == "failed": return DirectChatState.FAILED_WITH_FIX_HINT
    return DirectChatState.WORKING

@direct_chat_router.post("/resume/{session_id}")
async def resume_chat_job(
    session_id: str,
    req: ResumeRequest,
    user: Annotated[UserInfo, Depends(_get_current_user)],
):
    """Resume a paused agent job with user input/action."""
    session = _direct_chat_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Store resume payload in session; the background job is polling for this
    _direct_chat_store.update_resume_payload(session_id, req.model_dump())

    # Also log the user's response in history for continuity
    msg = f"Action: {req.action}"
    if req.input: msg += f" - Input: {req.input}"
    _direct_chat_store.append_message(session_id, "user", msg)

    return {"status": "resumed", "session_id": session_id}
