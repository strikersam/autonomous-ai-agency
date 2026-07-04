"""voice/tts.py — Text-to-Speech for the CEO voice pipeline.

Converts text to an OGG Opus audio file (Telegram-native voice note format).

Backends (auto-selected):
  1. ElevenLabs API (ELEVENLABS_API_KEY set) — high quality, natural
  2. gTTS (Google TTS, free) — no API key needed, good quality
  3. pyttsx3 (offline) — fully local, robotic but works without internet

Config env vars:
  TTS_BACKEND          — "elevenlabs" | "gtts" | "pyttsx3" (default: auto)
  ELEVENLABS_API_KEY   — for ElevenLabs
  ELEVENLABS_VOICE_ID  — voice ID (default: "21m00Tcm4TlvDq8ikWAM" = Rachel)
  TTS_LANGUAGE         — language for gTTS (default: "en")
  TTS_SYNTHESIZE_TIMEOUT_SEC — ceiling for a single synth call (default: 25)
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

log = logging.getLogger("qwen-proxy")

TTS_BACKEND = os.environ.get("TTS_BACKEND", "auto").lower()
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
TTS_LANGUAGE = os.environ.get("TTS_LANGUAGE", "en")

# The ElevenLabs branch already bounds itself via its own httpx timeout, but
# gTTS/pyttsx3 run as blocking calls with no bound at all — a stalled synth
# (e.g. gTTS's network call hanging) would keep the caller
# (POST /agent/sam/speak) awaiting forever. This ceiling makes synthesize()
# always resolve (None on timeout, same contract as any other failure)
# instead of hanging the request.
_SYNTHESIZE_TIMEOUT_SEC = float(os.environ.get("TTS_SYNTHESIZE_TIMEOUT_SEC", "25.0"))

# asyncio.wait_for() only stops *awaiting* a run_in_executor() future — it
# can't interrupt the blocking call already running in the thread, so a
# stalled gTTS/pyttsx3 job keeps occupying a worker after its timeout fires.
# Using the process-wide default executor for that would let repeated
# stalls exhaust the pool every other run_in_executor(None, ...) call in the
# app shares. A small dedicated pool contains that damage to TTS alone.
_TTS_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tts-synth")


async def synthesize(text: str) -> bytes | None:
    """Convert text to OGG voice note bytes. Returns None on failure."""
    if not text.strip():
        return None
    backend = _select_backend()
    log.info("TTS: backend=%s len=%d", backend, len(text))

    loop = asyncio.get_event_loop()
    try:
        if backend == "elevenlabs":
            coro = _synthesize_elevenlabs(text)
        elif backend == "gtts":
            coro = loop.run_in_executor(_TTS_EXECUTOR, _synthesize_gtts, text)
        else:
            coro = loop.run_in_executor(_TTS_EXECUTOR, _synthesize_pyttsx3, text)
        return await asyncio.wait_for(coro, timeout=_SYNTHESIZE_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        log.warning("TTS synthesize timed out (backend=%s, timeout=%ss)", backend, _SYNTHESIZE_TIMEOUT_SEC)
        return None


def _select_backend() -> str:
    if TTS_BACKEND != "auto":
        return TTS_BACKEND
    if ELEVENLABS_API_KEY:
        return "elevenlabs"
    try:
        import gtts  # noqa: F401
        return "gtts"
    except ImportError:
        pass
    return "pyttsx3"


async def _synthesize_elevenlabs(text: str) -> bytes | None:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": text[:2500],  # ElevenLabs limit
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
            )
            resp.raise_for_status()
            mp3_bytes = resp.content
            return _convert_to_ogg(mp3_bytes, ".mp3")
    except Exception as exc:
        log.warning("TTS elevenlabs failed: %s", exc)
        return None


def _synthesize_gtts(text: str) -> bytes | None:
    try:
        from gtts import gTTS
        import io
        buf = io.BytesIO()
        gTTS(text=text[:3000], lang=TTS_LANGUAGE, slow=False).write_to_fp(buf)
        mp3_bytes = buf.getvalue()
        return _convert_to_ogg(mp3_bytes, ".mp3")
    except Exception as exc:
        log.warning("TTS gtts failed: %s", exc)
        return None


def _synthesize_pyttsx3(text: str) -> bytes | None:
    try:
        import pyttsx3
        engine = pyttsx3.init()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        engine.save_to_file(text[:2000], wav_path)
        engine.runAndWait()
        wav_bytes = Path(wav_path).read_bytes()
        Path(wav_path).unlink(missing_ok=True)
        return _convert_to_ogg(wav_bytes, ".wav")
    except Exception as exc:
        log.warning("TTS pyttsx3 failed: %s", exc)
        return None


def _convert_to_ogg(audio_bytes: bytes, suffix: str) -> bytes | None:
    """Convert audio to OGG Opus (Telegram voice note format) via pydub+ffmpeg."""
    try:
        from pydub import AudioSegment
        import io
        seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format=suffix.lstrip("."))
        buf = io.BytesIO()
        seg.export(buf, format="ogg", codec="libopus", parameters=["-b:a", "32k"])
        return buf.getvalue()
    except Exception as exc:
        log.warning("TTS ogg conversion failed (%s); returning raw bytes", exc)
        return audio_bytes  # return unconverted as fallback
