"""tests/test_company_intel.py — reading what a company does from its own website.

Hermetic: every fetch goes through an ``httpx.MockTransport`` and the
DNS-resolving SSRF check is stubbed, so no test touches the network.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from services import company_intel
from services.company_intel import CompanyProfile, build_company_profile, classify_links, parse_page

_CLINIC_HOME = """
<html><head>
  <title>Bright Smile Dental | Family dentist in Leeds</title>
  <meta name="description" content="Family and cosmetic dentistry in Leeds. Book online today.">
  <script type="application/ld+json">{json_ld}</script>
</head><body>
  <header><a href="/book">Book an appointment</a></header>
  <nav><a href="/about-us">About</a><a href="/treatments">Treatments</a>
       <a href="/fees">Fees</a><a href="/careers">Careers</a>
       <a href="https://facebook.com/brightsmile">Facebook</a></nav>
  <h1>Gentle dentistry for the whole family</h1>
  <h2>Invisalign and teeth whitening</h2>
  <p>We have cared for Leeds families since 1998.</p>
</body></html>
"""
_CLINIC_JSONLD = {
    "@context": "https://schema.org",
    "@graph": [
        {"@type": "WebSite", "name": "Bright Smile"},
        {
            "@type": ["Dentist", "LocalBusiness"],
            "name": "Bright Smile Dental",
            "hasOfferCatalog": {"itemListElement": [
                {"itemOffered": {"@type": "Service", "name": "Invisalign"}},
                {"itemOffered": {"@type": "Service", "name": "Teeth whitening"}},
            ]},
        },
    ],
}
_TREATMENTS = "<html><head><title>Treatments</title></head><body><h1>Our treatments</h1><h2>Dental implants</h2></body></html>"


@pytest.fixture(autouse=True)
def _no_dns(monkeypatch):
    """Every test host is public; the SSRF check itself is covered separately."""
    monkeypatch.setattr(company_intel, "_unsafe_reason", lambda url: None)
    company_intel._cache.clear()


def _site(pages: dict[str, tuple[int, str]], hits: list[str] | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if hits is not None:
            hits.append(str(request.url))
        status, body = pages.get(request.url.path, (404, "missing"))
        if status in (301, 302):
            return httpx.Response(status, headers={"location": body})
        return httpx.Response(status, text=body, headers={"content-type": "text/html; charset=utf-8"})
    return httpx.MockTransport(handler)


def _clinic_pages() -> dict[str, tuple[int, str]]:
    home = _CLINIC_HOME.replace("{json_ld}", json.dumps(_CLINIC_JSONLD))
    return {"/": (200, home), "/treatments": (200, _TREATMENTS), "/about-us": (200, "<h1>About us</h1>")}


async def test_profile_describes_a_non_commerce_business():
    profile = await build_company_profile("brightsmile.example", transport=_site(_clinic_pages()))

    assert profile.name == "Bright Smile Dental"
    assert profile.industry_hint == "Healthcare"          # most specific type beats LocalBusiness
    assert profile.description.startswith("Family and cosmetic dentistry")
    assert profile.tagline == "Gentle dentistry for the whole family"
    assert profile.offerings == ["Invisalign", "Teeth whitening"]
    assert "Book an appointment" in profile.calls_to_action
    assert {"about", "services", "pricing", "careers"} <= set(profile.page_kinds)
    assert "Dental implants" in profile.headings          # read from the treatments sub-page
    assert not profile.is_thin()


async def test_only_self_description_pages_on_the_same_site_are_fetched():
    hits: list[str] = []
    await build_company_profile("https://brightsmile.example", transport=_site(_clinic_pages(), hits))

    paths = sorted(httpx.URL(u).path for u in hits)
    assert paths == ["/", "/about-us", "/fees", "/treatments"]   # careers and facebook skipped
    assert all("brightsmile.example" in u for u in hits)


async def test_every_hop_is_ssrf_checked_and_a_private_redirect_is_refused(monkeypatch):
    checked: list[str] = []

    def reason(url: str):
        checked.append(url)
        return "host resolves to a non-public address (10.0.0.5)" if "internal" in url else None

    monkeypatch.setattr(company_intel, "_unsafe_reason", reason)
    pages = {"/": (302, "http://internal.example/admin")}
    profile = await build_company_profile("https://evil.example", transport=_site(pages))

    assert checked == ["https://evil.example", "http://internal.example/admin"]
    assert profile.is_thin()
    assert "non-public" in profile.errors[0]


async def test_unreachable_site_degrades_to_a_thin_profile_not_an_exception():
    profile = await build_company_profile("https://down.example", transport=_site({"/": (503, "")}))

    assert profile.is_thin()
    assert profile.errors and "HTTP 503" in profile.errors[0]
    assert "could not be read" in profile.as_prompt_block()


async def test_profiles_are_cached_between_wizard_steps():
    hits: list[str] = []
    transport = _site(_clinic_pages(), hits)
    await build_company_profile("brightsmile.example", transport=transport)
    first = len(hits)
    await build_company_profile("brightsmile.example", transport=transport)

    assert len(hits) == first


def test_classify_links_ignores_other_hosts_and_unknown_paths():
    links = [
        ("https://acme.example/pricing", "Pricing"),
        ("https://www.acme.example/company/team", "Team"),
        ("https://other.example/about", "About"),
        ("https://acme.example/random-page", "Random"),
        ("mailto:hi@acme.example", "Email"),
    ]
    kinds = classify_links(links, "acme.example")

    assert kinds == {"pricing": "https://acme.example/pricing", "about": "https://www.acme.example/company/team"}


def test_parse_page_tolerates_broken_json_ld():
    html = '<html><head><script type="application/ld+json">{not json</script></head><body><h1>Hi</h1></body></html>'
    facts = parse_page(html, "https://x.example/")

    assert facts.jsonld == []
    assert facts.h1 == "Hi"


def test_prompt_block_labels_facts_and_skips_empty_ones():
    block = CompanyProfile(url="https://x.example", name="Acme", offerings=["Widgets"]).as_prompt_block()

    assert "- Name: Acme" in block
    assert "- Products / services named: Widgets" in block
    assert "Tagline" not in block


@pytest.mark.parametrize("url", ["http://[::1", "http://example.com:abc", "https://\x00bad"])
async def test_malformed_urls_yield_a_thin_profile_not_an_exception(url):
    profile = await build_company_profile(url, transport=_site({}))

    assert profile.is_thin()
    assert profile.errors


@pytest.mark.parametrize("jsonld", [
    '{"@type": "Organization", "hasOfferCatalog": {"itemListElement": 5}}',
    "[" * 100_000,
    '{"@graph": "not a list", "@type": ["Dentist", 7], "name": {"nested": true}}',
])
async def test_hostile_json_ld_never_breaks_the_read(jsonld):
    home = f'<html><head><script type="application/ld+json">{jsonld}</script></head><body><h1>Hi</h1></body></html>'
    profile = await build_company_profile("https://hostile.example", transport=_site({"/": (200, home)}))

    assert profile.tagline == "Hi"


async def test_oversized_pages_are_cut_off_while_streaming(monkeypatch):
    monkeypatch.setattr(company_intel, "MAX_HTML_CHARS", 1000)
    huge = "<html><body><h1>Big</h1>" + "x" * 50_000 + "</body></html>"
    client = httpx.AsyncClient(transport=_site({"/": (200, huge)}))
    async with client:
        _, html = await company_intel._fetch_html(client, "https://big.example/")

    assert len(html) == 1000


async def test_a_bogus_charset_falls_back_to_utf8():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<h1>Caf\xc3\xa9</h1>", headers={"content-type": "text/html; charset=no-such-codec"})

    profile = await build_company_profile("https://charset.example", transport=httpx.MockTransport(handler))

    assert profile.tagline == "Caf\u00e9"


async def test_a_trickling_site_hits_the_overall_deadline(monkeypatch):
    monkeypatch.setattr(company_intel, "PROFILE_DEADLINE_SECONDS", 0.2)

    async def slow_body():
        yield b"<html><body><h1>Slow"
        await asyncio.sleep(5)
        yield b"</h1></body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=slow_body(), headers={"content-type": "text/html"})

    profile = await build_company_profile("https://slow.example", transport=httpx.MockTransport(handler))

    assert profile.is_thin()
    assert profile.errors == ["site unreadable: TimeoutError"]
