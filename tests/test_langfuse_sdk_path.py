"""emit_chat_observation skips the v2-only SDK path on a v3+ client.

`_emit_sdk` calls ``lf.trace()``, which the Langfuse SDK dropped in v3. With the
4.x/5.x this repo installs, every chat trace raised AttributeError, logged
"Langfuse SDK emit failed" and fell back to HTTP. The fallback is the working
path, so it is now taken directly.
"""
from __future__ import annotations

import logging

import langfuse_obs


def _call() -> None:
    langfuse_obs.emit_chat_observation(
        email="a@b.c", department="eng", key_id=None, model="m",
        messages=[{"role": "user", "content": "hi"}], output_text="ok",
        prompt_tokens=1, completion_tokens=1,
    )


def _wire(monkeypatch, client):
    calls = {"http": 0, "sdk": 0}
    monkeypatch.setattr(langfuse_obs, "_langfuse_enabled", lambda: True)
    monkeypatch.setattr(langfuse_obs, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(langfuse_obs, "_emit_langfuse_http",
                        lambda **_: calls.__setitem__("http", calls["http"] + 1))
    monkeypatch.setattr(langfuse_obs, "_emit_sdk",
                        lambda *_a, **_k: calls.__setitem__("sdk", calls["sdk"] + 1))
    monkeypatch.delenv("LANGFUSE_USE_HTTP_ONLY", raising=False)
    monkeypatch.delenv("MONGO_URL", raising=False)
    return calls


class _V3Client:
    """Stands in for the v3+ SDK client: no trace() method."""

    def flush(self) -> None:
        pass


class _V2Client(_V3Client):
    def trace(self, **_):
        raise AssertionError("not called here; _emit_sdk is stubbed")


def test_v3_client_goes_straight_to_http_without_a_failure_log(monkeypatch, caplog):
    calls = _wire(monkeypatch, _V3Client())
    with caplog.at_level(logging.INFO, logger=langfuse_obs.log.name):
        _call()
    assert calls == {"http": 1, "sdk": 0}
    assert "SDK emit failed" not in caplog.text


def test_v2_client_still_uses_the_sdk(monkeypatch):
    calls = _wire(monkeypatch, _V2Client())
    _call()
    assert calls == {"http": 0, "sdk": 1}
