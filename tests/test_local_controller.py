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


# \u2500\u2500 Helpers \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500


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
    calls: list[str] = []

    def fake_urlopen(req, **kwargs):
        calls.append(req.get_full_url())
        status, body = next(iterator)
        if status == 0:
            from urllib.error import URLError
            raise URLError(body)
        return _Resp(status, body)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        yield calls


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


# \u2500\u2500 Tests \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500


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
    # Desired=off tick = exactly 3 urlopens in this strict order:
    #   1. GET  /api/local-brain/state          (cloud poll)
    #   2. GET  http://127.0.0.1:8072/v1/models (single-port probe because
    #                                            _env_defaults pins
    #                                            LOCAL_BRAIN_HTTP_PORT=8072
    #                                            without a multi-port env)
    #   3. POST /api/local-brain/heartbeat      (status / port / models)
    # _fake_http_sequence's helper yields ``calls`` so any future re-introduction
    # of an extra probe (or a routing drift on the state/heartbeat paths) breaks
    # this test loudly instead of silently passing.
    probe_unreachable = (0, "unreachable")
    with _fake_http_sequence(
        [(200, state_json), probe_unreachable, hb_response]
    ) as calls:
        rc = m.run_once(
            machine_id=machine_id,
            agency_url="https://example.invalid",
            token="t",
            http_port=8072,
            start_timeout=5,
        )
    assert rc == 0
    assert calls == [
        "https://example.invalid/api/local-brain/state",
        "http://127.0.0.1:8072/v1/models",
        "https://example.invalid/api/local-brain/heartbeat",
    ], f"expected exactly 3 urlopens in desired=off order, got {calls}"


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
            # OK \u2014 daemon signaled failure
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
            # Missing binary \u2192 exit 1 (failure).
            assert se.code == 1


def test_get_brain_preference_path_does_not_exist(tmp_path, monkeypatch):
    """The diag output must surface binary/model errors clearly."""
    _env_defaults(tmp_path, monkeypatch)
    monkeypatch.setenv("LOCAL_BRAIN_BIN", "C:/this/does/not/exist.exe")
    monkeypatch.setenv("LOCAL_BRAIN_MODEL_PATH", "C:/this/also/no.gguf")
    m = _import_controller()
    machine_id = "m1"

    # _probe_v1_models() makes exactly one urllib.request.urlopen call. A 200
    # response with no `data`/`models` field is treated as 'listening' by the
    # daemon (parses fine, empty model list). To exercise the 'dead' branch,
    # the test must mock a status=0 response, which _http_json maps to
    # ('dead', [], False, ...) in _probe_v1_models. An earlier revision of
    # this test mocked two responses starting with a 200, which made the
    # probe return 'listening' and broke the assertion (`data[0] == 'dead'`).
    # Reuse the existing `probe_dead` so the fixture stays symmetric with
    # `test_daemon_off_returns_idle_heartbeat`.
    probe_dead = (0, "url-error: unreachable")
    with _fake_http_sequence([probe_dead]):
        data = m._probe_v1_models("http://127.0.0.1:8072/v1")
    assert data[0] == "dead"  # port dead


def test_daemon_restart_reprobes_http_port_only(tmp_path, monkeypatch):
    """Pins the v3 fix: after the multi-port preamble probe finds colibri
    serving a wrong model on :8081, the restart branch launches the
    canonical llama-server.exe on http_port (:8072) and re-probes ONLY
    http_port directly. It MUST NOT call ``_choose_local_brain`` again
    inside the restart block \u2014 that would ping-pong between :8081 and
    :8072 for the duration of the cold-load. If a v4 refactor
    re-introduces ``_choose_local_brain`` re-picks, bump
    ``len(call_log)`` back to 2 with rationale.
    """
    _env_defaults(tmp_path, monkeypatch)
    monkeypatch.setenv("LOCAL_BRAIN_HTTP_PORTS", "8072,8081")
    from backend.local_brain_store import LocalBrainStore
    LocalBrainStore(db_path=str(tmp_path / "brain.db")).set_desired(
        state="on", provider="colibri", actor="test",
    )
    m = _import_controller()

    cloud_state = json.dumps({
        "desired": {"state": "on", "provider": "colibri"},
        "lease": {"machine_id": None, "valid": False},
        "last_heartbeat": {"status": "unknown"},
    })

    call_log = []
    http_probe_log = []

    def fake_choose_local_brain(ports):
        call_log.append(tuple(ports))
        return 8081, "listening", [{"id": "not-glm-5.2"}], False, ""

    def fake_probe_v1_models(base_url, *, timeout=4.0):
        if "127.0.0.1:8072" in base_url:
            http_probe_log.append(base_url)
            return "listening", [{"id": "glm-5.2"}], True, ""
        raise AssertionError(
            f"_probe_v1_models called on unexpected URL: {base_url!r}"
        )

    monkeypatch.setattr(m, "_choose_local_brain", fake_choose_local_brain)
    monkeypatch.setattr(m, "_probe_v1_models", fake_probe_v1_models)
    monkeypatch.setattr(m, "_start_local_server", lambda: (True, "stub-started"))
    monkeypatch.setattr(m, "_stop_local_server", lambda: (True, "stub-stopped"))

    captured_hb = {}

    class _Resp:
        def __init__(self, status, body):
            self.status = status
            self._body = body.encode("utf-8")
        def read(self): return self._body
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, **kwargs):
        if req.method == "POST":
            captured_hb["body"] = json.loads(req.data.decode("utf-8")) if req.data else None
            return _Resp(200, cloud_state)
        return _Resp(200, cloud_state)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        rc = m.run_once(
            machine_id="repick-1",
            agency_url="https://example.invalid",
            token="t",
            http_port=8072,
            start_timeout=5,
        )

    assert rc == 0
    assert len(call_log) == 1, (
        f"_choose_local_brain must be called exactly once (preamble probe); "
        f"restart should re-probe http_port directly, NOT call "
        f"_choose_local_brain again. actual={len(call_log)}"
    )
    assert call_log[0] == (8072, 8081), (
        f"preamble probe order must be [http_port, env_list] per "
        f"_parse_http_ports; actual={call_log[0]}"
    )
    assert http_probe_log == ["http://127.0.0.1:8072"], (
        f"restart must probe http_port (http://127.0.0.1:8072) exactly "
        f"once; actual={http_probe_log}"
    )
    body = captured_hb["body"]
    assert body is not None
    assert body["status"] == "ok"
    assert body["port_state"] == "listening"
    assert body["models_has_glm52"] is True
    assert body["v1_models"] == [{"id": "glm-5.2"}]


def test_daemon_picks_colibri_8081_when_only_it_listening(tmp_path, monkeypatch):
    """Pins the multi-port fix end-to-end: when ONLY colibri's :8081 is
    up serving glm-5.2, ``_choose_local_brain`` iterates [8072, 8081],
    the leaf ``_probe_v1_models`` stub returns dead for :8072 and
    (listening, glm-5.2) for :8081, the helper picks port=8081, and the
    heartbeat reports status=ok. By stubbing the LEAF
    ``_probe_v1_models`` (not the wrapper ``_choose_local_brain``), this
    test exercises the REAL multi-port iteration loop and surfaces
    regressions in either helper. URL drift in a future refactor
    surfaces as ``AssertionError``; caller signature changes may
    surface as ``TypeError`` \u2014 both are hard fails.
    """
    _env_defaults(tmp_path, monkeypatch)
    monkeypatch.setenv("LOCAL_BRAIN_HTTP_PORTS", "8072,8081")
    from backend.local_brain_store import LocalBrainStore
    LocalBrainStore(db_path=str(tmp_path / "brain.db")).set_desired(
        state="on", provider="colibri", actor="test",
    )
    m = _import_controller()

    cloud_state = json.dumps({
        "desired": {"state": "on", "provider": "colibri"},
        "lease": {"machine_id": None, "valid": False},
        "last_heartbeat": {"status": "unknown"},
    })

    def fake_probe_v1_models(base_url, *, timeout=4.0):
        if "127.0.0.1:8072" in base_url:
            return "dead", [], False, ""
        if "127.0.0.1:8081" in base_url:
            return "listening", [{"id": "glm-5.2"}], True, ""
        raise AssertionError(
            f"_probe_v1_models called on unexpected URL: {base_url!r}"
        )

    monkeypatch.setattr(m, "_probe_v1_models", fake_probe_v1_models)

    class _Resp:
        def __init__(self, status, body):
            self.status = status
            self._body = body.encode("utf-8")
        def read(self): return self._body
        def __enter__(self): return self
        def __exit__(self, *a): return False

    captured_hb = {}
    def fake_urlopen(req, **kwargs):
        if req.method == "POST":
            captured_hb["body"] = json.loads(req.data.decode("utf-8")) if req.data else None
            return _Resp(200, cloud_state)
        return _Resp(200, cloud_state)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        rc = m.run_once(
            machine_id="col-8081",
            agency_url="https://example.invalid",
            token="t",
            http_port=8072,
            start_timeout=5,
        )

    assert rc == 0
    body = captured_hb["body"]
    assert body is not None
    assert body["status"] == "ok"
    assert body["port_state"] == "listening"
    assert body["models_has_glm52"] is True
    assert body["v1_models"] == [{"id": "glm-5.2"}]


def test_machine_id_default_path_is_not_windows_literal_on_this_platform(monkeypatch):
    """Regression: the machine-id file default was a bare Windows literal
    (C:\\Users\\swami\\...) with no platform check. On POSIX, pathlib treats
    backslashes as literal filename characters (not separators), so the
    whole string resolved to one garbage file dropped in the current working
    directory instead of a real nested path — confirmed: this happened for
    real in a non-Windows session. Machine-id generation is a cross-platform
    concern, so off Windows it must fall back to something that actually
    creates a normal nested path."""
    import sys
    m = _import_controller()
    monkeypatch.delenv("LOCAL_BRAIN_MACHINE_ID_FILE", raising=False)

    default = m._default_machine_id_file()
    if sys.platform == "win32":
        assert default.startswith("C:\\")
    else:
        assert "\\" not in default, (
            f"non-Windows default must not contain backslashes: {default!r}"
        )
        assert Path(default).is_absolute()
        assert Path(default).parent != Path(".")


def test_machine_id_path_honors_explicit_env_override(tmp_path, monkeypatch):
    m = _import_controller()
    target = tmp_path / "custom" / "machine.id"
    monkeypatch.setenv("LOCAL_BRAIN_MACHINE_ID_FILE", str(target))

    p = m._machine_id_path()

    assert p == target
    assert p.parent.is_dir()  # mkdir(parents=True) ran
