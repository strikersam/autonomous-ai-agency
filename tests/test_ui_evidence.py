"""Screenshots as rule-49 proof for UI changes made by agency agents.

Covers which files count as UI, capturing pages served from the E2B sandbox,
the verification gate (a UI change needs a screenshot to pass on its own),
the screenshot endpoint and its access rule, and the browser's fallback when
Browserbase is down.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from agent import ui_evidence
from packages.config import control_overrides, settings
from tasks import screenshots
from tasks.api import task_router
from tasks.models import Task, TaskStatus
from tasks.store import TaskStore, set_task_store
from tasks.verification import unbacked_note, verification_from_run

JPEG = b"\xff\xd8\xff\xe0fakejpeg"


def _steps(*files):
    return [{"description": "edit", "status": "applied", "changed_files": list(files),
             "executed_checks": ["pytest -x tests/test_a.py: passed"]}]


def _run(files, ui):
    return {"steps": _steps(*files), "judge": {"verdict": "APPROVED"}, "ui_evidence": ui}


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    control_overrides.apply_overrides({})
    set_task_store(TaskStore())
    screenshots._memory.clear()
    monkeypatch.setattr(settings, "browserbase_api_key", "bb_test", raising=False)
    yield
    control_overrides.apply_overrides({})


class _Sandbox:
    def __init__(self, base="https://4173-sbx.e2b.app"):
        self.base = base

    async def preview_url(self, port=4173):
        return self.base


def _fake_browser(monkeypatch, ok=True):
    calls = []

    async def shot(url):
        calls.append(url)
        if not ok:
            return {"ok": False, "error": "browserbase failed to start: 403"}
        return {"ok": True, "url": url, "title": "Home", "image": JPEG}

    import agent.browser as browser
    monkeypatch.setattr(browser, "screenshot_page", shot)
    return calls


# ── which files are UI ───────────────────────────────────────────────────────

def test_ui_files_counts_pages_and_styles_not_tests_or_server_code():
    steps = _steps("site/index.html", "app.css", "src/App.jsx", "server.js", "api.py",
                   "src/__tests__/App.test.jsx", "tests/fixture.html", "src/testimonials.html")
    steps.append({"status": "failed", "changed_files": ["ignored.html"]})
    assert ui_evidence.ui_files(steps) == ["site/index.html", "app.css", "src/App.jsx", "src/testimonials.html"]


# ── capture ──────────────────────────────────────────────────────────────────

def test_capture_screenshots_changed_pages_served_from_the_sandbox(monkeypatch):
    calls = _fake_browser(monkeypatch)
    out = asyncio.run(ui_evidence.capture(_Sandbox(), _steps("site/about us.html", "a.py")))
    assert calls == ["https://4173-sbx.e2b.app/site/about%20us.html"]
    assert out[0]["shot_id"].startswith("shot_") and out[0]["page"] == "site/about us.html"
    stored = asyncio.run(screenshots.get_screenshot(out[0]["shot_id"]))
    assert stored["image"] == JPEG


def test_stylesheet_change_screenshots_the_home_page(monkeypatch):
    calls = _fake_browser(monkeypatch)
    asyncio.run(ui_evidence.capture(_Sandbox(), _steps("styles/site.css")))
    assert calls == ["https://4173-sbx.e2b.app/index.html"]


def test_component_change_is_reported_as_needing_a_build(monkeypatch):
    calls = _fake_browser(monkeypatch)
    out = asyncio.run(ui_evidence.capture(_Sandbox(), _steps("src/App.jsx")))
    assert calls == [] and "needs a build" in out[0]["error"]


def test_no_sandbox_means_no_screenshot_and_says_why(monkeypatch):
    _fake_browser(monkeypatch)
    out = asyncio.run(ui_evidence.capture(None, _steps("index.html")))
    assert "no E2B sandbox" in out[0]["error"]


def test_no_screenshots_with_a_local_browser(monkeypatch):
    """Agent-written page scripts must not run on this host's network (rule 14)."""
    calls = _fake_browser(monkeypatch)
    monkeypatch.setattr(settings, "browserbase_api_key", "", raising=False)
    out = asyncio.run(ui_evidence.capture(_Sandbox(), _steps("index.html")))
    assert calls == [] and "Browserbase" in out[0]["error"]


def test_capture_off_by_control(monkeypatch):
    calls = _fake_browser(monkeypatch)
    control_overrides.apply_overrides({"AGENT_UI_EVIDENCE": "false"})
    assert settings.agent_ui_evidence is False
    assert asyncio.run(ui_evidence.capture(_Sandbox(), _steps("index.html"))) == []
    assert calls == []


def test_browser_failure_is_a_gap_not_a_crash(monkeypatch):
    _fake_browser(monkeypatch, ok=False)
    out = asyncio.run(ui_evidence.capture(_Sandbox(), _steps("index.html")))
    assert "403" in out[0]["error"] and "shot_id" not in out[0]


# ── the gate ─────────────────────────────────────────────────────────────────

def test_ui_change_with_screenshot_passes_and_cites_it():
    run = _run(["index.html", "a.py"], [{"page": "index.html", "url": "https://h/index.html", "shot_id": "shot_0123456789abcdef"}])
    v = verification_from_run(run)
    assert v.verdict == "PASS"
    assert "screenshot:shot_0123456789abcdef https://h/index.html" in v.evidence
    assert any("real browser" in c for c in v.checked)
    assert unbacked_note(run) is None


@pytest.mark.parametrize("ui", [[], [{"page": "src/App.jsx", "error": "needs a build step to preview"}]])
def test_ui_change_without_screenshot_waits_for_a_person(ui):
    run = _run(["src/App.jsx", "a.py"], ui)
    assert verification_from_run(run) is None
    assert "screenshot" in unbacked_note(run)


def test_gap_message_names_the_control_only_when_it_is_off():
    run = _run(["index.html", "a.py"], [])
    assert "AGENT_UI_EVIDENCE" not in unbacked_note(run)
    control_overrides.apply_overrides({"AGENT_UI_EVIDENCE": "false"})
    assert "AGENT_UI_EVIDENCE is off" in unbacked_note(run)


def test_non_ui_change_needs_no_screenshot():
    assert verification_from_run(_run(["a.py"], [])).verdict == "PASS"


def test_rejected_ui_change_still_fails_without_screenshot():
    run = _run(["index.html"], [])
    run["judge"] = {"verdict": "REJECTED", "notes": "wrong page"}
    assert verification_from_run(run).verdict == "FAIL"


# ── endpoint ─────────────────────────────────────────────────────────────────

def _client(email="priya@x.com", role="admin"):
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user = SimpleNamespace(email=email, role=role)
        return await call_next(request)

    app.include_router(task_router)
    return TestClient(app)


async def _task_citing(shot_id, store):
    from tasks.verification import TaskVerification

    task = Task(owner_id="priya@x.com", title="t", status=TaskStatus.DONE, agent_id="dev")
    task.verification = TaskVerification(
        verdict="PASS", verifier="agent:judge", evidence=[screenshots.evidence_line(shot_id, "https://h/")]
    )
    await store.create(task)
    return task


@pytest.mark.asyncio
async def test_endpoint_serves_a_cited_screenshot_and_refuses_others():
    store = TaskStore()
    set_task_store(store)
    shot = await screenshots.save_screenshot(JPEG, page_url="https://h/")
    other = await screenshots.save_screenshot(b"\xff\xd8other", page_url="https://x/")
    task = await _task_citing(shot, store)
    c = _client()
    resp = c.get(f"/api/tasks/{task.task_id}/screenshots/{shot}")
    assert resp.status_code == 200 and resp.content == JPEG
    assert resp.headers["content-type"] == "image/jpeg"
    assert "no-store" in resp.headers["cache-control"]
    assert c.get(f"/api/tasks/{task.task_id}/screenshots/{other}").status_code == 404


def test_endpoint_requires_sign_in():
    app = FastAPI()
    app.include_router(task_router)
    assert TestClient(app).get("/api/tasks/t/screenshots/shot_0123456789abcdef").status_code == 401


@pytest.mark.asyncio
async def test_a_verdict_cannot_cite_another_tasks_screenshot():
    store = TaskStore()
    set_task_store(store)
    mine = await screenshots.save_screenshot(JPEG, page_url="https://h/")
    foreign = await screenshots.save_screenshot(b"\xff\xd8x", page_url="https://x/")
    task = await _task_citing(mine, store)
    body = {"verdict": "PASS", "evidence": [
        screenshots.evidence_line(mine, "https://h/"), screenshots.evidence_line(foreign, "https://x/"), "note"]}
    resp = _client().post(f"/api/tasks/{task.task_id}/verification", json=body)
    assert resp.status_code == 200, resp.text
    ev = resp.json()["task"]["verification"]["evidence"]
    assert ev == [screenshots.evidence_line(mine, "https://h/"), "note"]


# ── browser fallback when Browserbase is down ────────────────────────────────

def test_browse_page_falls_back_to_fetch_and_cools_down(monkeypatch):
    import agent.browser as browser

    monkeypatch.setattr(browser, "_down_until", 0.0)
    monkeypatch.setattr(browser.BrowserSession, "_check_available", lambda self: True)
    starts = []

    async def boom(self, **_):
        starts.append(1)
        raise RuntimeError("WebSocket error: wss://connect.browserbase.com?apiKey=bb_live_SECRET 500")

    async def stop(self):
        return None

    monkeypatch.setattr(browser.BrowserSession, "start", boom)
    monkeypatch.setattr(browser.BrowserSession, "stop", stop)

    class _Reach:
        def fetch_page(self, url):
            return {"ok": True, "url": url, "text": "plain text"}

    import agent.web_reach as web_reach
    monkeypatch.setattr(web_reach, "get_web_reach", lambda: _Reach())

    first = asyncio.run(browser.browse_page("https://example.com"))
    assert first["ok"] is True and first["backend"] == "fetch_fallback"
    assert "bb_live_SECRET" not in first["note"] and "apiKey=***" in first["note"]
    second = asyncio.run(browser.browse_page("https://example.com"))
    assert second["backend"] == "fetch_fallback" and len(starts) == 1  # cooled down, no retry
    shot = asyncio.run(browser.screenshot_page("https://example.com"))
    assert shot["ok"] is False and len(starts) == 1
