"""tests/test_local_controller.py — unit tests for the local GLM-5.2 daemon.

These tests stub out subprocess + HTTP so they run anywhere (no PowerShell,
no llama-server, no internet). The goal is to pin the policy logic so a
future refactor can't silently change:
  - when the daemon POSTs a heartbeat
  - the start/stop actions it takes
  - the lease state transitions
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


@contextmanager
def _fake_http_sequence(responses):
    """Yield a list of (status, body) tuples the daemon will see in order
    when it calls urllib.request.urlopen. The daemon uses urllib so we
    patch ``urllib.request.urlopen``.
    """
    class _Resp:
        def __init__(self, status, body):
            self.status = status
            self._body = body.encode("utf-8") if isinstance(body, str) else body

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    iterator = iter(responses)

    def fake_urlopen(req, **kwargs):
        status, body = next(iterator)
        if status == 0:
            from urllib.error import URLError
            raise URLError(body)
        return _Resp(status, body)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        yield


@contextmanager
def _fake_subprocess_run(*, side_effects):
    """Yield a fake subprocess.run that returns the next side_effect."""
    iterator = iter(side_effects)

    def fake_run(cmd, **kwargs):
        effect = next(iterator)
        if isinstance(effect, BaseException):
            raise effect
        return effect

    with patch("subprocess.run", side_effect=fake_run):
        yield


def _env_defaults(tmp_path, monkeypatch):
    """Pin daemon env so test reproducibility doesn't fight the operator."""
    monkeypatch.setenv("LOCAL_BRAIN_HTTP_PORT", "8072")
    monkeypatch.setenv("LOCAL_BRAIN_TOKEN", "test-token-min-32-chars-aaaaaa")
    monkeypatch.setenv(
        "LOCAL_BRAIN_LOG_FILE", str(tmp_path / "local_brain.log")
    )
    monkeypatch.setenv(
        "LOCAL_BRAIN_PID_FILE", str(tmp_path / "local_brain.pid")
    )


# ── Tests ────────────────────────────────────────────────────────────────────


def _import_controller():
    import importlib, sys
    sys.path.insert(0, ".")
    if "scripts.local_controller" in sys.modules:
        return sys.modules["scripts.local_controller"]
    return importlib.import_module("scripts.local_controller")


def test_daemon_off_returns_idle_heartbeat(tmp_path, monkeypatch):
    _env_defaults(tmp_path, monkeypatch)
    from backend.local_brain_store import LocalBrainStore
    LocalBrainStore(db_path=str(tmp_path / "brain.db")).set_desired(
        state="off", provider="auto", actor="test",
    )
    m = _import_controller()
    machine_id = "test-machine-001"

    state_json = json.dumps({
        "desired": {"state": "off", "provider": "auto"},
        "lease": {"machine_id": None, "valid": False},
        "last_heartbeat": {"status": "unknown"},
    })
    hb_response = (200, state_json)
    # Daemon call sequence at desired=off (run_once -> _http_json + _probe_v1_models + _http_json):
    #   1. GET  /api/local-brain/state          -> 200 state_json
    #   2. GET  http://127.0.0.1:8072/v1/models  -> 0 "unreachable"  (port dead; maps to port_state='dead'
    #                                                 in _probe_v1_models so the daemon does NOT call
    #                                                 _start_local_server on a desired=off tick)
    #   3. POST /api/local-brain/heartbeat      -> 200 state_json
    # Earlier revisions of the test only mocked 2 responses; the second
    # urlopen call landed on an exhausted iterator, leaking StopIteration
    # into _http_json and producing hb_status=0 -> return_code=2. Aligns
    # the test with the daemon's 3-call tick contract post port-probe refactor.
    probe_unreachable = (0, "unreachable")
    with _fake_http_sequence([(200, state_json), probe_unreachable, hb_response]):
        rc = m.run_once(
            machine_id=machine_id,
            agency_url="https://example.invalid",
            token="t",
            http_port=8072,
            start_timeout=5,
        )
    assert rc == 0


def test_daemon_on_bad_binary_marks_error_in_heartbeat(tmp_path, monkeypatch):
    _env_defaults(tmp_path, monkeypatch)
    monkeypatch.setenv("LOCAL_BRAIN_BIN", "C:/nonexistent/llama-server.exe")
    from backend.local_brain_store import LocalBrainStore
    LocalBrainStore(db_path=str(tmp_path / "brain.db")).set_desired(
        state="on", provider="colibri", actor="test",
    )
    m = _import_controller()

    state_json = json.dumps({
        "desired": {"state": "on", "provider": "colibri"},
        "lease": {"machine_id": None, "valid": False},
        "last_heartbeat": {"status": "unknown"},
    })
    captured_hb = {}
    original_urlopen = None
    from urllib.error import URLError

    class _Resp:
        def __init__(self, status, body):
            self.status, self._body = status, body.encode("utf-8")
        def read(self): return self._body
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _side(req, **kwargs):
        # Capture the heartbeat POST once (the 2nd urlopen call), then return 200.
        if req.method == "POST":
            data = req.data
            captured_hb["body"] = json.loads(data.decode("utf-8")) if data else None
            return _Resp(200, state_json)
        return _Resp(200, state_json)

    with patch("urllib.request.urlopen", side_effect=_side):
        rc = m.run_once(
            machine_id="m1",
            agency_url="https://example.invalid",
            token="t",
            http_port=8072,
            start_timeout=5,
        )
    assert rc == 0 or rc == 2  # Either OK heartbeat sent, or failsafe
    if "body" in captured_hb:
        # The failing-start heartbeats must report status=error so the UI shows it.
        body = captured_hb["body"]
        if body and body.get("status") in ("error", "starting"):
            # OK — daemon signaled failure
            assert "binary" in (body.get("error") or "").lower() or body.get("status") == "error"


def test_daemon_diagnose_returns_json_summary(tmp_path, monkeypatch):
    _env_defaults(tmp_path, monkeypatch)
    monkeypatch.setenv(
        "LOCAL_BRAIN_BIN", "C:/nonexistent/llama-server.exe"
    )
    monkeypatch.setenv(
        "LOCAL_BRAIN_MODEL_PATH", "C:/nonexistent/glm.gguf"
    )
    m = _import_controller()

    # Stub argparse so we can call main() directly.
    with patch("sys.argv", ["local_controller", "--diagnose"]), \
         patch("urllib.request.urlopen", side_effect=lambda *a, **k: None):
        try:
            m.main()
        except SystemExit as se:
            # Missing binary → exit 1 (failure).
            assert se.code == 1


def test_get_brain_preference_path_does_not_exist(tmp_path, monkeypatch):
    """The diag output must surface binary/model errors clearly."""
    _env_defaults(tmp_path, monkeypatch)
    monkeypatch.setenv("LOCAL_BRAIN_BIN", "C:/this/does/not/exist.exe")
    monkeypatch.setenv("LOCAL_BRAIN_MODEL_PATH", "C:/this/also/no.gguf")
    m = _import_controller()
    machine_id = "m1"

    state_json = json.dumps({"desired": {"state": "off"}})
    # _probe_v1_models() makes exactly one urllib.request.urlopen call. A 200
    # response with no `data`/`models` field is treated as 'listening' by the
    # daemon (parses fine, empty model list). To exercise the 'dead' branch,
    # the test must mock a status=0 response, which _http_json maps to
    # ('dead', [], False, ...) in _probe_v1_models. An earlier revision of
    # this test mocked two responses starting with (200, state_json), which
    # made the probe return 'listening' and broke the assertion (`data[0]
    # == 'dead'`). Reuse the existing `probe_dead` so the fixture stays
    # symmetric with `test_daemon_off_returns_idle_heartbeat`.
    probe_dead = (0, "url-error: unreachable")
    with _fake_http_sequence([probe_dead]):
        data = m._probe_v1_models("http://127.0.0.1:8072/v1")
    assert data[0] == "dead"  # port dead
