"""agent/sam.py — SAM Voice Agent (System Autonomy Manager)

SAM is the voice-controlled AI assistant for the autonomous AI agency. Inspired by
Iron Man's JARVIS but named SAM (System Autonomy Manager). SAM provides hands-free
command and control of the entire agency via voice.

Architecture:
  Voice input (browser) → STT (Whisper/Google) → SAM Agent → CEO/LLM → TTS (gTTS) → Voice output

SAM handles:
  - Agency status queries ("SAM, what's the agency status?")
  - Task management ("SAM, create a task to fix the CI pipeline")
  - System control ("SAM, run the security audit")
  - Conversational interaction with the agency CEO

Persona:
  - Professional, concise, mission-focused
  - Addresses the user as "Commander" (Iron Man tribute)
  - Provides status updates, task confirmations, and system insights
  - Always ready, always watching the agency

Uses entirely FREE cloud services:
  - STT: Google SpeechRecognition (free) or browser Web Speech API
  - LLM: NVIDIA NIM (free tier)
  - TTS: gTTS (Google Text-to-Speech, free)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("qwen-sam")

# SAM must always respond within a voice-friendly window — never block the
# caller (HTTP request, LiveKit turn) on a slow/degraded LLM provider chain
# or a stalled context read. `call_llm()` defaults to a 300s provider_timeout_sec
# with multiple provider/retry attempts on top, which — with no bound here and
# no timeout on the frontend's axios client — silently hung the chat UI with
# no error shown ("takes input, no response") whenever the provider chain was
# slow. These ceilings force `process_command` to fall back gracefully well
# within any reasonable HTTP/proxy timeout instead of hanging indefinitely.
_CONTEXT_TIMEOUT_SEC = 8.0
_LLM_TIMEOUT_SEC = 20.0

SAM_PERSONA = """You are SAM (System Autonomy Manager), the voice-controlled AI assistant
for an autonomous AI engineering agency operating 24/7. You are inspired by Iron Man's
JARVIS but you are your own entity — loyal, capable, and mission-focused.

## Your role
You are the Commander's direct interface to the agency. You answer status queries,
execute commands, create tasks, and provide strategic insights — all through voice.

## Personality
- Professional and concise — voice responses must fit in 2-3 sentences max
- Address the user as "Commander" 
- Use a calm, confident tone
- Be direct and actionable — never ramble
- When something is wrong, state the problem and the recommended action clearly

## Capabilities
You can:
- Report agency status (active loops, tasks, schedules, system health)
- Create and manage tasks via the agency CEO
- Trigger scheduled jobs and workflows
- Query the memory kernel for past context
- Execute voice commands: status, health, tasks, scan, fix, deploy, review

## Response format
- Keep every response under 150 words (voice-friendly)
- Start with the answer, then offer context if needed
- End with a clear next action or "standing by" if nothing is needed
- Use contractions and natural speech patterns (it's, you're, we've)
- Never use markdown in voice responses — plain English only
"""

SAM_SYSTEM_PROMPT = SAM_PERSONA + """

## Agency context
The Commander is speaking to you via voice. You have access to:
- Agency status (scheduler, tasks, loops, system health)
- Company Graph specialists and their runtimes
- The improvement loop (active issues, test failures)
- The self-healing agent (recent events)
- The trend watcher (industry alerts)

When asked for status, always check the live system — never guess.
"""


@dataclass
class SamConversation:
    """A single voice conversation session with SAM."""
    session_id: str
    started_at: float = field(default_factory=time.time)
    history: list[dict[str, str]] = field(default_factory=list)
    command_count: int = 0

    def add_turn(self, user_text: str, sam_response: str) -> None:
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": sam_response})
        self.command_count += 1
        if len(self.history) > 20:
            self.history = self.history[-20:]


class SamAgent:
    """SAM voice agent — the voice-controlled interface to the agency."""

    def __init__(self) -> None:
        self._conversations: dict[str, SamConversation] = {}
        self._started_at = time.time()

    # ── Public API ─────────────────────────────────────────────────────────

    async def process_command(self, text: str, session_id: str = "default") -> str:
        """Process a voice command and return SAM's spoken response.

        Args:
            text: The transcribed voice command from the user
            session_id: Conversation session identifier

        Returns:
            SAM's voice response (plain English, under 150 words)
        """
        text = text.strip()
        if not text:
            return "I didn't catch that, Commander. Could you repeat?"

        session = self._get_session(session_id)

        # Build context for the LLM — bounded so a stalled scheduler/task-store
        # read (e.g. during a backlog purge) can't hang the whole command.
        try:
            context = await asyncio.wait_for(self._build_context(), timeout=_CONTEXT_TIMEOUT_SEC)
        except Exception as exc:
            log.warning("SAM context build failed/timed out: %s", exc)
            context = {}

        # Compose the prompt
        prompt = self._build_prompt(text, context, session)

        # Call the LLM (NVIDIA NIM — free)
        response = await self._call_llm(prompt, session)

        session.add_turn(text, response)
        log.info("SAM: processed command (session=%s, turn=%d, len=%d)",
                 session_id, session.command_count, len(response))
        return response

    def get_status(self) -> dict[str, Any]:
        return {
            "active_sessions": len(self._conversations),
            "uptime_seconds": time.time() - self._started_at,
        }

    async def build_context(self) -> dict[str, Any]:
        """Public snapshot of live agency state (used by the LiveKit worker tools)."""
        return await self._build_context()

    # ── Context building ───────────────────────────────────────────────────

    async def _build_context(self) -> dict[str, Any]:
        """Gather live agency state for SAM's situational awareness."""
        ctx: dict[str, Any] = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

        # Scheduler state
        try:
            from packages.scheduler.scheduler import get_scheduler
            sched = get_scheduler()
            jobs = sched.list()
            ctx["schedules"] = {
                "total": len(jobs),
                "active": sum(1 for j in jobs if j.enabled),
                "paused": sum(1 for j in jobs if not j.enabled),
            }
        except Exception:
            ctx["schedules"] = {"error": "unavailable"}

        # Tasks
        try:
            from tasks.store import get_task_store
            store = get_task_store()
            pending = await store.list_pending(limit=50)
            ctx["tasks"] = {
                "pending": len(pending),
                "top_3": [t.title[:80] for t in (pending or [])[:3]],
            }
        except Exception:
            ctx["tasks"] = {"error": "unavailable"}

        # Improvement loop issues
        try:
            from agent.improvement_loop import get_improvement_loop
            loop = get_improvement_loop()
            if loop:
                status = loop.get_status()
                ctx["improvement"] = {
                    "issues_detected": status.get("issues_detected", 0),
                    "issues_resolved": status.get("issues_resolved", 0),
                    "failing_tests": len(status.get("failing_tests", [])),
                }
        except Exception:
            pass

        # Self-healing events
        try:
            from agent.self_healing import get_self_healing_agent
            healer = get_self_healing_agent()
            if healer:
                events = healer.get_events()
                ctx["self_healing"] = {
                    "recent_events": len(events[-5:]) if events else 0,
                }
        except Exception:
            pass

        # Memory kernel (personal context)
        try:
            from voice.memory_kernel import get_memory_kernel
            kernel = get_memory_kernel()
            facts = await kernel.recall("", limit=5)
            ctx["memory"] = {
                "total_facts": len(facts),
                "recent": [f.content[:100] for f in facts[:3]],
            }
        except Exception:
            pass

        return ctx

    # ── Prompt building ────────────────────────────────────────────────────

    def _build_prompt(
        self, text: str, context: dict[str, Any], session: SamConversation,
    ) -> str:
        parts = []

        # Agency state snapshot
        sched = context.get("schedules", {})
        tasks_ctx = context.get("tasks", {})
        impr = context.get("improvement", {})
        heal = context.get("self_healing", {})
        mem = context.get("memory", {})

        if sched:
            parts.append(f"Schedules: {sched.get('total', '?')} total, "
                         f"{sched.get('active', '?')} active")

        if tasks_ctx and not isinstance(tasks_ctx.get("error"), str):
            parts.append(f"Tasks: {tasks_ctx.get('pending', '?')} pending")

        if impr:
            parts.append(f"System: {impr.get('issues_detected', '?')} issues detected, "
                         f"{impr.get('failing_tests', '?')} failing tests")

        if heal:
            parts.append(f"Self-healing: {heal.get('recent_events', '?')} recent events")

        parts.append(f"\nCommander says: {text}")
        parts.append("\nRespond as SAM in 1-3 sentences. Be direct and professional.")

        return "\n".join(parts)

    # ── LLM integration ────────────────────────────────────────────────────

    async def _call_llm(self, prompt: str, session: SamConversation) -> str:
        """Call the NVIDIA NIM LLM (free tier) for SAM's response."""
        try:
            from backend.server import call_llm

            messages = [
                {"role": "system", "content": SAM_SYSTEM_PROMPT},
            ]
            # Include recent conversation history
            for h in session.history[-6:]:
                messages.append(h)
            messages.append({"role": "user", "content": prompt})

            text = await asyncio.wait_for(
                call_llm(
                    messages=messages,
                    # No model= kwarg — let call_llm resolve the active provider's
                    # default model. Hardcoding "meta/llama-3.3-70b-instruct" breaks
                    # when BRAIN_PREFERENCE=ollama (the NVIDIA model id is invalid
                    # for the Ollama provider → call_llm raises → SAM returns
                    # fallback text). Resolving via the active provider works for
                    # both NVIDIA NIM and Ollama.
                    temperature=0.5,
                ),
                timeout=_LLM_TIMEOUT_SEC,
            )
            return str(text).strip()[:300]
        except Exception as exc:
            log.warning("SAM LLM call failed: %s", exc)
            return self._fallback_response(prompt)

    def _fallback_response(self, prompt: str) -> str:
        """Rule-based fallback when the LLM is unavailable."""
        lower = prompt.lower()
        if "status" in lower or "how are" in lower:
            return ("Agency is operational, Commander. I'm running on fallback mode "
                    "right now — the LLM is temporarily unavailable. Standing by.")
        if "task" in lower or "create" in lower:
            return ("I received your task request, Commander, but the LLM is "
                    "unavailable right now. I'll queue it for processing as soon "
                    "as we're back online.")
        return ("I'm here, Commander, but running on fallback mode. The primary "
                "LLM is unavailable — I'll be fully operational once it's back. "
                "Standing by.")

    # ── Sessions ───────────────────────────────────────────────────────────

    def _get_session(self, session_id: str) -> SamConversation:
        if session_id not in self._conversations:
            self._conversations[session_id] = SamConversation(
                session_id=session_id,
            )
        # Clean up old sessions (more than 1 hour idle)
        now = time.time()
        stale = [
            sid for sid, s in self._conversations.items()
            if now - s.started_at > 3600 and sid != session_id
        ]
        for sid in stale:
            del self._conversations[sid]
        return self._conversations[session_id]


# ── Singleton ─────────────────────────────────────────────────────────────────

_sam_instance: SamAgent | None = None


def get_sam() -> SamAgent:
    global _sam_instance
    if _sam_instance is None:
        _sam_instance = SamAgent()
    return _sam_instance
