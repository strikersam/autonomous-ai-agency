"""The free-brain default model must be an endpoint-live model.

Regression for the historical latent bug where callers hit NIM with the
bare ``llama-3.3-nemotron-super-49b-v1`` id (without the ``nvidia/`` prefix) and
got 404. As of the 2026-06-20 live-NIM probe, BOTH namespaced IDs
(``nvidia/llama-3.3-nemotron-super-49b-v1`` and
``nvidia/llama-3.3-nemotron-super-49b-v1``) return HTTP 200. The default
brain now points at the 120B-a12b model (12B active/call, reasoning-tuned
MoE — empirically faster and stronger than the dense 49B on chain-of-thought
agent tasks), with the 49B kept as a fallback that the resolver still
honours when ``NVIDIA_DEFAULT_MODEL`` is explicitly set to it.
"""
from __future__ import annotations

import json
import os
import urllib.request

import pytest

import brain_policy


# Names that resolve on NVIDIA NIM today (live-verified 2026-06-20 via curl
# against https://integrate.api.nvidia.com/v1/chat/completions — both returned
# HTTP 200 with a coherent ~600-token reply). Keeping both names in tests so a
# future flip doesn't silently regress.
LIVE_MODELS = {
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "nvidia/llama-3.3-nemotron-super-49b-v1",
}

# Bare-name form that the previous-session 404 hit (NIM accepts only
# namespaced IDs). The test still rejects this so a regression to the bare
# id can't sneak back in.
DEAD_BARE_NAMES = {
    "llama-3.3-nemotron-super-49b-v1",  # no nvidia/ prefix → 404 on NIM
}


def test_default_model_is_a_live_namespaced_id():
    """Default must be one of the live NIM namespaced IDs — never the bare name."""
    assert brain_policy.DEFAULT_FREE_NVIDIA_MODEL not in DEAD_BARE_NAMES
    assert brain_policy.DEFAULT_FREE_NVIDIA_MODEL in LIVE_MODELS


def test_default_model_is_the_120b_a12b_moe():
    """Default is the v1.5 revision (live-verified against NIM)."""
    assert brain_policy.DEFAULT_FREE_NVIDIA_MODEL == "nvidia/llama-3.3-nemotron-super-49b-v1.5"


def test_resolve_uses_default_when_env_unset(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.delenv("NVIDIA_DEFAULT_MODEL", raising=False)
    resolved = brain_policy.resolve_free_nvidia_brain()
    assert resolved is not None, "a key is set, so a brain must resolve"
    _base, _headers, model = resolved
    assert model == "nvidia/llama-3.3-nemotron-super-49b-v1.5"


def test_resolve_respects_env_override(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.setenv("NVIDIA_DEFAULT_MODEL", "nvidia/some-other-model")
    resolved = brain_policy.resolve_free_nvidia_brain()
    assert resolved is not None
    assert resolved[2] == "nvidia/some-other-model"


def test_resolve_serves_49b_when_explicitly_requested(monkeypatch):
    """49B is still honored as a fallback when the operator opts in via env."""
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.setenv("NVIDIA_DEFAULT_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1")
    resolved = brain_policy.resolve_free_nvidia_brain()
    assert resolved is not None
    assert resolved[2] == "nvidia/llama-3.3-nemotron-super-49b-v1"


@pytest.mark.livenim
def test_default_model_actually_responds_against_nim():
    """Live smoke test: the default model must be reachable on NIM today.

    Skipped unless ``NVIDIA_API_KEY`` is in the env (set in CI / local dev).
    Catches the "default points at a 404" regression the user just hit.
    """
    key = (os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey") or "").strip()
    if not key:
        pytest.skip("NVIDIA_API_KEY not set in env — live smoke test skipped")
    req = urllib.request.Request(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        data=json.dumps({
            "model": brain_policy.DEFAULT_FREE_NVIDIA_MODEL,
            "messages": [{"role": "user", "content": "Reply with the single word: ok."}],
            "max_tokens": 8,
            "temperature": 0,
        }).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    text = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
    assert text.strip(), f"empty response from {brain_policy.DEFAULT_FREE_NVIDIA_MODEL}: {body!r}"
