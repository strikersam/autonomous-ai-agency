"""voice/stt.py — Speech-to-Text for the CEO voice pipeline.

Transcribes audio (OGG/MP3/WAV) to text using:
  1. OpenAI Whisper API (if OPENAI_API_KEY set) — cloud, accurate
  2. faster-whisper (if installed) — local GPU/CPU, free
  3. SpeechRecognition + Google (fallback) — no extra deps

Config env vars:
  WHISPER_BACKEND      — "openai" | "local" | "google" (default: auto-detect)
  OPENAI_API_KEY       — for OpenAI Whisper API backend
  WHISPER_MODEL        — model size for local backend (default: "base")
  WHISPER_LANGUAGE     — language hint (default: None = auto-detect)
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger("qwen-proxy")

WHISPER_BACKEND = os.environ.get("WHISPER_BACKEND", "auto").lower()
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")
WHISPER_LANGUAGE: Optional[str] = os.environ.get("WHISPER_LANGUAGE") or None
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


async def transcribe(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    """Transcribe audio bytes to text. Returns empty string on failure."""
    backend = _select_backend()
    log.info("STT: using backend=%s file=%s size=%d", backend, filename, len(audio_bytes))

    if backend == "openai":
        return await _transcribe_openai(audio_bytes, filename)
    if backend == "local":
        return _transcribe_local(audio_bytes, filename)
    return _transcribe_google(audio_bytes, filename)


def _select_backend() -> str:
    if WHISPER_BACKEND != "auto":
        return WHISPER_BACKEND
    if OPENAI_API_KEY:
        return "openai"
    try:
        import faster_whisper  # noqa: F401
        return "local"
    except ImportError:
        pass
    return "google"


async def _transcribe_openai(audio_bytes: bytes, filename: str) -> str:
    import httpx
    with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as f:
        f.write(audio_bytes)
        tmp = f.name
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": (filename, open(tmp, "rb"), "audio/ogg")},
                data={"model": "whisper-1", **({"language": WHISPER_LANGUAGE} if WHISPER_LANGUAGE else {})},
            )
            resp.raise_for_status()
            return resp.json().get("text", "").strip()
    except Exception as exc:
        log.warning("STT openai failed: %s", exc)
        return ""
    finally:
        Path(tmp).unlink(missing_ok=True)


def _transcribe_local(audio_bytes: bytes, filename: str) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        log.warning("faster-whisper not installed; falling back to google STT")
        return _transcribe_google(audio_bytes, filename)

    with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as f:
        f.write(audio_bytes)
        tmp = f.name
    try:
        model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(tmp, language=WHISPER_LANGUAGE, beam_size=5)
        return " ".join(s.text for s in segments).strip()
    except Exception as exc:
        log.warning("STT local whisper failed: %s", exc)
        return ""
    finally:
        Path(tmp).unlink(missing_ok=True)


def _transcribe_google(audio_bytes: bytes, filename: str) -> str:
    """Fallback: Google Web Speech API via SpeechRecognition library."""
    try:
        import speech_recognition as sr
    except ImportError:
        log.warning("SpeechRecognition not installed; STT unavailable")
        return ""

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    try:
        # Convert ogg → wav via pydub if available
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(
                tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False,
                                           mode="wb", buffering=0).__enter__().write(audio_bytes) or "",
            )
        except Exception:
            pass

        r = sr.Recognizer()
        with sr.AudioFile(wav_path) as src:
            audio_data = r.record(src)
        return r.recognize_google(audio_data, language=WHISPER_LANGUAGE or "en-US")
    except Exception as exc:
        log.warning("STT google failed: %s", exc)
        return ""
    finally:
        Path(wav_path).unlink(missing_ok=True)
