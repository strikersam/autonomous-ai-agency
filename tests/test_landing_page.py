"""The public landing page is crawlable, honest, and wired into every host.

Before 2026-10-08 every host served only the SPA, so crawlers that do not run
JavaScript saw a login shell and the agency had no indexable page. The
landing page is static HTML served at "/" (worker/index.js, Netlify
_redirects); the app shell is noindex.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PUBLIC = REPO / "frontend" / "public"
CANONICAL = "https://autonomous-ai-agency.strikersam.workers.dev/"
SPA_ROUTES = {"/login", "/v5", "/auth/callback", "/bootstrap"}
ALLOWED_HOSTS = ("https://github.com/strikersam/autonomous-ai-agency", "https://github.com/strikersam",
                 "https://autonomous-ai-agency.strikersam.workers.dev/", "https://opensource.org/licenses/MIT",
                 "https://schema.org")


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.ld: list[str] = []
        self._in_ld = False

    def handle_starttag(self, tag, attrs):
        a = {k: v or "" for k, v in attrs}
        self.tags.append((tag, a))
        self._in_ld = tag == "script" and a.get("type") == "application/ld+json"

    def handle_data(self, data):
        if self._in_ld:
            self.ld.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_ld = False


@pytest.fixture(scope="module")
def html() -> str:
    return (PUBLIC / "home.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def page(html) -> _Page:
    p = _Page()
    p.feed(html)
    return p


def _all(page: _Page, tag: str) -> list[dict[str, str]]:
    return [a for t, a in page.tags if t == tag]


def test_head_has_title_description_canonical_and_social_tags(html, page):
    title = re.search(r"<title>(.*?)</title>", html, re.S).group(1)
    assert 30 <= len(title) <= 70
    meta = {a.get("name") or a.get("property"): a.get("content", "") for a in _all(page, "meta")}
    assert 70 <= len(meta["description"]) <= 160
    assert {"og:title", "og:description", "og:image", "og:url", "twitter:card"} <= set(meta)
    assert meta["og:url"] == CANONICAL
    assert [a["href"] for a in _all(page, "link") if a.get("rel") == "canonical"] == [CANONICAL]
    assert (PUBLIC / meta["og:image"].removeprefix(CANONICAL)).is_file()


def test_semantic_structure(page):
    tags = [t for t, _ in page.tags]
    assert tags.count("h1") == 1
    for landmark in ("header", "nav", "main", "footer"):
        assert landmark in tags, landmark
    for img in _all(page, "img"):
        assert "alt" in img and img.get("width") and img.get("height")


def test_structured_data_is_valid_and_matches_the_project(page):
    graph = json.loads("".join(page.ld))["@graph"]
    app = next(n for n in graph if n["@type"] == "SoftwareApplication")
    assert app["url"] == CANONICAL
    assert app["license"].endswith("/MIT")
    assert app["offers"]["price"] == "0"
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert f"version-{app['softwareVersion']}-" in readme


def test_every_link_resolves(page):
    ids = {a["id"] for _, a in page.tags if "id" in a}
    for a in _all(page, "a"):
        href = a["href"]
        if href.startswith("#"):
            assert href[1:] in ids, href
        elif href.startswith("/"):
            assert href == "/" or href in SPA_ROUTES or (PUBLIC / href.lstrip("/")).is_file(), href
        else:
            assert href.startswith(ALLOWED_HOSTS), f"unexpected external link {href}"
            repo_file = re.match(r"https://github.com/strikersam/autonomous-ai-agency/blob/master/(.+)", href)
            if repo_file:
                assert (REPO / repo_file.group(1)).is_file(), href


def test_numbers_quoted_on_the_page_are_the_published_ones(html):
    proof = (REPO / "proof" / "README.md").read_text(encoding="utf-8")
    for score in re.findall(r"(\d+\.\d) / 100", html):
        assert f"{score}/100" in proof, score


def test_no_invented_customers_or_contacts(html):
    lowered = html.lower()
    for banned in ("gucci", "mailto:", "contact@", "twitter.com/", "x.com/", "testimonial"):
        assert banned not in lowered, banned


def test_hosts_serve_the_landing_page_at_root_and_hide_the_app_shell():
    redirects = (PUBLIC / "_redirects").read_text(encoding="utf-8").splitlines()
    assert redirects[0].split() == ["/", "/home.html", "200!"]
    assert redirects[-1].split() == ["/*", "/index.html", "200"]
    worker = (REPO / "worker" / "index.js").read_text(encoding="utf-8")
    assert 'new URL("/home", url.origin)' in worker
    # Cloudflare serves an existing asset (index.html for "/") without running the
    # Worker unless the path is listed here; found by running `wrangler dev`.
    wrangler = (REPO / "wrangler.jsonc").read_text(encoding="utf-8")
    first = json.loads(re.search(r'"run_worker_first":\s*(\[.*?\])', wrangler, re.S).group(1))
    assert "/" in first
    shell = (REPO / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex" />' in shell


def test_crawler_files_point_at_the_landing_page():
    robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8")
    assert f"Sitemap: {CANONICAL}sitemap.xml" in robots
    assert "Disallow: /v5/" in robots and "Disallow: /api/" in robots
    sitemap = (PUBLIC / "sitemap.xml").read_text(encoding="utf-8")
    assert f"<loc>{CANONICAL}</loc>" in sitemap
    assert CANONICAL in (PUBLIC / "llms.txt").read_text(encoding="utf-8")


def test_faq_is_visible_and_mirrored_in_faqpage_schema(html, page):
    graph = json.loads("".join(page.ld))["@graph"]
    types = {n["@type"] for n in graph}
    assert {"WebSite", "Organization", "FAQPage"} <= types
    faq = next(n for n in graph if n["@type"] == "FAQPage")["mainEntity"]
    assert len(faq) >= 5
    for q in faq:
        # Schema must match what a visitor can read; markup for hidden text is spam.
        assert q["name"].replace("&", "&amp;") in html
        assert q["acceptedAnswer"]["text"].replace("&", "&amp;") in html


def test_aliases_of_the_landing_page_redirect_in_the_worker_not_in_redirects_file():
    # Cloudflare static assets also read _redirects, so a "/home -> /" rule there makes the
    # Worker's own internal fetch of /home redirect to "/" and fall back to the noindex shell.
    redirects = [ln.split() for ln in (PUBLIC / "_redirects").read_text(encoding="utf-8").splitlines()]
    assert not [r for r in redirects if r[0].startswith("/home")]
    worker = (REPO / "worker" / "index.js").read_text(encoding="utf-8")
    assert 'LANDING_ALIASES = ["/home", "/home/", "/home.html"]' in worker
    wrangler = (REPO / "wrangler.jsonc").read_text(encoding="utf-8")
    first = json.loads(re.search(r'"run_worker_first":\s*(\[.*?\])', wrangler, re.S).group(1))
    assert {"/home", "/home/", "/home.html"} <= set(first)


def test_ai_crawlers_are_allowed_and_llms_txt_has_an_faq():
    robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8")
    for bot in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"):
        assert f"User-agent: {bot}" in robots, bot
    assert "## FAQ" in (PUBLIC / "llms.txt").read_text(encoding="utf-8")


def test_login_is_reached_by_form_not_crawlable_link(html):
    # /login is the deliberately noindex app shell; a crawlable <a> to it was flagged
    # as a Noindex page with no H1 and no internal links.
    assert 'href="/login"' not in html
    assert html.count('action="/login"') == 3


def test_indexnow_key_file_matches_its_name_and_robots_meta_allows_snippets(html):
    keys = [f for f in PUBLIC.glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}", f.stem)]
    assert len(keys) == 1
    assert keys[0].read_text(encoding="utf-8").strip() == keys[0].stem
    assert 'content="index,follow,max-snippet:-1,max-image-preview:large' in html
