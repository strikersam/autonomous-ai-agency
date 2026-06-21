"""
services/seo_audit.py - World-Class SEO / GEO / AIO Audit Engine

Screaming Frog-class site auditor (issue #533): crawls a website, runs the
full check catalog from services/seo_checks.py against every page plus
site-level signals (robots.txt, sitemaps, llms.txt, security headers, AI
crawler access), prioritizes findings, and produces a Screaming Frog-
compatible report with weighted health scores per pillar.

Usage:
    from models.seo_audit import SeoAuditRequest
    from services.seo_audit import SeoAuditEngine

    engine = SeoAuditEngine()
    report = await engine.run(SeoAuditRequest(website_url="https://example.com"))

The engine is deterministic and dependency-light (httpx + BeautifulSoup).
``analyze_page`` is exposed for unit testing individual checks without any
network access; ``transport`` may be injected for crawl tests.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import math
import re
import secrets
import threading
import urllib.robotparser
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from services.seo_fetch import PageFetcher, make_fetcher

from models.seo_audit import (
    SeoAuditReport,
    SeoAuditRequest,
    SeoAuditSummary,
    SeoDelegationTask,
    SeoIssueInstance,
    SeoIssueReportRow,
    SeoPageAudit,
    SeoSiteFindings,
)
from services import seo_checks as catalog
from services.scanner import _is_safe_url
from services.seo_checks import CHECKS

log = logging.getLogger("seo_audit")

USER_AGENT = "AgencySEOBot/1.0 (+https://github.com/strikersam/autonomous-ai-agency)"

# Bounded extra-request budgets (beyond the page crawl itself).
MAX_IMAGE_HEAD_REQUESTS = 40
MAX_LINK_HEAD_REQUESTS = 30
MAX_SITEMAP_FETCHES = 5
CRAWL_CONCURRENCY = 5

# Issue severity weighting for the 0-100 health scores.
_TYPE_FACTOR: Dict[str, float] = {"issue": 1.0, "warning": 0.55, "opportunity": 0.25}
_PRIORITY_WEIGHT: Dict[str, float] = {"high": 14.0, "medium": 7.0, "low": 3.0}

# Revenue-at-risk model (content-dependent, diminishing-returns).
#
# Each finding contributes "issue pressure" = severity x type x coverage-breadth.
# The aggregate pressure is mapped to an at-risk share of organic revenue via a
# saturating curve   share = MAX * (1 - e^(-pressure / SCALE))   so that:
#   * a handful of issues moves the figure only a little (NOT to the ceiling),
#   * a pervasively broken site approaches but never reaches the cap,
#   * the dollar number tracks what was actually measured instead of pinning to
#     the cap on almost any input.
# SCALE is calibrated so ~one site-wide high-priority issue (pressure ~= 14)
# puts ~8% at risk, and a catastrophic site (pressure ~= 150) ~= 33%.
MAX_REVENUE_LOSS_SHARE = 0.35
REVENUE_PRESSURE_SCALE = 50.0


def compute_pressure(
    rows: List[SeoIssueReportRow], total_pages: int
) -> tuple[list[float], float]:
    """Return (per-row issue pressure, total pressure) for the revenue model.

    pressure_i = PRIORITY_WEIGHT[priority] * TYPE_FACTOR[type] * min(1, urls/total_pages)
    """
    pressures = [
        _PRIORITY_WEIGHT[row.issue_priority]
        * _TYPE_FACTOR[row.issue_type]
        * min(1.0, row.urls_affected / total_pages)
        for row in rows
    ]
    return pressures, sum(pressures)


def loss_share_from_pressure(total_pressure: float) -> float:
    """Map aggregate issue pressure to an at-risk revenue share via the
    diminishing-returns curve (asymptotic to MAX_REVENUE_LOSS_SHARE)."""
    if total_pressure <= 0:
        return 0.0
    return MAX_REVENUE_LOSS_SHARE * (1.0 - math.exp(-total_pressure / REVENUE_PRESSURE_SCALE))


_VALID_HEAD_ELEMENTS = {
    "title", "meta", "link", "script", "style", "base", "noscript", "template", "head",
}

_QUESTION_PREFIXES = (
    "what", "how", "why", "when", "where", "who", "which", "can", "do", "does",
    "is", "are", "should", "will",
)

_HREFLANG_RE = re.compile(r"^[a-z]{2,3}(-[a-zA-Z]{2}|-[0-9]{3})?$")

_TRACKING_PARAM_RE = re.compile(r"(?:^|[?&])(?:utm_[a-z]+|_ga|_gl)=", re.IGNORECASE)

_DEV_HOSTS_RE = re.compile(
    r"^(localhost|127\.\d+\.\d+\.\d+|0\.0\.0\.0|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|\[?::1\]?)$"
    r"|\.(local|internal|test)$",
    re.IGNORECASE,
)

# Approximate SERP pixel widths per character (Arial-ish). Wide/narrow buckets
# keep the estimate honest without shipping a font metrics table.
_WIDE_CHARS = set("mwMW@")
_NARROW_CHARS = set("iljftI.,;:!'|()[] ")
_TITLE_AVG_PX = 9.0    # title font ~18px in SERPs (60 chars ~= 540px < 561px limit)
_DESC_AVG_PX = 6.3     # description font ~13px (155 chars ~= 977px < 985px limit)


# =============================================================================
# TEXT / URL HELPERS
# =============================================================================

def estimate_pixel_width(text: str, font: str = "title") -> int:
    """Approximate SERP rendering width of ``text`` in pixels."""
    avg = _TITLE_AVG_PX if font == "title" else _DESC_AVG_PX
    width = 0.0
    for ch in text:
        if ch in _WIDE_CHARS:
            width += avg * 1.45
        elif ch in _NARROW_CHARS:
            width += avg * 0.55
        else:
            width += avg
    return int(round(width))


def _count_syllables(word: str) -> int:
    word = word.lower().strip(".,;:!?\"'()[]")
    if not word:
        return 0
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def flesch_reading_ease(text: str) -> Optional[float]:
    """Flesch reading-ease score; None when there is too little text to score."""
    words = re.findall(r"[A-Za-z']+", text)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    if len(words) < 40 or not sentences:
        return None
    syllables = sum(_count_syllables(w) for w in words)
    score = 206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (syllables / len(words))
    return round(score, 1)


def normalize_url(url: str, base: str = "") -> str:
    """Resolve and normalize a URL: absolute, no fragment, no default port."""
    if base:
        url = urljoin(base, url)
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.port and not (
        (parsed.scheme == "http" and parsed.port == 80)
        or (parsed.scheme == "https" and parsed.port == 443)
    ):
        host = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    return urlunparse((parsed.scheme.lower(), host, path, "", parsed.query, ""))


def _host_key(url: str) -> str:
    """Host normalized for internal/external comparison (www. stripped)."""
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_internal(url: str, root: str) -> bool:
    """True when ``url`` belongs to the same site as ``root`` (www-insensitive)."""
    return bool(_host_key(url)) and _host_key(url) == _host_key(root)


def _visible_text(soup: BeautifulSoup) -> str:
    body = soup.find("body") or soup
    for tag in body.find_all(["script", "style", "noscript", "template"]):
        tag.decompose()
    return " ".join(body.get_text(" ").split())


# =============================================================================
# PER-PAGE ANALYSIS
# =============================================================================

class PageFindings:
    """Mutable per-page analysis result consumed by the site-level pass."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.audit: Optional[SeoPageAudit] = None
        self.issues: List[SeoIssueInstance] = []
        self.internal_hrefs: List[str] = []
        self.external_hrefs: List[str] = []
        self.image_urls: List[str] = []
        self.title: str = ""
        self.meta_description: str = ""
        self.first_h1: str = ""
        self.first_h2: str = ""
        self.indexable_html: bool = False
        self.has_favicon_link: bool = False
        self.has_feed_link: bool = False
        self.structured_data_types: List[str] = []
        self.hreflang_targets: List[str] = []


def analyze_page(
    url: str,
    html: str,
    status_code: int = 200,
    headers: Optional[Dict[str, str]] = None,
    *,
    depth: int = 0,
    final_url: str = "",
    fetch_ms: int = 0,
) -> PageFindings:
    """Run every page-scoped check against one HTML document (no network).

    Returns a PageFindings carrying the SeoPageAudit snapshot, fired issue
    instances and the raw facts needed by the site-level checks.
    """
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    findings = PageFindings(url)
    final_url = final_url or url
    issues = findings.issues

    def fire(code: str, detail: str = "", **evidence: Any) -> None:
        issues.append(SeoIssueInstance(
            check_code=code, url=url, detail=detail, evidence=evidence,
        ))

    # ---- URL structure checks (apply regardless of response body) ----------
    parsed = urlparse(url)
    path = parsed.path or "/"
    if "_" in path:
        fire("url_underscores", f"Path contains underscores: {path}")
    if any(c.isupper() for c in path):
        fire("url_uppercase", f"Path contains uppercase characters: {path}")
    if parsed.query:
        fire("url_parameters", f"URL contains query parameters: ?{parsed.query}")
    if _TRACKING_PARAM_RE.search("?" + parsed.query):
        fire("url_ga_tracking_params", "URL contains GA tracking parameters")
    if "//" in path:
        fire("url_multiple_slashes", f"Path contains multiple slashes: {path}")
    if len(url) > catalog.URL_MAX_CHARS:
        fire("url_over_115_chars", f"URL is {len(url)} characters")
    segments = [s for s in path.split("/") if s]
    repeated = {s for s in segments if segments.count(s) > 1}
    if repeated:
        fire("url_repetitive_path", f"Repeated path segments: {sorted(repeated)}")
    if any(ord(c) > 127 for c in url):
        fire("url_non_ascii", "URL contains non-ASCII characters")
    if " " in url or "%20" in path:
        fire("url_contains_space", "URL contains spaces")
    if parsed.scheme == "http":
        fire("security_http_url", "Page served over plain HTTP")

    # ---- Response-level checks ---------------------------------------------
    if 300 <= status_code < 400:
        fire("response_internal_3xx", f"URL responded {status_code}")
    elif 400 <= status_code < 500:
        fire("response_internal_4xx", f"URL responded {status_code}")
    elif status_code >= 500:
        fire("response_internal_5xx", f"URL responded {status_code}")

    if fetch_ms > catalog.SLOW_RESPONSE_MS:
        fire("performance_slow_response", f"Response took {fetch_ms / 1000:.1f}s")

    x_robots = headers.get("x-robots-tag", "").lower()
    content_type = headers.get("content-type", "")
    is_html = "html" in content_type or (bool(html.strip()) and content_type == "")

    # On-page checks only run against successfully served HTML documents -
    # error/redirect bodies would fire misleading content findings.
    if not html or not is_html or status_code != 200:
        findings.audit = SeoPageAudit(
            url=url, final_url=final_url, status_code=status_code,
            redirected=final_url != url, content_type=content_type,
            html_bytes=len(html.encode("utf-8", "ignore")) if html else 0,
            fetch_ms=fetch_ms, depth=depth,
            issue_codes=sorted({i.check_code for i in issues}),
        )
        return findings

    html_bytes = len(html.encode("utf-8", "ignore"))
    if html_bytes > catalog.HTML_MAX_BYTES:
        fire("validation_html_over_2mb", f"HTML document is {html_bytes / 1024 / 1024:.1f}MB")

    if not re.match(r"\s*<!doctype\s+html", html[:512], re.IGNORECASE):
        fire("validation_missing_doctype", "No <!DOCTYPE html> declaration")

    # Invalid <head> elements must be detected on the raw markup: HTML parsers
    # repair the tree (moving offenders into <body>), which hides the issue.
    head_match = re.search(r"<head[^>]*>(.*?)</head>", html, re.IGNORECASE | re.DOTALL)
    if head_match:
        raw_head = re.sub(
            r"<(script|style|noscript|template)[^>]*>.*?</\1>", "",
            head_match.group(1), flags=re.IGNORECASE | re.DOTALL,
        )
        bad = sorted({
            m.group(1).lower()
            for m in re.finditer(r"<([a-zA-Z][a-zA-Z0-9]*)\b", raw_head)
            if m.group(1).lower() not in _VALID_HEAD_ELEMENTS
        })
        if bad:
            fire("validation_invalid_head_elements",
                 f"Invalid elements in <head>: {', '.join(bad)}", elements=bad)

    soup = BeautifulSoup(html, "lxml")

    # ---- <head> metadata ----------------------------------------------------
    titles = soup.find_all("title")
    title = (titles[0].get_text() if titles else "").strip()
    findings.title = title
    if not title:
        fire("title_missing", "Page has no (or an empty) <title>")
    else:
        if len(titles) > 1:
            fire("title_multiple", f"Page has {len(titles)} <title> elements")
        if len(title) > catalog.TITLE_MAX_CHARS:
            fire("title_over_60", f"Title is {len(title)} characters: {title[:80]!r}")
        elif len(title) < catalog.TITLE_MIN_CHARS:
            fire("title_below_30", f"Title is only {len(title)} characters")
        px = estimate_pixel_width(title, "title")
        if px > catalog.TITLE_MAX_PIXELS:
            fire("title_over_561px", f"Title is ~{px}px wide")
        elif px < catalog.TITLE_MIN_PIXELS:
            fire("title_below_200px", f"Title is only ~{px}px wide")

    descs = [
        m for m in soup.find_all("meta", attrs={"name": re.compile("^description$", re.I)})
    ]
    desc = (descs[0].get("content") or "").strip() if descs else ""
    findings.meta_description = desc
    if not desc:
        fire("meta_desc_missing", "Page has no (or an empty) meta description")
    else:
        if len(descs) > 1:
            fire("meta_desc_multiple", f"Page has {len(descs)} meta description elements")
        if len(desc) > catalog.META_DESC_MAX_CHARS:
            fire("meta_desc_over_155", f"Meta description is {len(desc)} characters")
        elif len(desc) < catalog.META_DESC_MIN_CHARS:
            fire("meta_desc_below_70", f"Meta description is only {len(desc)} characters")
        px = estimate_pixel_width(desc, "desc")
        if px > catalog.META_DESC_MAX_PIXELS:
            fire("meta_desc_over_985px", f"Meta description is ~{px}px wide")
        elif px < catalog.META_DESC_MIN_PIXELS:
            fire("meta_desc_below_400px", f"Meta description is only ~{px}px wide")

    # robots directives (meta + X-Robots-Tag header)
    robots_meta = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    robots_content = ((robots_meta.get("content") or "") if robots_meta else "").lower()
    directives = [d.strip() for d in (robots_content + "," + x_robots).split(",") if d.strip()]
    if "noindex" in directives:
        fire("directive_noindex", "Page carries a noindex directive")
    if "nofollow" in directives:
        fire("directive_nofollow", "Page carries a nofollow directive")
    if soup.find("meta", attrs={"http-equiv": re.compile("^refresh$", re.I)}):
        fire("directive_meta_refresh", "Page uses a meta refresh redirect")

    # charset / viewport / lang
    has_charset = bool(
        soup.find("meta", charset=True)
        or soup.find("meta", attrs={"http-equiv": re.compile("^content-type$", re.I)})
        or "charset" in content_type
    )
    if not has_charset:
        fire("validation_missing_charset", "No character encoding declared")
    viewport = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
    if not viewport:
        fire("validation_missing_viewport", "No viewport meta tag")
    html_tag = soup.find("html")
    lang = (html_tag.get("lang") or "").strip() if html_tag else ""
    if not lang:
        fire("validation_missing_lang", "<html> element has no lang attribute")

    # ---- canonicals ----------------------------------------------------------
    canonicals = soup.find_all("link", rel=lambda v: v and "canonical" in v)
    canonical_hrefs = [(c.get("href") or "").strip() for c in canonicals if c.get("href")]
    canonical = canonical_hrefs[0] if canonical_hrefs else ""
    if not canonical_hrefs:
        fire("canonical_missing", "Page declares no canonical URL")
    else:
        distinct = {normalize_url(h, final_url) for h in canonical_hrefs}
        if len(distinct) > 1:
            fire("canonical_multiple_conflicting",
                 f"{len(canonical_hrefs)} conflicting canonicals", canonicals=canonical_hrefs)
        if not canonical.startswith(("http://", "https://")):
            fire("canonical_relative", f"Canonical is relative: {canonical}")
        if normalize_url(canonical, final_url) != normalize_url(final_url):
            fire("canonical_canonicalised",
                 f"Canonical points elsewhere: {canonical}", canonical=canonical)

    # ---- hreflang ------------------------------------------------------------
    hreflangs = soup.find_all("link", rel=lambda v: v and "alternate" in v, hreflang=True)
    if hreflangs:
        values = [(h.get("hreflang") or "").strip() for h in hreflangs]
        hrefs = {normalize_url(h.get("href") or "", final_url) for h in hreflangs}
        findings.hreflang_targets = sorted(hrefs)
        invalid = [v for v in values if v.lower() != "x-default" and not _HREFLANG_RE.match(v)]
        if invalid:
            fire("hreflang_invalid_codes", f"Invalid hreflang values: {invalid}")
        if normalize_url(final_url) not in hrefs:
            fire("hreflang_missing_self_reference", "No self-referencing hreflang annotation")
        if not any(v.lower() == "x-default" for v in values):
            fire("hreflang_missing_x_default", "No x-default hreflang annotation")

    # ---- headings ------------------------------------------------------------
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    levels = [int(h.name[1]) for h in headings]
    h1s = [h.get_text(" ").strip() for h in soup.find_all("h1")]
    h1s = [h for h in h1s if h]
    h2s = [h.get_text(" ").strip() for h in soup.find_all("h2")]
    h2s = [h for h in h2s if h]
    findings.first_h1 = h1s[0] if h1s else ""
    findings.first_h2 = h2s[0] if h2s else ""

    if not h1s:
        fire("h1_missing", "Page has no (or an empty) <h1>")
    else:
        if len(h1s) > 1:
            fire("h1_multiple", f"Page has {len(h1s)} <h1> elements")
        long_h1 = [h for h in h1s if len(h) > catalog.HEADING_MAX_CHARS]
        if long_h1:
            fire("h1_over_70", f"<h1> is {len(long_h1[0])} characters")
        if levels and levels[0] != 1:
            fire("h1_non_sequential", f"First heading on the page is an <h{levels[0]}>")
        if title and h1s[0].strip().lower() == title.strip().lower():
            fire("title_same_as_h1", "Title and <h1> are identical")
    if not h2s:
        fire("h2_missing", "Page has no (or an empty) <h2>")
    else:
        if len(h2s) > 1:
            fire("h2_multiple", f"Page has {len(h2s)} <h2> elements")
        long_h2 = [h for h in h2s if len(h) > catalog.HEADING_MAX_CHARS]
        if long_h2:
            fire("h2_over_70", f"{len(long_h2)} <h2>(s) over {catalog.HEADING_MAX_CHARS} characters")
        if 1 in levels and 2 in levels:
            i1, i2 = levels.index(1), levels.index(2)
            between = levels[i1 + 1:i2] if i2 > i1 else []
            if i2 < i1 or any(level > 2 for level in between):
                fire("h2_non_sequential", "First <h2> is not the second heading level after the <h1>")
        elif 2 in levels and 1 not in levels:
            fire("h2_non_sequential", "Page has <h2>s but no <h1> before them")

    # heading anchors (GEO: citable fragments)
    sub_headings = soup.find_all(["h2", "h3"])
    if sub_headings and not any(h.get("id") for h in sub_headings):
        fire("geo_missing_heading_anchors",
             f"None of the {len(sub_headings)} h2/h3 headings have id attributes")

    # ---- content -------------------------------------------------------------
    text = _visible_text(BeautifulSoup(html, "lxml"))
    words = re.findall(r"[A-Za-z']+", text)
    word_count = len(words)
    if word_count < catalog.LOW_CONTENT_WORDS:
        fire("content_low_word_count", f"Page has only {word_count} words")
    flesch = flesch_reading_ease(text)
    if flesch is not None:
        if flesch < catalog.FLESCH_VERY_DIFFICULT:
            fire("content_readability_very_difficult", f"Flesch reading ease is {flesch}")
        elif flesch < catalog.FLESCH_DIFFICULT:
            fire("content_readability_difficult", f"Flesch reading ease is {flesch}")
    if "lorem ipsum" in text.lower():
        fire("content_placeholder_text", "Page contains 'lorem ipsum' placeholder text")
    long_paras = [
        p for p in soup.find_all("p")
        if len(re.findall(r"[A-Za-z']+", p.get_text(" "))) > catalog.LONG_PARAGRAPH_WORDS
    ]
    if long_paras:
        fire("content_long_paragraphs",
             f"{len(long_paras)} paragraph(s) over {catalog.LONG_PARAGRAPH_WORDS} words")

    # ---- images ----------------------------------------------------------------
    imgs = soup.find_all("img")
    missing_alt_attr = [i for i in imgs if not i.has_attr("alt")]
    missing_alt_text = [i for i in imgs if i.has_attr("alt") and not (i.get("alt") or "").strip()]
    missing_size = [i for i in imgs if not (i.get("width") and i.get("height"))]
    if missing_alt_attr:
        fire("image_missing_alt_attribute",
             f"{len(missing_alt_attr)} image(s) with no alt attribute",
             srcs=[i.get("src", "")[:200] for i in missing_alt_attr[:10]])
    if missing_alt_text:
        fire("image_missing_alt_text",
             f"{len(missing_alt_text)} image(s) with empty alt text",
             srcs=[i.get("src", "")[:200] for i in missing_alt_text[:10]])
    if imgs and missing_size:
        fire("image_missing_size_attributes",
             f"{len(missing_size)} image(s) without width/height attributes")
    # Lazy-loading gap analysis (everything after the first/LCP image counts).
    not_lazy = [i for i in imgs[1:] if (i.get("loading") or "").lower() != "lazy"]
    if not_lazy:
        fire("image_not_lazy_loaded",
             f"{len(not_lazy)} of {len(imgs)} image(s) not lazy loaded")
    findings.image_urls = [
        normalize_url(i.get("src"), final_url) for i in imgs if i.get("src")
        and not str(i.get("src")).startswith("data:")
    ]

    # ---- links -----------------------------------------------------------------
    anchors = [a for a in soup.find_all("a", href=True)]
    internal: List[str] = []
    external: List[str] = []
    empty_anchor_count = 0
    unsafe_blank = 0
    localhost_links: List[str] = []
    for a in anchors:
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = normalize_url(href, final_url)
        if urlparse(absolute).scheme not in ("http", "https"):
            continue
        host = urlparse(absolute).hostname or ""
        # A link is a "leaked dev URL" only when it points at a dev host that
        # is NOT the site being audited (auditing a staging host is valid).
        if _DEV_HOSTS_RE.search(host) and _host_key(absolute) != _host_key(final_url):
            localhost_links.append(absolute)
            continue
        if is_internal(absolute, final_url):
            internal.append(absolute)
            anchor_text = a.get_text(" ").strip()
            img_alt = any((i.get("alt") or "").strip() for i in a.find_all("img"))
            if not anchor_text and not img_alt and not (a.get("aria-label") or "").strip():
                empty_anchor_count += 1
        else:
            external.append(absolute)
            target = a.get("target") or ""
            rel = " ".join(a.get("rel") or []) if isinstance(a.get("rel"), list) else (a.get("rel") or "")
            if target == "_blank" and "noopener" not in rel and "noreferrer" not in rel:
                unsafe_blank += 1
    findings.internal_hrefs = internal
    findings.external_hrefs = external
    if localhost_links:
        fire("links_localhost_or_dev",
             f"{len(localhost_links)} link(s) to development hosts",
             targets=localhost_links[:10])
    if not internal:
        fire("links_no_internal_outlinks", "Page links to no other internal pages")
    if empty_anchor_count:
        fire("links_no_anchor_text",
             f"{empty_anchor_count} internal link(s) without anchor text")
    if len(external) > catalog.HIGH_EXTERNAL_OUTLINKS:
        fire("links_high_external_outlinks", f"Page has {len(external)} external outlinks")
    if unsafe_blank:
        fire("security_unsafe_cross_origin_links",
             f"{unsafe_blank} target=\"_blank\" link(s) without rel=\"noopener\"")

    # ---- pagination -------------------------------------------------------------
    rel_links = soup.find_all("link", rel=lambda v: v and ("next" in v or "prev" in v))
    pagination_urls = {
        normalize_url(link.get("href"), final_url) for link in rel_links if link.get("href")
    }
    if pagination_urls:
        anchor_hrefs = {normalize_url(a.get("href"), final_url) for a in anchors if a.get("href")}
        missing_pg = pagination_urls - anchor_hrefs
        if missing_pg:
            fire("pagination_url_not_in_anchor",
                 "Pagination URL(s) not linked in an anchor tag",
                 targets=sorted(missing_pg))

    # ---- security: mixed content / protocol-relative / forms ---------------------
    resource_attrs: List[str] = []
    for tag, attr in (("img", "src"), ("script", "src"), ("link", "href"),
                      ("iframe", "src"), ("source", "src"), ("video", "src"),
                      ("audio", "src")):
        for el in soup.find_all(tag):
            val = (el.get(attr) or "").strip()
            if val:
                resource_attrs.append(val)
    if urlparse(final_url).scheme == "https":
        insecure = [r for r in resource_attrs if r.startswith("http://")]
        if insecure:
            fire("security_mixed_content",
                 f"{len(insecure)} resource(s) loaded over HTTP", resources=insecure[:10])
    protocol_relative = [r for r in resource_attrs if r.startswith("//")]
    if protocol_relative:
        fire("security_protocol_relative_resources",
             f"{len(protocol_relative)} protocol-relative resource link(s)")
    insecure_forms = [
        f for f in soup.find_all("form") if (f.get("action") or "").startswith("http://")
    ]
    if insecure_forms:
        fire("security_form_posts_to_http",
             f"{len(insecure_forms)} form(s) posting to HTTP endpoints")

    # ---- structured data / AIO ----------------------------------------------------
    sd_types: List[str] = []
    invalid_jsonld = 0
    for script in soup.find_all("script", type=re.compile("application/ld\\+json", re.I)):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            invalid_jsonld += 1
            continue
        nodes: List[Any] = data if isinstance(data, list) else [data]
        for node in list(nodes):
            if isinstance(node, dict) and "@graph" in node and isinstance(node["@graph"], list):
                nodes.extend(node["@graph"])
        for node in nodes:
            if isinstance(node, dict):
                t = node.get("@type")
                if isinstance(t, str):
                    sd_types.append(t)
                elif isinstance(t, list):
                    sd_types.extend(str(x) for x in t)
    findings.structured_data_types = sd_types
    if invalid_jsonld:
        fire("aio_invalid_json_ld", f"{invalid_jsonld} JSON-LD block(s) failed to parse")
    if not sd_types and not invalid_jsonld:
        fire("aio_no_structured_data", "Page carries no JSON-LD structured data")

    sd_lower = {t.lower() for t in sd_types}
    if "breadcrumblist" not in sd_lower:
        fire("aio_missing_breadcrumb_schema", "No BreadcrumbList schema on the page")

    question_headings = [
        h for h in (h1s + h2s + [x.get_text(" ").strip() for x in soup.find_all("h3")])
        if h and (h.rstrip().endswith("?")
                  or h.split(" ", 1)[0].lower() in _QUESTION_PREFIXES)
    ]
    if len(question_headings) >= 3 and not ({"faqpage", "qapage"} & sd_lower):
        fire("aio_faq_content_without_schema",
             f"{len(question_headings)} question-style headings but no FAQPage schema")

    article_like = bool(soup.find("article")) or bool(
        {"article", "blogposting", "newsarticle"} & sd_lower
    )
    if article_like:
        has_dates = bool(
            soup.find("meta", attrs={"property": "article:published_time"})
            or re.search(r'"datePublished"\s*:', html)
        )
        if not has_dates:
            fire("aio_missing_article_dates", "Article page without datePublished metadata")
        has_author = bool(
            re.search(r'"author"\s*:', html)
            or soup.find("meta", attrs={"name": re.compile("^author$", re.I)})
            or soup.find("a", rel=lambda v: v and "author" in v)
        )
        if not has_author:
            fire("aio_missing_author_markup", "Article page without author markup")

    # ---- social sharing --------------------------------------------------------------
    og = {
        (m.get("property") or "").lower(): (m.get("content") or "").strip()
        for m in soup.find_all("meta", property=re.compile("^og:", re.I))
    }
    if not og:
        fire("social_missing_open_graph", "Page has no Open Graph tags")
    elif not all(og.get(k) for k in ("og:title", "og:description", "og:image")):
        missing = [k for k in ("og:title", "og:description", "og:image") if not og.get(k)]
        fire("social_incomplete_open_graph", f"Missing Open Graph tags: {', '.join(missing)}")
    if not soup.find("meta", attrs={"name": re.compile("^twitter:card$", re.I)}):
        fire("social_missing_twitter_card", "Page has no twitter:card meta tag")

    # ---- GEO: semantic structure -------------------------------------------------------
    if not soup.find(["main", "article", "nav", "header", "footer", "section"]):
        fire("geo_no_semantic_landmarks", "Page uses no semantic HTML5 landmark elements")

    # ---- site-fact extraction (favicon, feeds) -----------------------------------------
    findings.has_favicon_link = bool(
        soup.find("link", rel=lambda v: v and any("icon" in r for r in (
            v if isinstance(v, list) else [v]
        )))
    )
    findings.has_feed_link = bool(
        soup.find("link", rel=lambda v: v and "alternate" in v,
                  type=re.compile("application/(rss|atom)\\+xml", re.I))
    )

    findings.indexable_html = (
        status_code == 200 and "noindex" not in directives
    )
    findings.audit = SeoPageAudit(
        url=url,
        final_url=final_url,
        status_code=status_code,
        redirected=normalize_url(final_url) != normalize_url(url),
        content_type=content_type,
        html_bytes=html_bytes,
        fetch_ms=fetch_ms,
        depth=depth,
        title=title,
        meta_description=desc,
        canonical=canonical,
        lang=lang,
        robots_directives=directives,
        h1s=h1s,
        h2s=h2s[:20],
        word_count=word_count,
        flesch_reading_ease=flesch,
        internal_links=len(internal),
        external_links=len(external),
        images_total=len(imgs),
        structured_data_types=sd_types,
        has_open_graph=bool(og),
        has_twitter_card=bool(
            soup.find("meta", attrs={"name": re.compile("^twitter:card$", re.I)})
        ),
        has_viewport=bool(viewport),
        issue_codes=sorted({i.check_code for i in issues}),
    )
    return findings


# =============================================================================
# AUDIT ENGINE
# =============================================================================

class SeoAuditEngine:
    """Crawls a site and produces a complete SeoAuditReport."""

    def __init__(
        self,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        fetcher: Optional[PageFetcher] = None,
    ) -> None:
        # ``transport`` lets tests inject httpx.MockTransport - no network needed.
        # ``fetcher`` lets tests/callers inject a custom (e.g. browser) backend.
        self._transport = transport
        self._fetcher = fetcher

    def _build_fetcher(self, request: SeoAuditRequest) -> PageFetcher:
        """Pick the fetch backend for this run (http / browser / auto)."""
        if self._fetcher is not None:
            return self._fetcher
        return make_fetcher(
            fetch_mode=request.fetch_mode,
            timeout=request.timeout_seconds,
            user_agent=USER_AGENT,
            transport=self._transport,
            concurrency=CRAWL_CONCURRENCY,
        )

    async def run(
        self,
        request: SeoAuditRequest,
        company_id: Optional[str] = None,
        audit_id: Optional[str] = None,
    ) -> SeoAuditReport:
        """Execute the full audit: crawl, page checks, site checks, scoring."""
        audit_id = audit_id or f"seoaudit_{secrets.token_hex(8)}"
        started = datetime.now(timezone.utc)
        root = normalize_url(request.website_url)

        if self._transport is None and self._fetcher is None and not _is_safe_url(root):
            return SeoAuditReport(
                audit_id=audit_id, company_id=company_id, website_url=root,
                status="failed", error="URL failed safety validation (private/loopback hosts are not allowed)",
                started_at=started, completed_at=datetime.now(timezone.utc),
            )

        fetcher = self._build_fetcher(request)
        try:
            return await self._run_with_client(fetcher, request, audit_id, company_id, started, root)
        except Exception:  # noqa: BLE001 - audit must fail closed, not raise
            # Full details go to server logs only; the report payload is
            # client-visible and must not leak internal runtime details.
            log.exception("SEO audit %s failed", audit_id)
            return SeoAuditReport(
                audit_id=audit_id, company_id=company_id, website_url=root,
                status="failed", error="Audit execution failed - see server logs",
                started_at=started, completed_at=datetime.now(timezone.utc),
            )
        finally:
            try:
                await fetcher.aclose()
            except Exception as exc:  # noqa: BLE001 - teardown best-effort
                log.warning("SEO audit %s fetcher teardown error: %s", audit_id, exc)

    # ------------------------------------------------------------------
    # crawl + analysis
    # ------------------------------------------------------------------

    async def _run_with_client(
        self,
        fetcher: PageFetcher,
        request: SeoAuditRequest,
        audit_id: str,
        company_id: Optional[str],
        started: datetime,
        root: str,
    ) -> SeoAuditReport:
        base = f"{urlparse(root).scheme}://{urlparse(root).netloc}"

        # ---- site discovery files -------------------------------------------------
        robots_txt, robots_status = await fetcher.get_text(f"{base}/robots.txt")
        robots_present = robots_status == 200 and bool(robots_txt.strip())
        robot_parser = urllib.robotparser.RobotFileParser()
        sitemap_urls_declared: List[str] = []
        ai_blocked: List[str] = []
        if robots_present:
            robot_parser.parse(robots_txt.splitlines())
            sitemap_urls_declared = [
                line.split(":", 1)[1].strip()
                for line in robots_txt.splitlines()
                if line.lower().startswith("sitemap:")
            ]
            for agent in catalog.AI_CRAWLER_USER_AGENTS:
                if not robot_parser.can_fetch(agent, base + "/"):
                    ai_blocked.append(agent)
        else:
            robot_parser.parse([])  # everything allowed

        sitemap_candidates = sitemap_urls_declared or [
            f"{base}/sitemap.xml", f"{base}/sitemap_index.xml"
        ]
        sitemap_present, sitemap_found_urls, sitemap_page_urls = await self._discover_sitemaps(
            fetcher, sitemap_candidates, root
        )

        llms_txt, llms_status = await fetcher.get_text(f"{base}/llms.txt")
        llms_present = llms_status == 200 and bool(llms_txt.strip()) and "<html" not in llms_txt[:500].lower()

        # ---- BFS crawl -------------------------------------------------------------
        queue: "OrderedDict[str, int]" = OrderedDict()
        queue[root] = 0
        if request.include_sitemap:
            for u in sitemap_page_urls[: request.max_pages * 2]:
                queue.setdefault(u, 1)

        visited: Set[str] = set()
        blocked_by_robots: List[str] = []
        pages: List[PageFindings] = []
        redirect_map: Dict[str, str] = {}      # requested -> final
        status_map: Dict[str, int] = {}
        pages_failed = 0
        root_headers: Dict[str, str] = {}
        semaphore = asyncio.Semaphore(CRAWL_CONCURRENCY)

        async def fetch_page(url: str, depth: int) -> Optional[PageFindings]:
            nonlocal pages_failed, root_headers
            async with semaphore:
                try:
                    result = await fetcher.get(url)
                except Exception as exc:  # noqa: BLE001 - record and continue crawling
                    pages_failed += 1
                    log.debug("Fetch failed for %s: %s", url, exc)
                    return None
            final = normalize_url(result.final_url)
            redirect_map[url] = final
            # The status the *requested* URL answered with (pre-redirect).
            first_status = result.first_status
            status_map[url] = first_status
            status_map[final] = result.status_code
            headers = dict(result.headers)  # already lower-cased by the fetcher
            if url == root:
                root_headers = dict(headers)
            body = result.text  # fetcher blanks non-HTML bodies
            redirected = final != url

            redirect_issue = SeoIssueInstance(
                check_code="response_internal_3xx", url=url,
                detail=f"URL responded {first_status} and redirects to {final}",
                evidence={"final_url": final},
            )
            if redirected and (final in visited or not is_internal(final, root)):
                # Final destination already crawled (or off-site): record only
                # the redirect against the requested URL.
                slim = PageFindings(url)
                slim.issues.append(redirect_issue)
                return slim
            analysis_url = final if redirected else url
            if redirected:
                visited.add(final)
            findings = analyze_page(
                analysis_url, body, status_code=result.status_code,
                headers=headers, depth=depth, final_url=final, fetch_ms=result.elapsed_ms,
            )
            if redirected:
                findings.issues.append(redirect_issue)
            return findings

        while queue and len(visited) < request.max_pages:
            batch: List[Tuple[str, int]] = []
            while queue and len(batch) + len(visited) < request.max_pages:
                url, depth = queue.popitem(last=False)
                if url in visited or depth > request.max_depth:
                    continue
                if request.respect_robots and robots_present and not robot_parser.can_fetch(
                    USER_AGENT, url
                ):
                    blocked_by_robots.append(url)
                    visited.add(url)
                    continue
                visited.add(url)
                batch.append((url, depth))
            if not batch:
                break
            results = await asyncio.gather(*(fetch_page(u, d) for u, d in batch))
            for (url, depth), findings in zip(batch, results):
                if findings is None:
                    continue
                pages.append(findings)
                if depth < request.max_depth:
                    for link in findings.internal_hrefs:
                        if link not in visited and link not in queue:
                            queue[link] = depth + 1

        # ---- site-level facts --------------------------------------------------------
        favicon_present = any(p.has_favicon_link for p in pages)
        if not favicon_present:
            _, fav_status = await fetcher.head(f"{base}/favicon.ico")
            favicon_present = fav_status == 200
        rss_present = any(p.has_feed_link for p in pages)
        if not rss_present:
            for feed_path in ("/feed", "/rss.xml", "/atom.xml", "/feed.xml"):
                _, st = await fetcher.head(base + feed_path)
                if st == 200:
                    rss_present = True
                    break

        site = SeoSiteFindings(
            https=urlparse(root).scheme == "https",
            robots_txt_present=robots_present,
            robots_txt_url=f"{base}/robots.txt" if robots_present else "",
            sitemap_present=sitemap_present,
            sitemap_urls=sitemap_found_urls,
            sitemap_in_robots=bool(sitemap_urls_declared),
            llms_txt_present=llms_present,
            rss_feed_present=rss_present,
            favicon_present=favicon_present,
            ai_crawlers_blocked=ai_blocked,
            security_headers={
                "strict-transport-security": "strict-transport-security" in root_headers,
                "content-security-policy": "content-security-policy" in root_headers,
                "x-content-type-options": "x-content-type-options" in root_headers,
                "x-frame-options": (
                    "x-frame-options" in root_headers
                    or "frame-ancestors" in root_headers.get("content-security-policy", "")
                ),
                "referrer-policy": "referrer-policy" in root_headers,
            },
        )

        issues: List[SeoIssueInstance] = [i for p in pages for i in p.issues]
        issues.extend(self._site_checks(root, pages, site, root_headers, blocked_by_robots,
                                        redirect_map, status_map))

        # bounded image-weight checks
        if request.check_image_sizes:
            issues.extend(await self._check_image_weights(fetcher, pages, root))
        if request.check_external_links:
            issues.extend(await self._check_external_links(fetcher, pages))

        # ---- aggregate ----------------------------------------------------------------
        return self._build_report(
            audit_id, company_id, root, started, request, pages, pages_failed,
            len(visited) + len(queue), issues, site,
        )

    # ------------------------------------------------------------------
    # site-level checks
    # ------------------------------------------------------------------

    def _site_checks(
        self,
        root: str,
        pages: List[PageFindings],
        site: SeoSiteFindings,
        root_headers: Dict[str, str],
        blocked_by_robots: List[str],
        redirect_map: Dict[str, str],
        status_map: Dict[str, int],
    ) -> List[SeoIssueInstance]:
        issues: List[SeoIssueInstance] = []

        def fire(code: str, url: str, detail: str = "", **evidence: Any) -> None:
            issues.append(SeoIssueInstance(check_code=code, url=url, detail=detail, evidence=evidence))

        # duplicates across indexable pages
        indexable = [p for p in pages if p.indexable_html]

        def _dupes(values: Iterable[Tuple[str, str]], code: str, label: str) -> None:
            groups: Dict[str, List[str]] = {}
            for url, value in values:
                if value:
                    groups.setdefault(value.strip().lower(), []).append(url)
            for value, urls in groups.items():
                if len(urls) > 1:
                    for u in urls:
                        fire(code, u, f"{label} shared by {len(urls)} pages: {value[:90]!r}",
                             shared_with=[x for x in urls if x != u][:5])

        _dupes(((p.url, p.title) for p in indexable), "title_duplicate", "Title")
        _dupes(((p.url, p.meta_description) for p in indexable),
               "meta_desc_duplicate", "Meta description")
        _dupes(((p.url, p.first_h1) for p in indexable), "h1_duplicate", "H1")
        _dupes(((p.url, p.first_h2) for p in indexable), "h2_duplicate", "H2")

        # internal links pointing at robots-blocked / redirecting / broken URLs
        crawled_status = dict(status_map)
        blocked_set = set(blocked_by_robots)
        for p in pages:
            broken = sorted({
                t for t in p.internal_hrefs
                if 400 <= crawled_status.get(t, 0) < 600
            })
            if broken:
                fire("links_broken_internal", p.url,
                     f"{len(broken)} internal link(s) to erroring URLs", targets=broken[:10])
            redirecting = sorted({
                t for t in p.internal_hrefs
                if t in redirect_map and redirect_map[t] != t
            })
            if redirecting:
                fire("links_internal_redirect", p.url,
                     f"{len(redirecting)} internal link(s) through redirects",
                     targets=redirecting[:10])
            blocked = sorted(set(p.internal_hrefs) & blocked_set)
            if blocked:
                fire("response_blocked_by_robots", p.url,
                     f"{len(blocked)} internal link(s) blocked by robots.txt",
                     targets=blocked[:10])

        # hreflang annotations pointing at crawled URLs that carry noindex
        noindexed = {
            p.url for p in pages
            if p.audit is not None and "noindex" in p.audit.robots_directives
        }
        if noindexed:
            for p in pages:
                bad_targets = sorted(set(p.hreflang_targets) & noindexed)
                if bad_targets:
                    fire("hreflang_noindex_return_links", p.url,
                         f"{len(bad_targets)} hreflang target(s) are noindexed",
                         targets=bad_targets[:10])

        # site-wide single-fire checks (reported against the root URL)
        if not site.robots_txt_present:
            fire("geo_missing_robots_txt", root, "No robots.txt found")
        if not site.sitemap_present:
            fire("geo_missing_sitemap", root, "No XML sitemap found")
        elif not site.sitemap_in_robots:
            fire("geo_sitemap_not_in_robots", root,
                 "Sitemap exists but is not declared in robots.txt")
        if not site.llms_txt_present:
            fire("geo_missing_llms_txt", root, "No llms.txt found")
        if site.ai_crawlers_blocked:
            fire("geo_ai_crawlers_blocked", root,
                 f"robots.txt blocks AI crawlers: {', '.join(site.ai_crawlers_blocked)}",
                 agents=site.ai_crawlers_blocked)
        if not site.rss_feed_present:
            fire("geo_missing_rss_feed", root, "No RSS/Atom feed discovered")
        if not site.favicon_present:
            fire("validation_missing_favicon", root, "No favicon discovered")

        if root_headers:
            hdr = site.security_headers
            if site.https and not hdr.get("strict-transport-security"):
                fire("security_missing_hsts", root, "Missing Strict-Transport-Security header")
            if not hdr.get("content-security-policy"):
                fire("security_missing_csp", root, "Missing Content-Security-Policy header")
            if not hdr.get("x-content-type-options"):
                fire("security_missing_x_content_type_options", root,
                     "Missing X-Content-Type-Options header")
            if not hdr.get("x-frame-options"):
                fire("security_missing_x_frame_options", root,
                     "Missing X-Frame-Options header (and no CSP frame-ancestors)")
            if not hdr.get("referrer-policy"):
                fire("security_missing_referrer_policy", root,
                     "Missing secure Referrer-Policy header")

        # missing organization schema anywhere on the site
        all_types = {t.lower() for p in pages for t in p.structured_data_types}
        if pages and not ({"organization", "website", "localbusiness", "corporation"} & all_types):
            fire("aio_missing_organization_schema", root,
                 "No Organization or WebSite schema found on any crawled page")

        return issues

    async def _check_image_weights(
        self,
        fetcher: PageFetcher,
        pages: List[PageFindings],
        root: str,
    ) -> List[SeoIssueInstance]:
        """HEAD a bounded set of internal images and flag heavyweight ones."""
        image_pages: Dict[str, List[str]] = {}
        for p in pages:
            for img in p.image_urls:
                if is_internal(img, root):
                    image_pages.setdefault(img, []).append(p.url)
        issues: List[SeoIssueInstance] = []
        for img_url in list(image_pages.keys())[:MAX_IMAGE_HEAD_REQUESTS]:
            headers, status = await fetcher.head(img_url)
            if status != 200:
                continue
            try:
                size = int(headers.get("content-length", "0"))
            except ValueError:
                continue
            if size > catalog.IMAGE_MAX_BYTES:
                for page_url in image_pages[img_url][:5]:
                    issues.append(SeoIssueInstance(
                        check_code="image_over_100kb",
                        url=page_url,
                        detail=f"Image {img_url} is {size / 1024:.0f} kB",
                        evidence={"image": img_url, "bytes": size},
                    ))
        return issues

    async def _check_external_links(
        self,
        fetcher: PageFetcher,
        pages: List[PageFindings],
    ) -> List[SeoIssueInstance]:
        """HEAD a bounded set of external link targets and flag dead ones."""
        link_pages: Dict[str, List[str]] = {}
        for p in pages:
            for href in p.external_hrefs:
                link_pages.setdefault(href, []).append(p.url)
        issues: List[SeoIssueInstance] = []
        for href in list(link_pages.keys())[:MAX_LINK_HEAD_REQUESTS]:
            _, status = await fetcher.head(href)
            if 400 <= status < 600:
                for page_url in sorted(set(link_pages[href]))[:5]:
                    issues.append(SeoIssueInstance(
                        check_code="links_broken_external",
                        url=page_url,
                        detail=f"External link {href} responded {status}",
                        evidence={"target": href, "status": status},
                    ))
        return issues

    # ------------------------------------------------------------------
    # report assembly
    # ------------------------------------------------------------------

    def _build_report(
        self,
        audit_id: str,
        company_id: Optional[str],
        root: str,
        started: datetime,
        request: SeoAuditRequest,
        pages: List[PageFindings],
        pages_failed: int,
        urls_discovered: int,
        issues: List[SeoIssueInstance],
        site: SeoSiteFindings,
    ) -> SeoAuditReport:
        total_pages = max(1, len(pages))

        by_check: Dict[str, List[SeoIssueInstance]] = {}
        for issue in issues:
            if issue.check_code in CHECKS:
                by_check.setdefault(issue.check_code, []).append(issue)

        rows: List[SeoIssueReportRow] = []
        for code, instances in by_check.items():
            check = CHECKS[code]
            urls = sorted({i.url for i in instances})
            rows.append(SeoIssueReportRow(
                check_code=code,
                issue_name=check.name,
                issue_type=check.issue_type,
                issue_priority=check.priority,
                urls_affected=len(urls),
                percent_of_total=round(len(urls) / total_pages * 100, 2),
                description=check.description,
                how_to_fix=check.how_to_fix,
                help_url=check.help_url,
                pillar=check.pillar,
                auto_fixable=check.auto_fixable,
                sample_urls=urls[:5],
            ))
        type_order = {"issue": 0, "warning": 1, "opportunity": 2}
        priority_order = {"high": 0, "medium": 1, "low": 2}
        rows.sort(key=lambda r: (
            priority_order[r.issue_priority], type_order[r.issue_type], -r.urls_affected,
        ))

        # Portfolio quantification: translate the measured issue pressure into
        # estimated monthly revenue at risk via a diminishing-returns curve, so
        # the dollar figure reflects what was actually found (see the model notes
        # at REVENUE_PRESSURE_SCALE). Only meaningful when a baseline is given.
        revenue = request.monthly_organic_revenue
        total_loss = 0.0
        loss_share = 0.0
        if revenue > 0 and rows:
            pressures, total_pressure = compute_pressure(rows, total_pages)
            loss_share = loss_share_from_pressure(total_pressure)
            total_loss = round(revenue * loss_share, 2)
            # Attribute the modeled loss across findings by their pressure share.
            rows = [
                row.model_copy(update={
                    "estimated_monthly_revenue_loss": (
                        round(total_loss * (p / total_pressure), 2)
                        if total_pressure > 0 else 0.0
                    ),
                })
                for row, p in zip(rows, pressures)
            ]

        health = self._score(rows, total_pages, pillar=None)
        pillar_scores = {
            pillar: self._score(rows, total_pages, pillar=pillar)
            for pillar in ("technical", "content", "security", "social", "geo", "aio")
        }
        by_priority: Dict[str, int] = {"high": 0, "medium": 0, "low": 0}
        by_type: Dict[str, int] = {"issue": 0, "warning": 0, "opportunity": 0}
        for row in rows:
            by_priority[row.issue_priority] += row.urls_affected
            by_type[row.issue_type] += row.urls_affected

        top = [r for r in rows if r.issue_priority == "high"][:5]
        summary_bits = [
            f"Crawled {len(pages)} page(s) of {root} - health score {health}/100.",
            f"{len(rows)} distinct finding types across {len(issues)} occurrences "
            f"({by_priority['high']} high, {by_priority['medium']} medium, "
            f"{by_priority['low']} low priority URL hits).",
        ]
        if top:
            summary_bits.append(
                "Top high-priority findings: " + "; ".join(
                    f"{r.issue_name} ({r.urls_affected} URLs)" for r in top
                ) + "."
            )
        fixable = sum(1 for r in rows if r.auto_fixable)
        if fixable:
            summary_bits.append(
                f"{fixable} finding type(s) are auto-fixable by the repo-aware SEO fixer."
            )
        if total_loss > 0:
            summary_bits.append(
                f"Estimated monthly organic revenue at risk: "
                f"{total_loss:,.0f} of {revenue:,.0f} "
                f"({total_loss / revenue * 100:.1f}% of baseline)."
            )

        return SeoAuditReport(
            audit_id=audit_id,
            company_id=company_id,
            website_url=root,
            status="success" if pages else "failed",
            error="" if pages else "No pages could be crawled",
            started_at=started,
            completed_at=datetime.now(timezone.utc),
            pages_crawled=len(pages),
            pages_failed=pages_failed,
            urls_discovered=urls_discovered,
            health_score=health,
            pillar_scores=pillar_scores,
            total_issues=len(issues),
            issues_by_priority=by_priority,
            issues_by_type=by_type,
            monthly_organic_revenue=revenue,
            estimated_monthly_revenue_loss=total_loss,
            rows=rows,
            issues=issues,
            pages=[p.audit for p in pages if p.audit is not None],
            site=site,
            delegation_plan=self._build_delegation_plan(rows),
            summary=" ".join(summary_bits),
        )

    # Which specialist family is best placed to execute fixes per category.
    _CATEGORY_SPECIALIST: Dict[str, str] = {
        "Security": "security",
        "Images": "frontend",
        "Performance": "platform",
        "Links": "frontend",
        "Page Titles": "seo",
        "Meta Description": "seo",
        "H1": "content",
        "H2": "content",
        "Content": "content",
        "Structured Data": "seo",
        "GEO": "seo",
        "Social": "marketing",
        "URL": "engineering",
        "Response Codes": "engineering",
        "Validation": "frontend",
        "Canonicals": "seo",
        "Directives": "seo",
        "Hreflang": "seo",
        "Pagination": "frontend",
    }

    @classmethod
    def _build_delegation_plan(
        cls, rows: List[SeoIssueReportRow]
    ) -> List[SeoDelegationTask]:
        """Group findings into agent-delegable work packages, one per category."""
        by_category: Dict[str, List[SeoIssueReportRow]] = {}
        for row in rows:
            check = CHECKS.get(row.check_code)
            if check:
                by_category.setdefault(check.category, []).append(row)

        priority_order = {"high": 0, "medium": 1, "low": 2}
        # WSJF component mappings (modified-Fibonacci scale, as in agents/portfolio.py).
        time_criticality_map = {"high": 8, "medium": 5, "low": 2}
        risk_reduction_map = {
            "security": 8, "technical": 5, "geo": 3, "aio": 3, "content": 2, "social": 2,
        }
        job_size_map = {"S": 2, "M": 5, "L": 8}

        # Relative share -> modified-Fibonacci business value bucket.
        def fib_bucket(share: float) -> int:
            for threshold, score in ((0.8, 20), (0.6, 13), (0.4, 8),
                                     (0.25, 5), (0.1, 3), (0.03, 2)):
                if share >= threshold:
                    return score
            return 1

        groups = list(by_category.items())
        group_value = {
            category: sum(r.estimated_monthly_revenue_loss for r in group)
            for category, group in groups
        }
        group_urls = {
            category: sum(r.urls_affected for r in group) for category, group in groups
        }
        # Business value is relative to the biggest package: by recoverable
        # revenue when a baseline was modeled, by URL volume otherwise.
        revenue_modeled = any(v > 0 for v in group_value.values())
        basis = group_value if revenue_modeled else {
            k: float(v) for k, v in group_urls.items()
        }
        max_basis = max(basis.values()) if basis else 0.0

        tasks: List[SeoDelegationTask] = []
        for category, group in groups:
            urls_total = group_urls[category]
            priority = min((r.issue_priority for r in group), key=lambda p: priority_order[p])
            effort = "S" if urls_total <= 3 else ("M" if urls_total <= 20 else "L")
            sample: List[str] = []
            for r in group:
                for u in r.sample_urls:
                    if u not in sample:
                        sample.append(u)
            instructions = "\n".join(
                f"- {r.issue_name} ({r.urls_affected} URLs): {r.how_to_fix}" for r in group
            )
            slug = re.sub(r"[^a-z0-9]+", "-", category.lower()).strip("-")
            pillar = group[0].pillar
            value = round(group_value[category], 2)
            business_value = fib_bucket(basis[category] / max_basis) if max_basis > 0 else 1
            time_criticality = time_criticality_map[priority]
            risk_reduction = risk_reduction_map.get(pillar, 1)
            job_size = job_size_map[effort]
            tasks.append(SeoDelegationTask(
                task_key=f"seo-fix-{slug}",
                title=(
                    f"Fix {category} findings: {len(group)} finding type(s) "
                    f"across {urls_total} URL hit(s)"
                ),
                priority=priority,
                effort=effort,  # type: ignore[arg-type]
                pillar=pillar,
                category=category,
                suggested_specialist=cls._CATEGORY_SPECIALIST.get(category, "seo"),
                check_codes=[r.check_code for r in group],
                urls_affected=urls_total,
                auto_fixable=all(r.auto_fixable for r in group),
                instructions=instructions,
                sample_urls=sample[:5],
                estimated_monthly_value=value,
                business_value=business_value,
                time_criticality=time_criticality,
                risk_reduction=risk_reduction,
                job_size=job_size,
                wsjf_score=round(
                    (business_value + time_criticality + risk_reduction) / job_size, 2
                ),
            ))
        # Portfolio order: WSJF first (higher schedules sooner), then priority.
        tasks.sort(key=lambda t: (-t.wsjf_score, priority_order[t.priority], -t.urls_affected))
        return tasks

    @staticmethod
    def _score(rows: List[SeoIssueReportRow], total_pages: int, pillar: Optional[str]) -> float:
        deduction = 0.0
        for row in rows:
            if pillar is not None and row.pillar != pillar:
                continue
            ratio = min(1.0, row.urls_affected / total_pages)
            deduction += (
                _PRIORITY_WEIGHT[row.issue_priority]
                * _TYPE_FACTOR[row.issue_type]
                * ratio
            )
        return round(max(0.0, 100.0 - deduction), 1)

    # ------------------------------------------------------------------
    # fetch helpers
    # ------------------------------------------------------------------

    async def _discover_sitemaps(
        self,
        fetcher: PageFetcher,
        candidates: List[str],
        root: str,
    ) -> Tuple[bool, List[str], List[str]]:
        """Fetch sitemap candidates (one index level deep) and collect page URLs."""
        found: List[str] = []
        page_urls: List[str] = []
        fetched = 0
        queue = list(candidates)
        while queue and fetched < MAX_SITEMAP_FETCHES:
            sm_url = queue.pop(0)
            fetched += 1
            text, status = await fetcher.get_text(sm_url)
            if status != 200 or "<" not in text:
                continue
            found.append(sm_url)
            locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)
            if "<sitemapindex" in text:
                queue.extend(locs[: MAX_SITEMAP_FETCHES - fetched])
            else:
                page_urls.extend(
                    normalize_url(u) for u in locs if is_internal(u, root)
                )
        return bool(found), found, page_urls


# =============================================================================
# EXPORTS
# =============================================================================

def report_to_csv(report: SeoAuditReport) -> str:
    """Render the report rows as a Screaming Frog-compatible CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
    writer.writerow([
        "Issue Name", "Issue Type", "Issue Priority", "URLs", "% of Total",
        "Description", "How To Fix", "Help URL",
    ])
    for row in report.rows:
        writer.writerow([
            row.issue_name,
            row.issue_type.capitalize(),
            row.issue_priority.capitalize(),
            row.urls_affected,
            f"{row.percent_of_total:.3f}",
            row.description,
            row.how_to_fix,
            row.help_url,
        ])
    return buf.getvalue()


def report_to_pages_csv(report: SeoAuditReport) -> str:
    """Per-URL inventory CSV - one row per crawled page (Screaming Frog
    'internal_all'-style export for heavy analysis in spreadsheets)."""
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
    writer.writerow([
        "URL", "Status Code", "Redirected", "Final URL", "Depth", "Fetch ms",
        "HTML Bytes", "Title", "Title Length", "Meta Description",
        "Meta Description Length", "H1", "H1 Count", "Word Count",
        "Flesch Reading Ease", "Canonical", "Lang", "Robots Directives",
        "Internal Links", "External Links", "Images", "Structured Data Types",
        "Open Graph", "Twitter Card", "Viewport", "Issue Count", "Issues",
    ])
    for p in report.pages:
        writer.writerow([
            p.url, p.status_code, "yes" if p.redirected else "no",
            p.final_url if p.redirected else "", p.depth, p.fetch_ms,
            p.html_bytes, p.title, len(p.title), p.meta_description,
            len(p.meta_description), p.h1s[0] if p.h1s else "", len(p.h1s),
            p.word_count,
            p.flesch_reading_ease if p.flesch_reading_ease is not None else "",
            p.canonical, p.lang, "; ".join(p.robots_directives),
            p.internal_links, p.external_links, p.images_total,
            "; ".join(p.structured_data_types),
            "yes" if p.has_open_graph else "no",
            "yes" if p.has_twitter_card else "no",
            "yes" if p.has_viewport else "no",
            len(p.issue_codes), "; ".join(p.issue_codes),
        ])
    return buf.getvalue()


def report_to_issues_csv(report: SeoAuditReport) -> str:
    """Every individual issue occurrence as CSV - one row per (check, URL)."""
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
    writer.writerow([
        "Issue Name", "Issue Type", "Issue Priority", "Pillar", "URL", "Detail",
    ])
    for issue in report.issues:
        check = CHECKS.get(issue.check_code)
        if check is None:
            continue
        writer.writerow([
            check.name, check.issue_type.capitalize(), check.priority.capitalize(),
            check.pillar, issue.url, issue.detail,
        ])
    return buf.getvalue()


def report_to_markdown(report: SeoAuditReport) -> str:
    """Render an executive Markdown report."""
    lines = [
        f"# SEO / GEO / AIO Audit - {report.website_url}",
        "",
        f"- **Audit ID:** `{report.audit_id}`",
        f"- **Status:** {report.status}",
        f"- **Pages crawled:** {report.pages_crawled} ({report.pages_failed} failed)",
        f"- **Health score:** **{report.health_score}/100**",
    ]
    if report.monthly_organic_revenue > 0:
        share = (
            report.estimated_monthly_revenue_loss / report.monthly_organic_revenue * 100
            if report.monthly_organic_revenue else 0.0
        )
        lines.append(
            f"- **Estimated monthly revenue at risk (model estimate):** "
            f"**{report.estimated_monthly_revenue_loss:,.0f}** "
            f"({share:.1f}% of the {report.monthly_organic_revenue:,.0f}/month "
            f"organic baseline you supplied)"
        )
        lines += [
            "",
            "> **How this figure is derived (read before quoting it):** This is a "
            "*model estimate*, not a measured loss. It is the supplied organic-revenue "
            "baseline multiplied by an at-risk share computed from the findings: each "
            "finding contributes severity x type x page-coverage 'pressure', and the "
            "aggregate is mapped through a diminishing-returns curve (cap 35%). It "
            "depends entirely on the baseline you provide and on crawl breadth - "
            "treat it as a prioritisation signal, not a guaranteed dollar amount.",
        ]
    lines += [
        "",
        "## Pillar Scores",
        "",
        "| Pillar | Score |",
        "|--------|-------|",
    ]
    for pillar, score in report.pillar_scores.items():
        lines.append(f"| {pillar.upper() if pillar in ('geo', 'aio') else pillar.title()} | {score}/100 |")
    revenue_modeled = report.monthly_organic_revenue > 0
    if revenue_modeled:
        lines += ["", "## Findings", "",
                  "| Priority | Type | Issue | URLs | % | $ at risk/mo | Auto-fixable |",
                  "|----------|------|-------|------|----|--------------|--------------|"]
    else:
        lines += ["", "## Findings", "",
                  "| Priority | Type | Issue | URLs | % | Auto-fixable |",
                  "|----------|------|-------|------|----|--------------|"]
    for row in report.rows:
        cells = (
            f"| {row.issue_priority.capitalize()} | {row.issue_type.capitalize()} "
            f"| {row.issue_name} | {row.urls_affected} | {row.percent_of_total:.1f}% "
        )
        if revenue_modeled:
            cells += f"| {row.estimated_monthly_revenue_loss:,.0f} "
        cells += f"| {'yes' if row.auto_fixable else ''} |"
        lines.append(cells)

    if report.delegation_plan:
        lines += ["", "## Delegation Plan (agent-ready work packages)", ""]
        for task in report.delegation_plan:
            lines += [
                f"### `{task.task_key}` - {task.title}",
                "",
                f"- **Priority:** {task.priority} | **Effort:** {task.effort} "
                f"| **Pillar:** {task.pillar} "
                f"| **Suggested specialist:** {task.suggested_specialist}"
                f"{' | **auto-fixable**' if task.auto_fixable else ''}",
                f"- **WSJF:** {task.wsjf_score} "
                f"(value {task.business_value} + urgency {task.time_criticality} "
                f"+ risk {task.risk_reduction}, size {task.job_size})"
                + (f" | **recoverable: {task.estimated_monthly_value:,.0f}/mo**"
                   if task.estimated_monthly_value > 0 else ""),
                "",
                task.instructions,
                "",
            ]

    # Per-page appendix: the worst pages with their full issue lists.
    worst = sorted(report.pages, key=lambda p: -len(p.issue_codes))[:50]
    if worst:
        lines += ["", "## Page Details (worst first)", ""]
        for p in worst:
            if not p.issue_codes:
                continue
            lines += [
                f"### {p.url}",
                "",
                f"- Status {p.status_code} | {p.word_count} words | "
                f"{p.internal_links} internal / {p.external_links} external links | "
                f"{p.images_total} images | title: {p.title[:80]!r}",
                f"- Issues ({len(p.issue_codes)}): "
                + ", ".join(f"`{c}`" for c in p.issue_codes),
                "",
            ]

    lines += ["", "## Summary", "", report.summary, ""]
    return "\n".join(lines)


# =============================================================================
# AUDIT REGISTRY (in-memory, capped)
# =============================================================================

_MAX_REPORTS = 50
_reports: "OrderedDict[str, SeoAuditReport]" = OrderedDict()
_reports_lock = threading.RLock()


def save_report(report: SeoAuditReport) -> None:
    """Store a report in the bounded in-memory registry."""
    with _reports_lock:
        _reports[report.audit_id] = report
        while len(_reports) > _MAX_REPORTS:
            _reports.popitem(last=False)


def get_report(audit_id: str) -> Optional[SeoAuditReport]:
    """Fetch a stored report by id."""
    with _reports_lock:
        return _reports.get(audit_id)


def list_reports(company_id: Optional[str] = None) -> List[SeoAuditSummary]:
    """List stored reports (most recent first), optionally filtered by company."""
    with _reports_lock:
        snapshot = list(_reports.values())
    summaries = [
        SeoAuditSummary(
            audit_id=r.audit_id,
            company_id=r.company_id,
            website_url=r.website_url,
            status=r.status,
            started_at=r.started_at,
            completed_at=r.completed_at,
            pages_crawled=r.pages_crawled,
            total_issues=r.total_issues,
            health_score=r.health_score,
        )
        for r in reversed(snapshot)
        if company_id is None or r.company_id == company_id
    ]
    return summaries


# =============================================================================
# SYNC BRIDGE (skill execution from non-async contexts)
# =============================================================================

def run_audit_sync(request: SeoAuditRequest, company_id: Optional[str] = None) -> SeoAuditReport:
    """Run an audit from synchronous code, loop-safe.

    Used by the skill-bindings executor which is synchronous; spins up a fresh
    event loop in a worker thread when one is already running here.
    """
    async def _run() -> SeoAuditReport:
        report = await SeoAuditEngine().run(request, company_id=company_id)
        save_report(report)
        return report

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run())

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _run()).result()
