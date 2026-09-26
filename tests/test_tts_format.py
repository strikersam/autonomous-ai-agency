"""tests/test_tts_format.py — SAM speech comes back as MP3 for browsers.

Regression: /agent/sam/speak only produced OGG Opus, which Safari/iOS cannot
play, so the SAM screen showed "SAM is speaking" with no sound.
"""

from __future__ import annotations

import asyncio

from voice import tts

_MP3 = b"ID3\x04fake-mp3-frames"


def test_mp3_request_passes_gtts_mp3_through(monkeypatch):
    called = {}

    def _fake_gtts(text, fmt="ogg"):
        called["fmt"] = fmt
        return tts._convert(_MP3, ".mp3", fmt)

    monkeypatch.setattr(tts, "_select_backend", lambda: "gtts")
    monkeypatch.setattr(tts, "_synthesize_gtts", _fake_gtts)

    audio = asyncio.run(tts.synthesize("Standing by, Commander.", "mp3"))

    assert called["fmt"] == "mp3"
    assert audio == _MP3  # untouched — no lossy re-encode, no ffmpeg needed


def test_default_format_is_still_ogg_for_telegram(monkeypatch):
    seen = []
    monkeypatch.setattr(tts, "_convert_to_ogg", lambda b, s: seen.append(s) or b"OggS")

    assert tts._convert(_MP3, ".mp3", "ogg") == b"OggS"
    assert seen == [".mp3"]


def test_speak_request_accepts_mp3_and_rejects_unknown():
    import pytest
    from pydantic import ValidationError

    from backend.server import SamSpeakRequest

    assert SamSpeakRequest(text="hi").format == "ogg"
    assert SamSpeakRequest(text="hi", format="mp3").format == "mp3"
    with pytest.raises(ValidationError):
        SamSpeakRequest(text="hi", format="wav")
