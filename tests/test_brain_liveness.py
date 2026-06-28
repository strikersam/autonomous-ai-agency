"""Regression tests for services/brain_liveness.py.

The bug these guard against: ``_probe_openai_compat`` referenced
``time.monotonic()`` but ``time`` was only imported *inside*
``probe_model_liveness`` and ``_probe_ollama`` — never at module scope and not
in ``_probe_openai_compat``. So every Cerebras/Groq/NVIDIA probe raised
``NameError: name 'time' is not defined``, which the outer handler reported as
``Probe error: name 'time' is...`` and the PATCH endpoint then refused with
"Refusing to persist a dead model (liveness probe failed)" — blocking ALL
non-Ollama brain saves from the UI.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

import services.brain_liveness as bl
from services.brain_liveness import ProbeResult, probe_model_liveness


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "ok") -> None:
        self.status_code = status_code
        self.text = text


class _FakeAsyncClient:
    """Minimal httpx.AsyncClient stand-in that returns a canned response."""

    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        return self._response

    async def get(self, url):
        return self._response


def _patch_client(monkeypatch, response: _FakeResponse) -> None:
    monkeypatch.setattr(
        bl.httpx, "AsyncClient", lambda *a, **k: _FakeAsyncClient(response)
    )


def test_openai_compat_probe_does_not_raise_nameerror(monkeypatch):
    """A live Cerebras probe must return live=True with a timing — not a NameError.

    Before the fix this returned ``Probe error: name 'time' is not defined``.
    """
    monkeypatch.setenv("CEREBRAS_API_KEY", "csk-test")
    _patch_client(monkeypatch, _FakeResponse(200, "ok"))

    result = asyncio.run(probe_model_liveness("cerebras", "qwen-3-coder-480b"))

    assert isinstance(result, ProbeResult)
    assert result.live is True
    assert result.status_code == 200
    assert "name 'time'" not in result.reason  # the exact symptom of the bug
    assert result.elapsed_ms is not None and result.elapsed_ms >= 0


def test_openai_compat_probe_reports_dead_model_410(monkeypatch):
    """A 410 from the provider is reported as a retired/dead model (not live)."""
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    _patch_client(monkeypatch, _FakeResponse(410, "model retired"))

    result = asyncio.run(
        probe_model_liveness("nvidia", "nvidia/llama-3.3-nemotron-super-49b-v1.5")
    )

    assert result.live is False
    assert result.status_code == 410
    assert "410" in result.reason


def test_probe_rejects_unknown_provider():
    result = asyncio.run(probe_model_liveness("cerebrass", "whatever"))
    assert result.live is False
    assert "Unknown provider" in result.reason


def test_probe_requires_key_for_cloud_provider(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    result = asyncio.run(probe_model_liveness("groq", "llama-3.3-70b-versatile"))
    assert result.live is False
    assert "API key not configured" in result.reason
