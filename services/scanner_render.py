"""services/scanner_render.py — optional headless-browser render pass for the scanner.

Static HTML scanning misses technologies that only reveal themselves at runtime —
single-page apps expose their stack via JavaScript globals (``window.Shopify``,
``window.__NEXT_DATA__``, ``Vue.version`` …) rather than in the served markup.
This module renders a page with Playwright/Chromium and reads those globals so the
scanner can evaluate Wappalyzer ``js`` rules.

It is **opt-in** (enabled by the ``SCANNER_RENDER`` env var) and degrades
gracefully: if Playwright or the browser binary is unavailable, or anything goes
wrong, :func:`render` returns ``None`` and the caller falls back to the static scan.

Security: a browser will follow redirects and load subresources, which reopens the
SSRF surface the static scanner closes. Every request the page makes is intercepted
and aborted unless its host passes the same ``_is_safe_url`` guard, so the browser
cannot be steered at loopback / link-local / private addresses.

NOTE: the live browser path cannot be exercised in the CI sandbox (no Chromium /
restricted egress). The pure helpers below are unit-tested; the browser glue must be
validated in an environment with ``playwright install chromium``.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

log = logging.getLogger("company_graph.scanner")

# JS evaluated inside the page: given a list of dotted global paths, return a map of
# {path: stringified value} for every path that resolves to a defined, non-null value.
_JS_READ_PATHS = """(paths) => {
  const out = {};
  for (const path of paths) {
    try {
      let cur = window;
      let ok = true;
      for (const seg of path.split('.')) {
        if (cur === null || cur === undefined) { ok = false; break; }
        cur = cur[seg];
      }
      if (ok && cur !== undefined && cur !== null) {
        let s;
        try { s = String(cur); } catch (e) { s = 'true'; }
        out[path] = s;
      }
    } catch (e) { /* ignore */ }
  }
  return out;
}"""

_SAFE_NONNETWORK_SCHEMES = ("data", "blob", "about")


def collect_js_paths(tech_data: Dict[str, Any]) -> List[str]:
    """Every distinct JS global path referenced by ``js`` rules in the DB."""
    paths = set()
    for spec in tech_data.get("apps", {}).values():
        js = spec.get("js")
        if isinstance(js, dict):
            paths.update(js.keys())
    return sorted(paths)


def request_allowed(req_url: str, is_safe_url: Callable[[str], bool], cache: Dict[str, bool]) -> bool:
    """Decide whether the browser may issue a request to ``req_url``.

    Non-network schemes (data:/blob:/about:) are always allowed; http(s) requests
    are gated by ``is_safe_url`` (cached per host); anything else is blocked.
    """
    try:
        parsed = urlparse(req_url)
    except Exception:
        return False
    scheme = (parsed.scheme or "").lower()
    if scheme in _SAFE_NONNETWORK_SCHEMES:
        return True
    if scheme not in ("http", "https"):
        return False
    host = parsed.hostname or ""
    if host not in cache:
        try:
            cache[host] = bool(is_safe_url(req_url))
        except Exception:
            cache[host] = False
    return cache[host]


async def render(
    url: str,
    *,
    is_safe_url: Callable[[str], bool],
    js_paths: List[str],
    timeout_ms: int = 15000,
    user_agent: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Render ``url`` in headless Chromium and return ``{html, headers, js_values}``.

    Returns ``None`` if Playwright/Chromium is unavailable or anything fails — the
    caller should fall back to the static scan.
    """
    try:
        from playwright.async_api import async_playwright
    except Exception as e:  # playwright not installed — feature simply stays off
        log.info(f"render pass unavailable (playwright not installed): {e}")
        return None

    host_cache: Dict[str, bool] = {}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                context = await browser.new_context(
                    user_agent=user_agent,
                    java_script_enabled=True,
                )
                page = await context.new_page()

                async def _route(route: Any) -> None:
                    if request_allowed(route.request.url, is_safe_url, host_cache):
                        await route.continue_()
                    else:
                        log.warning(f"render: blocked request to disallowed host: {route.request.url}")
                        await route.abort()

                await page.route("**/*", _route)

                response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                html = await page.content()
                headers = dict(response.headers) if response else {}
                js_values = await page.evaluate(_JS_READ_PATHS, js_paths) if js_paths else {}
                return {"html": html or "", "headers": headers, "js_values": js_values or {}}
            finally:
                await browser.close()
    except Exception as e:
        log.warning(f"render pass failed for {url}: {e}")
        return None
