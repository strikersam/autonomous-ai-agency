from __future__ import annotations

import sys
import types

import services.otel_tracing as ot
from agent.web_reach import unsafe_target_reason


def _fake_otel(monkeypatch):
    events: list[tuple[str, dict]] = []

    class _Span:
        def is_recording(self):
            return True

        def add_event(self, name, attributes=None):
            events.append((name, attributes or {}))

    trace = types.ModuleType("opentelemetry.trace")
    trace.get_current_span = lambda: _Span()
    pkg = types.ModuleType("opentelemetry")
    pkg.trace = trace
    monkeypatch.setitem(sys.modules, "opentelemetry", pkg)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", trace)
    return events


def test_blocked_url_emits_event_with_host_only(monkeypatch):
    events = _fake_otel(monkeypatch)
    monkeypatch.setattr(ot, "_OTEL_ENABLED", True)
    reason = unsafe_target_reason("http://127.0.0.1:8001/admin?token=secret")
    assert reason
    assert len(events) == 1
    name, attrs = events[0]
    assert name == "safety_event"
    assert attrs["kind"] == "web_reach_block"
    assert attrs["subject"] == "127.0.0.1"
    assert "secret" not in str(attrs)


def test_silent_when_otel_disabled(monkeypatch):
    events = _fake_otel(monkeypatch)
    monkeypatch.setattr(ot, "_OTEL_ENABLED", False)
    assert unsafe_target_reason("http://127.0.0.1/") is not None
    assert events == []


def test_emit_never_raises(monkeypatch):
    monkeypatch.setattr(ot, "_OTEL_ENABLED", True)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", None)
    ot.emit_safety_event("k", "s", "r")


def test_opens_own_span_when_no_recording_span(monkeypatch):
    events = _fake_otel(monkeypatch)
    spans: list[str] = []

    class _Own:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def add_event(self, name, attributes=None):
            events.append((name, attributes or {}))

    class _Tracer:
        def start_as_current_span(self, name):
            spans.append(name)
            return _Own()

    class _Idle:
        def is_recording(self):
            return False

        def add_event(self, *a, **k):
            raise AssertionError("event sent to non-recording span")

    sys.modules["opentelemetry.trace"].get_current_span = lambda: _Idle()
    monkeypatch.setattr(ot, "_OTEL_ENABLED", True)
    monkeypatch.setattr(ot, "get_tracer", lambda name="x": _Tracer())
    ot.emit_safety_event("k", "host", "why")
    assert spans == ["safety_event"]
    assert events and events[0][1]["subject"] == "host"
