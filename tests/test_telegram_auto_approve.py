"""Auto-approve policy for Telegram plain-text → orchestrator routing.

Routine work runs hands-free; the approval gate only fires when the agent can't
safely decide on its own. ``auto_approve=True`` requires ALL of: a confident
``execute_now`` intent, an admin sender, and a non-sensitive request. Everything
else gates (``auto_approve=False``).
"""
from __future__ import annotations

import pytest

from packages.notifications import bot as tb
import telegram_inbound_handlers as tih
from services import inbound_router as ir


@pytest.fixture()
def admin_user(monkeypatch):
    monkeypatch.setattr(tb, "ADMIN_USER_IDS", {123}, raising=False)
    return 123


@pytest.fixture()
def non_admin_user(monkeypatch):
    monkeypatch.setattr(tb, "ADMIN_USER_IDS", {123}, raising=False)
    return 999


def _auto_approve(req) -> bool:
    assert req is not None, "ExecutionRequest should build"
    return bool(req.auto_approve)


def test_admin_execute_now_routine_auto_approves(admin_user):
    req = tih._build_execution_request(user_id=admin_user, text="fix the failing test in utils", intent="execute_now")
    assert _auto_approve(req) is True
    assert req.metadata.get("auto_approved") is True


def test_admin_execute_after_approval_gates(admin_user):
    req = tih._build_execution_request(user_id=admin_user, text="refactor the billing module", intent="execute_after_approval")
    assert _auto_approve(req) is False


def test_non_admin_execute_now_gates(non_admin_user):
    req = tih._build_execution_request(user_id=non_admin_user, text="fix the failing test", intent="execute_now")
    assert _auto_approve(req) is False, "only the admin operator may auto-approve"


def test_admin_execute_now_sensitive_target_gates(admin_user):
    # Sensitive (key_store) request must NOT auto-approve even from an admin with
    # an execute_now intent — belt-and-braces floor independent of the classifier.
    req = tih._build_execution_request(user_id=admin_user, text="rotate the key_store secret", intent="execute_now")
    assert _auto_approve(req) is False


def test_default_intent_gates(admin_user):
    # Defensive default: omitting intent must NOT auto-approve.
    req = tih._build_execution_request(user_id=admin_user, text="do the thing")
    assert _auto_approve(req) is False


def test_is_sensitive_matches_targets():
    assert ir.is_sensitive("please update admin_auth flow")
    assert ir.is_sensitive("rotate the API credential")
    assert ir.is_sensitive("change the service_manager config")
    assert not ir.is_sensitive("write a blog post about cats")
    assert not ir.is_sensitive("")
