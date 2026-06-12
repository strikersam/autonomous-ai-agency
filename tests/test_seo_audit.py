"""tests/test_seo_audit.py - SEO / GEO / AIO audit engine tests (issue #533).

Covers:
- catalog integrity (unique codes, complete metadata, Screaming Frog parity)
- every page-scoped check against crafted HTML (positive + negative)
- site-scoped checks (duplicates, robots, sitemaps, llms.txt, AI crawlers)
- the crawler end-to-end over httpx.MockTransport (no network)
- prioritized report rows, % of total, health scores and exports
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from models.seo_audit import SeoAuditRequest
from services import seo_checks
from services.seo_audit import (
    SeoAuditEngine,
    analyze_page,
    estimate_pixel_width,
    flesch_reading_ease,
    is_internal,
    normalize_url,
    report_to_csv,
    report_to_markdown,
)
from services.seo_checks import CHECKS


def codes(findings) -> set[str]:
    return {i.check_code for i in findings.issues}


# =============================================================================
# CATALOG INTEGRITY
# =============================================================================

class TestCatalog:
    def test_catalog_is_substantial(self):
        # World-class coverage: more checks than the Screaming Frog CSV in #533.
        assert len(CHECKS) >= 80

    def test_codes_and_names_unique(self):
        names = [c.name for c in CHECKS.values()]
        assert len(names) == len(set(names))

    def test_every_check_fully_specified(self):
        for check in CHECKS.values():
            assert check.description, check.code
            assert check.how_to_fix, check.code
            assert check.issue_type in ("issue", "warning", "opportunity")
            assert check.priority in ("high", "medium", "low")

    def test_screaming_frog_issue_533_parity(self):
        """Every issue family from the gucci.com CSV in issue #533 is covered."""
        expected = [
            "content_low_word_count", "h1_over_70", "hreflang_missing_self_reference",
            "url_multiple_slashes", "url_underscores", "title_over_561px", "h2_over_70",
            "security_missing_csp", "response_internal_3xx", "image_missing_size_attributes",
            "security_unsafe_cross_origin_links", "meta_desc_below_400px",
            "hreflang_invalid_codes", "canonical_missing", "meta_desc_missing",
            "url_ga_tracking_params", "canonical_canonicalised", "hreflang_missing_x_default",
            "links_no_internal_outlinks", "validation_invalid_head_elements",
            "content_readability_very_difficult", "h2_non_sequential",
            "validation_html_over_2mb", "response_blocked_by_robots", "h2_duplicate",
            "url_repetitive_path", "image_over_100kb", "response_internal_4xx",
            "url_parameters", "pagination_url_not_in_anchor", "h1_missing",
            "title_duplicate", "title_over_60", "h1_duplicate", "url_over_115_chars",
            "image_missing_alt_text", "meta_desc_over_155",
            "security_missing_referrer_policy", "h1_multiple", "meta_desc_over_985px",
            "h1_non_sequential", "links_high_external_outlinks", "directive_nofollow",
            "title_below_30", "security_protocol_relative_resources", "title_below_200px",
            "meta_desc_duplicate", "links_no_anchor_text", "meta_desc_below_70",
            "directive_noindex", "h2_missing", "content_readability_difficult",
        ]
        for code in expected:
            assert code in CHECKS, f"Screaming Frog parity check missing: {code}"

    def test_geo_and_aio_pillars_present(self):
        geo = [c for c in CHECKS.values() if c.pillar == "geo"]
        aio = [c for c in CHECKS.values() if c.pillar == "aio"]
        assert len(geo) >= 6, "GEO pillar must be substantial"
        assert len(aio) >= 6, "AIO pillar must be substantial"

    def test_auto_fixable_checks_exist(self):
        fixable = [c for c in CHECKS.values() if c.auto_fixable]
        assert len(fixable) >= 10


# =============================================================================
# TEXT HELPERS
# =============================================================================

class TestHelpers:
    def test_pixel_estimate_scales_with_length(self):
        assert estimate_pixel_width("a" * 60, "title") > estimate_pixel_width("a" * 30, "title")
        assert estimate_pixel_width("MMMM", "title") > estimate_pixel_width("iiii", "title")

    def test_sixty_char_title_within_561px(self):
        # Calibration: a typical 60-character mixed title stays inside 561px.
        title = "Premium Garden Tools and Outdoor Supplies for Every Season"
        assert len(title) <= 60
        assert estimate_pixel_width(title, "title") <= 561

    def test_flesch_simple_vs_complex(self):
        simple = "The cat sat on the mat. " * 20
        complex_text = (
            "Notwithstanding institutional heterogeneity, organizational "
            "epistemologies necessitate multidimensional reconceptualization "
            "of infrastructural interdependencies. " * 10
        )
        s = flesch_reading_ease(simple)
        c = flesch_reading_ease(complex_text)
        assert s is not None and c is not None
        assert s > 80
        assert c < 30

    def test_flesch_too_short_returns_none(self):
        assert flesch_reading_ease("Too short.") is None

    def test_normalize_url(self):
        assert normalize_url("HTTPS://Example.com:443/a#frag") == "https://example.com/a"
        assert normalize_url("b", "https://example.com/a/") == "https://example.com/a/b"
        assert normalize_url("/b", "https://example.com/a/") == "https://example.com/b"

    def test_is_internal_www_insensitive(self):
        assert is_internal("https://www.example.com/x", "https://example.com")
        assert not is_internal("https://other.com/x", "https://example.com")


# =============================================================================
# PAGE-LEVEL CHECKS
# =============================================================================

GOOD_BODY_TEXT = (
    "<p>" + "Our garden tools are made to last for many years of happy use. "
    "Each tool is tested by hand and we ship them to you fast. "
    "You can trust our small team to help you pick the right tool. " * 5 + "</p>"
)

CLEAN_PAGE = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Premium Garden Tools and Outdoor Supplies Shop</title>
  <meta name="description" content="Shop premium garden tools, outdoor supplies and expert growing advice. Fast shipping, fair prices and friendly help from real gardeners.">
  <link rel="canonical" href="https://example.com/tools">
  <link rel="icon" href="/favicon.ico">
  <meta property="og:title" content="Premium Garden Tools">
  <meta property="og:description" content="Shop premium garden tools.">
  <meta property="og:image" content="https://example.com/og.png">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">
  {{"@context": "https://schema.org", "@type": "Organization", "name": "Example"}}
  </script>
  <script type="application/ld+json">
  {{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": []}}
  </script>
</head>
<body>
  <header><nav><a href="/about">About our garden experts</a></nav></header>
  <main>
    <h1>Hand Forged Garden Tools Built To Last</h1>
    <h2 id="quality">Quality you can feel</h2>
    {GOOD_BODY_TEXT}
    <img src="/img/spade.jpg" alt="Hand forged spade" width="640" height="480">
    <a href="/shop">Browse the tool shop</a>
  </main>
  <footer><a href="https://partner.example.org" target="_blank" rel="noopener">Partner</a></footer>
</body>
</html>"""


class TestCleanPage:
    def test_clean_page_fires_almost_nothing(self):
        findings = analyze_page("https://example.com/tools", CLEAN_PAGE,
                                headers={"content-type": "text/html"})
        fired = codes(findings)
        # The only acceptable residual finding on this deliberately clean page:
        allowed = {"geo_missing_rss_feed"}
        unexpected = fired - allowed
        assert not unexpected, f"Clean page unexpectedly fired: {sorted(unexpected)}"

    def test_clean_page_snapshot(self):
        findings = analyze_page("https://example.com/tools", CLEAN_PAGE,
                                headers={"content-type": "text/html"})
        page = findings.audit
        assert page is not None
        assert page.title.startswith("Premium Garden Tools")
        assert page.h1s == ["Hand Forged Garden Tools Built To Last"]
        assert page.word_count > 200
        assert "Organization" in page.structured_data_types
        assert page.has_open_graph and page.has_twitter_card and page.has_viewport


BAD_PAGE = """<html>
<head>
  <title>Buy</title>
  <title>Second title</title>
  <img src="/sneaky.png">
  <meta name="robots" content="noindex, nofollow">
  <meta http-equiv="refresh" content="5;url=/new">
  <link rel="canonical" href="/relative">
  <link rel="canonical" href="https://other.example.com/x">
  <link rel="alternate" hreflang="english" href="https://example.com/en">
  <link rel="next" href="https://example.com/page_2">
</head>
<body>
  <h3>Deep heading first</h3>
  <h1>Welcome</h1>
  <h1>Welcome again to the very best page of garden tools that anyone has ever seen online</h1>
  <p>Lorem ipsum dolor sit amet.</p>
  <img src="//cdn.example.com/x.png">
  <img src="/y.png" alt="">
  <a href="https://external.example.org" target="_blank">ext</a>
  <a href="http://localhost:3000/dev">dev link</a>
  <form action="http://insecure.example.com/submit"><input></form>
  <script type="application/ld+json">{not valid json</script>
</body>
</html>"""


class TestBadPage:
    @pytest.fixture(scope="class")
    def fired(self):
        findings = analyze_page(
            "https://example.com/Bad_Page//path?utm_source=x&q=1",
            BAD_PAGE, headers={"content-type": "text/html"},
        )
        return codes(findings)

    @pytest.mark.parametrize("code", [
        "title_below_30", "title_below_200px", "title_multiple",
        "meta_desc_missing",
        "h1_multiple", "h1_non_sequential", "h1_over_70",
        "h2_missing",
        "directive_noindex", "directive_nofollow", "directive_meta_refresh",
        "canonical_multiple_conflicting", "canonical_relative", "canonical_canonicalised",
        "hreflang_invalid_codes", "hreflang_missing_self_reference",
        "hreflang_missing_x_default",
        "url_underscores", "url_uppercase", "url_parameters",
        "url_ga_tracking_params", "url_multiple_slashes",
        "validation_missing_doctype", "validation_missing_charset",
        "validation_missing_viewport", "validation_missing_lang",
        "validation_invalid_head_elements",
        "content_low_word_count", "content_placeholder_text",
        "image_missing_alt_attribute", "image_missing_alt_text",
        "image_missing_size_attributes",
        "links_no_internal_outlinks", "links_localhost_or_dev",
        "security_unsafe_cross_origin_links", "security_protocol_relative_resources",
        "security_form_posts_to_http",
        "pagination_url_not_in_anchor",
        "aio_invalid_json_ld",
        "social_missing_open_graph", "social_missing_twitter_card",
        "geo_no_semantic_landmarks",
    ])
    def test_bad_page_fires(self, fired, code):
        assert code in fired, f"{code} should fire on the bad page"

    def test_no_unknown_codes(self, fired):
        unknown = fired - set(CHECKS)
        assert not unknown, f"Issues fired with codes missing from catalog: {unknown}"


class TestSpecificChecks:
    def test_http_page_fires_http_check(self):
        findings = analyze_page("http://example.com/", "<html></html>",
                                headers={"content-type": "text/html"})
        assert "security_http_url" in codes(findings)

    def test_mixed_content_only_on_https(self):
        html = '<html><body><script src="http://x.com/a.js"></script></body></html>'
        https = analyze_page("https://example.com/", html, headers={"content-type": "text/html"})
        assert "security_mixed_content" in codes(https)

    def test_long_title_fires_both_char_and_pixel(self):
        html = f"<title>{'Wide Words ' * 12}</title>"
        fired = codes(analyze_page("https://example.com/", html,
                                   headers={"content-type": "text/html"}))
        assert "title_over_60" in fired
        assert "title_over_561px" in fired

    def test_error_page_skips_on_page_checks(self):
        fired = codes(analyze_page("https://example.com/missing", "<html>404</html>",
                                   status_code=404, headers={"content-type": "text/html"}))
        assert "response_internal_4xx" in fired
        assert "title_missing" not in fired

    def test_html_over_2mb(self):
        html = "<html><body>" + "x" * (2 * 1024 * 1024 + 10) + "</body></html>"
        fired = codes(analyze_page("https://example.com/", html,
                                   headers={"content-type": "text/html"}))
        assert "validation_html_over_2mb" in fired

    def test_faq_content_without_schema(self):
        html = (
            "<html><body><h2>What is composting?</h2><h2>How do I start?</h2>"
            "<h2>Why does it smell?</h2></body></html>"
        )
        fired = codes(analyze_page("https://example.com/faq", html,
                                   headers={"content-type": "text/html"}))
        assert "aio_faq_content_without_schema" in fired

    def test_article_without_dates_or_author(self):
        html = "<html><body><article><p>Post body</p></article></body></html>"
        fired = codes(analyze_page("https://example.com/blog/post", html,
                                   headers={"content-type": "text/html"}))
        assert "aio_missing_article_dates" in fired
        assert "aio_missing_author_markup" in fired

    def test_x_robots_tag_header_detected(self):
        fired = codes(analyze_page(
            "https://example.com/", "<html><body>hi</body></html>",
            headers={"content-type": "text/html", "x-robots-tag": "noindex"},
        ))
        assert "directive_noindex" in fired

    def test_question_headings_with_faq_schema_pass(self):
        html = (
            '<html><body><script type="application/ld+json">'
            '{"@type": "FAQPage"}</script>'
            "<h2>What is composting?</h2><h2>How do I start?</h2>"
            "<h2>Why does it smell?</h2></body></html>"
        )
        fired = codes(analyze_page("https://example.com/faq", html,
                                   headers={"content-type": "text/html"}))
        assert "aio_faq_content_without_schema" not in fired


# =============================================================================
# CRAWLER (httpx.MockTransport - no network)
# =============================================================================

SITE_HOME = """<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><title>Mock Site Home Page For Crawl Testing</title>
</head><body><main><h1>Home</h1>
<a href="/about">About us</a>
<a href="/missing">Broken</a>
<a href="/old">Old page</a>
<a href="/secret/page">Secret</a>
</main></body></html>"""

SITE_ABOUT = """<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><title>Mock Site Home Page For Crawl Testing</title>
</head><body><main><h1>About</h1><a href="/">Home</a></main></body></html>"""


def _mock_site_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    path = request.url.path
    html = {"content-type": "text/html"}
    if path == "/robots.txt":
        return httpx.Response(200, text=(
            "User-agent: *\nDisallow: /secret/\n\n"
            "User-agent: GPTBot\nDisallow: /\n\n"
            f"Sitemap: https://mocksite.test/sitemap.xml\n"
        ))
    if path == "/sitemap.xml":
        return httpx.Response(200, text=(
            '<?xml version="1.0"?><urlset>'
            "<loc>https://mocksite.test/</loc>"
            "<loc>https://mocksite.test/about</loc>"
            "</urlset>"
        ), headers={"content-type": "application/xml"})
    if path == "/llms.txt":
        return httpx.Response(404, text="nope")
    if path == "/":
        return httpx.Response(200, text=SITE_HOME, headers=html)
    if path == "/about":
        return httpx.Response(200, text=SITE_ABOUT, headers=html)
    if path == "/missing":
        return httpx.Response(404, text="<html>gone</html>", headers=html)
    if path == "/old":
        return httpx.Response(301, headers={"location": "/about", **html})
    if path == "/favicon.ico":
        return httpx.Response(200, content=b"icon")
    return httpx.Response(404, text="not found", headers=html)


@pytest.fixture
def mock_report():
    transport = httpx.MockTransport(_mock_site_handler)
    engine = SeoAuditEngine(transport=transport)
    request = SeoAuditRequest(website_url="https://mocksite.test/", max_pages=10)
    return asyncio.run(engine.run(request, company_id="co_test"))


class TestCrawl:
    def test_crawl_succeeds(self, mock_report):
        assert mock_report.status == "success"
        assert mock_report.pages_crawled >= 3
        assert mock_report.company_id == "co_test"

    def test_site_findings(self, mock_report):
        site = mock_report.site
        assert site.robots_txt_present
        assert site.sitemap_present
        assert site.sitemap_in_robots
        assert not site.llms_txt_present
        assert site.favicon_present
        assert "GPTBot" in site.ai_crawlers_blocked

    def test_geo_checks_fire(self, mock_report):
        fired = {i.check_code for i in mock_report.issues}
        assert "geo_missing_llms_txt" in fired
        assert "geo_ai_crawlers_blocked" in fired

    def test_broken_and_redirect_links_detected(self, mock_report):
        fired = {i.check_code for i in mock_report.issues}
        assert "links_broken_internal" in fired
        assert "response_internal_4xx" in fired
        assert "response_internal_3xx" in fired

    def test_robots_blocked_links_detected(self, mock_report):
        fired = {i.check_code for i in mock_report.issues}
        assert "response_blocked_by_robots" in fired
        # The blocked URL itself must not have been fetched.
        crawled = {p.url for p in mock_report.pages}
        assert "https://mocksite.test/secret/page" not in crawled

    def test_duplicate_titles_detected(self, mock_report):
        fired = {i.check_code for i in mock_report.issues}
        assert "title_duplicate" in fired

    def test_security_header_checks_fire(self, mock_report):
        fired = {i.check_code for i in mock_report.issues}
        assert "security_missing_csp" in fired
        assert "security_missing_hsts" in fired

    def test_rows_sorted_by_priority(self, mock_report):
        order = {"high": 0, "medium": 1, "low": 2}
        priorities = [order[r.issue_priority] for r in mock_report.rows]
        assert priorities == sorted(priorities)

    def test_health_scores_in_range(self, mock_report):
        assert 0 <= mock_report.health_score < 100
        for pillar, score in mock_report.pillar_scores.items():
            assert 0 <= score <= 100, pillar

    def test_percent_of_total(self, mock_report):
        for row in mock_report.rows:
            assert 0 < row.percent_of_total <= 100 * row.urls_affected
            assert row.urls_affected <= max(1, mock_report.pages_crawled)

    def test_ssrf_protection_blocks_private_hosts(self):
        engine = SeoAuditEngine()  # no transport -> safety check active
        report = asyncio.run(engine.run(SeoAuditRequest(website_url="http://127.0.0.1/")))
        assert report.status == "failed"
        assert "safety" in report.error.lower()


# =============================================================================
# EXPORTS
# =============================================================================

class TestExports:
    def test_csv_has_screaming_frog_columns(self, mock_report):
        out = report_to_csv(mock_report)
        header = out.splitlines()[0]
        assert header == (
            '"Issue Name","Issue Type","Issue Priority","URLs","% of Total",'
            '"Description","How To Fix","Help URL"'
        )
        assert len(out.splitlines()) == len(mock_report.rows) + 1

    def test_csv_capitalizes_taxonomy(self, mock_report):
        out = report_to_csv(mock_report)
        assert '"Issue"' in out or '"Warning"' in out or '"Opportunity"' in out

    def test_markdown_report(self, mock_report):
        md = report_to_markdown(mock_report)
        assert "# SEO / GEO / AIO Audit" in md
        assert "Pillar Scores" in md
        assert "GEO" in md and "AIO" in md

    def test_markdown_is_full_heavy_report(self, mock_report):
        md = report_to_markdown(mock_report)
        assert "## Delegation Plan" in md
        assert "## Page Details" in md
        # every crawled page with issues appears in the appendix
        assert "https://mocksite.test/about" in md

    def test_pages_csv_one_row_per_page(self, mock_report):
        from services.seo_audit import report_to_pages_csv

        out = report_to_pages_csv(mock_report)
        lines = out.strip().splitlines()
        assert lines[0].startswith('"URL","Status Code"')
        assert len(lines) == len(mock_report.pages) + 1

    def test_issues_csv_one_row_per_occurrence(self, mock_report):
        from services.seo_audit import report_to_issues_csv

        out = report_to_issues_csv(mock_report)
        lines = out.strip().splitlines()
        assert lines[0].startswith('"Issue Name","Issue Type","Issue Priority","Pillar","URL"')
        assert len(lines) == len(mock_report.issues) + 1


class TestDelegationPlan:
    def test_plan_groups_by_category(self, mock_report):
        plan = mock_report.delegation_plan
        assert plan, "delegation plan must not be empty"
        categories = [t.category for t in plan]
        assert len(categories) == len(set(categories))

    def test_plan_sorted_by_wsjf(self, mock_report):
        scores = [t.wsjf_score for t in mock_report.delegation_plan]
        assert scores == sorted(scores, reverse=True)
        assert all(s > 0 for s in scores)

    def test_plan_tasks_are_actionable(self, mock_report):
        for task in mock_report.delegation_plan:
            assert task.task_key.startswith("seo-fix-")
            assert task.suggested_specialist
            assert task.instructions
            assert task.effort in ("S", "M", "L")
            assert task.urls_affected > 0

    def test_geo_findings_route_to_seo_specialist(self, mock_report):
        geo_tasks = [t for t in mock_report.delegation_plan if t.category == "GEO"]
        assert geo_tasks
        assert geo_tasks[0].suggested_specialist == "seo"

    def test_security_findings_route_to_security_specialist(self, mock_report):
        sec = [t for t in mock_report.delegation_plan if t.category == "Security"]
        assert sec
        assert sec[0].suggested_specialist == "security"


class TestRevenuePortfolio:
    """Severity -> potential revenue loss via the portfolio mechanism (PR #534 review)."""

    @pytest.fixture(scope="class")
    def revenue_report(self):
        transport = httpx.MockTransport(_mock_site_handler)
        engine = SeoAuditEngine(transport=transport)
        request = SeoAuditRequest(
            website_url="https://mocksite.test/", max_pages=10,
            monthly_organic_revenue=100_000.0,
        )
        return asyncio.run(engine.run(request, company_id="co_rev"))

    def test_total_loss_estimated_and_capped(self, revenue_report):
        r = revenue_report
        assert r.monthly_organic_revenue == 100_000.0
        assert 0 < r.estimated_monthly_revenue_loss <= 35_000.0  # 35% cap

    def test_per_row_losses_sum_to_total(self, revenue_report):
        rows_sum = sum(row.estimated_monthly_revenue_loss for row in revenue_report.rows)
        assert rows_sum == pytest.approx(revenue_report.estimated_monthly_revenue_loss, rel=0.01)

    def test_high_priority_rows_carry_more_loss(self, revenue_report):
        by_priority: dict[str, float] = {"high": 0.0, "medium": 0.0, "low": 0.0}
        for row in revenue_report.rows:
            # normalize per affected URL so volume doesn't mask severity weighting
            by_priority[row.issue_priority] += (
                row.estimated_monthly_revenue_loss / max(1, row.urls_affected)
            )
        assert by_priority["high"] > by_priority["low"]

    def test_delegation_tasks_carry_wsjf_and_value(self, revenue_report):
        plan = revenue_report.delegation_plan
        assert plan
        assert any(t.estimated_monthly_value > 0 for t in plan)
        for t in plan:
            assert t.wsjf_score == pytest.approx(
                (t.business_value + t.time_criticality + t.risk_reduction) / t.job_size,
                rel=0.01,
            )

    def test_wsjf_components_match_portfolio_initiative_contract(self, revenue_report):
        """Delegation packages must slot directly into agents/portfolio.py."""
        from agents.portfolio import Initiative

        task = revenue_report.delegation_plan[0]
        initiative = Initiative(
            initiative_id=task.task_key,
            title=task.title,
            business_value=task.business_value,
            time_criticality=task.time_criticality,
            risk_reduction=task.risk_reduction,
            job_size=task.job_size,
            source="seo_audit",
        )
        assert initiative.wsjf == pytest.approx(task.wsjf_score, rel=0.01)

    def test_no_revenue_baseline_means_no_dollar_figures(self, mock_report):
        assert mock_report.monthly_organic_revenue == 0
        assert mock_report.estimated_monthly_revenue_loss == 0
        assert all(row.estimated_monthly_revenue_loss == 0 for row in mock_report.rows)
        # WSJF is still computed (relative basis: URL volume)
        assert all(t.wsjf_score > 0 for t in mock_report.delegation_plan)

    def test_markdown_shows_revenue_when_modeled(self, revenue_report):
        md = report_to_markdown(revenue_report)
        assert "revenue at risk" in md.lower()
        assert "$ at risk/mo" in md
        assert "WSJF" in md


class TestNewChecks:
    def test_slow_response_check(self):
        fired = codes(analyze_page(
            "https://example.com/", "<html><body>x</body></html>",
            headers={"content-type": "text/html"}, fetch_ms=5000,
        ))
        assert "performance_slow_response" in fired

    def test_lazy_loading_gap_detected(self):
        html = (
            '<html><body><img src="/hero.png" alt="Hero">'
            '<img src="/a.png" alt="A"><img src="/b.png" alt="B" loading="lazy">'
            "</body></html>"
        )
        findings = analyze_page("https://example.com/", html,
                                headers={"content-type": "text/html"})
        hits = [i for i in findings.issues if i.check_code == "image_not_lazy_loaded"]
        assert hits and "1 of 3" in hits[0].detail

    def test_all_lazy_below_fold_passes(self):
        html = (
            '<html><body><img src="/hero.png" alt="Hero">'
            '<img src="/a.png" alt="A" loading="lazy"></body></html>'
        )
        fired = codes(analyze_page("https://example.com/", html,
                                   headers={"content-type": "text/html"}))
        assert "image_not_lazy_loaded" not in fired
