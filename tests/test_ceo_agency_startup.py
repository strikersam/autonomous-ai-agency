"""tests/test_ceo_agency_startup.py — the CEO loop must actually be started.

Root cause of "agents sit idle all the time": start_background_services launched the
dispatcher/scheduler/self-bootstrap but never started the proactive 24x7 CEO Agency
loop, so nothing generated work between reactive events. These tests pin the gating.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture(autouse=True)
def _reset_agency_singleton(monkeypatch):
    import agent.agency as agency_mod
    # Reset the module-global singleton around each test.
    monkeypatch.setattr(agency_mod, "_agency_instance", None, raising=False)
    yield
    monkeypatch.setattr(agency_mod, "_agency_instance", None, raising=False)


def test_ceo_agency_starts_by_default(monkeypatch):
    import agent.agency as agency_mod
    from services.background import _start_ceo_agency

    monkeypatch.delenv("AGENCY_CEO_ENABLED", raising=False)
    started = {"v": False}
    monkeypatch.setattr(agency_mod.Agency, "start", lambda self: started.__setitem__("v", True))

    _start_ceo_agency()

    assert agency_mod.get_agency() is not None, "CEO agency must be registered on startup"
    assert started["v"] is True, "CEO agency loop must be started"


def test_ceo_agency_can_be_disabled(monkeypatch):
    import agent.agency as agency_mod
    from services.background import _start_ceo_agency

    monkeypatch.setenv("AGENCY_CEO_ENABLED", "false")
    monkeypatch.setattr(agency_mod.Agency, "start", lambda self: (_ for _ in ()).throw(AssertionError("should not start")))

    _start_ceo_agency()

    assert agency_mod.get_agency() is None, "disabled flag must prevent CEO startup"


def test_ceo_agency_startup_never_raises(monkeypatch):
    """A failure constructing/starting the CEO must not crash app startup."""
    import agent.agency as agency_mod
    from services.background import _start_ceo_agency

    monkeypatch.delenv("AGENCY_CEO_ENABLED", raising=False)

    def boom(self):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(agency_mod.Agency, "start", boom)
    # Should swallow the error, not propagate.
    _start_ceo_agency()
