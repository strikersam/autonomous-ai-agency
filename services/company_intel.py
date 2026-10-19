"""services/company_intel.py — understand what an onboarded company actually does.

The website scanner (``services/scanner.py``) answers "what is this site built
with?". Onboarding also needs "what does this company sell, to whom, and how do
customers engage with it?" — otherwise every company with the same stack gets
the same questions, and a dental clinic on WordPress is asked about publishing
cadence. This module reads the public homepage plus a handful of the pages a
company uses to describe itself (about, products, services, pricing, customers)
and returns a :class:`CompanyProfile` of facts, each traceable to a page.

It is deliberately domain-agnostic: nothing here assumes e-commerce or SaaS.
Industry comes from the schema.org types the site declares about itself; when it
declares none, the profile says so and the question generator infers it from
the text instead.

Every fetched URL — the operator-supplied homepage and every link read out of
it — passes ``unsafe_target_reason()`` before the request, and redirects are
followed by hand so each hop is re-checked (CLAUDE.md rule 14).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

log = logging.getLogger("qwen-proxy")

MAX_PAGES = 6                      # homepage + up to 5 self-description pages
FETCH_TIMEOUT_SECONDS = 8.0
MAX_REDIRECTS = 5
MAX_HTML_CHARS = 2_000_000         # a page bigger than this is not a marketing page
EXCERPT_CHARS = 1200
CACHE_TTL_SECONDS = 900.0          # the wizard re-mounts steps; don't refetch each time
_CACHE_MAX_ENTRIES = 64
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_REDIRECT_CODES = {301, 302, 303, 307, 308}

# Section kinds a company site usually has, keyed by the words that name them in
# a link's path or text. Order matters: the first kind that matches wins.
_PAGE_KINDS: dict[str, tuple[str, ...]] = {
    "about": ("about", "company", "who-we-are", "our-story", "mission", "team"),
    "pricing": ("pricing", "plans", "prices", "fees", "rates"),
    "services": ("services", "what-we-do", "practice-areas", "treatments", "specialties", "expertise"),
    "products": ("products", "product", "solutions", "features", "platform", "shop", "store", "catalog", "menu", "collections"),
    "customers": ("customers", "case-studies", "clients", "testimonials", "portfolio", "success-stories"),
    "careers": ("careers", "jobs", "join-us", "hiring", "work-with-us", "vacancies"),
    "contact": ("contact", "locations", "find-us", "visit"),
    "docs": ("docs", "documentation", "developers", "api-reference"),
    "blog": ("blog", "news", "insights", "articles", "press", "stories"),
}
# Kinds worth reading in full; the rest are only recorded as present.
_FETCH_KINDS = ("about", "services", "products", "pricing", "customers")

# schema.org @type → a readable industry. Only types that name a line of
# business; generic ones (Organization, WebSite, Product) say nothing about it.
_SCHEMA_INDUSTRY: dict[str, str] = {
    "SoftwareApplication": "Software", "WebApplication": "Software",
    "MobileApplication": "Software", "OnlineStore": "Retail", "Store": "Retail",
    "ClothingStore": "Retail", "ElectronicsStore": "Retail", "GroceryStore": "Retail",
    "Restaurant": "Food & hospitality", "FoodEstablishment": "Food & hospitality",
    "CafeOrCoffeeShop": "Food & hospitality", "Bakery": "Food & hospitality",
    "Hotel": "Hospitality", "LodgingBusiness": "Hospitality", "TravelAgency": "Travel",
    "MedicalOrganization": "Healthcare", "MedicalClinic": "Healthcare",
    "Hospital": "Healthcare", "Physician": "Healthcare", "Dentist": "Healthcare",
    "Pharmacy": "Healthcare", "VeterinaryCare": "Veterinary care",
    "LegalService": "Legal services", "Attorney": "Legal services", "Notary": "Legal services",
    "FinancialService": "Financial services", "BankOrCreditUnion": "Financial services",
    "AccountingService": "Accounting", "InsuranceAgency": "Insurance",
    "EducationalOrganization": "Education", "CollegeOrUniversity": "Education",
    "School": "Education", "RealEstateAgent": "Real estate",
    "AutoDealer": "Automotive", "AutomotiveBusiness": "Automotive", "AutoRepair": "Automotive",
    "NewsMediaOrganization": "Media & publishing", "NGO": "Non-profit",
    "GovernmentOrganization": "Public sector", "HealthAndBeautyBusiness": "Health & beauty",
    "BeautySalon": "Health & beauty", "DaySpa": "Health & beauty",
    "ExerciseGym": "Fitness", "SportsActivityLocation": "Fitness",
    "HomeAndConstructionBusiness": "Home services & construction",
    "GeneralContractor": "Home services & construction", "Plumber": "Home services & construction",
    "Electrician": "Home services & construction", "EmploymentAgency": "Recruitment",
    "EntertainmentBusiness": "Entertainment", "EventVenue": "Events",
    "ProfessionalService": "Professional services", "Airline": "Travel",
    "MovingCompany": "Logistics", "LocalBusiness": "Local business",
}

# Verbs that open a call to action. The CTAs a site leads with say how its
# customers engage — "Book a demo" and "Add to cart" are different businesses.
_CTA_PATTERN = re.compile(
    r"^(book|buy|shop|order|start|try|get|request|schedule|sign up|join|donate|"
    r"apply|subscribe|download|contact|call|reserve|enrol|enroll|register|"
    r"talk to|see pricing|view plans|add to)\b",
    re.IGNORECASE,
)
_WS = re.compile(r"\s+")


class CompanyProfile(BaseModel):
    """Public facts about a company, read from its own website."""

    url: str
    name: str = ""
    description: str = ""
    tagline: str = ""
    industry_hint: str = Field(default="", description="From schema.org types; empty when the site declares none")
    schema_types: list[str] = Field(default_factory=list)
    offerings: list[str] = Field(default_factory=list, description="Named products or services")
    headings: list[str] = Field(default_factory=list)
    calls_to_action: list[str] = Field(default_factory=list)
    page_kinds: list[str] = Field(default_factory=list, description="Sections the site has, e.g. pricing, careers")
    excerpt: str = ""
    pages_read: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def is_thin(self) -> bool:
        """True when too little was read to say what the company does."""
        return not (self.description or self.excerpt or self.offerings or self.headings)

    def as_prompt_block(self) -> str:
        """Render the profile as a compact, labelled block for an LLM prompt."""
        if self.is_thin():
            return "Website content: could not be read (blocked or empty)."
        rows = [
            ("Name", self.name), ("Tagline", self.tagline),
            ("Self-description", self.description),
            ("Declared industry (schema.org)", self.industry_hint),
            ("Products / services named", ", ".join(self.offerings)),
            ("Main calls to action", ", ".join(self.calls_to_action)),
            ("Site sections present", ", ".join(self.page_kinds)),
            ("Key headings", " | ".join(self.headings)),
            ("Text excerpt", self.excerpt),
        ]
        return "\n".join(f"- {label}: {value}" for label, value in rows if value)


@dataclass
class _PageFacts:
    """What one page says about the company. Internal: merged into a profile."""

    url: str
    title: str = ""
    description: str = ""
    site_name: str = ""
    h1: str = ""
    headings: list[str] = field(default_factory=list)
    jsonld: list[dict[str, Any]] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)
    ctas: list[str] = field(default_factory=list)
    text: str = ""


# ── parsing (sync, CPU-bound: always called through asyncio.to_thread) ───────

def _clean(text: str | None, limit: int = 300) -> str:
    return _WS.sub(" ", text or "").strip()[:limit]


def _meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
        if tag and tag.get("content"):
            return _clean(tag["content"])
    return ""


def _jsonld_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Every JSON-LD object on the page, with ``@graph`` containers flattened."""
    found: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack and len(found) < 50:
            item = stack.pop(0)
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("@graph"), list):
                stack.extend(item["@graph"])
            found.append(item)
    return found


def _ctas(soup: BeautifulSoup) -> list[str]:
    seen: list[str] = []
    for tag in soup.find_all(["a", "button"]):
        text = _clean(tag.get_text(" "), 40)
        if 3 <= len(text) <= 40 and _CTA_PATTERN.match(text) and text.lower() not in (s.lower() for s in seen):
            seen.append(text)
        if len(seen) >= 8:
            break
    return seen


def parse_page(html: str, url: str) -> _PageFacts:
    """Extract the company-describing facts from one HTML page."""
    soup = BeautifulSoup(html, "lxml")
    facts = _PageFacts(url=url)
    facts.title = _clean(soup.title.string if soup.title else "", 160)
    facts.description = _meta(soup, "description", "og:description", "twitter:description")
    facts.site_name = _meta(soup, "og:site_name", "application-name")
    facts.jsonld = _jsonld_objects(soup)
    facts.ctas = _ctas(soup)
    for a in soup.find_all("a", href=True)[:400]:
        facts.links.append((urljoin(url, a["href"]), _clean(a.get_text(" "), 60)))
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form"]):
        tag.decompose()
    h1 = soup.find("h1")
    facts.h1 = _clean(h1.get_text(" ") if h1 else "", 160)
    for h in soup.find_all(["h1", "h2"])[:20]:
        text = _clean(h.get_text(" "), 120)
        if text and text not in facts.headings:
            facts.headings.append(text)
    body = soup.body or soup
    facts.text = _clean(body.get_text(" "), EXCERPT_CHARS * 2)
    return facts


# ── interpretation ───────────────────────────────────────────────────────────

def _types_of(obj: dict[str, Any]) -> list[str]:
    raw = obj.get("@type")
    return [t for t in (raw if isinstance(raw, list) else [raw]) if isinstance(t, str)]


def _offerings_from_jsonld(objects: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for obj in objects:
        types = _types_of(obj)
        if any(t in ("Product", "Service", "SoftwareApplication", "Course", "MenuItem", "Offer") for t in types):
            name = _clean(str(obj.get("name") or ""), 80)
            if name and name not in names:
                names.append(name)
        catalog = obj.get("hasOfferCatalog")
        if isinstance(catalog, dict):
            for item in catalog.get("itemListElement") or []:
                inner = item.get("itemOffered", item) if isinstance(item, dict) else {}
                name = _clean(str(inner.get("name") or ""), 80) if isinstance(inner, dict) else ""
                if name and name not in names:
                    names.append(name)
    return names[:15]


def _org_name(objects: list[dict[str, Any]]) -> str:
    for obj in objects:
        types = _types_of(obj)
        if obj.get("name") and (
            "Organization" in types or "Corporation" in types
            or any(t in _SCHEMA_INDUSTRY for t in types)
        ):
            return _clean(str(obj["name"]), 120)
    return ""


def _industry_from_types(types: list[str]) -> str:
    # The most specific declared type wins: a Dentist is also a LocalBusiness.
    for t in types:
        if t in _SCHEMA_INDUSTRY and t != "LocalBusiness":
            return _SCHEMA_INDUSTRY[t]
    return _SCHEMA_INDUSTRY["LocalBusiness"] if "LocalBusiness" in types else ""


def _kind_of(link_url: str, link_text: str) -> str:
    path = urlparse(link_url).path.lower().strip("/")
    first = path.split("/")[0] if path else ""
    text = link_text.lower()
    for kind, words in _PAGE_KINDS.items():
        if any(first == w or text == w.replace("-", " ") for w in words):
            return kind
    return ""


def classify_links(links: list[tuple[str, str]], host: str) -> dict[str, str]:
    """Map each section kind to the first same-site link that names it."""
    kinds: dict[str, str] = {}
    for link_url, text in links:
        parsed = urlparse(link_url)
        if parsed.scheme not in ("http", "https") or _bare_host(parsed.hostname) != host:
            continue
        kind = _kind_of(link_url, text)
        if kind and kind not in kinds:
            kinds[kind] = parsed._replace(fragment="", query="").geturl()
    return kinds


def _bare_host(hostname: str | None) -> str:
    host = (hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def merge_pages(url: str, home: _PageFacts, others: list[_PageFacts], kinds: list[str]) -> CompanyProfile:
    """Combine the homepage and sub-pages into one profile. Homepage facts lead."""
    pages = [home, *others]
    objects = [obj for p in pages for obj in p.jsonld]
    schema_types = sorted({t for obj in objects for t in _types_of(obj)})
    offerings = _offerings_from_jsonld(objects)
    headings: list[str] = []
    ctas: list[str] = []
    for p in pages:
        headings.extend(h for h in p.headings if h not in headings)
        ctas.extend(c for c in p.ctas if c.lower() not in (x.lower() for x in ctas))
    excerpt = " … ".join(p.text[: EXCERPT_CHARS // len(pages)] for p in pages if p.text)
    return CompanyProfile(
        url=url,
        name=_org_name(objects) or home.site_name or home.title.split("|")[0].split(" - ")[0].strip(),
        description=home.description or next((p.description for p in others if p.description), ""),
        tagline=home.h1,
        industry_hint=_industry_from_types(schema_types),
        schema_types=schema_types[:20],
        offerings=offerings,
        headings=headings[:15],
        calls_to_action=ctas[:8],
        page_kinds=kinds,
        excerpt=excerpt[:EXCERPT_CHARS],
        pages_read=[p.url for p in pages],
    )


# ── fetching ─────────────────────────────────────────────────────────────────

def _unsafe_reason(url: str) -> str | None:
    """Indirection so tests can stub the DNS-resolving SSRF check."""
    from agent.web_reach import unsafe_target_reason

    return unsafe_target_reason(url)


async def _fetch_html(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
    """GET *url*, following redirects by hand; return (final_url, html)."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        reason = await asyncio.to_thread(_unsafe_reason, current)
        if reason:
            raise ValueError(f"blocked: {reason}")
        resp = await client.get(current)
        location = resp.headers.get("location")
        if resp.status_code in _REDIRECT_CODES and location:
            current = urljoin(current, location)
            continue
        if resp.status_code >= 400:
            raise ValueError(f"HTTP {resp.status_code}")
        if "html" not in resp.headers.get("content-type", "html").lower():
            raise ValueError("not an HTML page")
        return current, resp.text[:MAX_HTML_CHARS]
    raise ValueError("too many redirects")


async def _read_page(client: httpx.AsyncClient, url: str) -> _PageFacts | None:
    try:
        final_url, html = await _fetch_html(client, url)
    except (httpx.HTTPError, ValueError) as exc:
        log.info("Company intel: skipped %s: %s", url, exc)
        return None
    return await asyncio.to_thread(parse_page, html, final_url)


def _normalise(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return urlparse(url)._replace(fragment="").geturl()


_cache: dict[str, tuple[float, CompanyProfile]] = {}


async def build_company_profile(
    url: str, *, transport: httpx.AsyncBaseTransport | None = None, use_cache: bool = True
) -> CompanyProfile:
    """Read a company's public site and return what it says about itself.

    Never raises: an unreachable or blocked site yields a profile whose
    ``errors`` say why and whose ``is_thin()`` is true, so callers can fall back
    to stack-only signals.
    """
    target = _normalise(url)
    cached = _cache.get(target)
    if use_cache and cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    async with httpx.AsyncClient(
        transport=transport, timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=False,
        headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    ) as client:
        try:
            final_url, html = await _fetch_html(client, target)
        except (httpx.HTTPError, ValueError) as exc:
            log.info("Company intel: homepage %s unreadable: %s", target, exc)
            return CompanyProfile(url=target, errors=[f"homepage unreadable: {exc}"])
        home = await asyncio.to_thread(parse_page, html, final_url)
        kinds = classify_links(home.links, _bare_host(urlparse(final_url).hostname))
        to_read = [kinds[k] for k in _FETCH_KINDS if k in kinds and kinds[k] != final_url]
        others = await asyncio.gather(*(_read_page(client, u) for u in to_read[: MAX_PAGES - 1]))

    profile = merge_pages(final_url, home, [p for p in others if p], sorted(kinds))
    if len(_cache) >= _CACHE_MAX_ENTRIES:
        _cache.pop(next(iter(_cache)))
    _cache[target] = (time.monotonic(), profile)
    return profile
