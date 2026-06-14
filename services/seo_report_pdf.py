"""
services/seo_report_pdf.py - CTO-level PDF export for SEO/GEO/AEO/AIO audits

Renders a ``SeoAuditReport`` (models/seo_audit.py) into a multi-section PDF:

- Cover page (audit metadata, revenue baseline, disclaimer)
- Executive summary (pillar scores, $ at risk by priority, top findings)
- Methodology & revenue-model explainer (formula + sensitivity table)
- One deep-dive section per pillar (technical/content/aio/geo/social/security)
  with a findings table and the engine's own delegation-plan instructions as
  "recommended fix" text
- Appendix A: full findings table
- Appendix B: WSJF-prioritised fix roadmap
- Appendix C: worst pages by issue count

Everything is generated from the report object itself - there is no
per-company or per-category hardcoded prose. ``SeoDelegationTask.instructions``
(already produced dynamically by ``SeoAuditEngine._build_delegation_plan``)
supplies the "recommended fix" text for every finding category, so this
module works the same way for any audited site, with or without a revenue
baseline.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from html import escape as _esc

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from models.seo_audit import SeoAuditReport, SeoDelegationTask, SeoIssueReportRow
from services.seo_audit import (
    MAX_REVENUE_LOSS_SHARE,
    REVENUE_PRESSURE_SCALE,
    compute_pressure,
    loss_share_from_pressure,
)

# =============================================================================
# COLORS / LABELS
# =============================================================================

BRAND = colors.HexColor("#1f3a5f")
BRAND_HEX = "#1f3a5f"
ACCENT = colors.HexColor("#b9770e")
LIGHT_BG = colors.HexColor("#f4f6f8")
GRID_COLOR = colors.HexColor("#d0d5dc")
MUTED_HEX = "#5d6d7e"

PRIORITY_HEX = {"high": "#c0392b", "medium": "#b9770e", "low": MUTED_HEX}

PILLAR_LABELS = {
    "technical": "SEO — Technical (Crawlability, Indexation & On-Page Structure)",
    "content": "SEO — Content",
    "aio": "AEO / AIO — Structured Data & Answer-Engine Readiness",
    "geo": "GEO — Generative Engine Optimization",
    "social": "Social — Share Previews (AEO-adjacent)",
    "security": "Security",
}
PILLAR_ORDER = ["technical", "content", "aio", "geo", "social", "security"]

# Usable content width on a US-Letter page with 0.75" margins.
_PAGE_W = 7.0 * inch


def money(value: float) -> str:
    return f"${value:,.0f}"


# =============================================================================
# STYLES & TABLE FORMATTING
# =============================================================================

def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("CoverTitle", parent=ss["Title"], fontSize=24, leading=28,
                           textColor=BRAND, spaceAfter=6))
    ss.add(ParagraphStyle("CoverSub", parent=ss["Normal"], fontSize=13, leading=16,
                           textColor=colors.HexColor(MUTED_HEX), spaceAfter=4))
    ss.add(ParagraphStyle("CoverMeta", parent=ss["Normal"], fontSize=10, leading=14))
    ss.add(ParagraphStyle("H1", parent=ss["Heading1"], fontSize=17, leading=21,
                           textColor=BRAND, spaceBefore=2, spaceAfter=8))
    ss.add(ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13, leading=17,
                           textColor=BRAND, spaceBefore=10, spaceAfter=6))
    ss.add(ParagraphStyle("H3", parent=ss["Heading3"], fontSize=11, leading=14,
                           textColor=ACCENT, spaceBefore=8, spaceAfter=3))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=9.5, leading=13.5,
                           spaceAfter=4))
    ss.add(ParagraphStyle("BodySmall", parent=ss["Normal"], fontSize=8.5, leading=12,
                           textColor=colors.HexColor(MUTED_HEX), spaceAfter=3))
    ss.add(ParagraphStyle("Cell", parent=ss["Normal"], fontSize=7, leading=9))
    ss.add(ParagraphStyle("CellBold", parent=ss["Normal"], fontSize=7, leading=9,
                           fontName="Helvetica-Bold", textColor=colors.white))
    ss.add(ParagraphStyle("FixBullet", parent=ss["Normal"], fontSize=8.5, leading=12))
    ss.add(ParagraphStyle("Disclaimer", parent=ss["Normal"], fontSize=8.5, leading=12,
                           textColor=colors.HexColor(MUTED_HEX), borderColor=GRID_COLOR,
                           borderWidth=0.5, borderPadding=6, backColor=LIGHT_BG))
    return ss


_TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BRAND),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 7),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
    ("GRID", (0, 0), (-1, -1), 0.5, GRID_COLOR),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
])

_META_TABLE_STYLE = TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#e3e7eb")),
])


def _cell(value, styles, bold=False) -> Paragraph:
    style = styles["CellBold"] if bold else styles["Cell"]
    return Paragraph(_esc(str(value)), style)


def _findings_table(rows: list[SeoIssueReportRow], styles, revenue_modeled: bool) -> Table:
    if revenue_modeled:
        header = ["Priority", "Type", "Issue", "URLs", "%", "$/mo at risk", "Auto-fix"]
        col_widths = [0.70, 0.80, 3.00, 0.50, 0.50, 0.85, 0.65]
    else:
        header = ["Priority", "Type", "Issue", "URLs", "%", "Auto-fix"]
        col_widths = [0.75, 0.85, 3.60, 0.55, 0.55, 0.70]
    data = [[Paragraph(h, styles["CellBold"]) for h in header]]
    for r in rows:
        hexcol = PRIORITY_HEX.get(r.issue_priority, "#000000")
        cells = [
            Paragraph(f"<font color='{hexcol}'><b>{_esc(r.issue_priority.capitalize())}</b></font>",
                      styles["Cell"]),
            _cell(r.issue_type.capitalize(), styles),
            _cell(r.issue_name, styles),
            _cell(r.urls_affected, styles),
            _cell(f"{r.percent_of_total:.1f}%", styles),
        ]
        if revenue_modeled:
            cells.append(Paragraph(f"<font color='#b9770e'>{_esc(money(r.estimated_monthly_revenue_loss))}</font>",
                                    styles["Cell"]))
        cells.append(_cell("Yes" if r.auto_fixable else "—", styles))
        data.append(cells)
    t = Table(data, colWidths=[w * inch for w in col_widths], repeatRows=1)
    t.setStyle(_TABLE_STYLE)
    return t


# =============================================================================
# COVER PAGE
# =============================================================================

def _cover_page(report: SeoAuditReport, styles, revenue_modeled: bool, baseline: float) -> list:
    flow: list = [Spacer(1, 0.5 * inch)]
    flow.append(Paragraph("SEO / GEO / AEO / AIO Audit Report", styles["CoverTitle"]))
    flow.append(Paragraph(_esc(report.website_url), styles["CoverSub"]))
    flow.append(Spacer(1, 0.25 * inch))
    flow.append(HRFlowable(width="100%", thickness=1, color=GRID_COLOR))
    flow.append(Spacer(1, 0.2 * inch))

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    meta_rows = [
        ("Audit ID", report.audit_id),
        ("Status", report.status),
        ("Pages crawled", f"{report.pages_crawled} ({report.pages_failed} failed)"),
        ("Health score", f"{report.health_score}/100"),
        ("Report generated", generated),
    ]
    if revenue_modeled:
        share = (report.estimated_monthly_revenue_loss / baseline * 100) if baseline else 0.0
        meta_rows.append(("Monthly organic revenue (supplied baseline)", money(baseline)))
        meta_rows.append((
            "Modeled monthly revenue at risk",
            f"{money(report.estimated_monthly_revenue_loss)} ({share:.1f}% of baseline)",
        ))
    else:
        meta_rows.append((
            "Monthly organic revenue baseline",
            "Not supplied — $ figures are omitted; findings are prioritised by "
            "severity and URL coverage instead.",
        ))

    table = Table(
        [[Paragraph(f"<b>{_esc(k)}</b>", styles["CoverMeta"]), Paragraph(_esc(str(v)), styles["CoverMeta"])]
         for k, v in meta_rows],
        colWidths=[2.3 * inch, 4.7 * inch],
    )
    table.setStyle(_META_TABLE_STYLE)
    flow.append(table)
    flow.append(Spacer(1, 0.35 * inch))

    if revenue_modeled:
        flow.append(Paragraph(
            "<b>Important — read before sharing externally:</b> The dollar figures "
            "in this report are <b>model estimates</b>, not measured revenue losses. "
            "They are derived from the supplied organic-revenue baseline and the audit "
            "findings via a diminishing-returns formula explained in the Methodology "
            "section. Treat them as a prioritisation signal, not a guaranteed amount.",
            styles["Disclaimer"],
        ))
    return flow


# =============================================================================
# EXECUTIVE SUMMARY
# =============================================================================

def _executive_summary(report: SeoAuditReport, styles, revenue_modeled: bool, baseline: float) -> list:
    flow: list = [Paragraph("Executive Summary", styles["H1"])]
    if report.summary:
        flow.append(Paragraph(_esc(report.summary), styles["Body"]))
        flow.append(Spacer(1, 8))

    if report.pillar_scores:
        flow.append(Paragraph("Pillar Scores", styles["H2"]))
        data = [[Paragraph("Pillar", styles["CellBold"]), Paragraph("Score / 100", styles["CellBold"])]]
        for pillar in PILLAR_ORDER:
            if pillar in report.pillar_scores:
                data.append([_cell(PILLAR_LABELS.get(pillar, pillar.title()), styles),
                              _cell(f"{report.pillar_scores[pillar]}", styles)])
        t = Table(data, colWidths=[5.0 * inch, 2.0 * inch])
        t.setStyle(_TABLE_STYLE)
        flow.append(t)
        flow.append(Spacer(1, 10))

    if report.rows:
        if revenue_modeled:
            flow.append(Paragraph("Modeled $ at Risk by Priority Band", styles["H2"]))
            bands = {"high": [0, 0.0], "medium": [0, 0.0], "low": [0, 0.0]}
            for r in report.rows:
                bands[r.issue_priority][0] += r.urls_affected
                bands[r.issue_priority][1] += r.estimated_monthly_revenue_loss
            data = [[Paragraph(h, styles["CellBold"]) for h in
                     ("Priority", "URL-hit occurrences", "$/mo at risk")]]
            for p in ("high", "medium", "low"):
                data.append([_cell(p.capitalize(), styles), _cell(bands[p][0], styles),
                              _cell(money(bands[p][1]), styles)])
            data.append([_cell("Total", styles, bold=True),
                          _cell(sum(b[0] for b in bands.values()), styles, bold=True),
                          _cell(money(report.estimated_monthly_revenue_loss), styles, bold=True)])
            t = Table(data, colWidths=[2.0 * inch, 2.5 * inch, 2.5 * inch])
        else:
            flow.append(Paragraph("Findings by Priority", styles["H2"]))
            data = [[Paragraph(h, styles["CellBold"]) for h in ("Priority", "URL-hit occurrences")]]
            for p in ("high", "medium", "low"):
                data.append([_cell(p.capitalize(), styles),
                              _cell(report.issues_by_priority.get(p, 0), styles)])
            t = Table(data, colWidths=[3.5 * inch, 3.5 * inch])
        t.setStyle(_TABLE_STYLE)
        flow.append(t)
        flow.append(Spacer(1, 10))

        flow.append(Paragraph("Top 5 Highest-Impact Findings", styles["H2"]))
        if revenue_modeled:
            top = sorted(report.rows, key=lambda r: -r.estimated_monthly_revenue_loss)[:5]
        else:
            top = report.rows[:5]
        flow.append(_findings_table(top, styles, revenue_modeled))
        flow.append(Spacer(1, 10))

    flow.append(Paragraph("How to Read This Report", styles["H2"]))
    bullets = []
    if revenue_modeled:
        bullets.append(
            "$/mo figures are model estimates of revenue at risk, not measured "
            "losses — see Methodology & Revenue Model."
        )
    bullets += [
        "Pillar deep-dive sections group findings by category, each with the audit "
        "engine's own remediation instructions.",
        "Appendix B (WSJF) ranks fix packages by value vs. effort, highest first — "
        "work top-down for the best return on engineering time.",
        "“Auto-fix” marks findings the repo-aware SEO fixer can remediate "
        "automatically (POST /api/company/{id}/seo/fix).",
    ]
    flow.append(ListFlowable(
        [ListItem(Paragraph(_esc(b), styles["Body"])) for b in bullets],
        bulletType="bullet",
    ))
    return flow


# =============================================================================
# METHODOLOGY & REVENUE MODEL
# =============================================================================

def _methodology_section(report: SeoAuditReport, styles, total_pages: int,
                          revenue_modeled: bool, baseline: float) -> list:
    flow: list = [Paragraph("Methodology & Revenue Model", styles["H1"])]
    flow.append(Paragraph(
        "Every finding is assigned an <b>issue pressure</b> based on its priority, "
        "type, and how much of the site it affects. Aggregate pressure is then "
        "mapped to an at-risk share of organic revenue via a diminishing-returns "
        "curve, so a handful of issues moves the figure only a little while a "
        "pervasively broken site approaches — but never reaches — the cap:",
        styles["Body"],
    ))
    formula_rows = [
        ("pressure", "= priority_weight × type_factor × min(1, urls_affected / pages_crawled)"),
        ("priority_weight", "high = 14.0, medium = 7.0, low = 3.0"),
        ("type_factor", "issue = 1.0, warning = 0.55, opportunity = 0.25"),
        ("total_pressure", "= sum(pressure) across all findings"),
        ("loss_share", f"= {MAX_REVENUE_LOSS_SHARE:.2f} × (1 - e^(-total_pressure / {REVENUE_PRESSURE_SCALE:.0f}))"),
        ("modeled $ at risk", "= monthly_organic_revenue × loss_share"),
    ]
    t = Table(
        [[Paragraph(f"<font face='Courier' size=7>{_esc(k)}</font>", styles["Cell"]),
          Paragraph(f"<font face='Courier' size=7>{_esc(v)}</font>", styles["Cell"])]
         for k, v in formula_rows],
        colWidths=[2.0 * inch, 5.0 * inch],
    )
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT_BG]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(Spacer(1, 4))
    flow.append(t)
    flow.append(Spacer(1, 8))

    if report.rows:
        _pressures, total_pressure = compute_pressure(report.rows, total_pages)
        loss_share = loss_share_from_pressure(total_pressure)
        flow.append(Paragraph(
            f"<b>This audit's numbers:</b> {len(report.rows)} finding type(s) across "
            f"{report.pages_crawled} crawled page(s) produce a total issue pressure of "
            f"<b>{total_pressure:.2f}</b>, which maps to a loss share of "
            f"<b>{loss_share * 100:.1f}%</b> (cap {MAX_REVENUE_LOSS_SHARE * 100:.0f}%). "
            f"This share is determined entirely by the findings — it does not "
            f"depend on the revenue baseline.",
            styles["Body"],
        ))
        flow.append(Spacer(1, 6))

        flow.append(Paragraph("Sensitivity — Modeled At-Risk Across Baselines", styles["H2"]))
        flow.append(Paragraph(
            f"Because the {loss_share * 100:.1f}% at-risk share is fixed by this "
            "audit's findings, the modeled dollar figure simply scales with whatever "
            "monthly organic revenue baseline is supplied:",
            styles["Body"],
        ))
        sample_baselines = [100_000, 250_000, 500_000, 1_000_000, 2_000_000, 5_000_000]
        if revenue_modeled and baseline > 0:
            sample_baselines.append(baseline)
        sample_baselines = sorted(set(sample_baselines))
        data = [[Paragraph(h, styles["CellBold"]) for h in
                 ("Monthly organic revenue", "Modeled at-risk $/mo", "% of baseline")]]
        for b in sample_baselines:
            marker = ""
            if revenue_modeled and abs(b - baseline) < 0.5:
                marker = "  ← this audit's baseline"
            data.append([_cell(money(b), styles), _cell(money(b * loss_share) + marker, styles),
                          _cell(f"{loss_share * 100:.1f}%", styles)])
        t2 = Table(data, colWidths=[2.3 * inch, 3.0 * inch, 1.7 * inch])
        t2.setStyle(_TABLE_STYLE)
        flow.append(Spacer(1, 4))
        flow.append(t2)
        flow.append(Spacer(1, 8))
    else:
        flow.append(Paragraph(
            "No findings were recorded for this audit, so no $ figures are modeled.",
            styles["Body"],
        ))
        flow.append(Spacer(1, 8))

    flow.append(Paragraph(
        "<b>How this figure is derived (read before quoting it):</b> This is a "
        "<i>model estimate</i>, not a measured loss. It is the supplied "
        "organic-revenue baseline multiplied by an at-risk share computed from the "
        "findings: each finding contributes severity × type × page-coverage "
        "'pressure', and the aggregate is mapped through a diminishing-returns curve "
        f"(cap {MAX_REVENUE_LOSS_SHARE * 100:.0f}%). It depends entirely on the "
        "baseline you provide and on crawl breadth — treat it as a "
        "prioritisation signal, not a guaranteed dollar amount. Do not present these "
        "figures as measured revenue losses.",
        styles["Disclaimer"],
    ))
    return flow


# =============================================================================
# PILLAR DEEP-DIVES
# =============================================================================

def _package_block(task: SeoDelegationTask, styles, revenue_modeled: bool) -> list:
    flow: list = [Paragraph(_esc(task.title), styles["H3"])]
    badges = [
        f"Priority: {task.priority}",
        f"Effort: {task.effort}",
        f"Specialist: {task.suggested_specialist}",
        f"WSJF: {task.wsjf_score}",
    ]
    if task.auto_fixable:
        badges.append("auto-fixable")
    if revenue_modeled and task.estimated_monthly_value > 0:
        badges.append(f"{money(task.estimated_monthly_value)}/mo recoverable")
    flow.append(Paragraph(_esc(" · ".join(badges)), styles["BodySmall"]))

    items = []
    for line in task.instructions.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            line = line[2:]
        if line:
            items.append(ListItem(Paragraph(_esc(line), styles["FixBullet"])))
    if items:
        flow.append(Paragraph("Recommended fix:", styles["BodySmall"]))
        flow.append(ListFlowable(items, bulletType="bullet"))
    flow.append(Spacer(1, 6))
    return flow


def _pillar_section(report: SeoAuditReport, styles, pillar: str, revenue_modeled: bool) -> list:
    rows = [r for r in report.rows if r.pillar == pillar]
    tasks = [t for t in report.delegation_plan if t.pillar == pillar]
    score = report.pillar_scores.get(pillar)
    if score is None and not rows and not tasks:
        return []

    flow: list = [Paragraph(PILLAR_LABELS.get(pillar, pillar.title()), styles["H1"])]
    if score is not None:
        flow.append(Paragraph(f"Pillar score: <b>{score}</b>/100", styles["BodySmall"]))

    if not rows:
        flow.append(Paragraph("No findings in this pillar.", styles["Body"]))
        return flow

    urls_total = sum(r.urls_affected for r in rows)
    summary = f"{len(rows)} finding type(s), {urls_total} URL-hit occurrence(s)"
    if revenue_modeled:
        loss_total = sum(r.estimated_monthly_revenue_loss for r in rows)
        if report.estimated_monthly_revenue_loss > 0:
            share = loss_total / report.estimated_monthly_revenue_loss * 100
            summary += f", {money(loss_total)}/mo modeled at-risk ({share:.1f}% of the total)"
    flow.append(Paragraph(summary + ".", styles["Body"]))
    flow.append(Spacer(1, 6))
    flow.append(_findings_table(rows, styles, revenue_modeled))
    flow.append(Spacer(1, 8))

    for task in tasks:
        flow += _package_block(task, styles, revenue_modeled)
    return flow


# =============================================================================
# APPENDICES
# =============================================================================

def _appendix_full_findings(report: SeoAuditReport, styles, revenue_modeled: bool) -> list:
    flow: list = [Paragraph("Appendix A — Full Findings Table", styles["H1"])]
    if not report.rows:
        flow.append(Paragraph("No findings recorded.", styles["Body"]))
        return flow
    if revenue_modeled:
        rows = sorted(report.rows, key=lambda r: -r.estimated_monthly_revenue_loss)
        order = "modeled $ at risk (highest first)"
    else:
        rows = report.rows
        order = "priority"
    flow.append(Paragraph(f"All {len(rows)} finding type(s), sorted by {order}.", styles["BodySmall"]))
    flow.append(Spacer(1, 4))
    flow.append(_findings_table(rows, styles, revenue_modeled))
    return flow


def _appendix_wsjf_roadmap(report: SeoAuditReport, styles, revenue_modeled: bool) -> list:
    flow: list = [Paragraph("Appendix B — WSJF-Prioritised Fix Roadmap", styles["H1"])]
    if not report.delegation_plan:
        flow.append(Paragraph("No delegation plan was generated for this audit.", styles["Body"]))
        return flow

    flow.append(Paragraph(
        "This is the audit engine's own delegation plan — one agent-ready work "
        "package per finding category — re-rendered here in WSJF order. "
        "WSJF = (business_value + time_criticality + risk_reduction) / job_size; "
        "higher scores should be scheduled sooner.",
        styles["Body"],
    ))
    flow.append(Spacer(1, 4))

    header = ["#", "WSJF", "Package", "Priority", "Effort", "Pillar", "Specialist", "URL hits"]
    col_widths = [0.25, 0.45, 2.40, 0.55, 0.50, 0.60, 0.75, 0.50]
    if revenue_modeled:
        header.append("$/mo recoverable")
        col_widths.append(0.80)
        # rebalance package column so the row still totals 7.0in
        col_widths[2] = 2.0
    data = [[Paragraph(h, styles["CellBold"]) for h in header]]
    for i, t in enumerate(report.delegation_plan, 1):
        row = [_cell(i, styles), _cell(f"{t.wsjf_score:.2f}", styles), _cell(t.title, styles),
               _cell(t.priority, styles), _cell(t.effort, styles), _cell(t.pillar, styles),
               _cell(t.suggested_specialist, styles), _cell(t.urls_affected, styles)]
        if revenue_modeled:
            row.append(_cell(money(t.estimated_monthly_value), styles))
        data.append(row)
    t_tbl = Table(data, colWidths=[w * inch for w in col_widths], repeatRows=1)
    t_tbl.setStyle(_TABLE_STYLE)
    flow.append(t_tbl)
    flow.append(Spacer(1, 10))

    flow.append(Paragraph("WSJF Score Breakdown", styles["H2"]))
    bheader = ["Package", "WSJF", "Business value", "Time criticality", "Risk reduction", "Job size"]
    bdata = [[Paragraph(h, styles["CellBold"]) for h in bheader]]
    for t in report.delegation_plan:
        bdata.append([_cell(t.title, styles), _cell(f"{t.wsjf_score:.2f}", styles),
                       _cell(t.business_value, styles), _cell(t.time_criticality, styles),
                       _cell(t.risk_reduction, styles), _cell(t.job_size, styles)])
    bt = Table(bdata, colWidths=[w * inch for w in (3.0, 0.6, 1.0, 1.1, 1.0, 0.8)], repeatRows=1)
    bt.setStyle(_TABLE_STYLE)
    flow.append(bt)
    return flow


def _appendix_worst_pages(report: SeoAuditReport, styles) -> list:
    flow: list = [Paragraph("Appendix C — Worst Pages", styles["H1"])]
    if not report.pages:
        flow.append(Paragraph("No per-page data recorded.", styles["Body"]))
        return flow
    worst = sorted(report.pages, key=lambda p: -len(p.issue_codes))[:15]
    flow.append(Paragraph(
        f"Top {len(worst)} of {len(report.pages)} crawled pages, ranked by total issue count.",
        styles["BodySmall"],
    ))
    flow.append(Spacer(1, 4))
    header = ["#", "Issues", "Words", "Title", "URL"]
    data = [[Paragraph(h, styles["CellBold"]) for h in header]]
    for i, p in enumerate(worst, 1):
        url = p.final_url or p.url
        if len(url) > 70:
            url = url[:67] + "..."
        title = p.title or "(no title)"
        data.append([_cell(i, styles), _cell(len(p.issue_codes), styles), _cell(p.word_count, styles),
                      _cell(title, styles), _cell(url, styles)])
    t = Table(data, colWidths=[w * inch for w in (0.3, 0.5, 0.6, 2.6, 3.0)], repeatRows=1)
    t.setStyle(_TABLE_STYLE)
    flow.append(t)
    return flow


# =============================================================================
# ENTRY POINT
# =============================================================================

def report_to_pdf(report: SeoAuditReport) -> bytes:
    """Render a full CTO-level PDF for ``report`` and return the PDF bytes."""
    styles = _styles()
    revenue_modeled = report.monthly_organic_revenue > 0
    baseline = report.monthly_organic_revenue
    total_pages = max(1, report.pages_crawled)

    sections: list[list] = [
        _cover_page(report, styles, revenue_modeled, baseline),
        _executive_summary(report, styles, revenue_modeled, baseline),
        _methodology_section(report, styles, total_pages, revenue_modeled, baseline),
    ]
    for pillar in PILLAR_ORDER:
        section = _pillar_section(report, styles, pillar, revenue_modeled)
        if section:
            sections.append(section)
    sections.append(_appendix_full_findings(report, styles, revenue_modeled))
    sections.append(_appendix_wsjf_roadmap(report, styles, revenue_modeled))
    sections.append(_appendix_worst_pages(report, styles))

    story: list = []
    for i, section in enumerate(sections):
        if i > 0:
            story.append(PageBreak())
        story.extend(section)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.7 * inch, bottomMargin=0.6 * inch,
        title=f"SEO / GEO / AEO / AIO Audit Report - {report.website_url}",
        author="autonomous-ai-agency SEO audit engine",
    )
    doc.build(story)
    return buf.getvalue()
