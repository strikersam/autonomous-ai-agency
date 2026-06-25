#!/usr/bin/env python3
"""
scripts/run_seo_audit.py — Parameterised full-site SEO / GEO / AEO / AIO audit.

Crawls any public website using Chrome TLS impersonation (curl_cffi), runs the
full seo_audit check catalog, and writes an executive PDF + CSV/JSON/MD files.

Usage:
    python scripts/run_seo_audit.py --website-url https://www.example.com

See --help for all options or read .claude/skills/seo-audit-report/SKILL.md.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, Tuple
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seo_audit_runner")


# ---------------------------------------------------------------------------
# curl_cffi fetcher (Chrome TLS impersonation — bypasses Akamai / Cloudflare)
# ---------------------------------------------------------------------------
def _build_curl_cffi_fetcher():  # type: ignore[return]
    """Return a PageFetcher that uses curl_cffi for all requests."""
    try:
        import curl_cffi.requests as cr
    except ImportError as exc:
        log.error("curl_cffi not installed: %s", exc)
        sys.exit(1)

    from services.seo_fetch import FetchResult

    class CurlCffiPageFetcher:
        """PageFetcher using curl_cffi Chrome-120 TLS impersonation."""

        def __init__(self, *, timeout: float, user_agent: str, concurrency: int = 5) -> None:
            self._timeout = timeout
            self._ua = user_agent
            self._sem = asyncio.Semaphore(concurrency)
            self._session: cr.AsyncSession | None = None

        async def _sess(self) -> cr.AsyncSession:
            if self._session is None:
                self._session = cr.AsyncSession(impersonate="chrome120")
            return self._session

        async def get(self, url: str) -> FetchResult:
            async with self._sem:
                t0 = time.monotonic()
                try:
                    sess = await self._sess()
                    r = await asyncio.wait_for(
                        sess.get(url, timeout=self._timeout, allow_redirects=True),
                        timeout=self._timeout + 5,
                    )
                    headers = {k.lower(): v for k, v in r.headers.items()}
                    headers.setdefault("content-type", "text/html")
                    return FetchResult(
                        requested_url=url,
                        final_url=str(r.url),
                        status_code=r.status_code,
                        first_status=r.status_code,
                        headers=headers,
                        text=r.text,
                        elapsed_ms=int((time.monotonic() - t0) * 1000),
                        via="curl_cffi",
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning("GET failed %s: %s", url, exc)
                    return FetchResult(
                        requested_url=url,
                        final_url=url,
                        status_code=0,
                        first_status=0,
                        headers={},
                        text="",
                        elapsed_ms=int((time.monotonic() - t0) * 1000),
                        via="curl_cffi",
                    )

        async def get_text(self, url: str) -> Tuple[str, int]:
            r = await self.get(url)
            return r.text, r.status_code

        async def head(self, url: str) -> Tuple[Dict[str, str], int]:
            async with self._sem:
                try:
                    sess = await self._sess()
                    r = await asyncio.wait_for(
                        sess.head(url, timeout=self._timeout, allow_redirects=True),
                        timeout=self._timeout + 5,
                    )
                    return {k.lower(): v for k, v in r.headers.items()}, r.status_code
                except Exception as exc:  # noqa: BLE001
                    log.warning("HEAD failed %s: %s", url, exc)
                    return {}, 0

        async def aclose(self) -> None:
            if self._session is not None:
                await self._session.close()

    return CurlCffiPageFetcher


# ---------------------------------------------------------------------------
# PDF builder (reportlab)
# ---------------------------------------------------------------------------
def _build_pdf(report_data: dict, output_path: Path, website_url: str) -> None:
    """Render an executive-level PDF from the audit report dict."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            HRFlowable,
            KeepTogether,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        log.warning("reportlab not installed — skipping PDF generation (pip install reportlab)")
        return

    W, H = A4
    GUCCI_BLACK = colors.HexColor("#1a1a1a")
    GOLD        = colors.HexColor("#C6963A")
    LIGHT_GRAY  = colors.HexColor("#F5F1EC")
    MID_GRAY    = colors.HexColor("#CCCCCC")
    DARK_GRAY   = colors.HexColor("#555555")
    RED         = colors.HexColor("#C0392B")
    ORANGE      = colors.HexColor("#E67E22")
    GREEN       = colors.HexColor("#27AE60")

    def score_color(s: float) -> object:
        if s >= 80: return GREEN
        if s >= 60: return ORANGE
        return RED

    def S(name: str, **kw: object) -> ParagraphStyle:  # noqa: N802
        return ParagraphStyle(name, **kw)  # type: ignore[arg-type]

    sTitle  = S("T",  fontName="Helvetica-Bold",   fontSize=26, textColor=GUCCI_BLACK, spaceAfter=6,  leading=32)
    sSub    = S("Su", fontName="Helvetica",         fontSize=12, textColor=DARK_GRAY,   spaceAfter=4,  leading=16)
    sSec    = S("Se", fontName="Helvetica-Bold",    fontSize=13, textColor=GUCCI_BLACK, spaceBefore=14,spaceAfter=4,  leading=17)
    sBody   = S("B",  fontName="Helvetica",         fontSize=9,  textColor=GUCCI_BLACK, spaceAfter=4,  leading=13)
    sSmall  = S("Sm", fontName="Helvetica",         fontSize=8,  textColor=DARK_GRAY,   spaceAfter=2,  leading=11)
    sNote   = S("N",  fontName="Helvetica-Oblique", fontSize=8,  textColor=DARK_GRAY,   leftIndent=10, spaceAfter=6,  leading=12)
    sTC     = S("TC", fontName="Helvetica",         fontSize=8,  textColor=GUCCI_BLACK, leading=11)
    sTCS    = S("TCS",fontName="Helvetica",         fontSize=7,  textColor=DARK_GRAY,   leading=10)

    def hr(gold: bool = False) -> HRFlowable:
        return HRFlowable(width="100%", thickness=2 if gold else 0.5,
                          color=GOLD if gold else MID_GRAY, spaceAfter=8, spaceBefore=4)

    def section(txt: str) -> list:
        return [Spacer(1, 4), Paragraph(txt.upper(), sSec), hr(gold=True)]

    rows           = report_data.get("rows", [])
    health_score   = report_data.get("health_score", 0)
    pillar_scores  = report_data.get("pillar_scores", {})
    pages_crawled  = report_data.get("pages_crawled", 0)
    pages_failed   = report_data.get("pages_failed", 0)
    ibp            = report_data.get("issues_by_priority", {})
    audit_id       = report_data.get("audit_id", "")
    summary_txt    = report_data.get("summary", "")

    high_rows   = [r for r in rows if r.get("issue_priority") == "high"]
    medium_rows = [r for r in rows if r.get("issue_priority") == "medium"]
    low_rows    = [r for r in rows if r.get("issue_priority") == "low"]

    story: list = []

    # ── Cover ──────────────────────────────────────────────────────────────
    story.append(Spacer(1, 2*cm))
    story.append(HRFlowable(width="100%", thickness=6, color=GOLD, spaceAfter=16))
    domain = urlparse(website_url).netloc or website_url
    story.append(Paragraph(domain.upper(), sTitle))
    story.append(Paragraph("Full-Site SEO / GEO / AEO / AIO Audit", sSub))
    story.append(Paragraph("Executive Report", S("_", fontName="Helvetica-Oblique",
        fontSize=10, textColor=DARK_GRAY, spaceAfter=2)))
    story.append(Spacer(1, 0.6*cm))
    story.append(hr())

    meta = [
        ["Overall Health Score", f"{health_score}/100"],
        ["Pages Crawled", str(pages_crawled)],
        ["Pages Failed",  str(pages_failed)],
        ["High-Priority Occurrences", str(ibp.get("high", 0))],
        ["Total Finding Occurrences", str(sum(ibp.values()))],
        ["Audit Date", datetime.date.today().strftime("%B %d, %Y")],
        ["Audit ID",   audit_id[:28] + "..." if len(audit_id) > 28 else audit_id],
    ]
    mt = Table(meta, colWidths=[8*cm, 8*cm])
    mt.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), GUCCI_BLACK),
        ("TEXTCOLOR",     (0, 0), (-1, -1), colors.white),
        ("FONTNAME",      (0, 0), (0, -1),  "Helvetica-Bold"),
        ("FONTNAME",      (1, 0), (1, -1),  "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("TEXTCOLOR",     (1, 0), (1, 0),   score_color(health_score)),
        ("FONTNAME",      (1, 0), (1, 0),   "Helvetica-Bold"),
        ("FONTSIZE",      (1, 0), (1, 0),   14),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#404040")),
    ]))
    story.append(mt)
    story.append(Spacer(1, 0.8*cm))

    pillar_order  = ["technical", "content", "security", "social", "geo", "aio"]
    pillar_labels = {"technical": "Technical SEO", "content": "Content Quality",
                     "security": "Security & Headers", "social": "Social / OGP",
                     "geo": "GEO (AI Crawlability)", "aio": "AIO (AI Answerability)"}
    pr = [["Pillar", "Score", "Status"]]
    for p in pillar_order:
        sc = pillar_scores.get(p, 0)
        pr.append([pillar_labels.get(p, p), f"{sc}/100",
                   "Good" if sc >= 80 else ("Needs Work" if sc >= 60 else "Critical")])
    pt = Table(pr, colWidths=[7*cm, 4*cm, 5*cm])
    pts: list = [
        ("BACKGROUND",    (0, 0), (-1, 0),  GUCCI_BLACK),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ALIGN",         (1, 0), (2, -1),  "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [LIGHT_GRAY, colors.white]),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("GRID",          (0, 0), (-1, -1), 0.3, MID_GRAY),
    ]
    for i, p in enumerate(pillar_order, 1):
        col = score_color(pillar_scores.get(p, 0))
        pts += [("TEXTCOLOR", (1, i), (2, i), col),
                ("FONTNAME",  (1, i), (1, i), "Helvetica-Bold")]
    pt.setStyle(TableStyle(pts))
    story.append(pt)
    story.append(Spacer(1, 0.8*cm))
    story.append(hr())
    story.append(Paragraph(
        "Methodology: crawled via curl_cffi Chrome-120 TLS impersonation (bypasses bot protection). "
        "Revenue-at-risk figures are model estimates (saturating exponential); not measured losses.",
        sSmall))
    story.append(PageBreak())

    # ── Executive Summary ──────────────────────────────────────────────────
    story += section("Executive Summary")
    story.append(Paragraph(summary_txt, sBody))
    story.append(Spacer(1, 0.3*cm))

    # Top findings table
    top = high_rows[:5]
    if top:
        story.append(Paragraph("Top High-Priority Findings", S("_",
            fontName="Helvetica-Bold", fontSize=10, textColor=GUCCI_BLACK, spaceAfter=4)))
        td = [["Finding", "URLs", "%", "Pillar", "Fix"]]
        for r in top:
            td.append([
                Paragraph(r.get("issue_name", ""), sTC),
                str(r.get("urls_affected", 0)),
                f"{r.get('percent_of_total', 0):.1f}%",
                r.get("pillar", "").upper(),
                Paragraph(r.get("how_to_fix", "")[:80], sTCS),
            ])
        tt = Table(td, colWidths=[4.5*cm, 1.4*cm, 1.4*cm, 1.6*cm, 7.1*cm])
        tt.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  RED),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [LIGHT_GRAY, colors.white]),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("GRID",          (0, 0), (-1, -1), 0.3, MID_GRAY),
            ("ALIGN",         (1, 0), (3, -1),  "CENTER"),
        ]))
        story.append(tt)
    story.append(PageBreak())

    # ── Full Findings ──────────────────────────────────────────────────────
    story += section("Full Findings by Priority")

    def findings_block(frows: list, label: str, col: object) -> list:
        if not frows:
            return []
        out: list = [Paragraph(f"● {label}", S("_", fontName="Helvetica-Bold",
            fontSize=10, textColor=col, spaceAfter=4, spaceBefore=8))]
        fd = [["Finding", "Type", "URLs", "%", "Pillar", "Auto-fix"]]
        for r in frows:
            fd.append([
                Paragraph(r.get("issue_name", ""), sTC),
                r.get("issue_type", ""),
                str(r.get("urls_affected", 0)),
                f"{r.get('percent_of_total', 0):.1f}%",
                r.get("pillar", "").upper(),
                "✓" if r.get("auto_fixable") else "",
            ])
        ft = Table(fd, colWidths=[6*cm, 1.8*cm, 1.4*cm, 1.4*cm, 1.6*cm, 1.8*cm])
        ft.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  col),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [LIGHT_GRAY, colors.white]),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("GRID",          (0, 0), (-1, -1), 0.3, MID_GRAY),
            ("ALIGN",         (2, 0), (-1, -1), "CENTER"),
            ("TEXTCOLOR",     (5, 1), (5, -1),  GREEN),
            ("FONTNAME",      (5, 1), (5, -1),  "Helvetica-Bold"),
        ]))
        out.append(ft)
        return out

    story += findings_block(high_rows,   "HIGH PRIORITY",              RED)
    story += findings_block(medium_rows, "MEDIUM PRIORITY",            ORANGE)
    story.append(PageBreak())
    story += findings_block(low_rows,    "LOW PRIORITY / OPPORTUNITIES", GREEN)
    story.append(PageBreak())

    # ── Methodology ────────────────────────────────────────────────────────
    story += section("Methodology & Limitations")
    story.append(Paragraph("<b>Crawl Method</b>",
        S("_", fontName="Helvetica-Bold", fontSize=9, textColor=GUCCI_BLACK, spaceAfter=2)))
    story.append(Paragraph(
        "Pages fetched via curl_cffi Chrome-120 TLS impersonation. "
        "Playwright browser mode used when system libraries are available; curl_cffi is the "
        "automatic fallback and handles most enterprise bot-protection layers.",
        sBody))
    story.append(Paragraph("<b>Revenue-at-Risk Disclaimer (load-bearing)</b>",
        S("_", fontName="Helvetica-Bold", fontSize=9, textColor=GUCCI_BLACK, spaceAfter=2)))
    story.append(Paragraph(
        "How this figure is derived: share = 0.35 × (1 − e^(−pressure/50)) applied to aggregate "
        "issue severity pressure. These are model estimates of proportional organic revenue "
        "exposure — NOT measured revenue losses. Do not present as measured losses.",
        sNote))
    story.append(Spacer(1, 0.5*cm))
    story.append(hr(gold=True))
    story.append(Paragraph(
        f"Report generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M UTC')}  |  "
        f"Audit ID: {audit_id}  |  Engine: autonomous-ai-agency",
        sSmall))

    # ── Build ──────────────────────────────────────────────────────────────
    def header_footer(canvas: object, doc: object) -> None:  # type: ignore[type-arg]
        canvas.saveState()  # type: ignore[attr-defined]
        canvas.setFillColor(GUCCI_BLACK)  # type: ignore[attr-defined]
        canvas.rect(0, 0, W, 1.1*cm, fill=1, stroke=0)  # type: ignore[attr-defined]
        canvas.setFillColor(colors.white)  # type: ignore[attr-defined]
        canvas.setFont("Helvetica", 8)  # type: ignore[attr-defined]
        canvas.drawString(1*cm, 0.4*cm,  # type: ignore[attr-defined]
            f"SEO / GEO / AIO AUDIT — {domain.upper()} — CONFIDENTIAL")
        canvas.drawRightString(W - 1*cm, 0.4*cm, f"Page {doc.page}")  # type: ignore[attr-defined]
        canvas.setFillColor(GOLD)  # type: ignore[attr-defined]
        canvas.rect(0, H - 0.25*cm, W, 0.25*cm, fill=1, stroke=0)  # type: ignore[attr-defined]
        canvas.restoreState()  # type: ignore[attr-defined]

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.5*cm, bottomMargin=1.8*cm,
        title=f"{domain} SEO/GEO/AIO Audit — Executive Report",
        author="autonomous-ai-agency",
    )
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    log.info("PDF written: %s", output_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def run_audit(args: argparse.Namespace) -> int:
    """Run the full audit and write output files. Returns exit code."""
    import services.seo_audit as seo_audit_mod
    from models.seo_audit import SeoAuditRequest
    from services.seo_audit import (
        SeoAuditEngine,
        report_to_csv,
        report_to_issues_csv,
        report_to_markdown,
        report_to_pages_csv,
    )

    # Patch make_fetcher to use curl_cffi (bypasses bot walls).
    # We patch the local name in seo_audit because it imports make_fetcher
    # directly: `from services.seo_fetch import make_fetcher`.
    FetcherClass = _build_curl_cffi_fetcher()

    def patched_make_fetcher(
        *,
        fetch_mode: str,
        timeout: float,
        user_agent: str,
        transport: object = None,
        concurrency: int = 5,
    ) -> object:
        log.info("Using CurlCffiPageFetcher (Chrome-120 TLS impersonation)")
        return FetcherClass(timeout=timeout, user_agent=user_agent, concurrency=concurrency)

    seo_audit_mod.make_fetcher = patched_make_fetcher  # type: ignore[attr-defined]

    request = SeoAuditRequest(
        website_url=args.website_url,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        fetch_mode="browser",
        timeout_seconds=args.timeout_seconds,
        include_sitemap=True,
        respect_robots=True,
        check_image_sizes=args.check_image_sizes,
        monthly_organic_revenue=args.monthly_organic_revenue,
    )

    log.info("Starting SEO audit: %s  (max_pages=%d, max_depth=%d)",
             args.website_url, args.max_pages, args.max_depth)
    report = await SeoAuditEngine().run(request)
    log.info("Audit complete — status=%s  pages=%d  health_score=%s",
             report.status, report.pages_crawled, report.health_score)

    # Verify bypass quality
    pages = report.pages or []
    blocked = [p for p in pages if getattr(p, "status_code", 200) in (401, 403, 406, 429, 503)]
    ok_200  = [p for p in pages if getattr(p, "status_code", 0) == 200]
    log.info("Pages 200: %d | blocked: %d | other: %d",
             len(ok_200), len(blocked), len(pages) - len(ok_200) - len(blocked))
    if len(blocked) > len(ok_200):
        log.warning(
            "More blocked responses than successful ones — "
            "bot-wall may not be fully bypassed. Report findings as-is."
        )

    # Output directory & file stems
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    domain_slug = re.sub(r"[^\w\-]", "_", urlparse(args.website_url).netloc or "site")

    # Write data files
    json_path   = output_dir / f"{domain_slug}_report.json"
    md_path     = output_dir / f"{domain_slug}_report.md"
    csv_path    = output_dir / f"{domain_slug}_findings.csv"
    pages_path  = output_dir / f"{domain_slug}_pages.csv"
    issues_path = output_dir / f"{domain_slug}_issues.csv"
    pdf_path    = output_dir / f"{domain_slug}_seo_audit.pdf"

    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(report_to_markdown(report), encoding="utf-8")
    csv_path.write_text(report_to_csv(report), encoding="utf-8")
    pages_path.write_text(report_to_pages_csv(report), encoding="utf-8")
    issues_path.write_text(report_to_issues_csv(report), encoding="utf-8")

    log.info("Data files written to %s", output_dir)

    # Build PDF
    _build_pdf(
        report_data=report.model_dump(),
        output_path=pdf_path,
        website_url=args.website_url,
    )

    # Summary
    print("\n" + "=" * 60)
    print(f"SEO AUDIT COMPLETE — {args.website_url}")
    print("=" * 60)
    print(f"  Health score : {report.health_score}/100")
    print(f"  Status       : {report.status}")
    print(f"  Pages crawled: {report.pages_crawled}  (failed: {report.pages_failed})")
    print(f"  Pages 200    : {len(ok_200)}  |  blocked: {len(blocked)}")
    print(f"  Pillar scores: {report.pillar_scores}")
    print(f"  Summary      : {report.summary}")
    print(f"  Output dir   : {output_dir.resolve()}")
    print("=" * 60 + "\n")

    return 0 if report.status == "success" else 1


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Full-site SEO / GEO / AEO / AIO audit with executive PDF output.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--website-url",  required=True,
                   help="Full URL of the site to audit (e.g. https://www.example.com)")
    p.add_argument("--max-pages",    type=int,   default=100,
                   help="Crawl budget in pages")
    p.add_argument("--max-depth",    type=int,   default=3,
                   help="Maximum link-follow depth")
    p.add_argument("--output-dir",   default="./seo-audit-output",
                   help="Directory for output files")
    p.add_argument("--timeout-seconds", type=float, default=30,
                   help="Per-page fetch timeout in seconds")
    p.add_argument("--monthly-organic-revenue", type=float, default=0,
                   help="Monthly organic revenue baseline (0 = unknown; leave at 0 if unsure)")
    p.add_argument("--check-image-sizes",  action="store_true",  default=True,
                   help="HEAD-request images to determine their sizes (default: on)")
    p.add_argument("--no-check-image-sizes", dest="check_image_sizes", action="store_false",
                   help="Skip image size checks (faster crawl)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return asyncio.run(run_audit(args))


if __name__ == "__main__":
    sys.exit(main())
