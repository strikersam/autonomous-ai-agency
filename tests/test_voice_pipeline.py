"""Tests: Voice pipeline — STT backend selection, TTS backend selection, memory kernel."""
from __future__ import annotations

import asyncio
import pytest


# ── STT backend selection ─────────────────────────────────────────────────────

def test_stt_selects_openai_when_key_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("WHISPER_BACKEND", "auto")
    import importlib, voice.stt as stt
    importlib.reload(stt)
    assert stt._select_backend() == "openai"


def test_stt_selects_google_fallback_no_deps(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("WHISPER_BACKEND", "auto")
    import importlib, voice.stt as stt
    importlib.reload(stt)
    # faster-whisper not installed in CI → falls through to google
    backend = stt._select_backend()
    assert backend in ("local", "google")


def test_stt_explicit_backend(monkeypatch):
    monkeypatch.setenv("WHISPER_BACKEND", "google")
    import importlib, voice.stt as stt
    importlib.reload(stt)
    assert stt._select_backend() == "google"


# ── TTS backend selection ─────────────────────────────────────────────────────

def test_tts_selects_elevenlabs_when_key_set(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
    monkeypatch.setenv("TTS_BACKEND", "auto")
    import importlib, voice.tts as tts
    importlib.reload(tts)
    assert tts._select_backend() == "elevenlabs"


def test_tts_explicit_backend(monkeypatch):
    monkeypatch.setenv("TTS_BACKEND", "gtts")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    import importlib, voice.tts as tts
    importlib.reload(tts)
    assert tts._select_backend() == "gtts"


@pytest.mark.asyncio
async def test_synthesize_times_out_on_stalled_backend(monkeypatch):
    """A stalled gTTS/pyttsx3 call must not hang synthesize() forever.

    gTTS/pyttsx3 run as blocking calls with no bound of their own — a
    stalled synth (e.g. gTTS's network call hanging) must not keep the
    caller (POST /agent/sam/speak) awaiting indefinitely.

    Uses the shared event loop (not asyncio.run) — asyncio.run() waits for
    the default executor to fully drain on teardown, which would make this
    test's wall-clock time include the stalled thread's full duration and
    mask the fact that synthesize() itself already returned on time.
    """
    import time
    monkeypatch.setenv("TTS_BACKEND", "gtts")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    import importlib, voice.tts as tts
    importlib.reload(tts)
    monkeypatch.setattr(tts, "_SYNTHESIZE_TIMEOUT_SEC", 0.05)
    monkeypatch.setattr(tts, "_synthesize_gtts", lambda text: time.sleep(0.3))

    start = time.monotonic()
    result = await tts.synthesize("hello there")
    elapsed = time.monotonic() - start

    assert result is None
    assert elapsed < 0.2, f"synthesize() must respect _SYNTHESIZE_TIMEOUT_SEC, took {elapsed}s"


def test_synthesize_timeout_is_configurable_via_env(monkeypatch):
    """TTS_SYNTHESIZE_TIMEOUT_SEC must override the default ceiling."""
    monkeypatch.setenv("TTS_SYNTHESIZE_TIMEOUT_SEC", "5")
    import importlib, voice.tts as tts
    importlib.reload(tts)
    assert tts._SYNTHESIZE_TIMEOUT_SEC == 5.0


@pytest.mark.asyncio
async def test_synthesize_uses_dedicated_executor_not_default(monkeypatch):
    """gTTS/pyttsx3 must run on a dedicated executor, not the shared default.

    asyncio.wait_for() can't interrupt a blocking call already running in a
    thread — a timed-out synth keeps occupying a worker. Using the
    process-wide default executor for that would let repeated TTS stalls
    exhaust the pool every other run_in_executor(None, ...) call shares.
    """
    monkeypatch.setenv("TTS_BACKEND", "gtts")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    import importlib, voice.tts as tts
    importlib.reload(tts)
    monkeypatch.setattr(tts, "_synthesize_gtts", lambda text: b"fake-audio")

    seen_executors = []
    loop = asyncio.get_event_loop()
    original_run_in_executor = loop.run_in_executor

    def _spy_run_in_executor(executor, func, *args):
        seen_executors.append(executor)
        return original_run_in_executor(executor, func, *args)

    monkeypatch.setattr(loop, "run_in_executor", _spy_run_in_executor)

    result = await tts.synthesize("hello there")

    assert result == b"fake-audio"
    assert len(seen_executors) == 1
    assert seen_executors[0] is tts._TTS_EXECUTOR
    assert seen_executors[0] is not None


# ── Memory kernel ─────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_kernel(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_KERNEL_DIR", str(tmp_path))
    # Reset singleton
    import voice.memory_kernel as mk
    mk._kernel = None
    yield mk.get_memory_kernel()
    mk._kernel = None


@pytest.mark.asyncio
async def test_memory_store_and_recall(tmp_kernel):
    fact = await tmp_kernel.store("CEO prefers Qwen3-Coder", source="telegram_voice")
    assert fact.fact_id
    assert fact.content == "CEO prefers Qwen3-Coder"
    assert fact.source == "telegram_voice"
    assert fact.confidence == 1.0

    results = await tmp_kernel.recall("Qwen3")
    assert len(results) == 1
    assert results[0].content == "CEO prefers Qwen3-Coder"


@pytest.mark.asyncio
async def test_memory_reinforcement(tmp_kernel):
    f1 = await tmp_kernel.store("CEO loves Telegram", source="telegram_text")
    f2 = await tmp_kernel.store("CEO loves Telegram", source="telegram_text")
    assert f2.reinforcement_count == 2
    assert f2.confidence > f1.confidence


@pytest.mark.asyncio
async def test_memory_forget(tmp_kernel):
    fact = await tmp_kernel.store("temporary thought", source="api")
    removed = await tmp_kernel.forget(fact.fact_id)
    assert removed is True
    results = await tmp_kernel.recall("temporary thought")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_memory_recall_empty(tmp_kernel):
    results = await tmp_kernel.recall("nonexistent topic")
    assert results == []


@pytest.mark.asyncio
async def test_memory_export_markdown(tmp_kernel):
    await tmp_kernel.store("fact one", source="api")
    await tmp_kernel.store("fact two", source="telegram_voice")
    md = await tmp_kernel.export_markdown()
    assert "# CEO Memory Kernel" in md
    assert "fact one" in md
    assert "fact two" in md
