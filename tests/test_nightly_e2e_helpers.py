"""Nightly e2e helpers (#1565) — hermetic, no browser or backend.

Two failures hid in the nightly regression workflow:

* ``tests/e2e/test_regression.py::browser_login`` waited on
  ``wait_for_load_state("networkidle")`` after submit. In a single-page app that
  state was reached before submit, so it returned in ~1ms and the login XHR plus
  React's redirect got a 500ms sleep. A backend seconds into startup took longer
  and both viewports reported "still on /login". Reproduced locally by holding
  the login XHR 400ms.
* ``tests/e2e/test_telegram_approval_e2e.py`` put its JWT under a localStorage
  key the SPA never reads, opened a route that no longer exists, and read
  ``execution_approved`` from the top level of a ``{"task": {...}}`` response.
  It failed every night, hidden by ``continue-on-error``.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

REPO = Path(__file__).resolve().parent.parent
E2E = REPO / "tests" / "e2e"


def _load(name: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "test-only-password")  # nosec B105 — fake
    spec = importlib.util.spec_from_file_location(f"_nightly_{name}", E2E / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ── browser_login ────────────────────────────────────────────────────────────


class _Loc:
    def __init__(self, page: "_SlowLoginPage", kind: str) -> None:
        self.page, self.kind = page, kind

    @property
    def first(self) -> "_Loc":
        return self

    def count(self) -> int:
        return 0 if self.kind == "toggle" else 1

    def is_visible(self) -> bool:
        return True

    def fill(self, value: str) -> None:
        pass

    def click(self) -> None:
        self.page.submitted = True

    def press(self, key: str) -> None:
        self.page.submitted = True


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status


class _ExpectResponse:
    def __init__(self, page: "_SlowLoginPage") -> None:
        self.page = page

    def __enter__(self) -> "_ExpectResponse":
        return self

    def __exit__(self, *exc) -> None:
        if not self.page.submitted:
            raise self.page.timeout_error("no login request")

    @property
    def value(self) -> _Response:
        return _Response(self.page.status)


class _SlowLoginPage:
    """A SPA whose login round-trip takes longer than any fixed sleep.

    The URL only leaves /login once the caller actually waits for it, so a
    helper that sleeps a fixed interval and then reads ``page.url`` fails
    exactly as the nightly did.
    """

    def __init__(self, timeout_error: type[Exception], status: int = 200) -> None:
        self.timeout_error = timeout_error
        self.status = status
        self.submitted = False
        self.url = "http://localhost:8001/login"

    def goto(self, url: str, **_: object) -> None:
        self.url = url

    def wait_for_timeout(self, ms: int) -> None:
        pass

    def wait_for_load_state(self, state: str = "load", **_: object) -> None:
        pass  # already reached: the SPA document never reloads

    def locator(self, selector: str) -> _Loc:
        return _Loc(self, "toggle" if "toggle-admin-login" in selector else "field")

    def expect_response(self, predicate, **_: object) -> _ExpectResponse:
        return _ExpectResponse(self)

    def wait_for_url(self, predicate, **_: object) -> None:
        if self.submitted and self.status == 200:
            self.url = "http://localhost:8001/v5"
        if not predicate(self.url):
            raise self.timeout_error("still on /login")


class TestBrowserLogin:
    @pytest.fixture()
    def reg(self, monkeypatch):
        module = _load("test_regression", monkeypatch)
        module.Report.reset()
        return module

    def test_waits_for_the_redirect_instead_of_a_fixed_sleep(self, reg) -> None:
        page = _SlowLoginPage(reg.PlaywrightTimeoutError)
        assert reg.browser_login(page) is True, reg.Report.errors
        assert page.url.endswith("/v5")

    def test_bad_credentials_are_reported_as_such(self, reg) -> None:
        page = _SlowLoginPage(reg.PlaywrightTimeoutError, status=401)
        assert reg.browser_login(page) is False
        assert "returned 401" in reg.Report.errors[-1]

    def test_no_login_request_is_reported(self, reg, monkeypatch) -> None:
        page = _SlowLoginPage(reg.PlaywrightTimeoutError)
        monkeypatch.setattr(_Loc, "click", lambda self: None)
        monkeypatch.setattr(_Loc, "press", lambda self, key: None)
        assert reg.browser_login(page) is False
        assert "did not send POST /api/auth/login" in reg.Report.errors[-1]

    def test_never_waits_on_networkidle_after_submit(self) -> None:
        source = (E2E / "test_regression.py").read_text(encoding="utf-8")
        body = source.split("def browser_login", 1)[1].split("\ndef ", 1)[0]
        submit_onwards = body.split("btn = page.locator", 1)[1]
        code = "\n".join(line.split("#", 1)[0] for line in submit_onwards.splitlines())
        assert "wait_for_load_state" not in code


# ── Telegram approval e2e ────────────────────────────────────────────────────


class TestTelegramApprovalE2E:
    @pytest.fixture()
    def tg(self, monkeypatch):
        monkeypatch.delenv("ADMIN_JWT_LOCALSTORAGE_KEY", raising=False)
        return _load("test_telegram_approval_e2e", monkeypatch)

    def test_jwt_goes_where_the_spa_reads_it(self, tg) -> None:
        auth = (REPO / "frontend/src/AuthContext.js").read_text(encoding="utf-8")
        read_key = re.search(r"localStorage\.getItem\('([^']+)'\)", auth).group(1)
        assert tg.ADMIN_JWT_LOCALSTORAGE_KEY == read_key == "access_token"

    def test_task_board_path_is_a_real_v5_screen(self, tg) -> None:
        assert tg.TASK_BOARD_PATH == "/v5/work"
        v5 = (REPO / "frontend/src/v5/V5App.jsx").read_text(encoding="utf-8")
        assert re.search(r"\bwork:\s*<WorkHub\b", v5)
        hub = (REPO / "frontend/src/v5/screens/WorkHub.jsx").read_text(encoding="utf-8")
        assert "<TaskBoardScreen />" in hub

    def test_poll_reads_the_wrapped_task(self, tg, monkeypatch) -> None:
        class _R:
            status_code = 200

            @staticmethod
            def json() -> dict:
                return {"task": {"task_id": "t1", "execution_approved": True}}

        class _Client:
            def get(self, *a, **k) -> _R:
                return _R()

        monkeypatch.setattr(tg, "POLL_INTERVAL_SECONDS", 0)
        _, approved = tg._poll_task_execution_approved(
            _Client(), "jwt", "t1", deadline_seconds=1.0, expected=True
        )
        assert approved is True
