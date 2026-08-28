"""The free-brain default must be an id the endpoint actually serves.

Two regressions live here. The original one: callers hit NIM with a bare id
(no ``nvidia/`` prefix) and got 404, so the default must always be namespaced.

The second is this file's own history. It carried a ``LIVE_MODELS`` set
"live-verified 2026-06-20" naming ``z-ai/glm-5.2`` and
``meta/llama-3.3-70b-instruct``. By 2026-08-28 a live probe found **both**
answering 410 Gone — the set had become a frozen claim about the world that
nothing re-checked, which is the failure mode the whole NVIDIA series has been
unwinding. "Live" is now read from the catalogue, which
``.github/workflows/catalogue-probe.yml`` is what keeps honest.
"""
from __future__ import annotations

import json
import os
import urllib.request

import pytest

import packages.ai.brain as brain_policy
def _live_models() -> set[str]:
    """The ids the catalogue currently vouches for.

    Derived, not frozen: a hardcoded set here outlived the models twice.
    """
    from packages.ai.brain_config import PROVIDER_CANDIDATES, SAFE_DEFAULT_MODEL

    return set(PROVIDER_CANDIDATES.get("nvidia") or []) | {SAFE_DEFAULT_MODEL}

# Bare-name form that the previous-session 404 hit (NIM accepts only
# namespaced IDs). The test still rejects this so a regression to the bare
# id can't sneak back in.
DEAD_BARE_NAMES = {
    "llama-3.3-nemotron-super-49b-v1",  # no nvidia/ prefix → 404 on NIM
}


def test_default_model_is_a_live_namespaced_id():
    """Default must be one of the live NIM namespaced IDs — never the bare name."""
    live = _live_models()
    assert live, "the catalogue names no models; this guard would pass vacuously"
    assert brain_policy.DEFAULT_FREE_NVIDIA_MODEL not in DEAD_BARE_NAMES
    assert brain_policy.DEFAULT_FREE_NVIDIA_MODEL in live
    assert "/" in brain_policy.DEFAULT_FREE_NVIDIA_MODEL, "NIM ids must be namespaced"


def test_default_model_matches_the_catalogue():
    """The module-level copy must not drift from the catalogue's safe default.

    Was ``test_default_model_is_glm52``, pinning an id that later answered 410.
    """
    from packages.ai.brain_config import SAFE_DEFAULT_MODEL

    assert brain_policy.DEFAULT_FREE_NVIDIA_MODEL == SAFE_DEFAULT_MODEL


def test_resolve_uses_default_when_env_unset(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.delenv("NVIDIA_DEFAULT_MODEL", raising=False)
    resolved = brain_policy.resolve_free_nvidia_brain()
    assert resolved is not None, "a key is set, so a brain must resolve"
    _base, _headers, model = resolved
    assert model == brain_policy.DEFAULT_FREE_NVIDIA_MODEL


def test_resolve_respects_env_override(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.setenv("NVIDIA_DEFAULT_MODEL", "nvidia/some-other-model")
    resolved = brain_policy.resolve_free_nvidia_brain()
    assert resolved is not None
    assert resolved[2] == "nvidia/some-other-model"


def test_resolve_serves_49b_when_explicitly_requested(monkeypatch):
    """49B is still honored as a fallback when the operator opts in via env."""
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.setenv("NVIDIA_DEFAULT_MODEL", "meta/llama-3.3-70b-instruct")
    resolved = brain_policy.resolve_free_nvidia_brain()
    assert resolved is not None
    assert resolved[2] == "meta/llama-3.3-70b-instruct"
    monkeypatch.setenv("NVIDIA_DEFAULT_MODEL", "meta/llama-3.3-70b-instruct")
    resolved = brain_policy.resolve_free_nvidia_brain()
    assert resolved is not None
    assert resolved[2] == "meta/llama-3.3-70b-instruct"


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
