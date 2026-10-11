"""agent/ui_evidence.py — screenshot the pages an agent changed, as proof.

Rule 49 wants screenshots for any UI change. After a run whose judge approved
it, this serves the E2B sandbox's working copy over HTTP (the sandbox's public
preview host), opens each changed page in the real browser (Browserbase or
local Chromium, agent/browser.py) and stores the screenshot with the task
(tasks/screenshots.py). The verification report then cites each one.

What it can and cannot prove: static pages (``.html``) are served as written,
so the screenshot shows the agent's change. Pages that need a build step (a
``.jsx`` or ``.vue`` change) are not built here; for those the result says so
and the task waits for a person, rather than passing a screenshot of stale
output off as proof.

Gated by the live ``AGENT_UI_EVIDENCE`` control (default on).
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

log = logging.getLogger("qwen-proxy")

# Plain .js/.ts are left out: they are as often server code as page code.
UI_SUFFIXES = (".html", ".htm", ".css", ".scss", ".jsx", ".tsx", ".vue", ".svelte")
_PAGE_SUFFIXES = (".html", ".htm")
_STATIC_ASSETS = (".css",)
_MAX_PAGES = 3
_PREVIEW_PORT = 4173


def enabled() -> bool:
    """Read the live ``AGENT_UI_EVIDENCE`` control."""
    from packages.config import settings

    return bool(getattr(settings, "agent_ui_evidence", True))


def _remote_browser() -> bool:
    from packages.config import settings

    return bool(getattr(settings, "browserbase_configured", False))


def ui_files(steps: list[dict[str, Any]]) -> list[str]:
    """Changed files that affect what a person sees, from applied steps."""
    out: list[str] = []
    for step in steps:
        if step.get("status") != "applied":
            continue
        for f in step.get("changed_files") or []:
            name = str(f).replace("\\", "/")
            if name.lower().endswith(UI_SUFFIXES) and not _is_test(name):
                out.append(name)
    return list(dict.fromkeys(out))


def _is_test(path: str) -> bool:
    parts = path.lower().split("/")
    return any(p in {"tests", "test", "__tests__"} for p in parts[:-1]) or ".test." in parts[-1] or ".spec." in parts[-1]


def _pages(files: list[str]) -> tuple[list[str], list[str]]:
    """(pages to open, files that need a build to preview)."""
    pages = [f for f in files if f.lower().endswith(_PAGE_SUFFIXES)]
    built = [f for f in files if not f.lower().endswith(_PAGE_SUFFIXES + _STATIC_ASSETS)]
    if not pages and any(f.lower().endswith(_STATIC_ASSETS) for f in files):
        pages = ["index.html"]  # a stylesheet change shows on the home page
    return pages[:_MAX_PAGES], built


async def capture(mcp: Any, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Screenshot the changed pages. Returns one entry per page or gap:
    ``{page, shot_id}`` for a stored screenshot, ``{page, error}`` otherwise."""
    files = ui_files(steps)
    if not files or not enabled():
        return []
    pages, needs_build = _pages(files)
    gaps = [{"page": f, "error": "needs a build step to preview; not screenshotted"} for f in needs_build]
    if not _remote_browser():
        # Agent-written pages run their own scripts; on a local Chromium those
        # could reach this host's network (rule 14). Only the cloud browser
        # renders them.
        return gaps + [{"page": p, "error": "screenshots need the Browserbase cloud browser"} for p in pages]
    preview = getattr(mcp, "preview_url", None)
    if preview is None:
        return gaps + [{"page": p, "error": "no E2B sandbox attached to serve the page from"} for p in pages]
    base = await preview(_PREVIEW_PORT)
    if not base:
        return gaps + [{"page": p, "error": "sandbox preview server did not start"} for p in pages]
    return gaps + [await _shoot(f"{base}/{quote(p.lstrip('/'))}", p) for p in pages]


async def _shoot(url: str, page: str) -> dict[str, Any]:
    from agent.browser import screenshot_page
    from tasks.screenshots import save_screenshot

    shot = await screenshot_page(url)
    if not shot.get("ok"):
        return {"page": page, "error": str(shot.get("error") or "screenshot failed")[:300]}
    try:
        shot_id = await save_screenshot(shot["image"], page_url=url)
    except Exception as exc:  # noqa: BLE001 - storage failure is a gap, not a crash
        log.warning("UI evidence: could not store screenshot of %s: %s", page, exc)
        return {"page": page, "error": "screenshot could not be stored"}
    return {"page": page, "url": url, "shot_id": shot_id, "title": shot.get("title", "")}
