"""
services/seo_checks.py - SEO / GEO / AIO Check Catalog

The authoritative catalog of every check the audit engine can fire, with
Screaming Frog-compatible naming, typing (issue/warning/opportunity) and
prioritization (high/medium/low), plus remediation guidance per check.

Pillars beyond Screaming Frog parity:
- ``geo``  Generative Engine Optimization: is the site discoverable and
           citable by AI crawlers and answer engines?
- ``aio``  AI Overviews readiness: structured data, FAQ/HowTo schema,
           chunkable content, freshness and E-E-A-T signals.

The engine in services/seo_audit.py references checks by ``code``; the
repo-aware fixer in services/seo_fixer.py implements the ``auto_fixable`` ones.
"""

from __future__ import annotations

from typing import Dict, List

from models.seo_audit import SeoCheckDefinition

# Thresholds used by the engine (kept here so catalog text and engine agree).
TITLE_MAX_CHARS = 60
TITLE_MIN_CHARS = 30
TITLE_MAX_PIXELS = 561
TITLE_MIN_PIXELS = 200
META_DESC_MAX_CHARS = 155
META_DESC_MIN_CHARS = 70
META_DESC_MAX_PIXELS = 985
META_DESC_MIN_PIXELS = 400
HEADING_MAX_CHARS = 70
LOW_CONTENT_WORDS = 200
URL_MAX_CHARS = 115
HIGH_EXTERNAL_OUTLINKS = 100
IMAGE_MAX_BYTES = 100 * 1024
HTML_MAX_BYTES = 2 * 1024 * 1024
LONG_PARAGRAPH_WORDS = 300
FLESCH_DIFFICULT = 50.0
FLESCH_VERY_DIFFICULT = 30.0
SLOW_RESPONSE_MS = 3000

# AI / answer-engine crawlers checked for robots.txt access (GEO pillar).
AI_CRAWLER_USER_AGENTS: List[str] = [
    "GPTBot",            # OpenAI / ChatGPT browsing + training
    "OAI-SearchBot",     # OpenAI search
    "ChatGPT-User",      # ChatGPT on-demand fetches
    "ClaudeBot",         # Anthropic
    "Claude-Web",        # Anthropic on-demand fetches
    "PerplexityBot",     # Perplexity
    "Google-Extended",   # Gemini grounding/training opt-in
    "Applebot-Extended", # Apple Intelligence
    "Bytespider",        # ByteDance
    "CCBot",             # Common Crawl (feeds many LLMs)
]

_SF = "https://www.screamingfrog.co.uk/seo-spider/issues/"
_GOOGLE = "https://developers.google.com/search/docs"
_MDN = "https://developer.mozilla.org/en-US/docs"
_SCHEMA = "https://schema.org"


def _c(
    code: str,
    name: str,
    category: str,
    issue_type: str,
    priority: str,
    description: str,
    how_to_fix: str,
    *,
    pillar: str = "technical",
    scope: str = "page",
    help_url: str = "",
    auto_fixable: bool = False,
) -> SeoCheckDefinition:
    return SeoCheckDefinition(
        code=code,
        name=name,
        category=category,
        issue_type=issue_type,  # type: ignore[arg-type]
        priority=priority,  # type: ignore[arg-type]
        pillar=pillar,  # type: ignore[arg-type]
        scope=scope,  # type: ignore[arg-type]
        description=description,
        how_to_fix=how_to_fix,
        help_url=help_url,
        auto_fixable=auto_fixable,
    )


_ALL_CHECKS: List[SeoCheckDefinition] = [
    # =========================================================================
    # PAGE TITLES
    # =========================================================================
    _c("title_missing", "Page Titles: Missing", "Page Titles", "issue", "high",
       "Pages with a missing <title> element, or one that is empty or whitespace. "
       "The page title is one of the strongest on-page ranking signals and is shown "
       "as the clickable headline in search results.",
       "Write a concise, unique and descriptive title for every indexable page, "
       "including target keywords where natural.",
       help_url=f"{_GOOGLE}/appearance/title-link"),
    _c("title_duplicate", "Page Titles: Duplicate", "Page Titles", "opportunity", "medium",
       "Pages which have duplicate page titles. If pages share the same title it is "
       "harder for users and search engines to distinguish one page from another.",
       "Update duplicate page titles so each page has a unique and descriptive title. "
       "If the pages themselves are duplicates, consolidate with redirects or canonicals.",
       scope="site", help_url=_SF),
    _c("title_over_60", "Page Titles: Over 60 Characters", "Page Titles", "opportunity", "medium",
       f"Pages whose titles exceed {TITLE_MAX_CHARS} characters. Characters over the limit "
       "may be truncated in Google's search results and carry less weight in scoring.",
       "Write concise page titles so important words are not truncated in the SERPs.",
       help_url=_SF),
    _c("title_below_30", "Page Titles: Below 30 Characters", "Page Titles", "opportunity", "medium",
       f"Pages whose titles are under {TITLE_MIN_CHARS} characters. Not necessarily a problem, "
       "but there is room to target additional keywords or communicate USPs.",
       "Consider using the available space for additional target keywords or USPs.",
       help_url=_SF),
    _c("title_over_561px", "Page Titles: Over 561 Pixels", "Page Titles", "opportunity", "medium",
       f"Pages whose titles exceed Google's estimated {TITLE_MAX_PIXELS}px SERP display width. "
       "Google truncation is based on pixels rather than characters.",
       "Write concise page titles so important words remain visible in the search results.",
       help_url=_SF),
    _c("title_below_200px", "Page Titles: Below 200 Pixels", "Page Titles", "opportunity", "medium",
       f"Pages whose titles are much shorter than Google's pixel limit (under {TITLE_MIN_PIXELS}px), "
       "indicating room to target additional keywords or USPs.",
       "Consider using the available pixel space for additional keywords or USPs.",
       help_url=_SF),
    _c("title_multiple", "Page Titles: Multiple", "Page Titles", "issue", "medium",
       "Pages with more than one <title> element in the <head>. Search engines may pick "
       "an unintended title when several are present.",
       "Keep exactly one <title> element per page.",
       help_url=_SF),
    _c("title_same_as_h1", "Page Titles: Same as H1", "Page Titles", "opportunity", "low",
       "Pages where the title duplicates the H1 exactly. This is a missed opportunity to "
       "target keyword variations across the two strongest on-page elements.",
       "Consider varying the title and H1 to cover complementary phrasing and intent.",
       help_url=_SF),

    # =========================================================================
    # META DESCRIPTION
    # =========================================================================
    _c("meta_desc_missing", "Meta Description: Missing", "Meta Description", "opportunity", "low",
       "Pages with a missing, empty or whitespace meta description. This is a missed "
       "opportunity to influence click-through rates from search results.",
       "Write unique, descriptive meta descriptions on key pages that communicate the "
       "purpose of the page and entice clicks.",
       auto_fixable=True, help_url=f"{_GOOGLE}/appearance/snippet"),
    _c("meta_desc_duplicate", "Meta Description: Duplicate", "Meta Description", "opportunity", "low",
       "Pages which share an identical meta description. Duplicate or irrelevant "
       "descriptions are usually ignored by search engines when generating snippets.",
       "Write a distinct meta description per page; consolidate truly duplicate pages.",
       scope="site", help_url=_SF),
    _c("meta_desc_over_155", "Meta Description: Over 155 Characters", "Meta Description",
       "opportunity", "low",
       f"Pages whose meta descriptions exceed {META_DESC_MAX_CHARS} characters and may be "
       "truncated in search results.",
       "Write concise meta descriptions so important words are not truncated.",
       help_url=_SF),
    _c("meta_desc_below_70", "Meta Description: Below 70 Characters", "Meta Description",
       "opportunity", "low",
       f"Pages whose meta descriptions are under {META_DESC_MIN_CHARS} characters. There is "
       "additional room to communicate benefits, USPs or calls to action.",
       "Consider using the remaining space for benefits, USPs or calls to action to improve CTR.",
       help_url=_SF),
    _c("meta_desc_over_985px", "Meta Description: Over 985 Pixels", "Meta Description",
       "opportunity", "low",
       f"Pages whose meta descriptions exceed Google's estimated {META_DESC_MAX_PIXELS}px "
       "snippet display width.",
       "Write concise meta descriptions to avoid truncation in the SERPs.",
       help_url=_SF),
    _c("meta_desc_below_400px", "Meta Description: Below 400 Pixels", "Meta Description",
       "opportunity", "low",
       f"Pages whose meta descriptions are much shorter than the pixel limit (under "
       f"{META_DESC_MIN_PIXELS}px), indicating room for more compelling copy.",
       "Consider using the remaining space for benefits, USPs or calls to action.",
       help_url=_SF),
    _c("meta_desc_multiple", "Meta Description: Multiple", "Meta Description", "issue", "low",
       "Pages with more than one meta description element. Search engines may pick an "
       "unintended description when several are present.",
       "Keep exactly one meta description element per page.",
       help_url=_SF),

    # =========================================================================
    # H1 / H2
    # =========================================================================
    _c("h1_missing", "H1: Missing", "H1", "issue", "medium",
       "Pages with a missing or empty <h1>. The H1 should describe the main title and "
       "purpose of the page and is one of the stronger on-page ranking signals.",
       "Ensure important pages have a concise, descriptive and unique <h1>.",
       help_url=_SF),
    _c("h1_duplicate", "H1: Duplicate", "H1", "opportunity", "low",
       "Pages which share the same <h1> as other pages, making it harder to distinguish "
       "pages from one another.",
       "Give important pages a unique and descriptive <h1>; consolidate duplicate pages.",
       scope="site", help_url=_SF),
    _c("h1_over_70", "H1: Over 70 Characters", "H1", "opportunity", "low",
       f"Pages whose <h1> exceeds {HEADING_MAX_CHARS} characters. There is no hard limit, "
       "but headings should be clear and concise for users.",
       "Write concise <h1>s including target keywords where natural - without stuffing.",
       help_url=_SF),
    _c("h1_multiple", "H1: Multiple", "H1", "warning", "medium",
       "Pages with multiple <h1> elements. HTML5 permits this, but a single <h1> with "
       "h2-h6 used for structure is still generally recommended for users and SEO.",
       "Use a single <h1> per page and the full heading rank (h2-h6) for additional headings.",
       help_url=_SF),
    _c("h1_non_sequential", "H1: Non-Sequential", "H1", "warning", "low",
       "Pages where the <h1> is not the first heading on the page. Headings should be in "
       "logical sequentially-descending order to convey document structure.",
       "Ensure the <h1> is the first heading, followed by <h2> etc. in descending order.",
       help_url=_SF),
    _c("h2_missing", "H2: Missing", "H2", "warning", "low",
       "Pages with no <h2>. H2s describe sections within a document, act as signposts "
       "for users and help search engines understand the page.",
       "Use logical, descriptive <h2>s on important pages.",
       help_url=_SF),
    _c("h2_duplicate", "H2: Duplicate", "H2", "opportunity", "low",
       "Pages with duplicate <h2>s across the site, making pages harder to distinguish.",
       "Use unique, descriptive <h2>s on important pages.",
       scope="site", help_url=_SF),
    _c("h2_over_70", "H2: Over 70 Characters", "H2", "opportunity", "low",
       f"Pages whose <h2>s exceed {HEADING_MAX_CHARS} characters; long headings are less "
       "helpful to users.",
       "Write concise <h2>s including target keywords where natural.",
       help_url=_SF),
    _c("h2_multiple", "H2: Multiple", "H2", "warning", "low",
       "Pages with multiple <h2>s. HTML standards allow this within a logical heading "
       "hierarchy; the filter helps review whether they are used appropriately.",
       "Ensure <h2>s sit in a logical hierarchical structure, using h3-h6 for deeper "
       "levels where appropriate.",
       help_url=_SF),
    _c("h2_non_sequential", "H2: Non-Sequential", "H2", "warning", "low",
       "Pages where an <h2> is not the second heading level after the <h1>. Heading "
       "elements should descend logically from <h1> to <h6>.",
       "Review and update heading levels so they descend in order (h1 then h2, etc.).",
       help_url=_SF),

    # =========================================================================
    # CONTENT
    # =========================================================================
    _c("content_low_word_count", "Content: Low Content Pages", "Content", "opportunity", "medium",
       f"Pages with fewer than {LOW_CONTENT_WORDS} words of body copy. Search engines need "
       "descriptive text to understand the purpose of a page; treat this as a rough guide.",
       "Consider adding descriptive content to help users and search engines better "
       "understand the page.",
       pillar="content", help_url=_SF),
    _c("content_readability_difficult", "Content: Readability Difficult", "Content",
       "opportunity", "low",
       "Copy on the page is difficult to read (Flesch reading-ease 30-50) and is best "
       "understood by college graduates.",
       "Use shorter sentences and simpler words to improve readability for your audience.",
       pillar="content", help_url=_SF),
    _c("content_readability_very_difficult", "Content: Readability Very Difficult", "Content",
       "opportunity", "low",
       "Copy on the page is very difficult to read (Flesch reading-ease below 30) and is "
       "best understood by university graduates.",
       "Use shorter sentences and simpler words to improve readability for your audience.",
       pillar="content", help_url=_SF),
    _c("content_placeholder_text", "Content: Placeholder Text", "Content", "issue", "high",
       "Pages containing placeholder copy such as 'lorem ipsum'. Placeholder text signals "
       "unfinished pages to users and search engines.",
       "Replace placeholder text with real, descriptive content before the page is indexed.",
       pillar="content"),
    _c("content_long_paragraphs", "Content: Long Unbroken Paragraphs", "Content",
       "opportunity", "low",
       f"Pages with single paragraphs over {LONG_PARAGRAPH_WORDS} words. Answer engines and "
       "AI Overviews extract self-contained passages; very long paragraphs are hard to cite.",
       "Break long paragraphs into focused, self-contained chunks with descriptive subheadings "
       "so passages can be quoted and cited by answer engines.",
       pillar="aio"),

    # =========================================================================
    # IMAGES
    # =========================================================================
    _c("image_missing_alt_text", "Images: Missing Alt Text", "Images", "issue", "low",
       "Images with an alt attribute that is empty where the image is meaningful. Alt text "
       "helps visually-impaired users and search engines understand the image.",
       "Add descriptive alt text; use empty alt (alt=\"\") only for decorative images.",
       auto_fixable=True, help_url=f"{_GOOGLE}/appearance/google-images"),
    _c("image_missing_alt_attribute", "Images: Missing Alt Attribute", "Images", "issue", "low",
       "Images with no alt attribute at all. Without it, assistive technologies announce "
       "the raw filename and search engines get no signal.",
       "Add an alt attribute to every <img>; empty for decorative, descriptive otherwise.",
       auto_fixable=True, help_url=f"{_GOOGLE}/appearance/google-images"),
    _c("image_missing_size_attributes", "Images: Missing Size Attributes", "Images",
       "opportunity", "low",
       "Image elements without width and height attributes. Browsers cannot reserve space, "
       "causing layout shifts (CLS) as the page loads.",
       "Declare native width and height attributes on images so the browser can reserve "
       "space before they load.",
       auto_fixable=True, help_url=f"{_MDN}/Web/Performance/Guides/CLS"),
    _c("image_not_lazy_loaded", "Images: Not Lazy Loaded", "Images", "opportunity", "low",
       "Below-the-fold images without a loading=\"lazy\" attribute. Eagerly loading "
       "every image delays page rendering and wastes bandwidth; native lazy loading "
       "defers offscreen images until needed.",
       "Add loading=\"lazy\" to below-the-fold images (keep the LCP/hero image eager). "
       "Audit video and iframe elements for the same opportunity.",
       auto_fixable=True, help_url=f"{_MDN}/Web/Performance/Guides/Lazy_loading"),
    _c("image_over_100kb", "Images: Over 100 kB", "Images", "opportunity", "medium",
       "Images over 100 kB. Large images are one of the most common causes of slow pages.",
       "Compress, properly scale and use modern formats (WebP/AVIF) to reduce image weight.",
       help_url=_SF),

    # =========================================================================
    # LINKS
    # =========================================================================
    _c("links_broken_internal", "Links: Broken Internal Links", "Links", "issue", "high",
       "Internal links resolving to client errors (4xx). Broken links waste crawl budget, "
       "lose PageRank and frustrate users.",
       "Update broken links to their correct locations, or remove them; add redirects "
       "where appropriate.",
       help_url=_SF),
    _c("links_internal_redirect", "Links: Internal Redirects (3xx)", "Links", "warning", "low",
       "Internal links pointing at URLs which redirect. Redirect hops add latency for "
       "users and reduce crawl efficiency.",
       "Link directly to the canonical resolving URL instead of through redirects.",
       help_url=_SF),
    _c("links_no_internal_outlinks", "Links: Pages Without Internal Outlinks", "Links",
       "warning", "high",
       "Pages with no links to other internal pages. Search engines have trouble "
       "discovering pages that are not linked, and PageRank cannot flow onwards.",
       "Link to relevant internal pages to help users continue their journey and pass "
       "PageRank onwards. If links are only client-side, render them server-side.",
       help_url=_SF),
    _c("links_no_anchor_text", "Links: Internal Outlinks With No Anchor Text", "Links",
       "opportunity", "low",
       "Internal links without anchor text (or linked images without alt text). Anchor "
       "text gives users and search engines context about the target page.",
       "Add useful, descriptive anchor text (or alt text for linked images).",
       help_url=_SF),
    _c("links_high_external_outlinks", "Links: Pages With High External Outlinks", "Links",
       "warning", "low",
       f"Pages with more than {HIGH_EXTERNAL_OUTLINKS} external outlinks. This can be valid, "
       "but may also indicate link spam or poorly curated content.",
       "Review external links to ensure they are credible, trusted and useful to users.",
       help_url=_SF),
    _c("links_broken_external", "Links: Broken External Links", "Links", "issue", "medium",
       "External outlinks resolving to client or server errors. Broken external links "
       "erode user trust and signal unmaintained content to search engines.",
       "Update or remove links to dead external resources.",
       help_url=_SF),
    _c("links_localhost_or_dev", "Links: Localhost / Development URLs", "Links", "issue", "high",
       "Links pointing at localhost, 127.0.0.1 or private development hosts. These leak "
       "from development environments and are broken for real users.",
       "Replace development URLs with production URLs (relative or absolute).",
       ),

    # =========================================================================
    # CANONICALS
    # =========================================================================
    _c("canonical_missing", "Canonicals: Missing", "Canonicals", "warning", "medium",
       "Pages with no canonical URL (link element or HTTP header). Without one, search "
       "engines pick the version they consider best, which can be unpredictable when "
       "multiple versions exist.",
       "Specify a canonical URL on every indexable page.",
       auto_fixable=True,
       help_url=f"{_GOOGLE}/crawling-indexing/consolidate-duplicate-urls"),
    _c("canonical_canonicalised", "Canonicals: Canonicalised", "Canonicals", "warning", "high",
       "Pages whose canonical points to a different URL, instructing search engines to "
       "consolidate indexing signals elsewhere.",
       "Review carefully to ensure signals consolidate to the correct URL, and link "
       "internally to canonical versions where possible.",
       help_url=_SF),
    _c("canonical_multiple_conflicting", "Canonicals: Multiple Conflicting", "Canonicals",
       "issue", "high",
       "Pages with multiple canonical elements declaring different URLs. Google ignores "
       "all canonical hints when they conflict.",
       "Declare exactly one canonical URL per page.",
       help_url=_SF),
    _c("canonical_relative", "Canonicals: Relative URL", "Canonicals", "warning", "low",
       "Pages whose canonical is a relative URL. Relative canonicals are error-prone and "
       "can resolve to unintended locations (e.g. on protocol or host changes).",
       "Use absolute URLs (including scheme and host) in canonical elements.",
       help_url=_SF),

    # =========================================================================
    # DIRECTIVES
    # =========================================================================
    _c("directive_noindex", "Directives: Noindex", "Directives", "warning", "high",
       "URLs with a 'noindex' directive in a robots meta tag or X-Robots-Tag header. The "
       "page will be dropped from the index.",
       "Review carefully: remove 'noindex' from any page that should rank.",
       help_url=f"{_GOOGLE}/crawling-indexing/block-indexing"),
    _c("directive_nofollow", "Directives: Nofollow", "Directives", "warning", "high",
       "URLs with a 'nofollow' directive in a robots meta tag or X-Robots-Tag header, "
       "which stops PageRank from being passed onwards.",
       "Review carefully: remove 'nofollow' unless links genuinely must not be followed.",
       help_url=_SF),
    _c("directive_meta_refresh", "Directives: Meta Refresh", "Directives", "warning", "medium",
       "Pages using a meta refresh redirect. Meta refresh is slower than HTTP redirects "
       "and is discouraged by search engines.",
       "Replace meta refresh with a server-side 301 redirect.",
       help_url=_SF),

    # =========================================================================
    # HREFLANG
    # =========================================================================
    _c("hreflang_missing_self_reference", "Hreflang: Missing Self Reference", "Hreflang",
       "warning", "low",
       "URLs with hreflang annotations missing their own self-referencing rel=\"alternate\" "
       "hreflang. Google describes a self reference as best practice.",
       "Add a self-referencing hreflang annotation to each page in the set.",
       help_url=f"{_GOOGLE}/specialty/international/localized-versions"),
    _c("hreflang_missing_x_default", "Hreflang: Missing X-Default", "Hreflang", "warning", "low",
       "URLs with hreflang annotations but no x-default fallback for unmatched languages.",
       "Consider an x-default page, especially for language selectors or auto-redirecting "
       "homepages.",
       help_url=_SF),
    _c("hreflang_noindex_return_links", "Hreflang: Noindex Return Links", "Hreflang",
       "issue", "high",
       "Hreflang annotations pointing at URLs which carry a 'noindex' directive. All "
       "pages in an hreflang set should be indexable; noindex members can cause the "
       "whole relationship to be ignored.",
       "Update hreflang annotations to include indexable URLs only.",
       scope="site", help_url=_SF),
    _c("hreflang_invalid_codes", "Hreflang: Incorrect Language & Region Codes", "Hreflang",
       "issue", "high",
       "Hreflang annotations with invalid language (ISO 639-1) or region (ISO 3166-1 "
       "Alpha 2) values, which cannot be used for geotargeting.",
       "Use valid language and optional region codes (e.g. en, en-GB, x-default).",
       help_url=_SF),

    # =========================================================================
    # URL STRUCTURE
    # =========================================================================
    _c("url_underscores", "URL: Underscores", "URL", "opportunity", "low",
       "URLs containing underscores, which are not always treated as word separators by "
       "search engines.",
       "Prefer hyphens as word separators. Changing URLs is a big decision - if changed, "
       "add 301 redirects.",
       help_url=f"{_GOOGLE}/crawling-indexing/url-structure"),
    _c("url_uppercase", "URL: Uppercase Characters", "URL", "opportunity", "low",
       "URLs containing uppercase characters. Mixed-case URLs commonly cause duplicate "
       "content when both cases resolve.",
       "Standardize on lowercase URLs and redirect other variants.",
       help_url=_SF),
    _c("url_parameters", "URL: Parameters", "URL", "warning", "low",
       "URLs containing query parameters. Not a crawl problem at small scale, but "
       "parameterized URLs can be a sign of low value-add duplicates.",
       "Prefer static, parameter-free URLs for key indexable pages.",
       help_url=_SF),
    _c("url_ga_tracking_params", "URL: GA Tracking Parameters", "URL", "warning", "low",
       "Internal URLs containing Google Analytics tracking parameters (utm_, _ga, _gl). "
       "These create duplicate crawlable pages and corrupt session attribution.",
       "Remove tracking parameters from internal links; use event tracking instead.",
       help_url=_SF),
    _c("url_multiple_slashes", "URL: Multiple Slashes", "URL", "issue", "low",
       "URLs with repeated forward slashes in the path (example.com/page1//), usually by "
       "mistake, creating duplicate URLs.",
       "Use a single slash between path sections; 301 redirect malformed variants.",
       help_url=_SF),
    _c("url_over_115_chars", "URL: Over 115 Characters", "URL", "opportunity", "low",
       f"URLs longer than {URL_MAX_CHARS} characters. Research shows users prefer short, "
       "concise URLs.",
       "Use logical, concise URLs. If URLs are changed, add 301 redirects.",
       help_url=_SF),
    _c("url_repetitive_path", "URL: Repetitive Path", "URL", "warning", "low",
       "URLs with repeated path segments (example.com/page1/page2/page1), often pointing "
       "to poor structure or broken relative linking causing infinite URLs.",
       "Review URL structure and fix incorrect relative links; keep URLs concise.",
       help_url=_SF),
    _c("url_non_ascii", "URL: Non-ASCII Characters", "URL", "warning", "low",
       "URLs containing non-ASCII characters which must be percent-encoded and can break "
       "when shared or linked.",
       "Prefer ASCII characters in URLs; ensure proper encoding where non-ASCII is needed.",
       help_url=_SF),
    _c("url_contains_space", "URL: Contains Space", "URL", "issue", "medium",
       "URLs containing unencoded spaces, which break in many clients and crawlers.",
       "Replace spaces with hyphens (or properly encode them) and redirect old URLs.",
       help_url=_SF),

    # =========================================================================
    # SECURITY
    # =========================================================================
    _c("security_http_url", "Security: HTTP URLs", "Security", "issue", "high",
       "Pages served over plain HTTP. HTTPS is a ranking signal and browsers mark HTTP "
       "pages as 'not secure'.",
       "Serve all pages over HTTPS and 301 redirect HTTP to HTTPS.",
       pillar="security", help_url=f"{_GOOGLE}/crawling-indexing/http-https"),
    _c("security_mixed_content", "Security: Mixed Content", "Security", "issue", "high",
       "HTTPS pages loading resources (scripts, styles, images) over insecure HTTP. "
       "Browsers block or warn on mixed content.",
       "Load all subresources over HTTPS.",
       pillar="security", help_url=f"{_MDN}/Web/Security/Mixed_content"),
    _c("security_missing_hsts", "Security: Missing HSTS Header", "Security", "warning", "low",
       "URLs missing the Strict-Transport-Security header, which instructs browsers to "
       "only connect over HTTPS.",
       "Set a Strict-Transport-Security header (e.g. max-age=31536000; includeSubDomains).",
       pillar="security", scope="site", auto_fixable=True,
       help_url=f"{_MDN}/Web/HTTP/Reference/Headers/Strict-Transport-Security"),
    _c("security_missing_csp", "Security: Missing Content-Security-Policy Header", "Security",
       "warning", "low",
       "URLs missing the Content-Security-Policy response header, which guards against "
       "cross-site scripting by controlling which resources may load.",
       "Set a strict Content-Security-Policy response header across all pages.",
       pillar="security", scope="site", auto_fixable=True,
       help_url=f"{_MDN}/Web/HTTP/Guides/CSP"),
    _c("security_missing_x_content_type_options", "Security: Missing X-Content-Type-Options Header",
       "Security", "warning", "low",
       "URLs missing the X-Content-Type-Options: nosniff header, allowing browsers to "
       "MIME-sniff responses away from the declared content type.",
       "Set X-Content-Type-Options: nosniff on all responses.",
       pillar="security", scope="site", auto_fixable=True,
       help_url=f"{_MDN}/Web/HTTP/Reference/Headers/X-Content-Type-Options"),
    _c("security_missing_x_frame_options", "Security: Missing X-Frame-Options Header", "Security",
       "warning", "low",
       "URLs missing X-Frame-Options (or CSP frame-ancestors), leaving pages embeddable "
       "in iframes and exposed to clickjacking.",
       "Set X-Frame-Options: SAMEORIGIN or a CSP frame-ancestors directive.",
       pillar="security", scope="site", auto_fixable=True,
       help_url=f"{_MDN}/Web/HTTP/Reference/Headers/X-Frame-Options"),
    _c("security_missing_referrer_policy", "Security: Missing Secure Referrer-Policy Header",
       "Security", "warning", "low",
       "URLs missing a secure Referrer-Policy (no-referrer-when-downgrade, "
       "strict-origin-when-cross-origin, no-referrer or strict-origin). Full URLs can "
       "leak cross-origin in the Referer header.",
       "Set Referrer-Policy: strict-origin-when-cross-origin.",
       pillar="security", scope="site", auto_fixable=True,
       help_url=f"{_MDN}/Web/HTTP/Reference/Headers/Referrer-Policy"),
    _c("security_unsafe_cross_origin_links", "Security: Unsafe Cross-Origin Links", "Security",
       "warning", "low",
       "Links to external sites using target=\"_blank\" without rel=\"noopener\" (or "
       "noreferrer), exposing the page to reverse tabnabbing in legacy browsers.",
       "Add rel=\"noopener\" to links using target=\"_blank\".",
       pillar="security", auto_fixable=True,
       help_url=f"{_MDN}/Web/HTML/Reference/Attributes/rel/noopener"),
    _c("security_protocol_relative_resources", "Security: Protocol-Relative Resource Links",
       "Security", "warning", "low",
       "Resources loaded via protocol-relative links (//example.com/x.js). This is an "
       "anti-pattern with HTTPS everywhere and can enable man-in-the-middle attacks.",
       "Use absolute HTTPS URLs for all resource links.",
       pillar="security", auto_fixable=True, help_url=_SF),
    _c("security_form_posts_to_http", "Security: Form Posts to HTTP", "Security", "issue", "high",
       "Forms submitting to plain-HTTP endpoints, exposing submitted data on the network.",
       "Point all form actions at HTTPS endpoints.",
       pillar="security"),

    # =========================================================================
    # RESPONSE CODES
    # =========================================================================
    _c("response_internal_3xx", "Response Codes: Internal Redirection (3xx)", "Response Codes",
       "warning", "low",
       "Internal URLs which redirect to another URL. Redirect hops add latency for users "
       "and reduce crawl efficiency.",
       "Link internally to canonical resolving URLs and avoid linking to redirects.",
       help_url=_SF),
    _c("response_internal_4xx", "Response Codes: Internal Client Error (4xx)", "Response Codes",
       "issue", "high",
       "Internal URLs returning client errors (400/403/404/410/429...). The most common "
       "is a 404 broken page.",
       "Fix or redirect erroring URLs and update the links pointing at them.",
       help_url=_SF),
    _c("response_internal_5xx", "Response Codes: Internal Server Error (5xx)", "Response Codes",
       "issue", "high",
       "Internal URLs returning server errors. Persistent 5xx responses cause pages to be "
       "dropped from the index.",
       "Investigate and fix the server-side errors.",
       help_url=_SF),
    _c("response_blocked_by_robots", "Response Codes: Internal Blocked by Robots.txt",
       "Response Codes", "warning", "high",
       "Internal URLs disallowed by robots.txt. They cannot be crawled, which is critical "
       "if the content should be indexed.",
       "Review the disallow rules; allow URLs that should be crawled and remove internal "
       "links to genuinely-blocked URLs.",
       help_url=f"{_GOOGLE}/crawling-indexing/robots/intro"),

    # =========================================================================
    # VALIDATION
    # =========================================================================
    _c("validation_invalid_head_elements", "Validation: Invalid HTML Elements in <head>",
       "Validation", "warning", "high",
       "Pages with invalid elements (e.g. <img>, <iframe>, <div>) inside the <head>. "
       "Google assumes the head ended at the invalid element and ignores everything after "
       "it - including critical meta tags.",
       "Keep only title, meta, link, script, style, base, noscript and template elements "
       "in the <head>.",
       help_url=_SF),
    _c("validation_html_over_2mb", "Validation: HTML Document Over 2MB", "Validation",
       "issue", "high",
       "Pages over 2MB of HTML. Googlebot only indexes the first 2MB of an HTML file.",
       "Reduce document size: move inline CSS/JS to external files and split huge pages.",
       help_url=_SF),
    _c("validation_missing_doctype", "Validation: Missing DOCTYPE", "Validation", "warning", "low",
       "Pages without an HTML doctype declaration, triggering browser quirks mode and "
       "unpredictable rendering.",
       "Start every document with <!DOCTYPE html>.",
       help_url=f"{_MDN}/Glossary/Doctype"),
    _c("validation_missing_charset", "Validation: Missing Character Encoding", "Validation",
       "warning", "medium",
       "Pages without a declared character encoding (meta charset or Content-Type header), "
       "risking mojibake and inconsistent parsing.",
       "Declare <meta charset=\"utf-8\"> as the first element in the <head>.",
       auto_fixable=True, help_url=f"{_MDN}/Web/HTML/Reference/Elements/meta/charset"),
    _c("validation_missing_viewport", "Validation: Missing Viewport Tag", "Validation",
       "issue", "medium",
       "Pages without a viewport meta tag. Mobile rendering falls back to desktop width, "
       "harming mobile usability - a ranking factor under mobile-first indexing.",
       "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">.",
       auto_fixable=True, help_url=f"{_GOOGLE}/crawling-indexing/mobile/mobile-sites-mobile-first-indexing"),
    _c("validation_missing_lang", "Validation: Missing Lang Attribute", "Validation",
       "warning", "medium",
       "Pages whose <html> element has no lang attribute. Screen readers and search "
       "engines use it to determine the page language.",
       "Add a lang attribute to the <html> element (e.g. <html lang=\"en\">).",
       auto_fixable=True, help_url=f"{_MDN}/Web/HTML/Reference/Global_attributes/lang"),
    _c("validation_missing_favicon", "Validation: Missing Favicon", "Validation",
       "opportunity", "low",
       "No favicon was discovered. Favicons appear in browser tabs, bookmarks and Google's "
       "mobile search results.",
       "Add a favicon and declare it with a <link rel=\"icon\"> element.",
       scope="site", help_url=f"{_GOOGLE}/appearance/favicon-in-search"),

    # =========================================================================
    # PERFORMANCE
    # =========================================================================
    _c("performance_slow_response", "Performance: Slow Response Time", "Performance",
       "warning", "medium",
       f"Pages taking over {SLOW_RESPONSE_MS / 1000:.0f} seconds to respond. Slow server "
       "responses harm user experience, crawl budget and Core Web Vitals.",
       "Investigate server-side latency: caching, database queries, third-party calls "
       "and hosting capacity.",
       help_url=f"{_GOOGLE}/crawling-indexing/website-management"),

    # =========================================================================
    # PAGINATION
    # =========================================================================
    _c("pagination_url_not_in_anchor", "Pagination: Pagination URL Not in Anchor Tag",
       "Pagination", "issue", "high",
       "URLs referenced in rel=\"next\"/rel=\"prev\" that are not also linked via a normal "
       "<a href> on the page. Users cannot navigate and PageRank cannot flow.",
       "Link paginated URLs with regular anchor elements as well.",
       help_url=_SF),

    # =========================================================================
    # SOCIAL SHARING
    # =========================================================================
    _c("social_missing_open_graph", "Social: Missing Open Graph Tags", "Social",
       "opportunity", "medium",
       "Pages without Open Graph tags (og:title, og:description, og:image). Shares on "
       "social platforms and chat apps render without a rich preview, lowering CTR.",
       "Add og:title, og:description, og:image and og:url meta tags.",
       pillar="social", auto_fixable=True, help_url="https://ogp.me/"),
    _c("social_incomplete_open_graph", "Social: Incomplete Open Graph Tags", "Social",
       "opportunity", "low",
       "Pages with some Open Graph tags but missing og:title, og:description or og:image.",
       "Complete the Open Graph set so previews render fully on every platform.",
       pillar="social", help_url="https://ogp.me/"),
    _c("social_missing_twitter_card", "Social: Missing Twitter Card", "Social",
       "opportunity", "low",
       "Pages without a twitter:card meta tag; X/Twitter shares fall back to a bare link.",
       "Add <meta name=\"twitter:card\" content=\"summary_large_image\"> plus title, "
       "description and image tags.",
       pillar="social", auto_fixable=True,
       help_url="https://developer.x.com/en/docs/x-for-websites/cards/overview/markup"),

    # =========================================================================
    # AIO - STRUCTURED DATA & ANSWER-ENGINE READINESS
    # =========================================================================
    _c("aio_no_structured_data", "AIO: No Structured Data", "Structured Data",
       "opportunity", "high",
       "Pages with no JSON-LD structured data. Schema.org markup powers rich results and "
       "is a primary input for AI Overviews and answer engines to understand entities.",
       "Add JSON-LD structured data describing the page's primary entity (Article, "
       "Product, Organization, FAQPage, HowTo...).",
       pillar="aio", help_url=f"{_GOOGLE}/appearance/structured-data/intro-structured-data"),
    _c("aio_invalid_json_ld", "AIO: Invalid JSON-LD", "Structured Data", "issue", "high",
       "Pages with JSON-LD blocks that fail to parse. Broken structured data is ignored "
       "entirely by search engines and AI systems.",
       "Fix the JSON syntax; validate with the Rich Results Test or schema.org validator.",
       pillar="aio", help_url="https://validator.schema.org/"),
    _c("aio_missing_organization_schema", "AIO: Missing Organization Schema", "Structured Data",
       "opportunity", "medium",
       "No Organization (or WebSite) schema found anywhere on the site. Entity-level "
       "markup helps AI systems attribute content to a verified organization (E-E-A-T).",
       "Add Organization JSON-LD (name, url, logo, sameAs) on the homepage.",
       pillar="aio", scope="site", help_url=f"{_SCHEMA}/Organization"),
    _c("aio_missing_breadcrumb_schema", "AIO: Missing Breadcrumb Schema", "Structured Data",
       "opportunity", "low",
       "Pages without BreadcrumbList schema. Breadcrumbs help search and answer engines "
       "understand site hierarchy and display better result paths.",
       "Add BreadcrumbList JSON-LD reflecting the page's position in the site.",
       pillar="aio", help_url=f"{_GOOGLE}/appearance/structured-data/breadcrumb"),
    _c("aio_faq_content_without_schema", "AIO: FAQ Content Without FAQ Schema", "Structured Data",
       "opportunity", "medium",
       "Pages whose headings are question-styled (what/how/why...) but carry no FAQPage or "
       "QAPage schema. Question content is prime AI Overview material when marked up.",
       "Add FAQPage JSON-LD pairing each question heading with its answer.",
       pillar="aio", help_url=f"{_SCHEMA}/FAQPage"),
    _c("aio_missing_article_dates", "AIO: Missing Article Dates", "Structured Data",
       "opportunity", "low",
       "Article-like pages without datePublished/dateModified metadata. Freshness signals "
       "strongly influence whether AI Overviews cite a page.",
       "Add datePublished and dateModified to Article schema (and visible bylines).",
       pillar="aio", help_url=f"{_SCHEMA}/Article"),
    _c("aio_missing_author_markup", "AIO: Missing Author Markup", "Structured Data",
       "opportunity", "low",
       "Article-like pages without author metadata. Authorship is a core E-E-A-T signal "
       "for both classic ranking and AI citation.",
       "Add author Person schema (name, url) to articles and show visible bylines.",
       pillar="aio", help_url=f"{_SCHEMA}/Person"),

    # =========================================================================
    # GEO - GENERATIVE ENGINE OPTIMIZATION
    # =========================================================================
    _c("geo_missing_robots_txt", "GEO: Missing robots.txt", "GEO", "warning", "medium",
       "No robots.txt found. Crawlers (search and AI) fall back to default behavior and "
       "you lose the ability to declare sitemaps and per-bot policies.",
       "Add a robots.txt declaring crawl policy and the sitemap location.",
       pillar="geo", scope="site", auto_fixable=True,
       help_url=f"{_GOOGLE}/crawling-indexing/robots/intro"),
    _c("geo_missing_sitemap", "GEO: Missing XML Sitemap", "GEO", "issue", "medium",
       "No XML sitemap found. Sitemaps are the primary discovery mechanism for search "
       "engines and many AI crawlers.",
       "Generate a sitemap.xml of canonical URLs and reference it from robots.txt.",
       pillar="geo", scope="site", auto_fixable=True,
       help_url=f"{_GOOGLE}/crawling-indexing/sitemaps/overview"),
    _c("geo_sitemap_not_in_robots", "GEO: Sitemap Not Declared in robots.txt", "GEO",
       "opportunity", "low",
       "A sitemap exists but robots.txt does not declare it, so crawlers that only read "
       "robots.txt will not discover it.",
       "Add a 'Sitemap: <absolute-url>' line to robots.txt.",
       pillar="geo", scope="site", auto_fixable=True,
       help_url=f"{_GOOGLE}/crawling-indexing/sitemaps/build-sitemap"),
    _c("geo_missing_llms_txt", "GEO: Missing llms.txt", "GEO", "opportunity", "medium",
       "No llms.txt found. llms.txt is an emerging standard that gives LLMs and AI agents "
       "a curated, markdown map of your most important content - improving how AI systems "
       "summarize and cite the site.",
       "Add /llms.txt with a short site description and links to key pages and docs.",
       pillar="geo", scope="site", auto_fixable=True, help_url="https://llmstxt.org/"),
    _c("geo_ai_crawlers_blocked", "GEO: AI Crawlers Blocked by robots.txt", "GEO",
       "warning", "high",
       "robots.txt disallows one or more AI crawlers (GPTBot, ClaudeBot, PerplexityBot, "
       "Google-Extended...). Blocked engines cannot read - or cite - the site in AI "
       "answers, eliminating generative-search visibility.",
       "If AI visibility is desired, allow the AI user-agents in robots.txt. Blocking may "
       "be intentional for content protection - confirm it matches business strategy.",
       pillar="geo", scope="site", help_url="https://platform.openai.com/docs/bots"),
    _c("geo_missing_rss_feed", "GEO: Missing RSS/Atom Feed", "GEO", "opportunity", "low",
       "No RSS/Atom feed discovered. Feeds help aggregators and AI systems track fresh "
       "content and surface it quickly.",
       "Publish an RSS/Atom feed and declare it with <link rel=\"alternate\">.",
       pillar="geo", scope="site"),
    _c("geo_no_semantic_landmarks", "GEO: No Semantic HTML Landmarks", "GEO",
       "opportunity", "low",
       "Pages built without semantic HTML5 landmarks (<main>, <article>, <nav>, <header>, "
       "<footer>). Answer engines extract content far more reliably from semantic markup "
       "than from anonymous <div> soup.",
       "Structure pages with semantic HTML5 landmark elements.",
       pillar="geo", help_url=f"{_MDN}/Web/HTML/Reference/Elements"),
    _c("geo_missing_heading_anchors", "GEO: Headings Without Anchor IDs", "GEO",
       "opportunity", "low",
       "Section headings lack id attributes, so deep links to specific passages are "
       "impossible. Citable fragments improve how AI answers and SERP features link in.",
       "Add stable id attributes to h2/h3 headings to enable deep links.",
       pillar="geo"),
]


# Public catalog: code -> definition (validated unique at import time).
CHECKS: Dict[str, SeoCheckDefinition] = {}
for _check in _ALL_CHECKS:
    if _check.code in CHECKS:
        raise RuntimeError(f"Duplicate SEO check code: {_check.code}")
    CHECKS[_check.code] = _check


def get_check(code: str) -> SeoCheckDefinition:
    """Return the catalog definition for a check code (raises KeyError if unknown)."""
    return CHECKS[code]


def list_checks() -> List[SeoCheckDefinition]:
    """Return all check definitions."""
    return list(CHECKS.values())


def auto_fixable_checks() -> List[SeoCheckDefinition]:
    """Return checks the repo-aware fixer can remediate."""
    return [c for c in CHECKS.values() if c.auto_fixable]
