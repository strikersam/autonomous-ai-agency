"""voice/sam_livekit_worker.py — SAM realtime voice worker (LiveKit Agents).

Taskmaster-style realtime voice pipeline (github.com/keithschacht/taskmaster):
the dashboard joins a LiveKit room over WebRTC, this worker is dispatched to
the same room, and SAM converses hands-free:

    Commander's mic ─► LiveKit room ─► VAD (Silero) ─► STT ─► SAM LLM (+tools)
                                                                    │
    Commander's speakers ◄─ LiveKit room ◄─ TTS ◄──────────────────┘

Providers (resolved by voice/livekit_config.py, free-tier first):
  STT: Deepgram → Groq Whisper (free)
  LLM: any OpenAI-compatible endpoint — NVIDIA NIM (default), Hermes
       (http://localhost:8100/v1), or the proxy (http://localhost:8000/v1)
  TTS: ElevenLabs → Groq PlayAI (free)

Tools call the agency **in-process** (agent.sam context + tasks.store).

Two ways to run the worker:

1. **In-process (default, fully hands-off)** — the backend lifespan calls
   ``start_in_process()`` on startup, which runs the worker in a daemon
   thread inside the web process (same pattern as the in-web Telegram bot).
   Requires livekit-agents installed (Dockerfile.backend installs
   voice/requirements-livekit.txt) + the LIVEKIT_* env vars. Set
   ``SAM_VOICE_IN_PROCESS=false`` to opt out.

2. **Dedicated process** — from the repo root with the same env:

    pip install -r voice/requirements-livekit.txt
    python -m voice.sam_livekit_worker dev      # local dev (hot reload)
    python -m voice.sam_livekit_worker start    # production

Requires: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET (+ one STT and one
TTS provider key). The dashboard fetches its room token from
``POST /agent/sam/livekit/token`` and connects; LiveKit dispatches this worker
into the room automatically.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import TYPE_CHECKING, Any

from voice.livekit_config import LiveKitConfig, get_livekit_config

if TYPE_CHECKING:  # pragma: no cover — typing only
    from livekit.agents import JobContext

log = logging.getLogger("sam-livekit")

_INSTALL_HINT = "pip install -r voice/requirements-livekit.txt"

GREETING_INSTRUCTIONS = (
    "Greet the Commander in one short sentence: confirm SAM is online with "
    "realtime voice and standing by."
)

VOICE_EXTRA_INSTRUCTIONS = """

## Realtime voice session
You are in a live voice conversation over LiveKit. Replies are spoken aloud:
keep them to 1-3 short sentences, plain English, no markdown, no lists.
Use your tools for live agency state — never guess numbers. Confirm every
task you create by repeating its title back to the Commander.
"""


def _require_livekit_agents() -> None:
    """Fail fast with an actionable hint when optional deps are missing."""
    try:
        import livekit.agents  # noqa: F401
    except ImportError as exc:  # pragma: no cover — env-dependent
        raise SystemExit(
            f"livekit-agents is not installed. Run: {_INSTALL_HINT}"
        ) from exc


def _build_stt(cfg: LiveKitConfig) -> Any:
    """Pick an STT provider: Deepgram → Groq Whisper (free)."""
    if cfg.deepgram_api_key:
        from livekit.plugins import deepgram

        return deepgram.STT(model="nova-3", api_key=cfg.deepgram_api_key)
    if cfg.groq_api_key:
        from livekit.plugins import groq

        return groq.STT(model="whisper-large-v3-turbo", api_key=cfg.groq_api_key)
    raise SystemExit(
        "No STT provider configured — set DEEPGRAM_API_KEY or GROQ_API_KEY"
    )


def _build_llm(cfg: LiveKitConfig) -> Any:
    """SAM's brain: any OpenAI-compatible endpoint (NVIDIA NIM / Hermes / proxy)."""
    from livekit.plugins import openai

    if not cfg.llm_api_key:
        log.warning(
            "SAM_LLM_API_KEY/NVIDIA_API_KEY not set — LLM calls to %s may fail",
            cfg.llm_base_url,
        )
    return openai.LLM(
        model=cfg.llm_model,
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key or "not-set",
        temperature=0.5,
    )


def _build_tts(cfg: LiveKitConfig) -> Any:
    """Pick a TTS provider: ElevenLabs → Groq PlayAI (free)."""
    if cfg.elevenlabs_api_key:
        from livekit.plugins import elevenlabs

        return elevenlabs.TTS(
            voice_id=cfg.elevenlabs_voice_id, api_key=cfg.elevenlabs_api_key
        )
    if cfg.groq_api_key:
        from livekit.plugins import groq

        return groq.TTS(
            model="playai-tts", voice="Fritz-PlayAI", api_key=cfg.groq_api_key
        )
    raise SystemExit(
        "No TTS provider configured — set ELEVENLABS_API_KEY or GROQ_API_KEY"
    )


def _make_sam_assistant(owner_id: str) -> Any:
    """Build the SAM voice Agent with in-process agency tools.

    Defined inside a factory (not at module level) so importing this module
    never requires livekit-agents — only running the worker does.
    """
    from livekit.agents import Agent, function_tool

    from agent.sam import SAM_SYSTEM_PROMPT, get_sam

    class SamAssistant(Agent):
        """SAM persona + function tools against the live agency."""

        def __init__(self) -> None:
            super().__init__(instructions=SAM_SYSTEM_PROMPT + VOICE_EXTRA_INSTRUCTIONS)

        @function_tool
        async def get_agency_status(self) -> str:
            """Get the live agency status: schedules, pending tasks, detected
            issues, failing tests, and self-healing events. Call this whenever
            the Commander asks how the agency, system, or platform is doing."""
            try:
                snapshot = await get_sam().build_context()
                return json.dumps(snapshot, default=str)
            except Exception as exc:
                log.warning("get_agency_status failed: %s", exc)
                return f"Status unavailable right now: {exc}"

        @function_tool
        async def list_pending_tasks(self, limit: int = 10) -> str:
            """List the agency's pending tasks (title, status, priority).
            Call this when the Commander asks what's pending, queued, or on
            the task list."""
            try:
                from tasks.store import get_task_store

                pending = await get_task_store().list_pending(limit=max(1, min(limit, 25)))
                if not pending:
                    return "No pending tasks."
                lines = [
                    f"- {t.title} (status={t.status}, priority={t.priority})"
                    for t in pending
                ]
                return "\n".join(lines)
            except Exception as exc:
                log.warning("list_pending_tasks failed: %s", exc)
                return f"Task list unavailable right now: {exc}"

        @function_tool
        async def create_task(self, title: str, description: str = "") -> str:
            """Create a new task in the agency backlog. Call this when the
            Commander asks to create, add, or queue a task. Repeat the created
            task title back for confirmation."""
            try:
                from tasks.models import Task
                from tasks.store import get_task_store

                task = Task(
                    owner_id=owner_id or "sam-voice",
                    title=title[:512],
                    description=description[:4000],
                    task_type="voice",
                    tags=["sam-voice"],
                )
                created = await get_task_store().create(task)
                return f"Task created: '{created.title}' (id={created.task_id})"
            except Exception as exc:
                log.warning("create_task failed: %s", exc)
                return f"Could not create the task: {exc}"

    return SamAssistant()


async def entrypoint(ctx: "JobContext") -> None:
    """Join the room, wait for the Commander, and start the voice session."""
    from livekit.agents import AgentSession
    from livekit.plugins import silero

    cfg = get_livekit_config()
    await ctx.connect()
    participant = await ctx.wait_for_participant()
    log.info(
        "SAM voice session: room=%s commander=%s", ctx.room.name, participant.identity
    )

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=_build_stt(cfg),
        llm=_build_llm(cfg),
        tts=_build_tts(cfg),
    )
    await session.start(room=ctx.room, agent=_make_sam_assistant(participant.identity))
    await session.generate_reply(instructions=GREETING_INSTRUCTIONS)


# ── In-process mode (fully hands-off) ─────────────────────────────────────────

_inproc_thread: threading.Thread | None = None
_inproc_lock = threading.Lock()


def start_in_process() -> bool:
    """Start the voice worker in a daemon thread inside this process.

    Called by the backend lifespan on startup so a single web service carries
    SAM's realtime voice. Never raises — returns True only when a worker
    thread was actually started; every disqualifier is a logged no-op:
    flag off / TESTING, LiveKit env unset, livekit-agents not installed,
    or a worker thread already running.
    """
    global _inproc_thread
    cfg = get_livekit_config()
    if not cfg.in_process:
        log.info("SAM voice in-process worker disabled (SAM_VOICE_IN_PROCESS/TESTING)")
        return False
    if not cfg.configured:
        log.info("SAM voice in-process worker skipped — missing: %s", ", ".join(cfg.missing))
        return False
    try:
        import livekit.agents  # noqa: F401
    except ImportError:
        log.info("SAM voice in-process worker skipped — livekit-agents not installed (%s)",
                 _INSTALL_HINT)
        return False

    with _inproc_lock:
        if _inproc_thread is not None and _inproc_thread.is_alive():
            return False
        _inproc_thread = threading.Thread(
            target=_run_worker_thread, name="sam-livekit-worker", daemon=True
        )
        _inproc_thread.start()
    log.info("SAM voice worker started in-process (room prefix=%s)", cfg.room_prefix)
    return True


def _run_worker_thread() -> None:
    """Thread body: run the LiveKit agents server on a dedicated event loop."""
    import asyncio
    import math

    from livekit.agents import WorkerOptions

    cfg = get_livekit_config()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        opts = WorkerOptions(
            entrypoint_fnc=entrypoint,
            ws_url=cfg.url,
            api_key=cfg.api_key,
            api_secret=cfg.api_secret,
            # Free-tier web dyno: no prewarmed job subprocesses idling in RAM,
            # and never reject a job on CPU load (single-operator platform).
            num_idle_processes=0,
            load_threshold=math.inf,
            # The agents worker runs a small health HTTP server; bind it to an
            # ephemeral port so it can never collide with the web app (:8001)
            # or Hermes (:8100) inside the same container.
            port=0,
        )
        try:
            # livekit-agents >= 1.6: Worker was replaced by AgentServer
            from livekit.agents.worker import AgentServer

            server = AgentServer.from_server_options(opts)
            loop.run_until_complete(server.run())
        except ImportError:
            from livekit.agents import Worker  # older livekit-agents

            loop.run_until_complete(Worker(opts, loop=loop).run())
    except Exception as exc:
        # Never take the web process down with us — the dashboard keeps
        # working, only live voice is unavailable until the next restart.
        log.error("SAM voice in-process worker stopped: %s", exc)
    finally:
        loop.close()


def main() -> None:
    """CLI entrypoint: ``python -m voice.sam_livekit_worker dev|start``."""
    _require_livekit_agents()
    cfg = get_livekit_config()
    if not cfg.configured:
        raise SystemExit(
            "LiveKit is not configured — missing: " + ", ".join(cfg.missing)
        )

    from livekit.agents import WorkerOptions, cli

    logging.basicConfig(level=logging.INFO)
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
