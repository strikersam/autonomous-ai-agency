"""tests/test_sam_screen.py — SAM knows which dashboard screen the Commander is on."""

from __future__ import annotations

import importlib

import pytest

from agent import sam_screen
from agent.sam import SamAgent


@pytest.mark.parametrize("raw,expected", [
    ("work/roadmap", "work/roadmap"),
    ("HOME", "home"),
    ("", ""),
    ("../etc/passwd", ""),
    ("work/roadmap; drop", ""),
    ("a" * 30, ""),
])
def test_screen_is_normalised_to_a_safe_path(raw, expected):
    assert sam_screen.normalise_screen(raw) == expected


def test_labels():
    assert sam_screen.screen_label("work/roadmap") == "the Portfolio roadmap"
    assert sam_screen.screen_label("work/unknown_tab") == "the work unknown_tab screen"
    assert sam_screen.screen_label("") == ""


@pytest.mark.parametrize("text,screen,expected", [
    ("pick up the top one", "work/roadmap", "portfolio"),
    ("start this one", "work/roadmap", "portfolio"),
    ("work on them", "work/roadmap", "portfolio"),
    ("pick up the top one", "home", None),
    ("what is this", "work/roadmap", None),
])
def test_screen_resolves_deictic_requests(text, screen, expected):
    assert sam_screen.screen_intent(text, screen) == expected


async def test_top_one_on_the_roadmap_picks_up_portfolio_work(monkeypatch):
    """'pick up the top one' alone means nothing; on the roadmap it is portfolio intake."""
    orch = importlib.import_module("agent.sam_orchestrator")

    async def _pick():
        return "Picked up 1 portfolio initiative for the agents."

    monkeypatch.setattr(orch, "pick_up_portfolio", _pick)
    agent = SamAgent()
    assert (await agent.process_command("pick up the top one", is_admin=True, screen="work/roadmap")
            ).startswith("Picked up 1")
    assert "needs an admin" in await agent.process_command(
        "pick up the top one", is_admin=False, screen="work/roadmap")


async def test_prompt_says_where_the_commander_is(monkeypatch):
    prompts: list[str] = []

    async def _llm(self, prompt, session):
        prompts.append(prompt)
        return "ok"

    async def _facts(screen):
        return "The task queue is empty."

    monkeypatch.setattr(SamAgent, "_call_llm", _llm)
    monkeypatch.setattr(sam_screen, "_facts", _facts)
    await SamAgent().process_command("anything stuck here?", screen="work/now")
    assert "The Commander is looking at the task board. The task queue is empty." in prompts[0]


async def test_screen_facts_failure_never_blocks_sam(monkeypatch):
    async def _boom(screen):
        raise RuntimeError("store down")

    monkeypatch.setattr(sam_screen, "_facts", _boom)
    assert await sam_screen.screen_context("work/now") == "The Commander is looking at the task board."


def test_chat_endpoint_validates_and_forwards_screen(client, monkeypatch):
    from backend.server import app, get_current_user

    seen = {}

    async def _fake(self, text, session_id="default", owner_id="", *, is_admin=False, screen=""):
        seen["screen"] = screen
        return "ok"

    monkeypatch.setattr(SamAgent, "process_command", _fake)
    app.dependency_overrides[get_current_user] = lambda: {"_id": "u1", "role": "admin"}
    try:
        ok = client.post("/agent/sam/chat", json={"text": "hi", "screen": "work/roadmap"})
        bad = client.post("/agent/sam/chat", json={"text": "hi", "screen": "../../x"})
    finally:
        app.dependency_overrides.clear()
    assert ok.status_code == 200 and seen["screen"] == "work/roadmap"
    assert bad.status_code == 422
