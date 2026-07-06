"""voice/livekit_config.py — LiveKit configuration (config module).

Centralizes every environment variable the SAM ↔ LiveKit realtime voice
pipeline needs. This is a **config module** (like ``brain_policy.py`` /
``voice/tts.py``) — the only place in the voice pipeline allowed to read
``os.environ`` per the repository constitution.

Required for realtime voice:
  LIVEKIT_URL          — wss://<project>.livekit.cloud (or self-hosted URL)
  LIVEKIT_API_KEY      — LiveKit API key
  LIVEKIT_API_SECRET   — LiveKit API secret (signs access tokens)

Optional (worker brain / speech providers — sensible free-tier defaults):
  SAM_VOICE_IN_PROCESS — run the voice worker inside the web process (default
                         "false"; forced off under TESTING). Opt-in only: the
                         worker's plugin stack (numpy/onnxruntime/av) needs
                         roughly 300MB+ of headroom, which OOM-kills a 512MB
                         Render instance at boot. Set "true" only on >=2GB
                         instances; otherwise run the worker as a dedicated
                         process (see voice/sam_livekit_worker.py docstring).
  SAM_LIVEKIT_ROOM     — room name prefix (default: "sam-voice")
  SAM_LLM_BASE_URL     — OpenAI-compatible base URL for SAM's brain.
                         Point at Hermes (http://localhost:8100/v1), the
                         proxy (http://localhost:8000/v1), or leave the
                         default NVIDIA NIM endpoint.
  SAM_LLM_MODEL        — model id (default: NVIDIA_DEFAULT_MODEL)
  SAM_LLM_API_KEY      — API key for SAM_LLM_BASE_URL (default: NVIDIA_API_KEY)
  DEEPGRAM_API_KEY     — preferred STT (falls back to Groq Whisper)
  GROQ_API_KEY         — free Whisper STT + PlayAI TTS fallback
  ELEVENLABS_API_KEY   — preferred TTS voice
  ELEVENLABS_VOICE_ID  — ElevenLabs voice (default: Rachel)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

_NVIDIA_OPENAI_BASE = "https://integrate.api.nvidia.com/v1"
_DEFAULT_NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"


@dataclass(frozen=True)
class LiveKitConfig:
    """Resolved LiveKit + speech-provider configuration."""

    url: str
    api_key: str
    api_secret: str
    room_prefix: str = "sam-voice"

    # SAM's brain (OpenAI-compatible endpoint)
    llm_base_url: str = _NVIDIA_OPENAI_BASE
    llm_model: str = _DEFAULT_NVIDIA_MODEL
    llm_api_key: str = ""

    # Speech providers
    deepgram_api_key: str = ""
    groq_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    in_process: bool = False

    missing: tuple[str, ...] = field(default_factory=tuple)

    @property
    def configured(self) -> bool:
        """True when the LiveKit room transport itself is usable."""
        return bool(self.url and self.api_key and self.api_secret)


def get_livekit_config() -> LiveKitConfig:
    """Resolve LiveKit configuration from the environment (read fresh each call)."""
    url = os.environ.get("LIVEKIT_URL", "").strip()
    api_key = os.environ.get("LIVEKIT_API_KEY", "").strip()
    api_secret = os.environ.get("LIVEKIT_API_SECRET", "").strip()

    missing = tuple(
        name
        for name, value in (
            ("LIVEKIT_URL", url),
            ("LIVEKIT_API_KEY", api_key),
            ("LIVEKIT_API_SECRET", api_secret),
        )
        if not value
    )

    return LiveKitConfig(
        url=url,
        api_key=api_key,
        api_secret=api_secret,
        room_prefix=os.environ.get("SAM_LIVEKIT_ROOM", "sam-voice").strip() or "sam-voice",
        llm_base_url=os.environ.get("SAM_LLM_BASE_URL", "").strip() or _NVIDIA_OPENAI_BASE,
        llm_model=(
            os.environ.get("SAM_LLM_MODEL", "").strip()
            or os.environ.get("NVIDIA_DEFAULT_MODEL", "").strip()
            or _DEFAULT_NVIDIA_MODEL
        ),
        llm_api_key=(
            os.environ.get("SAM_LLM_API_KEY", "").strip()
            or os.environ.get("NVIDIA_API_KEY", "").strip()
        ),
        deepgram_api_key=os.environ.get("DEEPGRAM_API_KEY", "").strip(),
        groq_api_key=os.environ.get("GROQ_API_KEY", "").strip(),
        elevenlabs_api_key=os.environ.get("ELEVENLABS_API_KEY", "").strip(),
        elevenlabs_voice_id=(
            os.environ.get("ELEVENLABS_VOICE_ID", "").strip() or "21m00Tcm4TlvDq8ikWAM"
        ),
        # In-process worker: OPT-IN. Defaulting to "true" OOM-killed the
        # 512MB Render web instance at boot (worker plugin preload loads
        # numpy/onnxruntime/av on top of the backend) — every deploy after
        # PR #931 crash-looped until this became opt-in. Never under TESTING.
        in_process=(
            os.environ.get("SAM_VOICE_IN_PROCESS", "false").strip().lower()
            in {"1", "true", "yes"}
            and os.environ.get("TESTING", "").strip().lower() != "true"
        ),
        missing=missing,
    )
